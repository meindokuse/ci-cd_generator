# final_ci_generator.py

import os
from jinja2 import Template
from project_analyzer import ProjectAnalyzer
from build_generator import BuildStageGenerator
from lint_generator import LintStageGenerator
from security_generator import SecurityStageGenerator


class FinalCIGenerator:
    """
    Финальный генератор CI/CD
    Собирает все stage'и в один .gitlab-ci.yml файл
    """

    def __init__(self, analyzer: ProjectAnalyzer):
        """
        Args:
            analyzer: ProjectAnalyzer с данными проекта
        """
        self.analyzer = analyzer
        self.config = analyzer.get_summary()
        self.stages = {}

    def generate_all_stages(self):
        """Генерирует все stage'и"""

        print("🏗️  Генерирую stage'и...\n")

        # Build stage
        print("  → Генерирую BUILD stage...")
        build_gen = BuildStageGenerator(self.config['dockerfile_info'])
        self.stages['build'] = build_gen.get_output_string()

        # Lint stage
        print("  → Генерирую LINT stage...")
        lint_gen = LintStageGenerator(
            self.config['language'],
            self.config['base_image']
        )
        self.stages['lint'] = lint_gen.get_output_string()

        # Security stage
        print("  → Генерирую SECURITY stage...")
        security_gen = SecurityStageGenerator(
            self.config['language'],
            self.config['base_image'],
            has_dockerfile=True
        )
        self.stages['security'] = security_gen.get_output_string()

        print("\n✅ Все stage'и готовы\n")

    def assemble_config(self) -> str:
        """Собирает финальный .gitlab-ci.yml"""

        config = """stages:
  - build
  - lint
  - security

variables:
  DOCKER_IMAGE_TAG: "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA"
  DOCKER_IMAGE_LATEST: "$CI_REGISTRY_IMAGE:latest"

"""

        # Добавляем все stage'и
        for stage_name, stage_content in self.stages.items():
            config += f"# ========== {stage_name.upper()} STAGE ==========\n"
            config += stage_content
            config += "\n\n"

        return config

    def save(self, filepath: str = ".gitlab-ci.yml") -> str:
        """Сохраняет конфиг в файл"""

        config = self.assemble_config()

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(config)

        print(f"✅ Конфиг сохранён: {filepath}\n")
        return filepath

    def print_summary(self):
        """Печатает сводку генерации"""

        print("=" * 60)
        print("📋 ИТОГОВЫЙ КОНФИГ")
        print("=" * 60)

        print(f"\n📦 Проект:")
        print(f"   Язык: {self.config['language']}")
        print(f"   Версия: {self.config['version']}")
        print(f"   Базовый образ: {self.config['base_image']}")
        print(f"   Порт: {self.config['port']}")
        print(f"   Dockerfile: {'Найден' if self.config['dockerfile_exists'] else 'Сгенерирован'}")

        print(f"\n🎯 Stage'и:")
        print(f"   ✅ Build")
        print(f"   ✅ Lint")
        print(f"   ✅ Security")

        print("\n" + "=" * 60)
