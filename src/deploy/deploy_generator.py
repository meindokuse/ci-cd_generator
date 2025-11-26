from jinja2 import Template


class DeployStageGenerator:
    """
    Отвечает за генерацию deploy-джобы для .gitlab-ci.yml
    """

    SIMPLE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:24-cli
  services:
    - docker:24-dind

  script:
    - echo "🚀 Simple Docker deploy"
    - docker login "$CI_REGISTRY" -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD"
    - docker pull "$CI_REGISTRY_IMAGE:{{ image_tag }}"

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - ssh "$SSH_USER@$SSH_HOST" "
        docker stop app || true &&
        docker rm app || true &&
        docker run -d --name app -p {{ port }}:{{ port }} $CI_REGISTRY_IMAGE:{{ image_tag }}
      "

    - echo "✅ Deployment complete!"

  environment:
    name: production
    url: http://$SSH_HOST:{{ port }}
  only:
    - main
  when: manual
"""

    COMPOSE_TEMPLATE = """deploy_production:
  stage: deploy
  image: docker:latest
  services:
    - docker:dind

  script:
    - echo "🚀 Docker Compose deploy"
    - docker login "$CI_REGISTRY" -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD"

    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts

    - ssh "$SSH_USER@$SSH_HOST" "
        cd $REMOTE_COMPOSE_DIR &&
        docker compose pull &&
        docker compose up -d
      "

    - echo "✅ Deployment complete!"

  environment:
    name: production
    url: http://$SSH_HOST:{{ port }}
  only:
    - main
  when: manual
"""

    def __init__(self, config: dict, use_compose: bool = False):
        """
        config — summary из ProjectAnalyzer (там есть port)
        use_compose — True, если найден docker-compose.yml
        """
        self.config = config
        self.use_compose = use_compose

    def generate(self) -> str:
        port = self.config.get("port", 3000)
        image_tag = "$CI_COMMIT_SHA"  # договариваетесь с командой

        if self.use_compose:
            template = Template(self.COMPOSE_TEMPLATE)
        else:
            template = Template(self.SIMPLE_TEMPLATE)

        return template.render(port=port, image_tag=image_tag)

    def get_output_string(self) -> str:
        return self.generate()
