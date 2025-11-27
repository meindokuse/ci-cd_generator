# src/final_ci_generator.py

from project_analyzer import ProjectAnalyzer
from build_generator import BuildStageGenerator
from lint_generator import LintStageGenerator
from sonarqube_generator import SonarQubeStageGenerator
from test_generator import TestStageGenerator
from security_generator import SecurityStageGenerator
from deploy.deploy_generator import DeployStageGenerator


class FinalCIGenerator:
    """Финальный генератор CI/CD"""

    def __init__(self, analyzer: ProjectAnalyzer, sync_target: str, deploy_target: str = None):
        """
        Args:
            analyzer: ProjectAnalyzer
            sync_target: 'docker-registry', 'nexus', 'artifactory', 'gitlab-artifacts'
            deploy_target: 'server', 'github'
        """
        self.analyzer = analyzer
        self.config = analyzer.get_summary()
        self.stages = {}
        self.sync_target = sync_target
        self.deploy_target = deploy_target

    def generate_all_stages(self):
        """Генерирует все stage'и"""

        print("🏗️  Генерирую stage'и...\n")

        # Build
        print("  → Генерирую BUILD stage...")
        build_gen = BuildStageGenerator(self.config, self.sync_target)
        self.stages['build'] = build_gen.get_output_string()

        # Test (Unit + Integration)
        print("  → Генерирую TEST stages...")
        test_gen = TestStageGenerator(
            self.config['language'],
            self.config['version'],
            self.config['dockerfile_info'],
        )
        self.stages['test'] = test_gen.get_output_string()

        # Lint
        print("  → Генерирую LINT stage...")
        lint_gen = LintStageGenerator(
            self.config['language'],
            self.config['version']
        )
        self.stages['lint'] = lint_gen.get_output_string()

        # SonarQube
        print("  → Генерирую SONARQUBE stage...")
        sonar_gen = SonarQubeStageGenerator(
            self.config['language'],
            self.config['version']
        )
        self.stages['sonarqube'] = sonar_gen.get_output_string()

        # Security
        print("  → Генерирую SECURITY stage...")
        security_gen = SecurityStageGenerator(
            self.config['language'],
            self.config['version'],
            has_dockerfile=self.config['dockerfile_exists']
        )
        self.stages['security'] = security_gen.get_output_string()

        # Deploy stage
        print("  → Генерирую DEPLOY stage...")
        deploy_gen = DeployStageGenerator(self.config, self.sync_target, self.deploy_target)
        self.stages['deploy'] = deploy_gen.generate()

        print("\n✅ Все stage'и готовы\n")

    def assemble_config(self) -> str:
        """Собирает финальный .gitlab-ci.yml"""

        # Формируем список stages
        stages_list = "  - build\n  - test\n  - lint\n  - sonarqube\n  - security\n  - integration"
        if self.deploy_target:
            stages_list += "\n  - deploy"

        # Начинаем конфиг
        config = f"""stages:
{stages_list}

"""

        # ========== НОВОЕ: Добавляем переменные окружения из .env ==========
        if hasattr(self.analyzer, 'env_analyzer') and self.analyzer.env_analyzer.env_vars:
            env_section = self.analyzer.env_analyzer.generate_gitlab_ci_env_section()
            if env_section:
                config += "# ========== ENVIRONMENT VARIABLES ==========\n"
                config += env_section
                config += "\n"

        # Стандартные переменные в зависимости от sync_target
        config += "# ========== CI/CD VARIABLES ==========\n"
        config += "variables:\n"

        if self.sync_target == 'docker-registry':
            config += """  DOCKER_IMAGE_TAG: "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA"
  DOCKER_IMAGE_LATEST: "$CI_REGISTRY_IMAGE:latest"
  SSH_PORT: "22"
  DEPLOY_ENV: "production"
  SONAR_HOST_URL: "http://sonarqube:9000"
"""
        else:
            config += """  ARTIFACT_VERSION: "$CI_PIPELINE_ID"
  SONAR_HOST_URL: "http://sonarqube:9000"
"""

        config += "\n"

        # Добавляем все stage'и
        for stage_name, stage_content in self.stages.items():
            config += f"# ========== {stage_name.upper()} STAGE ==========\n"
            config += stage_content
            config += "\n\n"

        return config

    def save(self, filepath: str = ".gitlab-ci.yml") -> str:
        config = self.assemble_config()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(config)
        print(f"✅ Конфиг сохранён: {filepath}\n")
        return filepath

    def print_summary(self):
        print("=" * 70)
        print("📋 ИТОГОВЫЙ КОНФИГ")
        print("=" * 70)

        print(f"\n📦 Проект:")
        print(f"   Язык: {self.config['language']}")
        print(f"   Версия: {self.config['version']}")

        # ========== НОВОЕ: Вывод фреймворка ==========
        if self.config.get('framework'):
            print(f"   Фреймворк: {self.config['framework']}")

        print(f"   Dockerfile: {'✅ Найден' if self.config['dockerfile_exists'] else '❌ Не найден'}")

        if self.config.get('docker_compose_exists'):
            compose_info = self.config.get('docker_compose_info', {})
            print(f"   docker-compose.yml: ✅ Найден")
            print(f"      Файл: {compose_info.get('filename')}")
            print(f"      Сервисов: {compose_info.get('service_count', 0)}")
            if compose_info.get('services'):
                print(f"      Список: {', '.join(compose_info['services'])}")
        else:
            print(f"   docker-compose.yml: ❌ Не найден")

        if self.config.get('is_monorepo'):
            print(f"\n   🏗️  Тип: Monorepo")
            print(f"   Сервисов с Dockerfile: {len(self.config['services'])}")
            for svc in self.config['services']:
                print(f"      → {svc['name']} ({svc['path']})")

        # ========== НОВОЕ: Вывод статистики по .env ==========
        if self.config.get('env_summary', {}).get('total_vars', 0) > 0:
            env_sum = self.config['env_summary']
            print(f"\n🔐 Переменные окружения:")
            print(f"   Всего: {env_sum['total_vars']}")
            print(f"   Секреты: {env_sum['sensitive_vars']}")
            print(f"   Обязательные: {env_sum['required_vars']}")
            if env_sum.get('env_files'):
                print(f"   Файлы: {', '.join(env_sum['env_files'])}")

        print(f"\n🔄 Конфигурация:")
        print(f"   Sync target: {self.sync_target}")
        if self.deploy_target:
            print(f"   Deploy target: {self.deploy_target}")

        print(f"\n🎯 Stages:")
        for stage in ['build', 'test', 'lint', 'sonarqube', 'security', 'integration', 'deploy']:
            if stage in self.stages:
                print(f"   ✅ {stage}")

        print("\n" + "=" * 70)
