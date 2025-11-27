# test_deploy_stage_generator.py

import pytest
from deploy_generator import DeployStageGenerator


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

    # ============ SERVER DEPLOY ============

    @pytest.mark.parametrize("sync", [
        "docker-registry",
        "nexus",
        "artifactory",
        "gitlab-artifacts"
    ])
    def test_server_deploy_templates(self, basic_config, sync):
        """Тест: генерация deploy-стейджа для server"""
        generator = DeployStageGenerator(basic_config, sync=sync, deploy="server")
        result = generator.generate()

        assert "deploy_production:" in result
        assert "docker compose" in result
        assert "scp" in result
        assert "ssh" in result

    def test_server_deploy_monorepo(self, monorepo_config):
        """Тест: генерация deploy-стейджа для монорепозитория"""
        generator = DeployStageGenerator(monorepo_config, sync="docker-registry", deploy="server")
        result = generator.generate()

        assert "frontend:" in result
        assert "backend:" in result
        assert "bot:" in result

    # ============ GITHUB RELEASE ============

    @pytest.mark.parametrize("sync", [
        "nexus",
        "artifactory",
        "gitlab-artifacts"
    ])
    def test_github_release_templates(self, basic_config, sync):
        """Тест: генерация github-release стейджа"""
        generator = DeployStageGenerator(basic_config, sync=sync, deploy="github")
        result = generator.generate()

        assert "release_github:" in result
        assert "curl" in result
        assert "myapp" in result

    def test_docker_registry_to_github_warning(self, basic_config):
        """Тест: предупреждение при docker-registry + github"""
        generator = DeployStageGenerator(basic_config, sync="docker-registry", deploy="github")
        result = generator.generate()

        assert "WARNING" in result
        assert "необычная комбинация" in result

    # ============ EDGE CASES ============

    def test_invalid_deploy_target(self, basic_config):
        """Тест: ошибка при неверном deploy target"""
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
