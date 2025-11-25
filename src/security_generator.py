# security_generator.py

import os
from typing import List
from jinja2 import Template


class SecurityStageGenerator:
    """Генератор security stage для GitLab CI/CD"""

    SECURITY_TEMPLATE = """security:
  stage: security
  image: {{ base_image }}
  script:
    {% if setup_commands %}
    # Setup
    {% for cmd in setup_commands %}
    - {{ cmd }}
    {% endfor %}
    {% endif %}

    # Security checks
    {% if security_commands %}
    {% for cmd in security_commands %}
    - echo "Running: {{ cmd }}"
    - {{ cmd }} || true
    {% endfor %}
    {% else %}
    - echo "⚠️  No security checks configured"
    {% endif %}
  allow_failure: true
  only:
    - main
    - merge_requests
  tags:
    - docker
"""

    SECURITY_DOCKER_TEMPLATE = """security_docker:
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

    def __init__(self, language: str, base_image: str, has_dockerfile: bool = False):
        """
        Args:
            language: Язык проекта
            base_image: Базовый Docker образ
            has_dockerfile: Есть ли Dockerfile в проекте
        """
        self.language = language
        self.base_image = base_image
        self.has_dockerfile = has_dockerfile
        self.security_commands = self._detect_security_commands()
        self.setup_commands = self._detect_setup_commands()

    def _detect_security_commands(self) -> List[str]:
        """
        Определяет команды для security сканирования
        """

        commands = []

        # Проверка на секреты (универсально)
        if os.path.exists('.git'):
            commands.append(
                'echo "🔐 Checking for secrets in git..." && (git log -p | grep -iE "password|api_key|secret|token|private_key" && echo "⚠️  Potential secrets found!" || echo "✅ No obvious secrets found")')

        if self.language == 'python':
            # Bandit для Python
            if os.path.exists('setup.py') or os.path.exists('requirements.txt'):
                commands.append('bandit -r . -f txt -ll || true')

            # Safety для зависимостей
            if os.path.exists('requirements.txt'):
                commands.append('safety check --json || true')

        elif self.language == 'node':
            # npm audit для Node
            if os.path.exists('package.json'):
                commands.append('npm audit --audit-level=high || true')

        elif self.language == 'go':
            # gosec для Go
            if os.path.exists('go.mod'):
                commands.append('go install github.com/securego/gosec/v2/cmd/gosec@latest')
                commands.append('gosec ./... -no-fail || true')

        elif self.language == 'java':
            # Maven dependency check
            if os.path.exists('pom.xml'):
                commands.append('mvn dependency-check:check || true')

        elif self.language == 'php':
            # PHP security checker
            if os.path.exists('composer.json'):
                commands.append('composer audit --dry-run || true')

        elif self.language == 'rust':
            # Cargo audit
            if os.path.exists('Cargo.toml'):
                commands.append('cargo install --quiet cargo-audit')
                commands.append('cargo audit || true')

        elif self.language == 'ruby':
            # Bundler audit
            if os.path.exists('Gemfile'):
                commands.append('gem install bundler-audit')
                commands.append('bundler-audit check || true')

        return commands

    def _detect_setup_commands(self) -> List[str]:
        """Команды для подготовки окружения"""
        commands = []

        if self.language == 'python':
            commands.append('pip install --no-cache-dir -q bandit safety')

        elif self.language == 'go':
            # gosec будет установлен в security_commands
            pass

        return commands

    def generate(self) -> str:
        """Генерирует security stage YAML"""

        template = Template(self.SECURITY_TEMPLATE)

        yaml_output = template.render(
            base_image=self.base_image,
            security_commands=self.security_commands,
            setup_commands=self.setup_commands,
        )

        # Добавляем Docker сканирование если есть Dockerfile
        if self.has_dockerfile:
            yaml_output += "\n" + self.SECURITY_DOCKER_TEMPLATE

        return yaml_output

    def get_output_string(self) -> str:
        """Возвращает готовую строку YAML для добавления в конфиг"""

        # Security stage всегда полезен, даже без специфичных проверок
        return self.generate()
