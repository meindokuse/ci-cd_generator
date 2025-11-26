# deploy_stage_generator.py

from jinja2 import Template

class DeployStageGenerator:
    """
    Генератор deploy-стейджа на основе комбинации sync + deploy
    """
    
    def __init__(self, config: dict, sync: str, deploy: str):
        """
        config: summary из ProjectAnalyzer
        sync: "docker-registry", "nexus", "artifactory", "gitlab-artifacts"
        deploy: "server", "github"
        """
        self.config = config
        self.sync = sync
        self.deploy = deploy
        self.use_compose = config.get('has_docker_compose', False)
    
    def generate(self) -> str:
        # Роутинг по комбинациям
        if self.deploy == "server":
            return self._generate_server_deploy()
        elif self.deploy == "github":
            return self._generate_github_release()
        else:
            raise ValueError(f"Unknown deploy target: {self.deploy}")
    
    # ============ SERVER DEPLOY ============
    
    def _generate_server_deploy(self):
        """
        deploy=server → всегда Docker (образ или compose)
        Различие только в источнике образа (sync)
        """
        if self.sync == "docker-registry":
            return self._docker_registry_to_server()
        elif self.sync == "nexus":
            return self._nexus_docker_to_server()
        elif self.sync == "artifactory":
            return self._artifactory_docker_to_server()
        elif self.sync == "gitlab-artifacts":
            return self._artifacts_docker_to_server()
    
    def _docker_registry_to_server(self):
        """Комбинация 1: docker-registry + server"""
        if self.use_compose:
            return self._render(self.DOCKER_REGISTRY_COMPOSE_TEMPLATE)
        else:
            return self._render(self.DOCKER_REGISTRY_SIMPLE_TEMPLATE)
    
    def _nexus_docker_to_server(self):
        """Комбинация 2: nexus + server"""
        if self.use_compose:
            return self._render(self.NEXUS_DOCKER_COMPOSE_TEMPLATE)
        else:
            return self._render(self.NEXUS_DOCKER_SIMPLE_TEMPLATE)
    
    def _artifactory_docker_to_server(self):
        """Комбинация 3: artifactory + server"""
        if self.use_compose:
            return self._render(self.ARTIFACTORY_DOCKER_COMPOSE_TEMPLATE)
        else:
            return self._render(self.ARTIFACTORY_DOCKER_SIMPLE_TEMPLATE)
    
    def _artifacts_docker_to_server(self):
        """Комбинация 4: gitlab-artifacts + server"""
        if self.use_compose:
            return self._render(self.ARTIFACTS_DOCKER_COMPOSE_TEMPLATE)
        else:
            return self._render(self.ARTIFACTS_DOCKER_SIMPLE_TEMPLATE)
    
    # ============ GITHUB RELEASE ============
    
    def _generate_github_release(self):
        """
        deploy=github → публикация артефактов (бинарников)
        НЕ Docker-образов!
        """
        if self.sync == "nexus":
            return self._render(self.NEXUS_TO_GITHUB_TEMPLATE)
        elif self.sync == "artifactory":
            return self._render(self.ARTIFACTORY_TO_GITHUB_TEMPLATE)
        elif self.sync == "gitlab-artifacts":
            return self._render(self.ARTIFACTS_TO_GITHUB_TEMPLATE)
        elif self.sync == "docker-registry":
            # Предупреждение: странная комбинация
            print("⚠️  WARNING: docker-registry + github — необычная комбинация!")
            return self._render(self.DOCKER_TO_GITHUB_WARNING_TEMPLATE)
    
    def _render(self, template_str: str) -> str:
        """Рендерит Jinja2 шаблон с параметрами из config (результата get_summary)"""
        
        # Получаем данные только из self.config (который равен результату get_summary())
        language = self.config.get('language', 'unknown')
        version = self.config.get('version', 'latest')
        base_image = self.config.get('base_image', 'alpine:latest')
        
        # Dockerfile info может быть None, если Dockerfile не существует
        dockerfile_info = self.config.get('dockerfile_info') or {}
        
        # Дополнительная информация из dockerfile_info
        base_images = dockerfile_info.get('base_images', [])
        final_image = dockerfile_info.get('final_image', base_image)
        is_multistage = dockerfile_info.get('is_multistage', False)
        
        # Artifact paths - может быть None
        artifact_paths = self.config.get('artifact_paths') or {}
        
        # Language info
        language_info = self.config.get('language_info', {})
        
        # Параметры для рендеринга (ТОЛЬКО данные из анализатора)
        params = {
            # Основные параметры языка
            "language": language,
            "version": version,
            "base_image": base_image,
            "language_info": language_info,
            
            # Параметры из dockerfile_info
            "base_images": base_images,
            "final_image": final_image,
            "is_multistage": is_multistage,
            
            # Параметры артефактов
            "artifact_path": artifact_paths.get('artifact_path', ''),
            "artifact_name": artifact_paths.get('artifact_name', ''),
            "build_command": artifact_paths.get('build_command', ''),
            "artifact_type": artifact_paths.get('artifact_type', ''),
            
            "dockerfile_exists": self.config.get('dockerfile_exists', False),
        }
        
        template = Template(template_str)
        return template.render(**params)
    
    # ============ ШАБЛОНЫ ============
    
    # --- Docker Registry → Server ---
    
    DOCKER_REGISTRY_SIMPLE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind

  script:
    - echo "🚀 Deploy from GitLab Container Registry"
    - docker login "$CI_REGISTRY" -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD"
    - docker pull "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA"

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - ssh "$SSH_USER@$SSH_HOST" "
        docker login $CI_REGISTRY -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD &&
        docker stop $CONTAINER_NAME || true &&
        docker rm $CONTAINER_NAME || true &&
        docker run -d --name $CONTAINER_NAME -p $DEPLOY_PORT:$DEPLOY_PORT $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
      "

    - echo "✅ Deployed from Docker Registry!"

  environment:
    name: production
    url: http://$SSH_HOST:$DEPLOY_PORT
  only:
    - main
  when: manual
  tags:
    - docker
