# src/sonarqube_generator.py

from typing import Dict
from jinja2 import Template


class SonarQubeStageGenerator:
    """
    Генератор SonarQube stage.
    SonarQube автоматически анализирует и выводит реальный стек проекта.
    """

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
    - echo "🔍 SonarQube will automatically detect and analyze:"
    - echo "   ✓ Programming languages"
    - echo "   ✓ Frameworks (Django, Spring, React, etc.)"
    - echo "   ✓ Libraries and dependencies"
    - echo "   ✓ Security vulnerabilities (CVE)"
    - echo "   ✓ Code quality issues"
    - echo "   ✓ Technical debt"
    - echo ""
  script:
    - echo "🔍 Starting SonarQube Scanner..."
    - echo ""

    # Запуск SonarQube с выводом
    - sonar-scanner
      -Dsonar.projectKey=$CI_PROJECT_NAME
      -Dsonar.projectName="$CI_PROJECT_NAME"
      -Dsonar.projectVersion=$CI_COMMIT_SHORT_SHA
      -Dsonar.sources=.
      -Dsonar.host.url=$SONAR_HOST_URL
      -Dsonar.login=$SONAR_TOKEN
      -Dsonar.verbose=false
      {{ language_specific_params }}

    - echo ""
    - echo "✅ SonarQube analysis completed!"
    - echo ""

    # Получаем реальные данные из SonarQube API
    - echo "📊 FETCHING PROJECT ANALYSIS RESULTS..."
    - echo ""

    # Установка curl и jq для парсинга JSON
    - apk add --no-cache curl jq

    # Получаем метрики проекта через API
    - |
      echo "🔍 Detected Technologies and Stack:"
      echo ""

      # Получаем основные метрики
      METRICS=$(curl -s -u $SONAR_TOKEN: "$SONAR_HOST_URL/api/measures/component?component=$CI_PROJECT_NAME&metricKeys=ncloc,files,functions,classes,complexity,vulnerabilities,bugs,code_smells,coverage,duplicated_lines_density")

      # Парсим и выводим
      NCLOC=$(echo $METRICS | jq -r '.component.measures[] | select(.metric=="ncloc") | .value')
      FILES=$(echo $METRICS | jq -r '.component.measures[] | select(.metric=="files") | .value')
      FUNCTIONS=$(echo $METRICS | jq -r '.component.measures[] | select(.metric=="functions") | .value')
      CLASSES=$(echo $METRICS | jq -r '.component.measures[] | select(.metric=="classes") | .value')
      COMPLEXITY=$(echo $METRICS | jq -r '.component.measures[] | select(.metric=="complexity") | .value')
      VULNERABILITIES=$(echo $METRICS | jq -r '.component.measures[] | select(.metric=="vulnerabilities") | .value')
      BUGS=$(echo $METRICS | jq -r '.component.measures[] | select(.metric=="bugs") | .value')
      CODE_SMELLS=$(echo $METRICS | jq -r '.component.measures[] | select(.metric=="code_smells") | .value')
      COVERAGE=$(echo $METRICS | jq -r '.component.measures[] | select(.metric=="coverage") | .value')
      DUPLICATIONS=$(echo $METRICS | jq -r '.component.measures[] | select(.metric=="duplicated_lines_density") | .value')

      echo "📈 CODE METRICS:"
      echo "   Lines of Code: $NCLOC"
      echo "   Files: $FILES"
      echo "   Functions: $FUNCTIONS"
      echo "   Classes: $CLASSES"
      echo "   Complexity: $COMPLEXITY"
      echo ""

      echo "🐛 ISSUES FOUND:"
      echo "   Vulnerabilities: $VULNERABILITIES"
      echo "   Bugs: $BUGS"
      echo "   Code Smells: $CODE_SMELLS"
      echo ""

      echo "📊 QUALITY METRICS:"
      echo "   Coverage: $COVERAGE%"
      echo "   Duplications: $DUPLICATIONS%"
      echo ""

    # Получаем список языков проекта
    - |
      echo "💻 DETECTED LANGUAGES:"
      LANGUAGES=$(curl -s -u $SONAR_TOKEN: "$SONAR_HOST_URL/api/measures/component?component=$CI_PROJECT_NAME&metricKeys=ncloc_language_distribution")

      echo $LANGUAGES | jq -r '.component.measures[] | select(.metric=="ncloc_language_distribution") | .value' | tr ';' '\\n' | while read line; do
        echo "   • $line"
      done
      echo ""

    # Получаем список issues (реальные проблемы)
    - |
      echo "🔒 SECURITY & QUALITY ISSUES:"
      ISSUES=$(curl -s -u $SONAR_TOKEN: "$SONAR_HOST_URL/api/issues/search?componentKeys=$CI_PROJECT_NAME&ps=5&types=VULNERABILITY,BUG&severities=CRITICAL,MAJOR")

      echo $ISSUES | jq -r '.issues[] | "   • [\\(.severity)] \\(.message) (\\(.component | split(\\":\\")[1]):\\(.line))"' | head -10
      echo ""

    # Ссылка на полный отчет
    - echo "================================================"
    - echo "📊 FULL DETAILED REPORT:"
    - echo "   👉 $SONAR_HOST_URL/dashboard?id=$CI_PROJECT_NAME"
    - echo ""
    - echo "This report includes:"
    - echo "   • Complete technology stack detection"
    - echo "   • All detected frameworks and libraries"
    - echo "   • Security vulnerabilities with CVE references"
    - echo "   • Code quality breakdown by file"
    - echo "   • Technical debt estimation"
    - echo "================================================"

  after_script:
    - echo ""
    - echo "================================================"
    - echo "SONARQUBE ANALYSIS COMPLETE"
    - echo "================================================"
    - echo "Project: $CI_PROJECT_NAME"
    - echo "Version: $CI_COMMIT_SHORT_SHA"
    - echo ""
    - echo "🔗 View full analysis:"
    - echo "   $SONAR_HOST_URL/dashboard?id=$CI_PROJECT_NAME"
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
      -Dsonar.exclusions=**/tests/**,**/__pycache__/**,**/venv/**,**/.venv/**,**/migrations/**
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
      -Dsonar.exclusions=**/node_modules/**,**/dist/**,**/coverage/**,**/build/**,**/*.test.js
      -Dsonar.javascript.lcov.reportPaths=coverage/lcov.info
      -Dsonar.testExecutionReportPaths=test-results.xml""",

        'typescript': """-Dsonar.language=ts
      -Dsonar.sources=src
      -Dsonar.tests=test,tests,__tests__
      -Dsonar.exclusions=**/node_modules/**,**/dist/**,**/coverage/**,**/build/**,**/*.test.ts,**/*.spec.ts
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
        print(f"     ✅ SonarQube автоматически определит полный стек проекта")
        print(f"     ✅ Вывод реальных метрик через SonarQube API")

    def generate(self) -> str:
        template = Template(self.SONARQUBE_TEMPLATE)
        language_params = self.LANGUAGE_PARAMS.get(self.language, "")

        if not language_params:
            print(f"     ⚠️  Нет специфичной конфигурации для {self.language}")
            print(f"     ℹ️  SonarQube всё равно проанализирует проект")

        return template.render(
            language=self.language,
            version=self.version,
            language_specific_params=language_params
        )

    def get_output_string(self) -> str:
        return self.generate()
