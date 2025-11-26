# security_generator.py

from typing import Dict
from jinja2 import Template


class SecurityStageGenerator:
    """Генератор security stage"""

    SECURITY_TEMPLATES = {
        'python': """security:
  stage: security
  image: python:{{ version }}-slim
  script:
    - pip install --no-cache-dir -q bandit safety
    - echo "Running: bandit"
    - bandit -r . -f txt -ll || true
    - echo "Running: safety"
    - safety check --json || true
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
  script:
    - go install github.com/securego/gosec/v2/cmd/gosec@latest
    - echo "Running: gosec"
    - $GOPATH/bin/gosec ./... || true
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'node': """security:
  stage: security
  image: node:{{ version }}-alpine
  script:
    - npm install
    - echo "Running: npm audit"
    - npm audit --audit-level=moderate || true
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
  script:
    - npm install
    - echo "Running: npm audit"
    - npm audit --audit-level=moderate || true
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
  script:
    - echo "Running: dependency-check"
    - mvn dependency-check:check || true
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
  script:
    - echo "Running: dependency-check"
    - mvn dependency-check:check || true
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'php': """security:
  stage: security
  image: php:{{ version }}-cli
  script:
    - curl -fsSL https://getcomposer.org/installer | php
    - php composer.phar install
    - echo "Running: composer audit"
    - php composer.phar audit || true
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'rust': """security:
  stage: security
  image: rust:{{ version }}
  script:
    - cargo install cargo-audit
    - echo "Running: cargo-audit"
    - cargo-audit || true
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'ruby': """security:
  stage: security
  image: ruby:{{ version }}-alpine
  script:
    - gem install bundler-audit
    - echo "Running: bundler-audit"
    - bundler-audit check || true
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",
    }

    DOCKER_SECURITY = """security_docker:
  stage: security
  image: aquasec/trivy:latest
  script:
    - echo "🔒 Scanning Docker image for vulnerabilities..."
    - trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA || true
    - echo "✅ Docker security scan complete!"
  allow_failure: true
  only:
    - main
  tags:
    - docker
"""

    DEFAULT_TEMPLATE = """security:
  stage: security
  image: alpine:latest
  script:
    - echo "No security checks configured"
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
"""

    def __init__(self, language: str, version: str, has_dockerfile: bool = False):
        self.language = language
        self.version = version
        self.has_dockerfile = has_dockerfile

    def generate(self) -> str:
        output = ""

        # Code security
        template_str = self.SECURITY_TEMPLATES.get(self.language, self.DEFAULT_TEMPLATE)

        if '{{' in template_str:
            template = Template(template_str)
            output += template.render(version=self.version)
        else:
            output += template_str

        output += "\n"

        # Docker security (если есть Dockerfile)
        if self.has_dockerfile:
            output += self.DOCKER_SECURITY

        return output

    def get_output_string(self) -> str:
        return self.generate()
