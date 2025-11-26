# build_generator.py

import os
from typing import Dict, List
from jinja2 import Template


class BuildStageGenerator:
    """Генератор build stage с поддержкой monorepo"""

    # Docker build + push to Docker Registry
    DOCKER_BUILD = """build:
  stage: build
  image: docker:24-cli
  services:
    - docker:24-dind
  variables:
    DOCKER_DRIVER: overlay2
    DOCKER_TLS_CERTDIR: "/certs"
  before_script:
    - echo "🔐 Logging into Docker Registry..."
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - echo "🏗️  Building Docker image..."
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA -t $CI_REGISTRY_IMAGE:latest .
    - echo "📤 Pushing to Docker Registry..."
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - docker push $CI_REGISTRY_IMAGE:latest
    - echo "✅ Docker image stored in registry"
  only:
    - main
  tags:
    - docker
  retry:
    max: 2
"""

    # Build artifact + upload to Nexus
    NEXUS_BUILD = """build:
  stage: build
  image: {{ base_image }}
  script:
    - echo "🏗️  Building artifacts..."
    - {{ build_command }}
    - echo "📤 Uploading to Nexus..."
    - |
      for file in {{ artifact_path }}; do
        curl -v -u $NEXUS_USER:$NEXUS_PASSWORD \\
          --upload-file $file \\
          "$NEXUS_URL/repository/{{ repository }}/{{ group_id }}/{{ artifact_id }}/$CI_PIPELINE_ID/$(basename $file)"
      done
    - echo "✅ Artifact stored in Nexus"
  only:
    - main
  tags:
    - docker
"""

    # Build artifact + upload to Artifactory
    ARTIFACTORY_BUILD = """build:
  stage: build
  image: {{ base_image }}
  script:
    - echo "🏗️  Building artifacts..."
    - {{ build_command }}
    - echo "📤 Uploading to Artifactory..."
    - |
      for file in {{ artifact_path }}; do
        curl -u $ARTIFACTORY_USER:$ARTIFACTORY_PASSWORD \\
          -T $file \\
          "$ARTIFACTORY_URL/{{ repository }}/{{ group_id }}/{{ artifact_id }}/$CI_PIPELINE_ID/$(basename $file)"
      done
    - echo "✅ Artifact stored in Artifactory"
  only:
    - main
  tags:
    - docker
"""

    # Build artifact + save to GitLab Artifacts
    GITLAB_ARTIFACTS_BUILD = """build:
  stage: build
  image: {{ base_image }}
  script:
    - echo "🏗️  Building artifacts..."
    - {{ build_command }}
    - echo "✅ Artifact created locally"
  artifacts:
    paths:
      - {{ artifact_path }}
    expire_in: 1 week
  only:
    - main
  tags:
    - docker
"""

    def __init__(self, config: Dict, sync_target: str):
        """
        Args:
            config: Конфигурация проекта
            sync_target: 'docker-registry', 'nexus', 'artifactory', 'gitlab-artifacts'
        """
        self.config = config
        self.sync_target = sync_target
        self.is_monorepo = config.get('is_monorepo', False)
        self.services = config.get('services', [])

    def generate(self) -> str:
        """Генерирует build stage"""

        # Monorepo: несколько сервисов
        if self.is_monorepo and len(self.services) > 0:
            return self._generate_monorepo_builds()

        # Single service
        if self.sync_target == 'docker-registry':
            return self.DOCKER_BUILD
        elif self.sync_target == 'nexus':
            return self._generate_nexus()
        elif self.sync_target == 'artifactory':
            return self._generate_artifactory()
        elif self.sync_target == 'gitlab-artifacts':
            return self._generate_gitlab_artifacts()
        else:
            raise ValueError(f"❌ Unknown sync_target: {self.sync_target}")

    def _generate_monorepo_builds(self) -> str:
        """Генерирует отдельный build job для каждого сервиса в monorepo"""

        builds = []

        for service in self.services:
            service_name = service['name']
            service_path = service['path']

            build_job = f"""build_{service_name}:
  stage: build
  image: docker:24-cli
  services:
    - docker:24-dind
  variables:
    DOCKER_DRIVER: overlay2
    DOCKER_TLS_CERTDIR: "/certs"
  before_script:
    - echo "🔐 Logging into Docker Registry..."
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - echo "🏗️  Building {service_name} service..."
    - docker build -t $CI_REGISTRY_IMAGE/{service_name}:$CI_COMMIT_SHA -t $CI_REGISTRY_IMAGE/{service_name}:latest ./{service_path}
    - echo "📤 Pushing to Docker Registry..."
    - docker push $CI_REGISTRY_IMAGE/{service_name}:$CI_COMMIT_SHA
    - docker push $CI_REGISTRY_IMAGE/{service_name}:latest
    - echo "✅ {service_name} image stored in registry"
  only:
    - main
  tags:
    - docker
  retry:
    max: 2
"""
            builds.append(build_job)

        return "\n".join(builds)

    def _generate_nexus(self) -> str:
        template = Template(self.NEXUS_BUILD)
        artifact_paths = self.config.get('artifact_paths', {})
        language = self.config.get('language', 'unknown')

        return template.render(
            base_image=self.config.get('base_image', 'alpine:latest'),
            build_command=artifact_paths.get('build_command', 'echo "No build"'),
            artifact_path=artifact_paths.get('artifact_path', '*'),
            repository=self._get_nexus_repo(language),
            group_id=self._get_group_id(language),
            artifact_id=self._get_artifact_id(),
        )

    def _generate_artifactory(self) -> str:
        template = Template(self.ARTIFACTORY_BUILD)
        artifact_paths = self.config.get('artifact_paths', {})
        language = self.config.get('language', 'unknown')

        return template.render(
            base_image=self.config.get('base_image', 'alpine:latest'),
            build_command=artifact_paths.get('build_command', 'echo "No build"'),
            artifact_path=artifact_paths.get('artifact_path', '*'),
            repository=self._get_artifactory_repo(language),
            group_id=self._get_group_id(language),
            artifact_id=self._get_artifact_id(),
        )

    def _generate_gitlab_artifacts(self) -> str:
        template = Template(self.GITLAB_ARTIFACTS_BUILD)
        artifact_paths = self.config.get('artifact_paths', {})

        return template.render(
            base_image=self.config.get('base_image', 'alpine:latest'),
            build_command=artifact_paths.get('build_command', 'echo "No build"'),
            artifact_path=artifact_paths.get('artifact_path', '*'),
        )

    def _get_nexus_repo(self, language: str) -> str:
        repos = {
            'java': 'maven-releases',
            'kotlin': 'maven-releases',
            'python': 'pypi-hosted',
            'node': 'npm-hosted',
            'typescript': 'npm-hosted',
            'go': 'raw-hosted',
            'rust': 'raw-hosted',
        }
        return repos.get(language, 'raw-hosted')

    def _get_artifactory_repo(self, language: str) -> str:
        repos = {
            'java': 'libs-release-local',
            'kotlin': 'libs-release-local',
            'python': 'pypi-local',
            'node': 'npm-local',
            'typescript': 'npm-local',
            'go': 'go-local',
            'rust': 'generic-local',
        }
        return repos.get(language, 'generic-local')

    def _get_group_id(self, language: str) -> str:
        if language in ['java', 'kotlin']:
            return 'com.example'
        return language

    def _get_artifact_id(self) -> str:
        return os.path.basename(os.getcwd())

    def get_output_string(self) -> str:
        return self.generate()
