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
            'language_info': {}
        }
    
    @pytest.fixture
    def compose_config(self, basic_config):
        """Конфигурация с docker-compose"""
        config = basic_config.copy()
        config['has_docker_compose'] = True
        return config
    
    # ============ DOCKER REGISTRY → SERVER ============
    
    def test_docker_registry_simple_deploy(self, basic_config):
        """Тест: docker-registry + server (простой)"""
        generator = DeployStageGenerator(basic_config, sync="docker-registry", deploy="server")
        result = generator.generate()
        
        assert "deploy_production:" in result
        assert "docker:24-cli" in result
        assert "$CI_REGISTRY_IMAGE" in result
        assert "docker pull" in result
        assert "ssh" in result
        assert "docker run" in result
    
    def test_docker_registry_compose_deploy(self, compose_config):
        """Тест: docker-registry + server (compose)"""
        generator = DeployStageGenerator(compose_config, sync="docker-registry", deploy="server")
        result = generator.generate()
        
        assert "deploy_production:" in result
        assert "docker compose pull" in result
        assert "docker compose up -d" in result
        assert "$REMOTE_COMPOSE_DIR" in result
    
    # ============ NEXUS → SERVER ============
    
    def test_nexus_docker_simple_deploy(self, basic_config):
        """Тест: nexus + server (простой)"""
        generator = DeployStageGenerator(basic_config, sync="nexus", deploy="server")
        result = generator.generate()
        
        assert "deploy_production:" in result
        assert "$NEXUS_DOCKER_REGISTRY" in result
        assert "$NEXUS_USER" in result
        assert "$NEXUS_PASSWORD" in result
        assert "docker pull" in result
    
    def test_nexus_docker_compose_deploy(self, compose_config):
        """Тест: nexus + server (compose)"""
        generator = DeployStageGenerator(compose_config, sync="nexus", deploy="server")
        result = generator.generate()
        
        assert "docker compose pull" in result
        assert "$NEXUS_DOCKER_REGISTRY" in result
    
    # ============ ARTIFACTORY → SERVER ============
    
    def test_artifactory_docker_simple_deploy(self, basic_config):
        """Тест: artifactory + server (простой)"""
        generator = DeployStageGenerator(basic_config, sync="artifactory", deploy="server")
        result = generator.generate()
        
        assert "deploy_production:" in result
        assert "$ARTIFACTORY_DOCKER_REGISTRY" in result
        assert "$ARTIFACTORY_USER" in result
        assert "$ARTIFACTORY_PASSWORD" in result
    
    def test_artifactory_docker_compose_deploy(self, compose_config):
        """Тест: artifactory + server (compose)"""
        generator = DeployStageGenerator(compose_config, sync="artifactory", deploy="server")
        result = generator.generate()
        
        assert "docker compose pull" in result
        assert "$ARTIFACTORY_DOCKER_REGISTRY" in result
    
    # ============ GITLAB ARTIFACTS → SERVER ============
    
    def test_artifacts_docker_deploy(self, basic_config):
        """Тест: gitlab-artifacts + server"""
        generator = DeployStageGenerator(basic_config, sync="gitlab-artifacts", deploy="server")
        result = generator.generate()
        
        assert "deploy_production:" in result
        assert "docker load" in result
        assert "myapp-image.tar" in result
        assert "scp" in result
    
    # ============ GITHUB RELEASES ============
    
    def test_nexus_to_github_release(self, basic_config):
        """Тест: nexus + github"""
        generator = DeployStageGenerator(basic_config, sync="nexus", deploy="github")
        result = generator.generate()
        
        assert "release_github:" in result
        assert "$NEXUS_URL" in result
        assert "$GITHUB_TOKEN" in result
        assert "api.github.com/repos" in result
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
    
    # ============ ПАРАМЕТРИЗАЦИЯ ============
    
    @pytest.mark.parametrize("sync", [
        "docker-registry",
        "nexus",
        "artifactory",
        "gitlab-artifacts"
    ])
    def test_all_sync_methods_server_deploy(self, basic_config, sync):
        """Тест: все sync методы работают с deploy=server"""
        generator = DeployStageGenerator(basic_config, sync=sync, deploy="server")
        result = generator.generate()
        
        assert "deploy_production:" in result
        assert "stage: deploy" in result
    
    @pytest.mark.parametrize("sync,expected_var", [
        ("nexus", "$NEXUS_URL"),
        ("artifactory", "$ARTIFACTORY_URL"),
        ("gitlab-artifacts", "dependencies:")
    ])
    def test_github_releases_variables(self, basic_config, sync, expected_var):
        """Тест: правильные переменные для GitHub releases"""
        generator = DeployStageGenerator(basic_config, sync=sync, deploy="github")
        result = generator.generate()
        
        assert expected_var in result
    
    # ============ EDGE CASES ============
    
    def test_invalid_deploy_target(self, basic_config):
        """Тест: неверный deploy target вызывает ошибку"""
        generator = DeployStageGenerator(basic_config, sync="nexus", deploy="unknown")
        
        with pytest.raises(ValueError, match="Unknown deploy target"):
            generator.generate()
    
    def test_artifact_name_in_templates(self, basic_config):
        """Тест: artifact_name подставляется в шаблоны"""
        generator = DeployStageGenerator(basic_config, sync="gitlab-artifacts", deploy="server")
        result = generator.generate()
        
        assert "myapp-image.tar" in result
    
    def test_config_without_artifact_paths(self, basic_config):
        """Тест: конфигурация без artifact_paths"""
        config = basic_config.copy()
        config['artifact_paths'] = None
        
        generator = DeployStageGenerator(config, sync="nexus", deploy="server")
        result = generator.generate()
        
        # Не должно быть ошибок, просто пустые значения
        assert result is not None
    
    def test_config_without_dockerfile_info(self, basic_config):
        """Тест: конфигурация без dockerfile_info"""
        config = basic_config.copy()
        config['dockerfile_info'] = None
        
        generator = DeployStageGenerator(config, sync="docker-registry", deploy="server")
        result = generator.generate()
        
        # Не должно быть ошибок
        assert result is not None


# ============ ЗАПУСК ============

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
