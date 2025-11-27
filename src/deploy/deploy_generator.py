# src/deploy_generator.py

from jinja2 import Template


class DeployStageGenerator:
    """Генератор deploy-стейджа на основе комбинации sync + deploy"""

    def __init__(self, config: dict, sync: str, deploy: str):
        """
        config: summary из ProjectAnalyzer
        sync: "docker-registry", "nexus", "artifactory", "gitlab-artifacts"
        deploy: "server", "github"
        """
        self.config = config
        self.sync = sync
        self.deploy = deploy

    def generate(self) -> str:
        print(f"  → Генерирую DEPLOY stage ({self.sync} → {self.deploy})")

        # Роутинг по комбинациям
        if self.deploy == "server":
            return self._generate_server_deploy()
        elif self.deploy == "github":
            return self._generate_github_release()
        else:
            raise ValueError(f"Unknown deploy target: {self.deploy}")

    # ============ SERVER DEPLOY ============

    def _generate_server_deploy(self):
        """deploy=server → всегда Docker (compose или run)"""
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
            print("     ⚠️  docker-registry + github — необычная комбинация!")
            return self._render(self.DOCKER_TO_GITHUB_WARNING_TEMPLATE)

    def _render(self, template_str: str) -> str:
        """Рендерит Jinja2 шаблон с параметрами из config"""

        # Получаем данные
        language = self.config.get("language", "unknown")
        version = self.config.get("version", "latest")
        services = self.config.get("services", [])
        is_monorepo = self.config.get("is_monorepo", False)
        artifact_paths = self.config.get("artifact_paths") or {}
        artifact_name = artifact_paths.get("artifact_name", "app")

        # Для single service используем имя проекта
        project_name = self.config.get("language", "app")

        # Обработка env_summary
        env_summary = self.config.get("env_summary", {})
        env_vars = []
        if env_summary.get("variables"):
            for var_name, var_info in env_summary["variables"].items():
                # Берём только runtime-переменные
                if var_info["type"] in [
                    "secret",
                    "database",
                    "url",
                    "runtime_config",
                    "config",
                    "port",
                    "general",
                ]:
                    env_vars.append(var_name)

        # Параметры для рендеринга
        params = {
            "language": language,
            "version": version,
            "services": services,
            "is_monorepo": is_monorepo,
            "artifact_name": artifact_name,
            "project_name": project_name,
            "env_vars": env_vars,
        }
        template = Template(template_str)
        return template.render(**params)

    # ============ ШАБЛОНЫ ============

    # --- Docker Registry → Server ---

    DOCKER_REGISTRY_COMPOSE_TEMPLATE = """deploy_production:
  stage: deploy
  image: alpine:latest
  before_script:
    - echo "================================================"
    - echo "DEPLOY STAGE - Docker Registry → Server"
    - echo "================================================"
    - apk add --no-cache openssh-client docker-cli docker-compose
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_rsa
    - chmod 600 ~/.ssh/id_rsa
    - ssh-keyscan -H $SSH_HOST >> ~/.ssh/known_hosts 2>/dev/null
  script:
    - echo ""
    - echo "🐳 Generating docker-compose.prod.yml..."
    - |
      cat > docker-compose.prod.yml << 'COMPOSE_EOF'
      version: "3.9"
      services:
{% if is_monorepo %}
{% for service in services %}
        {{ service.name }}:
          image: ${CI_REGISTRY_IMAGE}/{{ service.name }}:${CI_COMMIT_SHA}
          restart: unless-stopped
{% if env_vars %}
          environment:
{% for var_name in env_vars %}
            - {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
{% endfor %}
{% else %}
        app:
          image: ${CI_REGISTRY_IMAGE}:${CI_COMMIT_SHA}
          restart: unless-stopped
          ports:
            - "3000:3000"
{% if env_vars %}
          environment:
{% for var_name in env_vars %}
            - {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
{% endif %}
      COMPOSE_EOF

    - echo ""
    - echo "📤 Uploading docker-compose.prod.yml to server..."
    - scp -P ${SSH_PORT:-22} docker-compose.prod.yml $SSH_USER@$SSH_HOST:/app/docker-compose.yml

    - echo ""
    - echo "📝 Creating .env file..."
    - |
      cat > .env.deploy << 'ENV_EOF'
      CI_REGISTRY_IMAGE=$CI_REGISTRY_IMAGE
      CI_COMMIT_SHA=$CI_COMMIT_SHA
{% if env_vars %}
      # Runtime environment variables
{% for var_name in env_vars %}
      {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
      ENV_EOF
    - scp -P ${SSH_PORT:-22} .env.deploy $SSH_USER@$SSH_HOST:/app/.env

    - echo ""
    - echo "🚀 Deploying on server..."
    - |
      ssh -p ${SSH_PORT:-22} $SSH_USER@$SSH_HOST << 'REMOTE_SCRIPT'
      cd /app
      export $(cat .env | xargs)
      docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
      docker-compose pull
      docker-compose up -d
      docker image prune -f
      echo "✅ Deploy complete!"
      REMOTE_SCRIPT

  environment:
    name: production
    url: http://$SSH_HOST
  only:
    - main
  when: manual
  tags:
    - docker
"""

    NEXUS_DOCKER_COMPOSE_TEMPLATE = """deploy_production:
  stage: deploy
  image: alpine:latest
  before_script:
    - echo "================================================"
    - echo "DEPLOY STAGE - Nexus Docker Registry → Server"
    - echo "================================================"
    - apk add --no-cache openssh-client docker-cli docker-compose
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_rsa
    - chmod 600 ~/.ssh/id_rsa
    - ssh-keyscan -H $SSH_HOST >> ~/.ssh/known_hosts 2>/dev/null
  script:
    - echo ""
    - echo "🐳 Generating docker-compose.prod.yml..."
    - |
      cat > docker-compose.prod.yml << 'COMPOSE_EOF'
      version: "3.9"
      services:
{% if is_monorepo %}
{% for service in services %}
        {{ service.name }}:
          image: ${NEXUS_DOCKER_REGISTRY}/{{ service.name }}:${CI_COMMIT_SHA}
          restart: unless-stopped
{% if env_vars %}
          environment:
{% for var_name in env_vars %}
            - {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
{% endfor %}
{% else %}
        app:
          image: ${NEXUS_DOCKER_REGISTRY}/{{ project_name }}:${CI_COMMIT_SHA}
          restart: unless-stopped
          ports:
            - "3000:3000"
{% if env_vars %}
          environment:
{% for var_name in env_vars %}
            - {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
{% endif %}
      COMPOSE_EOF

    - echo ""
    - echo "📤 Uploading to server..."
    - scp -P ${SSH_PORT:-22} docker-compose.prod.yml $SSH_USER@$SSH_HOST:/app/docker-compose.yml

    - |
      cat > .env.deploy << 'ENV_EOF'
      NEXUS_DOCKER_REGISTRY=$NEXUS_DOCKER_REGISTRY
      CI_COMMIT_SHA=$CI_COMMIT_SHA
      NEXUS_USER=$NEXUS_USER
      NEXUS_PASSWORD=$NEXUS_PASSWORD
{% if env_vars %}
      # Runtime environment variables
{% for var_name in env_vars %}
      {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
      ENV_EOF
    - scp -P ${SSH_PORT:-22} .env.deploy $SSH_USER@$SSH_HOST:/app/.env

    - echo ""
    - echo "🚀 Deploying..."
    - |
      ssh -p ${SSH_PORT:-22} $SSH_USER@$SSH_HOST << 'REMOTE_SCRIPT'
      cd /app
      export $(cat .env | xargs)
      docker login -u $NEXUS_USER -p $NEXUS_PASSWORD $NEXUS_DOCKER_REGISTRY
      docker-compose pull
      docker-compose up -d
      docker image prune -f
      echo "✅ Deploy complete!"
      REMOTE_SCRIPT

  environment:
    name: production
    url: http://$SSH_HOST
  only:
    - main
  when: manual
  tags:
    - docker

"""

    ARTIFACTORY_DOCKER_COMPOSE_TEMPLATE = """deploy_production:
  stage: deploy
  image: alpine:latest
  before_script:
    - echo "================================================"
    - echo "DEPLOY STAGE - Artifactory Docker Registry → Server"
    - echo "================================================"
    - apk add --no-cache openssh-client docker-cli docker-compose
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_rsa
    - chmod 600 ~/.ssh
    - ssh-keyscan -H $SSH_HOST >> ~/.ssh/known_hosts 2>/dev/null
  script:
    - echo ""
    - echo "🐳 Generating docker-compose.prod.yml..."
    - |
      cat > docker-compose.prod.yml << 'COMPOSE_EOF'
      version: "3.9"
      services:
{% if is_monorepo %}
{% for service in services %}
        {{ service.name }}:
          image: ${ARTIFACTORY_DOCKER_REGISTRY}/{{ service.name }}:${CI_COMMIT_SHA}
          restart: unless-stopped
{% if env_vars %}
          environment:
{% for var_name in env_vars %}
            - {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
{% endfor %}
{% else %}
        app:
          image: ${ARTIFACTORY_DOCKER_REGISTRY}/{{ project_name }}:${CI_COMMIT_SHA}
          restart: unless-stopped
          ports:
            - "3000:3000"
{% if env_vars %}
          environment:
{% for var_name in env_vars %}
            - {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
{% endif %}
      COMPOSE_EOF

    - echo ""
    - echo "📤 Uploading to server..."
    - scp -P ${SSH_PORT:-22} docker-compose.prod.yml $SSH_USER@$SSH_HOST:/app/docker-compose.yml

    - |
      cat > .env.deploy << 'ENV_EOF'
      ARTIFACTORY_DOCKER_REGISTRY=$ARTIFACTORY_DOCKER_REGISTRY
      CI_COMMIT_SHA=$CI_COMMIT_SHA
      ARTIFACTORY_USER=$ARTIFACTORY_USER
      ARTIFACTORY_PASSWORD=$ARTIFACTORY_PASSWORD
{% if env_vars %}
      # Runtime environment variables
{% for var_name in env_vars %}
      {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
      ENV_EOF
    - scp -P ${SSH_PORT:-22} .env.deploy $SSH_USER@$SSH_HOST:/app/.env

    - echo ""
    - echo "🚀 Deploying..."
    - |
      ssh -p ${SSH_PORT:-22} $SSH_USER@$SSH_HOST << 'REMOTE_SCRIPT'
      cd /app
      export $(cat .env | xargs)
      docker login -u $ARTIFACTORY_USER -p $ARTIFACTORY_PASSWORD $ARTIFACTORY_DOCKER_REGISTRY
      docker-compose pull
      docker-compose up -d
      docker image prune -f
      echo "✅ Deploy complete!"
      REMOTE_SCRIPT

  environment:
    name: production
    url: http://$SSH_HOST
  only:
    - main
  when: manual
  tags:
    - docker

"""
    ARTIFACTS_DOCKER_COMPOSE_TEMPLATE = """deploy_production:
  stage: deploy
  image: alpine:latest
  dependencies:
    - build
  before_script:
    - echo "================================================"
    - echo "DEPLOY STAGE - GitLab Artifacts → Server"
    - echo "================================================"
    - apk add --no-cache openssh-client docker-cli docker-compose
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_rsa
    - chmod 600 ~/.ssh
    - ssh-keyscan -H $SSH_HOST >> ~/.ssh/known_hosts 2>/dev/null
  script:
    - echo ""
    - echo "📦 Loading Docker images from artifacts..."
{% if is_monorepo %}
{% for service in services %}
    - docker load -i {{ service.name }}-image.tar
{% endfor %}
{% else %}
    - docker load -i {{ project_name }}-image.tar
{% endif %}

    - echo ""
    - echo "🐳 Generating docker-compose.prod.yml..."
    - |
      cat > docker-compose.prod.yml << 'COMPOSE_EOF'
      version: "3.9"
      services:
{% if is_monorepo %}
{% for service in services %}
        {{ service.name }}:
          image: {{ service.name }}:${CI_COMMIT_SHA}
          restart: unless-stopped
{% if env_vars %}
          environment:
{% for var_name in env_vars %}
            - {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
{% endfor %}
{% else %}
        app:
          image: {{ project_name }}:${CI_COMMIT_SHA}
          restart: unless-stopped
          ports:
            - "3000:3000"
{% if env_vars %}
          environment:
{% for var_name in env_vars %}
            - {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
{% endif %}
      COMPOSE_EOF

    - echo ""
    - echo "📤 Uploading to server..."
    - scp -P ${SSH_PORT:-22} docker-compose.prod.yml $SSH_USER@$SSH_HOST:/app/docker-compose.yml
{% if is_monorepo %}
{% for service in services %}
    - scp -P ${SSH_PORT:-22} {{ service.name }}-image.tar $SSH_USER@$SSH_HOST:/tmp/
{% endfor %}
{% else %}
    - scp -P ${SSH_PORT:-22} {{ project_name }}-image.tar $SSH_USER@$SSH_HOST:/tmp/
{% endif %}

    - echo ""
    - echo "📝 Creating .env file..."
    - |
      cat > .env.deploy << 'ENV_EOF'
      CI_COMMIT_SHA=$CI_COMMIT_SHA
{% if env_vars %}
      # Runtime environment variables
{% for var_name in env_vars %}
      {{ var_name }}=${{ var_name }}
{% endfor %}
{% endif %}
      ENV_EOF
    - scp -P ${SSH_PORT:-22} .env.deploy $SSH_USER@$SSH_HOST:/app/.env

    - echo ""
    - echo "🚀 Deploying..."
    - |
      ssh -p ${SSH_PORT:-22} $SSH_USER@$SSH_HOST << 'REMOTE_SCRIPT'
      cd /app
{% if is_monorepo %}
{% for service in services %}
      docker load -i /tmp/{{ service.name }}-image.tar
{% endfor %}
{% else %}
      docker load -i /tmp/{{ project_name }}-image.tar
{% endif %}
      export $(cat .env | xargs)
      docker-compose up -d
      docker image prune -f
      echo "✅ Deploy complete!"
      REMOTE_SCRIPT

  environment:
    name: production
    url: http://$SSH_HOST
  only:
    - main
  when: manual
  tags:
    - docker
"""

    # --- GitHub Releases ---

    NEXUS_TO_GITHUB_TEMPLATE = """release_github:
  stage: deploy
  image: alpine:latest
  before_script:
    - echo "================================================"
    - echo "RELEASE STAGE - Nexus → GitHub"
    - echo "================================================"
    - apk add --no-cache curl jq github-cli
  script:
    - echo ""
    - echo "⬇️  Downloading artifact from Nexus..."
    - curl -u $NEXUS_USER:$NEXUS_PASSWORD -o {{ artifact_name }} \\
        "$NEXUS_URL/repository/$NEXUS_REPOSITORY/$CI_PROJECT_NAME/$CI_COMMIT_TAG/{{ artifact_name }}"

    - echo ""
    - echo "📦 Creating GitHub Release..."
    - gh release create $CI_COMMIT_TAG \\
        --repo $GITHUB_REPO \\
        --title "Release $CI_COMMIT_TAG" \\
        --notes "Automated release from GitLab CI/CD" \\
        {{ artifact_name }}

    - echo ""
    - echo "✅ GitHub Release published!"

  only:
    - tags
  when: manual
  tags:
    - docker
"""

    ARTIFACTORY_TO_GITHUB_TEMPLATE = """release_github:
  stage: deploy
  image: alpine:latest
  before_script:
    - echo "================================================"
    - echo "RELEASE STAGE - Artifactory → GitHub"
    - echo "================================================"
    - apk add --no-cache curl jq github-cli
  script:
    - echo ""
    - echo "⬇️  Downloading artifact from Artifactory..."
    - curl -u $ARTIFACTORY_USER:$ARTIFACTORY_PASSWORD -o {{ artifact_name }} \\
        "$ARTIFACTORY_URL/$ARTIFACTORY_REPOSITORY/$CI_PROJECT_NAME/$CI_COMMIT_TAG/{{ artifact_name }}"

    - echo ""
    - echo "📦 Creating GitHub Release..."
    - gh release create $CI_COMMIT_TAG \\
        --repo $GITHUB_REPO \\
        --title "Release $CI_COMMIT_TAG" \\
        --notes "Automated release from GitLab CI/CD" \\
        {{ artifact_name }}

    - echo ""
    - echo "✅ GitHub Release published!"

  only:
    - tags
  when: manual
  tags:
    - docker
"""

    ARTIFACTS_TO_GITHUB_TEMPLATE = """release_github:
  stage: deploy
  image: alpine:latest
  dependencies:
    - build
  before_script:
    - echo "================================================"
    - echo "RELEASE STAGE - GitLab Artifacts → GitHub"
    - echo "================================================"
    - apk add --no-cache github-cli
  script:
    - echo ""
    - echo "📦 Creating GitHub Release..."
    - gh release create $CI_COMMIT_TAG \\
        --repo $GITHUB_REPO \\
        --title "Release $CI_COMMIT_TAG" \\
        --notes "Automated release from GitLab CI/CD" \\
        {{ artifact_name }}

    - echo ""
    - echo "✅ GitHub Release published!"

  only:
    - tags
  when: manual
  tags:
    - docker
"""

    DOCKER_TO_GITHUB_WARNING_TEMPLATE = """# ⚠️  WARNING: docker-registry + github-releases — необычная комбинация!
# Docker образы обычно не публикуются в GitHub Releases
# Рекомендуется:
#   - Для артефактов: --sync nexus/artifactory/gitlab-artifacts
#   - Для Docker: держать в Docker Registry
"""

