# lint_generator.py

import os
from typing import Dict, List
from jinja2 import Template


class LintStageGenerator:
    """Генератор lint stage для GitLab CI/CD"""

    LINT_TEMPLATE = """lint:
  stage: lint
  image: {{ base_image }}
  script:
    {% if setup_commands %}
    # Setup
    {% for cmd in setup_commands %}
    - {{ cmd }}
    {% endfor %}
    {% endif %}

    # Lint commands
    {% if lint_commands %}
    {% for cmd in lint_commands %}
    - echo "Running: {{ cmd }}"
    - {{ cmd }} || true
    {% endfor %}
    {% else %}
    - echo "⚠️  No lint configured for this project"
    {% endif %}
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
"""

    def __init__(self, language: str, base_image: str):
        """
        Args:
            language: Язык проекта (python, go, node, java, php, rust, ruby)
            base_image: Базовый Docker образ
        """
        self.language = language
        self.base_image = base_image
        self.lint_commands = self._detect_lint_commands()
        self.setup_commands = self._detect_setup_commands()

    def _detect_lint_commands(self) -> List[str]:
        """
        Определяет команды для линта по языку и наличию конфигов
        """

        commands = []

        if self.language == 'python':
            # Проверяем, есть ли конфиги линтеров
            if os.path.exists('.flake8') or self._file_has_config('setup.cfg', 'flake8') or self._file_has_config(
                    'pyproject.toml', 'flake8'):
                commands.append('flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics')
                commands.append('flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics')
            if os.path.exists('.pylintrc') or self._file_has_config('pyproject.toml', 'pylint'):
                commands.append('pylint **/*.py || true')

        elif self.language == 'go':
            # Go стандартный линтер
            commands.append('go vet ./...')
            commands.append('go fmt ./...')
            if os.path.exists('.golangci.yml') or os.path.exists('.golangci.yaml'):
                commands.append('golangci-lint run || true')

        elif self.language == 'node':
            # Node.js - eslint или npm lint
            if os.path.exists('package.json'):
                commands.append('npm run lint || true')
            if os.path.exists('.eslintrc.json') or os.path.exists('.eslintrc.js') or os.path.exists('.eslintrc.yml'):
                commands.append('npx eslint . || true')

        elif self.language == 'java':
            # Java - checkstyle через maven
            if os.path.exists('pom.xml'):
                commands.append('mvn checkstyle:check || true')

        elif self.language == 'php':
            # PHP - phpstan
            if os.path.exists('phpstan.neon') or os.path.exists('phpstan.neon.dist'):
                commands.append('./vendor/bin/phpstan analyse || true')

        elif self.language == 'rust':
            # Rust - clippy
            commands.append('cargo clippy -- -D warnings || true')

        elif self.language == 'ruby':
            # Ruby - rubocop
            if os.path.exists('.rubocop.yml') or os.path.exists('Gemfile'):
                commands.append('rubocop || true')

        return commands

    def _detect_setup_commands(self) -> List[str]:
        """Команды для подготовки окружения перед линтом"""
        commands = []

        if self.language == 'python':
            commands.append('pip install --no-cache-dir -q flake8 pylint')

        elif self.language == 'go':
            commands.append('go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest')

        elif self.language == 'ruby':
            commands.append('gem install rubocop')

        return commands

    def _file_has_config(self, filepath: str, section: str) -> bool:
        """Проверяет, есть ли конфиг в файле"""
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                return section in content
        except:
            return False

    def generate(self) -> str:
        """Генерирует lint stage YAML"""

        template = Template(self.LINT_TEMPLATE)

        return template.render(
            base_image=self.base_image,
            lint_commands=self.lint_commands,
            setup_commands=self.setup_commands,
        )

    def get_output_string(self) -> str:
        """Возвращает готовую строку YAML для добавления в конфиг"""

        # Если нет команд для линта, возвращаем комментарий
        if not self.lint_commands:
            return "# Lint stage: no lint configured\n"

        return self.generate()
