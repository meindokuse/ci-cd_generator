# test_deploy_stage_generator.py

import pytest
from deploy_stage_generator import DeployStageGenerator


class TestDeployStageGenerator:
    """Тесты для генератора deploy-стейджей"""

    # ============ FIXTURES ============

    @pytest.fixture
    def basic_config(self):
        """Базовая конфигурация проекта"""
        return {
            'language': 'python',
            'version': '3.11',
            'base_image': 'python:3.11-alpine',
            'has_docker_compose': False,
            'dockerfile_exists': True,
            'dockerfile_info': {
                'base_images': ['python:3.11-alpine'],
                'final_image': 'python:3.11-alpine',
                'is_multistage': False
            },
            'artifact_paths': {
                'artifact_path': 'dist/',
                'artifact_name': 'myapp',
                'build_command': 'python setup.py build',
                'artifact_type': 'binary'
            },
            'language_info': {},
            'services': [
                {'name': 'frontend', 'path': './frontend'},
                {'name': 'backend', 'path': './backend'},
                {'name': 'bot', 'path': './bot'},
            ],
            'is_monorepo': False
        }

    @pytest.fixture
    def monorepo_config(self, basic_config):
        """Конфигурация для монорепозитория"""
        config = basic_config.copy()
        config['is_monorepo'] = True
        return config

    # ============ DOCKER REGISTRY → SERVER ============

    def test_docker_registry_compose_deploy(self, basic_config):
        """Тест: docker-registry + server (compose)"""
        generator = DeployStageGenerator(basic_config, sync="docker-registry", deploy="server")
        result = generator.generate()

        assert "deploy_production:" in result
        assert "docker compose pull" in result
        assert "docker compose up -d" in result
        assert "$CI_REGISTRY_IMAGE" in result

    def test_docker_registry_compose_monorepo_deploy(self, monorepo_config):
        """Тест: docker-registry + server (compose, монорепозиторий)"""
        generator = DeployStageGenerator(monorepo_config, sync="docker-registry", deploy="server")
        result = generator.generate()

        assert "deploy_production:" in result
        assert "docker compose pull" in result
        assert "docker compose up -d" in result
        assert "frontend:" in result
        assert "backend:" in result
        assert "bot:" in result

    # ============ NEXUS → SERVER ============

    def test_nexus_docker_compose_deploy(self, basic_config):
        """Тест: nexus + server (compose)"""
        generator = DeployStageGenerator(basic_config, sync="nexus", deploy="server")
        result = generator.generate()

        assert "deploy_production:" in result
        assert "docker compose pull" in result
        assert "$NEXUS_DOCKER_REGISTRY" in result

    def test_nexus_docker_compose_monorepo_deploy(self, monorepo_config):
        """Тест: nexus + server (compose, монорепозиторий)"""
        generator = DeployStageGenerator(monorepo_config, sync="nexus", deploy="server")
        result = generator.generate()

        assert "deploy_production:" in result
        assert "docker compose pull" in result
        assert "frontend:" in result
        assert "backend:" in result
        assert "bot:" in result

    # ============ ARTIFACTORY → SERVER ============

    def test_artifactory_docker_compose_deploy(self, basic_config):
        """Тест: artifactory + server (compose)"""
        generator = DeployStageGenerator(basic_config, sync="artifactory", deploy="server")
        result = generator.generate()

        assert "deploy_production:" in result
        assert "docker compose pull" in result
        assert "$ARTIFACTORY_DOCKER_REGISTRY" in result

    def test_artifactory_docker_compose_monorepo_deploy(self, monorepo_config):
        """Тест: artifactory + server (compose, монорепозиторий)"""
        generator = DeployStageGenerator(monorepo_config, sync="artifactory", deploy="server")
        result = generator.generate()

        assert "deploy_production:" in result
        assert "docker compose pull" in result
        assert "frontend:" in result
        assert "backend:" in result
        assert "bot:" in result

    # ============ GITLAB ARTIFACTS → SERVER ============

    def test_artifacts_docker_compose_deploy(self, basic_config):
        """Тест: gitlab-artifacts + server (compose)"""
        generator = DeployStageGenerator(basic_config, sync="gitlab-artifacts", deploy="server")
        result = generator.generate()

        assert "deploy_production:" in result
        assert "docker compose up -d" in result
        assert "myapp-image.tar" in result

    def test_artifacts_docker_compose_monorepo_deploy(self, monorepo_config):
        """Тест: gitlab-artifacts + server (compose, монорепозиторий)"""
        generator = DeployStageGenerator(monorepo_config, sync="gitlab-artifacts", deploy="server")
        result = generator.generate()

        assert "deploy_production:" in result
        assert "docker compose up -d" in result
        assert "frontend:" in result
        assert "backend:" in result
        assert "bot:" in result

    # ============ GITHUB RELEASES ============

    def test_nexus_to_github_release(self, basic_config):
        """Тест: nexus + github"""
        generator = DeployStageGenerator(basic_config, sync="nexus", deploy="github")
        result = generator.generate()

        assert "release_github:" in result
        assert "$NEXUS_URL" in result
        assert "$GITHUB_TOKEN" in result
        assert "myapp" in result

    def test_artifactory_to_github_release(self, basic_config):
        """Тест: artifactory + github"""
        generator = DeployStageGenerator(basic_config, sync="artifactory", deploy="github")
        result = generator.generate()

        assert "release_github:" in result
        assert "$ARTIFACTORY_URL" in result
        assert "$GITHUB_TOKEN" in result

    def test_artifacts_to_github_release(self, basic_config):
        """Тест: gitlab-artifacts + github"""
        generator = DeployStageGenerator(basic_config, sync="gitlab-artifacts", deploy="github")
        result = generator.generate()

        assert "release_github:" in result
        assert "dependencies:" in result
        assert "$GITHUB_TOKEN" in result
        assert "myapp" in result

    def test_docker_registry_to_github_warning(self, basic_config):
        """Тест: docker-registry + github (предупреждение)"""
        generator = DeployStageGenerator(basic_config, sync="docker-registry", deploy="github")
        result = generator.generate()

        assert "WARNING" in result
        assert "необычная комбинация" in result

    # ============ EDGE CASES ============

    def test_invalid_deploy_target(self, basic_config):
        """Тест: неверный deploy target вызывает ошибку"""
        generator = DeployStageGenerator(basic_config, sync="nexus", deploy="unknown")

        with pytest.raises(ValueError, match="Unknown deploy target"):
            generator.generate()

    def test_config_without_services(self, basic_config):
        """Тест: конфигурация без services"""
        config = basic_config.copy()
        config['services'] = []

        generator = DeployStageGenerator(config, sync="docker-registry", deploy="server")
        result = generator.generate()

        assert result is not None

    def test_config_without_artifact_paths(self, basic_config):
        """Тест: конфигурация без artifact_paths"""
        config = basic_config.copy()
        config['artifact_paths'] = None

        generator = DeployStageGenerator(config, sync="nexus", deploy="server")
        result = generator.generate()

        assert result is not None

    def test_config_without_dockerfile_info(self, basic_config):
        """Тест: конфигурация без dockerfile_info"""
        config = basic_config.copy()
        config['dockerfile_info'] = None

        generator = DeployStageGenerator(config, sync="docker-registry", deploy="server")
        result = generator.generate()

        assert result is not None


# ============ ЗАПУСК ============

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
