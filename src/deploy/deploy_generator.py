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
        # Всегда генерируем compose, так как у нас есть services
        self.use_compose = True

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
        deploy=server → всегда Docker (compose)
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
        return self._render(self.DOCKER_REGISTRY_COMPOSE_TEMPLATE)

    def _nexus_docker_to_server(self):
        """Комбинация 2: nexus + server"""
        return self._render(self.NEXUS_DOCKER_COMPOSE_TEMPLATE)

    def _artifactory_docker_to_server(self):
        """Комбинация 3: artifactory + server"""
        return self._render(self.ARTIFACTORY_DOCKER_COMPOSE_TEMPLATE)

    def _artifacts_docker_to_server(self):
        """Комбинация 4: gitlab-artifacts + server"""
        return self._render(self.ARTIFACTS_DOCKER_COMPOSE_TEMPLATE)

    # ============ GITHUB RELEASE ============

    def _generate_github_release(self):
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

        # Получаем все данные из self.config (результат get_summary)
        language = self.config.get("language", "unknown")
        version = self.config.get("version", "latest")
        base_image = self.config.get("base_image", "alpine:latest")

        # Dockerfile info может быть None
        dockerfile_info = self.config.get("dockerfile_info") or {}
        base_images = dockerfile_info.get("base_images", [])
        final_image = dockerfile_info.get("final_image", base_image)
        is_multistage = dockerfile_info.get("is_multistage", False)

        # Docker Compose info
        docker_compose_exists = self.config.get("docker_compose_exists", False)
        docker_compose_info = self.config.get("docker_compose_info")

        # Информация о сервисах
        services = self.config.get("services", [])

        #   пример +- как выгляит это структура    "services = [
        #     {'name': 'frontend', 'path': './frontend'},
        #     {'name': 'backend', 'path': './backend'},
        #     {'name': 'bot', 'path': './bot'},
        # ]"

        # Артефакты
        artifact_paths = self.config.get("artifact_paths") or {}
        artifact_path = artifact_paths.get("artifact_path", "")
        artifact_name = artifact_paths.get("artifact_name", "")
        build_command = artifact_paths.get("build_command", "")
        artifact_type = artifact_paths.get("artifact_type", "")

        # Language info
        language_info = self.config.get("language_info", {})

        # Прочие поля
        is_monorepo = self.config.get("is_monorepo", False)
        dockerfile_exists = self.config.get("dockerfile_exists", False)

        # Параметры для рендеринга (все поля из анализатора)
        params = {
            # Основные параметры языка
            "language": language,
            "version": version,
            "base_image": base_image,
            "language_info": language_info,
            # Dockerfile info
            "base_images": base_images,
            "final_image": final_image,
            "is_multistage": is_multistage,
            "dockerfile_exists": dockerfile_exists,
            # Docker Compose info
            "docker_compose_exists": docker_compose_exists,
            "docker_compose_info": docker_compose_info,
            # Информация о сервисах
            "services": services,
            # Артефакты
            "artifact_path": artifact_path,
            "artifact_name": artifact_name,
            "build_command": build_command,
            "artifact_type": artifact_type,
            # Дополнительные поля
            "is_monorepo": is_monorepo,
        }

        template = Template(template_str)
        return template.render(**params)

    # ============ ШАБЛОНЫ ============

    # --- Docker Registry → Server ---

    DOCKER_REGISTRY_COMPOSE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind

  script:
    - echo "🚀 Deploy from GitLab Container Registry (compose)"
    - docker login "$CI_REGISTRY" -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD"

    # Подготовка SSH
    - apk add --no-cache openssh-client
    - eval $(ssh-agent -s)
    - echo "$SSH_PRIVATE_KEY" | tr -d '\r' | ssh-add -
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    # Генерация docker-compose.yml
    - |
      cat > docker-compose.yml << EOF
      version: '3.9'
      services:
      {% if is_monorepo %}
        {% for service in services %}
        {{ service.name }}:
          image: $CI_REGISTRY_IMAGE:{{ service.name }}-$CI_COMMIT_SHA
          build: {{ service.path }}
        {% endfor %}
      {% else %}
        app:
          image: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
          build: .
      {% endif %}
      EOF

    # Передача compose-файла на сервер
    - scp docker-compose.yml $SSH_USER@$SSH_HOST:$REMOTE_COMPOSE_DIR/
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

    NEXUS_DOCKER_COMPOSE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind

  script:
    - echo "🚀 Deploy from Nexus Docker Registry (compose)"
    - docker login $NEXUS_DOCKER_REGISTRY -u $NEXUS_USER -p $NEXUS_PASSWORD

    # Подготовка SSH
    - apk add --no-cache openssh-client
    - eval $(ssh-agent -s)
    - echo "$SSH_PRIVATE_KEY" | tr -d '\r' | ssh-add -
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    # Генерация docker-compose.yml
    - |
      cat > docker-compose.yml << EOF
      version: '3.9'
      services:
      {% if is_monorepo %}
        {% for service in services %}
        {{ service.name }}:
          image: $NEXUS_DOCKER_REGISTRY/{{ service.name }}:$CI_COMMIT_SHA
          build: {{ service.path }}
        {% endfor %}
      {% else %}
        app:
          image: $NEXUS_DOCKER_REGISTRY/$CI_PROJECT_NAME:$CI_COMMIT_SHA
          build: .
      {% endif %}
      EOF

    # Передача compose-файла на сервер
    - scp docker-compose.yml $SSH_USER@$SSH_HOST:$REMOTE_COMPOSE_DIR/
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

    ARTIFACTORY_DOCKER_COMPOSE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind

  script:
    - echo "🚀 Deploy from Artifactory Docker Registry (compose)"
    - docker login $ARTIFACTORY_DOCKER_REGISTRY -u $ARTIFACTORY_USER -p $ARTIFACTORY_PASSWORD

    # Подготовка SSH
    - apk add --no-cache openssh-client
    - eval $(ssh-agent -s)
    - echo "$SSH_PRIVATE_KEY" | tr -d '\r' | ssh-add -
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    # Генерация docker-compose.yml
    - |
      cat > docker-compose.yml << EOF
      version: '3.9'
      services:
      {% if is_monorepo %}
        {% for service in services %}
        {{ service.name }}:
          image: $ARTIFACTORY_DOCKER_REGISTRY/{{ service.name }}:$CI_COMMIT_SHA
          build: {{ service.path }}
        {% endfor %}
      {% else %}
        app:
          image: $ARTIFACTORY_DOCKER_REGISTRY/$CI_PROJECT_NAME:$CI_COMMIT_SHA
          build: .
      {% endif %}
      EOF

    # Передача compose-файла на сервер
    - scp docker-compose.yml $SSH_USER@$SSH_HOST:$REMOTE_COMPOSE_DIR/
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

    ARTIFACTS_DOCKER_COMPOSE_TEMPLATE = """deploy_production:
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

    # Подготовка SSH
    - apk add --no-cache openssh-client
    - eval $(ssh-agent -s)
    - echo "$SSH_PRIVATE_KEY" | tr -d '\r' | ssh-add -
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    # Генерация docker-compose.yml
    - |
      cat > docker-compose.yml << EOF
      version: '3.9'
      services:
      {% if is_monorepo %}
        {% for service in services %}
        {{ service.name }}:
          image: {{ service.name }}:$CI_COMMIT_SHA
          build: {{ service.path }}
        {% endfor %}
      {% else %}
        app:
          image: {{ artifact_name }}:$CI_COMMIT_SHA
          build: .
      {% endif %}
      EOF

    # Передача compose-файла на сервер
    - scp docker-compose.yml $SSH_USER@$SSH_HOST:$REMOTE_COMPOSE_DIR/
    - scp {{ artifact_name }}-image.tar $SSH_USER@$SSH_HOST:/tmp/
    - ssh "$SSH_USER@$SSH_HOST" "
        cd $REMOTE_COMPOSE_DIR &&
        docker load -i /tmp/{{ artifact_name }}-image.tar &&
        docker compose up -d
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