"""

    DOCKER_REGISTRY_COMPOSE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind

  script:
    - echo "🚀 Deploy from GitLab Container Registry (compose)"
    - docker login "$CI_REGISTRY" -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD"

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - ssh "$SSH_USER@$SSH_HOST" "
        cd $REMOTE_COMPOSE_DIR &&
        docker login $CI_REGISTRY -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD &&
        docker compose pull &&
        docker compose up -d
      "

    - echo "✅ Deployed via docker-compose!"

  environment:
    name: production
    url: http://$SSH_HOST:$DEPLOY_PORT
  only:
    - main
  when: manual
  tags:
    - docker
"""

    # --- Nexus Docker → Server ---
    
    NEXUS_DOCKER_SIMPLE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind

  script:
    - echo "🚀 Deploy from Nexus Docker Registry"
    - docker login $NEXUS_DOCKER_REGISTRY -u $NEXUS_USER -p $NEXUS_PASSWORD
    - docker pull $NEXUS_DOCKER_REGISTRY/$CI_PROJECT_NAME:$CI_COMMIT_SHA

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - ssh "$SSH_USER@$SSH_HOST" "
        docker login $NEXUS_DOCKER_REGISTRY -u $NEXUS_USER -p $NEXUS_PASSWORD &&
        docker stop $CONTAINER_NAME || true &&
        docker rm $CONTAINER_NAME || true &&
        docker run -d --name $CONTAINER_NAME -p $DEPLOY_PORT:$DEPLOY_PORT $NEXUS_DOCKER_REGISTRY/$CI_PROJECT_NAME:$CI_COMMIT_SHA
      "

    - echo "✅ Deployed from Nexus Docker Registry!"

  environment:
    name: production
    url: http://$SSH_HOST:$DEPLOY_PORT
  only:
    - main
  when: manual
  tags:
    - docker
