# lint_generator.py

from typing import Dict
from jinja2 import Template


class LintStageGenerator:
    """Генератор lint stage"""

    LINT_TEMPLATES = {
        'python': """lint:
  stage: lint
  image: python:{{ version }}-slim
  script:
    - pip install --no-cache-dir -q flake8 pylint
    - echo "Running: flake8"
    - flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics || true
    - echo "Running: pylint"
    - pylint **/*.py || true
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
  script:
    - apk add --no-cache git
    - go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
    - echo "Running: golangci-lint"
    - $GOPATH/bin/golangci-lint run ./... || true
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'node': """lint:
  stage: lint
  image: node:{{ version }}-alpine
  script:
    - npm install
    - echo "Running: eslint"
    - npx eslint . || true
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
  script:
    - echo "Running: checkstyle"
    - mvn checkstyle:check || true
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'php': """lint:
  stage: lint
  image: php:{{ version }}-cli
  script:
    - echo "Running: php lint"
    - find . -name "*.php" -exec php -l {} \\; || true
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'rust': """lint:
  stage: lint
  image: rust:{{ version }}
  script:
    - echo "Running: clippy"
    - cargo clippy -- -D warnings || true
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",

        'ruby': """lint:
  stage: lint
  image: ruby:{{ version }}-alpine
  script:
    - gem install rubocop
    - echo "Running: rubocop"
    - rubocop || true
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
""",
    }

    DEFAULT_TEMPLATE = """lint:
  stage: lint
  image: alpine:latest
  script:
    - echo "No lint configured for this language"
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
"""

    def __init__(self, language: str, version: str):
        self.language = language
        self.version = version

    def generate(self) -> str:
        template_str = self.LINT_TEMPLATES.get(self.language, self.DEFAULT_TEMPLATE)

        if '{{' in template_str:
            template = Template(template_str)
            return template.render(version=self.version)
        else:
            return template_str

    def get_output_string(self) -> str:
        return self.generate()
