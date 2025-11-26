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
    - docker pull "$CI_REGISTRY_IMAGE:{{ image_tag }}"

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - ssh "$SSH_USER@$SSH_HOST" "
        docker login $CI_REGISTRY -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD &&
        docker stop app || true &&
        docker rm app || true &&
        docker run -d --name app -p {{ port }}:{{ port }} $CI_REGISTRY_IMAGE:{{ image_tag }}
      "

    - echo "✅ Deployed from Docker Registry!"

  environment:
    name: production
    url: http://$SSH_HOST:{{ port }}
  only:
    - main
  when: manual
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
    url: http://$SSH_HOST:{{ port }}
  only:
    - main
  when: manual
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
    - docker pull $NEXUS_DOCKER_REGISTRY/{{ project_name }}:{{ image_tag }}

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - ssh "$SSH_USER@$SSH_HOST" "
        docker login $NEXUS_DOCKER_REGISTRY -u $NEXUS_USER -p $NEXUS_PASSWORD &&
        docker stop app || true &&
        docker rm app || true &&
        docker run -d --name app -p {{ port }}:{{ port }} $NEXUS_DOCKER_REGISTRY/{{ project_name }}:{{ image_tag }}
      "

    - echo "✅ Deployed from Nexus Docker Registry!"

  environment:
    name: production
    url: http://$SSH_HOST:{{ port }}
  only:
    - main
  when: manual
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
    url: http://$SSH_HOST:{{ port }}
  only:
    - main
  when: manual
"""

    # --- Artifactory Docker → Server (аналогично Nexus) ---
    
    ARTIFACTORY_DOCKER_SIMPLE_TEMPLATE = NEXUS_DOCKER_SIMPLE_TEMPLATE.replace("Nexus", "Artifactory").replace("$NEXUS", "$ARTIFACTORY")
    ARTIFACTORY_DOCKER_COMPOSE_TEMPLATE = NEXUS_DOCKER_COMPOSE_TEMPLATE.replace("Nexus", "Artifactory").replace("$NEXUS", "$ARTIFACTORY")

    # --- GitLab Artifacts Docker → Server ---
    
    ARTIFACTS_DOCKER_SIMPLE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind
  dependencies:
    - build  # получаем Docker tar из artifacts

  script:
    - echo "🚀 Deploy from GitLab Artifacts (Docker tar)"
    - docker load -i {{ project_name }}-image.tar
    - docker tag {{ project_name }}:{{ image_tag }} {{ project_name }}:latest

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - scp {{ project_name }}-image.tar $SSH_USER@$SSH_HOST:/tmp/
    - ssh "$SSH_USER@$SSH_HOST" "
        docker load -i /tmp/{{ project_name }}-image.tar &&
        docker stop app || true &&
        docker rm app || true &&
        docker run -d --name app -p {{ port }}:{{ port }} {{ project_name }}:{{ image_tag }}
      "

    - echo "✅ Deployed from artifacts!"

  environment:
    name: production
    url: http://$SSH_HOST:{{ port }}
  only:
    - main
  when: manual
"""

    ARTIFACTS_DOCKER_COMPOSE_TEMPLATE = """# TODO: docker compose + artifacts (сложнее, редко используется)"""

    # --- GitHub Releases ---
    
    NEXUS_TO_GITHUB_TEMPLATE = """release_github:
  stage: release
  image: alpine:latest
  script:
    - apk add --no-cache curl jq
    
    - echo "⬇️  Downloading from Nexus..."
    - curl -u $NEXUS_USER:$NEXUS_PASSWORD -o app-linux-amd64 \\
        http://nexus.local:8081/repository/raw-releases/{{ project_name }}/$CI_COMMIT_TAG/app-linux-amd64
    
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
        --data-binary @app-linux-amd64 \\
        "https://uploads.github.com/repos/$GITHUB_REPO/releases/$RELEASE_ID/assets?name=app-linux-amd64"
    
    - echo "✅ GitHub Release published!"
  
  only:
    - tags
"""

    ARTIFACTORY_TO_GITHUB_TEMPLATE = NEXUS_TO_GITHUB_TEMPLATE.replace("Nexus", "Artifactory").replace("nexus", "artifactory")

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
        -d '{"tag_name": "'$CI_COMMIT_TAG'", "name": "Release '$CI_COMMIT_TAG'"}' \\
        | jq -r '.id')
    
    - echo "⬆️  Uploading from artifacts..."
    - |
      for binary in app-*; do
        curl -X POST \\
          -H "Authorization: token $GITHUB_TOKEN" \\
          -H "Content-Type: application/octet-stream" \\
          --data-binary @$binary \\
          "https://uploads.github.com/repos/$GITHUB_REPO/releases/$RELEASE_ID/assets?name=$binary"
      done
    
    - echo "✅ GitHub Release published!"
  
  only:
    - tags
"""

    DOCKER_TO_GITHUB_WARNING_TEMPLATE = """# ⚠️  WARNING: docker-registry + github-releases — необычная комбинация!
# Рекомендуется использовать --sync nexus/artifactory/gitlab-artifacts
# Если всё же нужно, образ будет сохранён как .tar файл
"""

    # ============ HELPERS ============
    
    def _render(self, template_str: str) -> str:
        """Рендерит Jinja2 шаблон с параметрами"""
        template = Template(template_str)
        return template.render(
            port=self.config.get("port", 3000),
            image_tag="$CI_COMMIT_SHA",
            project_name=self.config.get("project_name", "app")
        )
    
    def get_output_string(self) -> str:
        return self.generate()
