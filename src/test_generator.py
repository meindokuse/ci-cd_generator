from test_analyzer import * 
from jinja2 import Template

def analyze():
    base_directory = "." 
    
    print("🔍 Поиск всех проектов...")
    projects = discover_projects(base_directory)
    
    print(f"📁 Найдено проектов: {len(projects)}")
    for i, project in enumerate(projects, 1):
        print(f"  {i}. {project['name']} ({project['language']}) - уверенность: {project['confidence']:.1f}")
    
    if projects:
        print(f"\n🧪 Анализируем все проекты...")
        results = analyze_all_projects(base_directory)
        
        for project_name, analysis in results.items():
            print(f"\n🎯 Проект: {project_name}")
            
            if analysis.get("status") == "error":
                print(f"   ❌ Ошибка: {analysis['error']}")
                continue
                
            print(f"   🌐 Язык: {analysis['project_language']}")
            print(f"   🧪 Тип тестов: {analysis['test_type_display']}")
            print(f"   🚀 Команда: {analysis['base_command']}")

    else:
        print("❌ Проекты не найдены")


class TestStageGenerator:
    TEST_TEMPLATE = '''test:
  stage: test
  script:
    - {{ run_tests }}
  after_script:
    {% if clean %}
    {% for cmd in clean %}
    - {{ cmd }}
    {% endfor %}
    {% endif %}
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

    def get_output_string(self, project_path: str, test_file: str, additional_args: str = "") -> str:
        cmd = get_test_command_for_file(project_path, test_file, additional_args)

        template = Template(self.TEST_TEMPLATE)
        yaml_output = template.render(
            run_tests=cmd,
            artifacts=self.resolve_test_artifacts(self.base_image),
            clean=self.resolve_cleanup_commands(self.base_image)
        )
        return yaml_output

    def resolve_test_artifacts(image: str) -> List[str]:
        """
        Возвращает список путей, которые должны быть сохранены как артефакты.
        Основано на типичных путях тестовых тулов по языкам.
        """

        image = image.lower()

        # --------------------------
        # PYTHON (pytest, coverage)
        # --------------------------
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

    def resolve_cleanup_commands(image: str) -> List[str]:
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
