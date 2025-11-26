# sonarqube_generator.py

from typing import Dict
from jinja2 import Template


class SonarQubeStageGenerator:
    """Генератор SonarQube stage для code quality analysis"""

    SONARQUBE_TEMPLATE = """sonarqube:
  stage: sonarqube
  image: sonarsource/sonar-scanner-cli:latest
  variables:
    SONAR_USER_HOME: "${CI_PROJECT_DIR}/.sonar"
    GIT_DEPTH: "0"  # Shallow clone disabled for better analysis
  script:
    - echo "🔍 Running SonarQube analysis..."
    - sonar-scanner
      -Dsonar.projectKey=$CI_PROJECT_NAME
      -Dsonar.sources=.
      -Dsonar.host.url=$SONAR_HOST_URL
      -Dsonar.login=$SONAR_TOKEN
      {{ language_specific_params }}
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
  cache:
    key: "${CI_COMMIT_REF_SLUG}-sonar"
    paths:
      - .sonar/cache
"""

    LANGUAGE_PARAMS = {
        'python': """-Dsonar.python.version=3
      -Dsonar.sources=.
      -Dsonar.exclusions=**/tests/**,**/__pycache__/**,**/venv/**
      -Dsonar.python.coverage.reportPaths=coverage.xml""",

        'go': """-Dsonar.sources=.
      -Dsonar.exclusions=**/*_test.go,**/vendor/**
      -Dsonar.go.coverage.reportPaths=coverage.out""",

        'node': """-Dsonar.sources=src
      -Dsonar.exclusions=**/node_modules/**,**/dist/**,**/*.test.js
      -Dsonar.javascript.lcov.reportPaths=coverage/lcov.info""",

        'typescript': """-Dsonar.sources=src
      -Dsonar.exclusions=**/node_modules/**,**/dist/**,**/*.test.ts
      -Dsonar.typescript.lcov.reportPaths=coverage/lcov.info""",

        'java': """-Dsonar.sources=src/main/java
      -Dsonar.tests=src/test/java
      -Dsonar.java.binaries=target/classes
      -Dsonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml""",

        'kotlin': """-Dsonar.sources=src/main/kotlin
      -Dsonar.tests=src/test/kotlin
      -Dsonar.java.binaries=target/classes
      -Dsonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml""",
    }

    def __init__(self, language: str, version: str):
        self.language = language
        self.version = version

    def generate(self) -> str:
        template = Template(self.SONARQUBE_TEMPLATE)

        language_params = self.LANGUAGE_PARAMS.get(self.language, "")

        return template.render(
            language_specific_params=language_params
        )

    def get_output_string(self) -> str:
        return self.generate()
