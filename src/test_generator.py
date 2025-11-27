from test_analyzer import * 
from jinja2 import Template


class TestStageGenerator:
    TEST_TEMPLATE = '''test:
  stage: test
  image: {{ image }}

  script:
    - {{ run_tests }}
  {% if clean %}
  after_script:
    {% for cmd in clean %}
    - {{ cmd }}
    {% endfor %}
  {% endif %}
  tags:
    - docker
  retry:
    max: 2
    when:
      - runner_system_failure
      - stuck_or_timeout_failure
  artifacts:
    paths:
      {% if artifacts %}
      {% for cmd in artifacts %}
      - {{ cmd }}
      {% endfor %}
      {% endif %}
    expire_in: 1 week
'''
    def __init__(self, language: str, base_image: str):
        self.language = language
        self.base_image = base_image
        self.base_directory = "."


    def get_output_string(self) -> str:

        cmd = get_test_command_for_file(self.base_directory, '')

        template = Template(self.TEST_TEMPLATE)
        yaml_output = template.render(
            run_tests=cmd,
            artifacts=self.resolve_test_artifacts(self.base_image),
            clean=self.resolve_cleanup_commands(self.base_image)
        )
        return yaml_output


    def resolve_test_artifacts(self, image: str) -> List[str]:
        """
        Возвращает список путей, которые должны быть сохранены как артефакты.
        Основано на типичных путях тестовых тулов по языкам.
        """

        image = image.lower()


        if "python" in image:
            return [
                "test-reports/",
                "htmlcov/",              # coverage html
                "coverage.xml",          # coverage xml
                "pytest.xml",            # junit report
            ]

        # --------------------------
        # NODE.js / JS / TS (Jest, Cypress)
        # --------------------------
        if "node" in image:
            return [
                "test-reports/",
                "coverage/",             # jest coverage
                "junit.xml",
                "reports/",              # cypress, mocha
            ]

        # --------------------------
        # JAVA (Maven + Surefire/Jacoco)
        # --------------------------
        if "maven" in image or "openjdk" in image or "temurin" in image:
            return [
                "target/surefire-reports/",
                "target/failsafe-reports/",
                "target/site/jacoco/",       # jacoco coverage html
                "target/jacoco.exec",        # raw
            ]

        # --------------------------
        # GRADLE
        # --------------------------
        if "gradle" in image:
            return [
                "build/test-results/test/",          # junit xml
                "build/reports/tests/test/",         # HTML отчеты
                "build/reports/jacoco/test/",        # coverage
            ]

        # --------------------------
        # GO
        # --------------------------
        if "golang" in image or "go:" in image:
            return [
                "coverage.out",            # go test -coverprofile
                "test-reports/",
            ]

        # --------------------------
        # DOTNET
        # --------------------------
        if "dotnet" in image or "mcr.microsoft.com/dotnet" in image:
            return [
                "TestResults/",            # MSTest/NUnit/XUnit
                "coverage.cobertura.xml",
            ]

        # --------------------------
        # PHP
        # --------------------------
        if "php" in image:
            return [
                "build/logs/",             # PHPUnit
                "coverage.xml",
            ]

        # --------------------------
        # RUBY
        # --------------------------
        if "ruby" in image:
            return [
                "coverage/",               # SimpleCov
                "test-reports/",
            ]

        # --------------------------
        # DEFAULT (если образ неизвестен)
        # --------------------------
        return [
            "test-reports/",
            "coverage/",
        ]

    def resolve_cleanup_commands(self, image: str) -> List[str]:
        """
        Возвращает список shell-команд для блока after_script
        в зависимости от образа.
        """

        img = image.lower()

        # --------------------------
        # PYTHON
        # --------------------------
        if "python" in img:
            return [
                # удаляем кеши и временные файлы
                "rm -rf .pytest_cache || true",
                "rm -rf __pycache__ */__pycache__ || true",
                "rm -f .coverage coverage.xml || true",
                "rm -rf htmlcov || true",
                "echo 'Python test cleanup done'",
            ]

        # --------------------------
        # NODE.js / JS / TS
        # --------------------------
        if "node" in img:
            return [
                # чистим кэш тестов, coverage и отчеты
                "rm -rf coverage || true",
                "rm -rf .nyc_output || true",
                "rm -rf test-reports || true",
                # node_modules обычно не нужно трогать в CI, их и так переустановят
                "echo 'Node.js test cleanup done'",
            ]

        # --------------------------
        # JAVA (Maven / JDK)
        # --------------------------
        if "maven" in img or "openjdk" in img or "temurin" in img:
            return [
                # не всегда нужно очищать target целиком (может пригодиться как artifacts),
                # поэтому чистим только временные отчеты, если надо
                "rm -rf target/surefire-reports/*.tmp || true",
                "rm -rf target/failsafe-reports/*.tmp || true",
                "echo 'Java (Maven) test cleanup done'",
            ]

        # --------------------------
        # GRADLE
        # --------------------------
        if "gradle" in img:
            return [
                "rm -rf build/tmp || true",
                "rm -rf build/reports/tests || true",
                "echo 'Gradle test cleanup done'",
            ]

        # --------------------------
        # GO
        # --------------------------
        if "golang" in img or "go:" in img:
            return [
                "rm -f coverage.out || true",
                "rm -rf test-reports || true",
                "echo 'Go test cleanup done'",
            ]

        # --------------------------
        # DOTNET
        # --------------------------
        if "dotnet" in img or "mcr.microsoft.com/dotnet" in img:
            return [
                "rm -rf TestResults || true",
                "rm -f coverage.cobertura.xml || true",
                "echo '.NET test cleanup done'",
            ]

        # --------------------------
        # PHP
        # --------------------------
        if "php" in img:
            return [
                "rm -rf build/logs || true",
                "rm -f coverage.xml || true",
                "echo 'PHP test cleanup done'",
            ]

        # --------------------------
        # RUBY
        # --------------------------
        if "ruby" in img:
            return [
                "rm -rf coverage || true",
                "rm -rf test-reports || true",
                "echo 'Ruby test cleanup done'",
            ]

        # --------------------------
        # DEFAULT (любой другой образ)
        # --------------------------
        return [
            "rm -rf test-reports || true",
            "rm -rf coverage || true",
            "echo 'Generic test cleanup done'",
        ]