"""

    NEXUS_DOCKER_COMPOSE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind

  script:
    - echo "🚀 Deploy from Nexus Docker Registry (compose)"
    - docker login $NEXUS_DOCKER_REGISTRY -u $NEXUS_USER -p $NEXUS_PASSWORD

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - ssh "$SSH_USER@$SSH_HOST" "
        cd $REMOTE_COMPOSE_DIR &&
        docker login $NEXUS_DOCKER_REGISTRY -u $NEXUS_USER -p $NEXUS_PASSWORD &&
        docker compose pull &&
        docker compose up -d
      "

    - echo "✅ Deployed via docker-compose from Nexus!"

  environment:
    name: production
    url: http://$SSH_HOST:$DEPLOY_PORT
  only:
    - main
  when: manual
  tags:
    - docker
"""

    # --- Artifactory Docker → Server ---
    
    ARTIFACTORY_DOCKER_SIMPLE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind

  script:
    - echo "🚀 Deploy from Artifactory Docker Registry"
    - docker login $ARTIFACTORY_DOCKER_REGISTRY -u $ARTIFACTORY_USER -p $ARTIFACTORY_PASSWORD
    - docker pull $ARTIFACTORY_DOCKER_REGISTRY/$CI_PROJECT_NAME:$CI_COMMIT_SHA

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - ssh "$SSH_USER@$SSH_HOST" "
        docker login $ARTIFACTORY_DOCKER_REGISTRY -u $ARTIFACTORY_USER -p $ARTIFACTORY_PASSWORD &&
        docker stop $CONTAINER_NAME || true &&
        docker rm $CONTAINER_NAME || true &&
        docker run -d --name $CONTAINER_NAME -p $DEPLOY_PORT:$DEPLOY_PORT $ARTIFACTORY_DOCKER_REGISTRY/$CI_PROJECT_NAME:$CI_COMMIT_SHA
      "

    - echo "✅ Deployed from Artifactory Docker Registry!"

  environment:
    name: production
    url: http://$SSH_HOST:$DEPLOY_PORT
  only:
    - main
  when: manual
  tags:
    - docker
"""

    ARTIFACTORY_DOCKER_COMPOSE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind

  script:
    - echo "🚀 Deploy from Artifactory Docker Registry (compose)"
    - docker login $ARTIFACTORY_DOCKER_REGISTRY -u $ARTIFACTORY_USER -p $ARTIFACTORY_PASSWORD

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - ssh "$SSH_USER@$SSH_HOST" "
        cd $REMOTE_COMPOSE_DIR &&
        docker login $ARTIFACTORY_DOCKER_REGISTRY -u $ARTIFACTORY_USER -p $ARTIFACTORY_PASSWORD &&
        docker compose pull &&
        docker compose up -d
      "

    - echo "✅ Deployed via docker-compose from Artifactory!"

  environment:
    name: production
    url: http://$SSH_HOST:$DEPLOY_PORT
  only:
    - main
  when: manual
  tags:
    - docker
"""

    # --- GitLab Artifacts Docker → Server ---
    
    ARTIFACTS_DOCKER_SIMPLE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind
  dependencies:
    - build

  script:
    - echo "🚀 Deploy from GitLab Artifacts (Docker tar)"
    - docker load -i {{ artifact_name }}-image.tar
    - docker tag {{ artifact_name }}:$CI_COMMIT_SHA {{ artifact_name }}:latest

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - scp {{ artifact_name }}-image.tar $SSH_USER@$SSH_HOST:/tmp/
    - ssh "$SSH_USER@$SSH_HOST" "
        docker load -i /tmp/{{ artifact_name }}-image.tar &&
        docker stop $CONTAINER_NAME || true &&
        docker rm $CONTAINER_NAME || true &&
        docker run -d --name $CONTAINER_NAME -p $DEPLOY_PORT:$DEPLOY_PORT {{ artifact_name }}:$CI_COMMIT_SHA
      "

    - echo "✅ Deployed from artifacts!"

  environment:
    name: production
    url: http://$SSH_HOST:$DEPLOY_PORT
  only:
    - main
  when: manual
  tags:
    - docker
