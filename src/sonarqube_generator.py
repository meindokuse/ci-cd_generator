# src/sonarqube_generator.py

from typing import Dict
from jinja2 import Template


class SonarQubeStageGenerator:
    """Генератор SonarQube stage для детального анализа кода"""

    SONARQUBE_TEMPLATE = """sonarqube:
  stage: sonarqube
  image: sonarsource/sonar-scanner-cli:latest
  variables:
    SONAR_USER_HOME: "${CI_PROJECT_DIR}/.sonar"
    GIT_DEPTH: "0"
  before_script:
    - echo "================================================"
    - echo "SONARQUBE ANALYSIS - {{ language }} {{ version }}"
    - echo "================================================"
    - echo "📊 SonarQube will analyze:"
    - echo "   - Code Quality"
    - echo "   - Code Smells"
    - echo "   - Bugs"
    - echo "   - Security Vulnerabilities"
    - echo "   - Code Coverage"
    - echo "   - Duplications"
    - echo "   - Technical Debt"
    - echo ""
  script:
    - echo "🔍 Running SonarQube Scanner..."
    - sonar-scanner
      -Dsonar.projectKey=$CI_PROJECT_NAME
      -Dsonar.projectName=$CI_PROJECT_NAME
      -Dsonar.projectVersion=$CI_COMMIT_SHORT_SHA
      -Dsonar.sources=.
      -Dsonar.host.url=$SONAR_HOST_URL
      -Dsonar.login=$SONAR_TOKEN
      {{ language_specific_params }}
    - echo ""
    - echo "✅ SonarQube analysis completed!"
    - echo "📊 View detailed report at: $SONAR_HOST_URL/dashboard?id=$CI_PROJECT_NAME"
  after_script:
    - echo ""
    - echo "================================================"
    - echo "SONARQUBE SUMMARY"
    - echo "================================================"
    - echo "Project: $CI_PROJECT_NAME"
    - echo "Version: $CI_COMMIT_SHORT_SHA"
    - echo "Dashboard: $SONAR_HOST_URL/dashboard?id=$CI_PROJECT_NAME"
    - echo "================================================"
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
        'python': """-Dsonar.language=py
      -Dsonar.python.version=3
      -Dsonar.sources=.
      -Dsonar.exclusions=**/tests/**,**/__pycache__/**,**/venv/**,**/.venv/**
      -Dsonar.python.coverage.reportPaths=coverage.xml
      -Dsonar.python.xunit.reportPath=test-results.xml""",

        'go': """-Dsonar.language=go
      -Dsonar.sources=.
      -Dsonar.exclusions=**/*_test.go,**/vendor/**
      -Dsonar.go.coverage.reportPaths=coverage.out
      -Dsonar.go.tests.reportPaths=test-report.json""",

        'node': """-Dsonar.language=js
      -Dsonar.sources=src
      -Dsonar.tests=test,tests,__tests__
      -Dsonar.exclusions=**/node_modules/**,**/dist/**,**/coverage/**,**/*.test.js
      -Dsonar.javascript.lcov.reportPaths=coverage/lcov.info
      -Dsonar.testExecutionReportPaths=test-results.xml""",

        'typescript': """-Dsonar.language=ts
      -Dsonar.sources=src
      -Dsonar.tests=test,tests,__tests__
      -Dsonar.exclusions=**/node_modules/**,**/dist/**,**/coverage/**,**/*.test.ts,**/*.spec.ts
      -Dsonar.typescript.lcov.reportPaths=coverage/lcov.info
      -Dsonar.testExecutionReportPaths=test-results.xml""",

        'java': """-Dsonar.language=java
      -Dsonar.sources=src/main/java
      -Dsonar.tests=src/test/java
      -Dsonar.java.binaries=target/classes
      -Dsonar.java.test.binaries=target/test-classes
      -Dsonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml
      -Dsonar.junit.reportPaths=target/surefire-reports""",

        'kotlin': """-Dsonar.language=kotlin
      -Dsonar.sources=src/main/kotlin
      -Dsonar.tests=src/test/kotlin
      -Dsonar.java.binaries=target/classes
      -Dsonar.java.test.binaries=target/test-classes
      -Dsonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml
      -Dsonar.junit.reportPaths=target/surefire-reports""",
    }

    def __init__(self, language: str, version: str):
        self.language = language
        self.version = version
        print(f"  → Генерирую SONARQUBE stage для {language}:{version}")
        print(f"     ✅ Детальный анализ: Code Quality, Security, Coverage, Duplications")

    def generate(self) -> str:
        template = Template(self.SONARQUBE_TEMPLATE)
        language_params = self.LANGUAGE_PARAMS.get(self.language, "")

        if not language_params:
            print(f"     ⚠️  Нет SonarQube конфигурации для {self.language}")

        return template.render(
            language=self.language,
            version=self.version,
            language_specific_params=language_params
        )

    def get_output_string(self) -> str:
        return self.generate()
