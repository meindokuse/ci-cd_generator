# src/security_generator.py

from typing import Dict
from jinja2 import Template


class SecurityStageGenerator:
    """Генератор security stage с отладочным выводом"""

    SECURITY_TEMPLATES = {
        'python': """security:
  stage: security
  image: python:{{ version }}-slim
  before_script:
    - echo "================================================"
    - echo "SECURITY STAGE - Python {{ version }}"
    - echo "================================================"
    - echo "📦 Installing security tools: bandit, safety"
    - pip install --no-cache-dir -q bandit safety
  script:
    - echo ""
    - echo "🔒 Running Bandit (security issue scanner)..."
    - bandit -r . -f txt -ll || true
    - echo ""
    - echo "🔒 Running Safety (dependency vulnerability checker)..."
    - safety check --json || true
    - echo ""
    - echo "✅ Security scan completed!"
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'go': """security:
  stage: security
  image: golang:{{ version }}-alpine
  before_script:
    - echo "================================================"
    - echo "SECURITY STAGE - Go {{ version }}"
    - echo "================================================"
    - echo "📦 Installing gosec (security scanner)..."
    - go install github.com/securego/gosec/v2/cmd/gosec@latest
  script:
    - echo ""
    - echo "🔒 Running gosec (Go security checker)..."
    - $GOPATH/bin/gosec -fmt=json -out=gosec-report.json ./... || true
    - $GOPATH/bin/gosec ./... || true
    - echo ""
    - echo "✅ Security scan completed!"
  artifacts:
    reports:
      sast: gosec-report.json
    expire_in: 1 week
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'typescript': """security:
  stage: security
  image: node:{{ version }}-alpine
  before_script:
    - echo "================================================"
    - echo "SECURITY STAGE - TypeScript (Node {{ version }})"
    - echo "================================================"
    - echo "📦 Installing dependencies..."
    - npm ci
  script:
    - echo ""
    - echo "🔒 Running npm audit (dependency vulnerabilities)..."
    - npm audit --audit-level=moderate || true
    - echo ""
    - echo "🔒 Generating npm audit report..."
    - npm audit --json > npm-audit.json || true
    - echo ""
    - echo "✅ Security scan completed!"
  artifacts:
    paths:
      - npm-audit.json
    expire_in: 1 week
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'java': """security:
  stage: security
  image: maven:3.9-eclipse-temurin-{{ version }}
  before_script:
    - echo "================================================"
    - echo "SECURITY STAGE - Java {{ version }}"
    - echo "================================================"
  script:
    - echo ""
    - echo "🔒 Running OWASP Dependency-Check..."
    - mvn dependency-check:check || true
    - echo ""
    - echo "🔒 Checking for vulnerable dependencies..."
    - mvn versions:display-dependency-updates || true
    - echo ""
    - echo "✅ Security scan completed!"
  artifacts:
    paths:
      - target/dependency-check-report.html
    expire_in: 1 week
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'kotlin': """security:
  stage: security
  image: maven:3.9-eclipse-temurin-{{ version }}
  before_script:
    - echo "================================================"
    - echo "SECURITY STAGE - Kotlin (Java {{ version }})"
    - echo "================================================"
  script:
    - echo ""
    - echo "🔒 Running OWASP Dependency-Check..."
    - mvn dependency-check:check || true
    - echo ""
    - echo "🔒 Checking for vulnerable dependencies..."
    - mvn versions:display-dependency-updates || true
    - echo ""
    - echo "✅ Security scan completed!"
  artifacts:
    paths:
      - target/dependency-check-report.html
    expire_in: 1 week
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",
    }

    DOCKER_SECURITY = """
security_docker:
  stage: security
  image: aquasec/trivy:latest
  before_script:
    - echo "================================================"
    - echo "DOCKER IMAGE SECURITY SCAN"
    - echo "================================================"
  script:
    - echo ""
    - echo "🔒 Scanning Docker image with Trivy..."
    - trivy image --exit-code 0 --severity HIGH,CRITICAL --format table $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - echo ""
    - echo "🔒 Generating JSON report..."
    - trivy image --exit-code 0 --severity HIGH,CRITICAL --format json --output trivy-report.json $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA || true
    - echo ""
    - echo "✅ Docker image scan completed!"
  artifacts:
    paths:
      - trivy-report.json
    expire_in: 1 week
  allow_failure: true
  only:
    - main
  tags:
    - docker
"""

    def __init__(self, language: str, version: str, has_dockerfile: bool = False):
        self.language = language
        self.version = version
        self.has_dockerfile = has_dockerfile
        print(f"  → Генерирую SECURITY stage для {language}:{version}")
        if has_dockerfile:
            print(f"     ✅ Docker security scan включён")

    def generate(self) -> str:
        output = ""

        # Code security
        template_str = self.SECURITY_TEMPLATES.get(self.language)

        if template_str:
            template = Template(template_str)
            output += template.render(version=self.version)
        else:
            print(f"     ⚠️  Нет security конфигурации для {self.language}")

        # Docker security (если есть Dockerfile)
        if self.has_dockerfile:
            output += "\n" + self.DOCKER_SECURITY

        return output

    def get_output_string(self) -> str:
        return self.generate()