"""

    ARTIFACTS_DOCKER_COMPOSE_TEMPLATE = """# TODO: docker compose + artifacts (сложнее, редко используется)"""

    # --- GitHub Releases ---
    
    NEXUS_TO_GITHUB_TEMPLATE = """release_github:
  stage: release
  image: alpine:latest
  script:
    - apk add --no-cache curl jq
    
    - echo "⬇️  Downloading artifact from Nexus..."
    - curl -u $NEXUS_USER:$NEXUS_PASSWORD -o {{ artifact_name }} \\
        "$NEXUS_URL/repository/$NEXUS_REPOSITORY/$CI_PROJECT_NAME/$CI_COMMIT_TAG/{{ artifact_name }}"
    
    - echo "📦 Creating GitHub Release..."
    - |
      RELEASE_ID=$(curl -X POST \\
        -H "Authorization: token $GITHUB_TOKEN" \\
        https://api.github.com/repos/$GITHUB_REPO/releases \\
        -d '{"tag_name": "'$CI_COMMIT_TAG'", "name": "Release '$CI_COMMIT_TAG'", "body": "Automated release"}' \\
        | jq -r '.id')
    
    - echo "⬆️  Uploading artifact to GitHub..."
    - |
      curl -X POST \\
        -H "Authorization: token $GITHUB_TOKEN" \\
        -H "Content-Type: application/octet-stream" \\
        --data-binary @{{ artifact_name }} \\
        "https://uploads.github.com/repos/$GITHUB_REPO/releases/$RELEASE_ID/assets?name={{ artifact_name }}"
    
    - echo "✅ GitHub Release published!"
  
  only:
    - tags
  when: manual
  tags:
    - docker
"""

    ARTIFACTORY_TO_GITHUB_TEMPLATE = """release_github:
  stage: release
  image: alpine:latest
  script:
    - apk add --no-cache curl jq
    
    - echo "⬇️  Downloading artifact from Artifactory..."
    - curl -u $ARTIFACTORY_USER:$ARTIFACTORY_PASSWORD -o {{ artifact_name }} \\
        "$ARTIFACTORY_URL/$ARTIFACTORY_REPOSITORY/$CI_PROJECT_NAME/$CI_COMMIT_TAG/{{ artifact_name }}"
    
    - echo "📦 Creating GitHub Release..."
    - |
      RELEASE_ID=$(curl -X POST \\
        -H "Authorization: token $GITHUB_TOKEN" \\
        https://api.github.com/repos/$GITHUB_REPO/releases \\
        -d '{"tag_name": "'$CI_COMMIT_TAG'", "name": "Release '$CI_COMMIT_TAG'"}' \\
        | jq -r '.id')
    
    - echo "⬆️  Uploading to GitHub..."
    - |
      curl -X POST \\
        -H "Authorization: token $GITHUB_TOKEN" \\
        -H "Content-Type: application/octet-stream" \\
        --data-binary @{{ artifact_name }} \\
        "https://uploads.github.com/repos/$GITHUB_REPO/releases/$RELEASE_ID/assets?name={{ artifact_name }}"
    
    - echo "✅ GitHub Release published!"
  
  only:
    - tags
  when: manual
  tags:
    - docker
"""

    ARTIFACTS_TO_GITHUB_TEMPLATE = """release_github:
  stage: release
  image: alpine:latest
  dependencies:
    - build
  script:
    - apk add --no-cache curl jq
    
    - echo "📦 Creating GitHub Release..."
    - |
      RELEASE_ID=$(curl -X POST \\
        -H "Authorization: token $GITHUB_TOKEN" \\
        https://api.github.com/repos/$GITHUB_REPO/releases \\
        -d '{"tag_name": "'$CI_COMMIT_TAG'", "name": "Release '$CI_COMMIT_TAG'", "body": "Automated release from GitLab CI"}' \\
        | jq -r '.id')
    
    - echo "⬆️  Uploading artifact to GitHub..."
    - |
      curl -X POST \\
        -H "Authorization: token $GITHUB_TOKEN" \\
        -H "Content-Type: application/octet-stream" \\
        --data-binary @{{ artifact_name }} \\
        "https://uploads.github.com/repos/$GITHUB_REPO/releases/$RELEASE_ID/assets?name={{ artifact_name }}"
    
    - echo "✅ GitHub Release published!"
  
  only:
    - tags
  when: manual
  tags:
    - docker
"""

    DOCKER_TO_GITHUB_WARNING_TEMPLATE = """# ⚠️  WARNING: docker-registry + github-releases — необычная комбинация!
# Рекомендуется использовать --sync nexus/artifactory/gitlab-artifacts
# Если всё же нужно, образ будет сохранён как .tar файл
"""
