# src/lint_generator.py

from typing import Dict
from jinja2 import Template


class LintStageGenerator:
    """Генератор lint stage с отладочным выводом"""

    LINT_TEMPLATES = {
        'python': """lint:
  stage: lint
  image: python:{{ version }}-slim
  before_script:
    - echo "================================================"
    - echo "LINT STAGE - Python {{ version }}"
    - echo "================================================"
    - echo "📦 Installing linters: flake8, pylint, black"
    - pip install --no-cache-dir -q flake8 pylint black isort
  script:
    - echo ""
    - echo "🔍 Running flake8 (syntax errors & undefined names)..."
    - flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics || true
    - echo ""
    - echo "🔍 Running pylint (code quality)..."
    - pylint **/*.py --exit-zero || true
    - echo ""
    - echo "🔍 Checking code formatting with black..."
    - black --check --diff . || true
    - echo ""
    - echo "🔍 Checking import sorting with isort..."
    - isort --check-only --diff . || true
    - echo ""
    - echo "✅ Lint stage completed!"
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'go': """lint:
  stage: lint
  image: golang:{{ version }}-alpine
  before_script:
    - echo "================================================"
    - echo "LINT STAGE - Go {{ version }}"
    - echo "================================================"
    - echo "📦 Installing golangci-lint..."
    - apk add --no-cache git
    - go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
  script:
    - echo ""
    - echo "🔍 Running golangci-lint (comprehensive Go linter)..."
    - $GOPATH/bin/golangci-lint run ./... --timeout=5m || true
    - echo ""
    - echo "🔍 Running go vet (official Go tool)..."
    - go vet ./... || true
    - echo ""
    - echo "🔍 Running go fmt check..."
    - test -z $(gofmt -l .) || (echo "Code not formatted!" && gofmt -d . && exit 1) || true
    - echo ""
    - echo "✅ Lint stage completed!"
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'typescript': """lint:
  stage: lint
  image: node:{{ version }}-alpine
  before_script:
    - echo "================================================"
    - echo "LINT STAGE - TypeScript (Node {{ version }})"
    - echo "================================================"
    - echo "📦 Installing dependencies..."
    - npm ci
  script:
    - echo ""
    - echo "🔍 Running ESLint..."
    - npx eslint . --ext .ts,.tsx --format stylish || true
    - echo ""
    - echo "🔍 Running TypeScript compiler check..."
    - npx tsc --noEmit || true
    - echo ""
    - echo "🔍 Checking code formatting with Prettier..."
    - npx prettier --check "**/*.{ts,tsx,json}" || true
    - echo ""
    - echo "✅ Lint stage completed!"
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'java': """lint:
  stage: lint
  image: maven:3.9-eclipse-temurin-{{ version }}
  before_script:
    - echo "================================================"
    - echo "LINT STAGE - Java {{ version }}"
    - echo "================================================"
  script:
    - echo ""
    - echo "🔍 Running Checkstyle (code style checker)..."
    - mvn checkstyle:check || true
    - echo ""
    - echo "🔍 Running PMD (static code analyzer)..."
    - mvn pmd:check || true
    - echo ""
    - echo "🔍 Running SpotBugs (bug detector)..."
    - mvn spotbugs:check || true
    - echo ""
    - echo "✅ Lint stage completed!"
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'kotlin': """lint:
  stage: lint
  image: maven:3.9-eclipse-temurin-{{ version }}
  before_script:
    - echo "================================================"
    - echo "LINT STAGE - Kotlin (Java {{ version }})"
    - echo "================================================"
  script:
    - echo ""
    - echo "🔍 Running Detekt (Kotlin linter)..."
    - mvn antrun:run@detekt || true
    - echo ""
    - echo "🔍 Running Ktlint (code formatter)..."
    - mvn antrun:run@ktlint || true
    - echo ""
    - echo "✅ Lint stage completed!"
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",
    }

    def __init__(self, language: str, version: str):
        self.language = language
        self.version = version
        print(f"  → Генерирую LINT stage для {language}:{version}")

    def generate(self) -> str:
        template_str = self.LINT_TEMPLATES.get(self.language)

        if template_str:
            template = Template(template_str)
            return template.render(version=self.version)
        else:
            print(f"     ⚠️  Нет lint конфигурации для {self.language}")
            return ""

    def get_output_string(self) -> str:
        return self.generate()
