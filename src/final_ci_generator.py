# final_ci_generator.py

from project_analyzer import ProjectAnalyzer
from build_generator import BuildStageGenerator
from lint_generator import LintStageGenerator
from security_generator import SecurityStageGenerator
from deploy_generator import DeployStageGenerator


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

        # Lint
        print("  → Генерирую LINT stage...")
        lint_gen = LintStageGenerator(
            self.config['language'],
            self.config['version']
        )
        self.stages['lint'] = lint_gen.get_output_string()

        # Security
        print("  → Генерирую SECURITY stage...")
        security_gen = SecurityStageGenerator(
            self.config['language'],
            self.config['version'],
            has_dockerfile=self.config['dockerfile_exists']
        )
        self.stages['security'] = security_gen.get_output_string()

        # Deploy
        if self.deploy_target:
            print(f"  → Генерирую DEPLOY stage ({self.sync_target} → {self.deploy_target})...")
            deploy_gen = DeployStageGenerator(self.config, self.sync_target, self.deploy_target)
            self.stages['deploy'] = deploy_gen.get_output_string()

        print("\n✅ Все stage'и готовы\n")

    def assemble_config(self) -> str:
        """Собирает финальный .gitlab-ci.yml"""

        stages_list = "  - build\n  - lint\n  - security"
        if self.deploy_target:
            stages_list += "\n  - deploy"

        config = f"""stages:
{stages_list}

variables:
"""

        if self.sync_target == 'docker-registry':
            config += """  DOCKER_IMAGE_TAG: "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA"
  DOCKER_IMAGE_LATEST: "$CI_REGISTRY_IMAGE:latest"
  SSH_PORT: "22"
  DEPLOY_ENV: "production"
"""
        elif self.sync_target in ['nexus', 'artifactory']:
            config += """  ARTIFACT_VERSION: "$CI_PIPELINE_ID"
"""
        else:
            config += """  ARTIFACT_VERSION: "$CI_PIPELINE_ID"
"""

        config += "\n"

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
        print(f"   Dockerfile: {'✅ Найден' if self.config['dockerfile_exists'] else '❌ Не найден'}")

        print(f"\n🔄 Конфигурация:")
        print(f"   Sync target: {self.sync_target}")
        if self.deploy_target:
            print(f"   Deploy target: {self.deploy_target}")

        print(f"\n🎯 Stages:")
        for stage in ['build', 'lint', 'security', 'deploy']:
            if stage in self.stages:
                print(f"   ✅ {stage}")

        print("\n" + "=" * 70)
