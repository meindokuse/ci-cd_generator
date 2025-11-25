# build_generator.py

from typing import Dict
from jinja2 import Template


class BuildStageGenerator:
    """Генератор build stage для GitLab CI/CD"""

    BUILD_TEMPLATE = """build:
  stage: build
  image: docker:24-cli
  services:
    - docker:24-dind
  variables:
    DOCKER_DRIVER: overlay2
    DOCKER_TLS_CERTDIR: "/certs"
  before_script:
    - echo "🔐 Logging into Container Registry..."
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - echo "🏗️  Building Docker image..."
    {% if build_args %}
    # Build с аргументами
    - docker build {{ build_args_string }} -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA -t $CI_REGISTRY_IMAGE:latest .
    {% else %}
    # Обычный build
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA -t $CI_REGISTRY_IMAGE:latest .
    {% endif %}
    - echo "📤 Pushing image to registry..."
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - docker push $CI_REGISTRY_IMAGE:latest
    - echo "✅ Build complete!"
  only:
    - main
  tags:
    - docker
  retry:
    max: 2
    when:
      - runner_system_failure
      - stuck_or_timeout_failure

build_test:
  stage: build
  image: docker:24-cli
  services:
    - docker:24-dind
  variables:
    DOCKER_DRIVER: overlay2
  script:
    - echo "🧪 Testing Dockerfile build..."
    {% if build_args %}
    - docker build {{ build_args_string }} .
    {% else %}
    - docker build .
    {% endif %}
    - echo "✅ Dockerfile is valid!"
  only:
    - merge_requests
  except:
    - main
  tags:
    - docker
"""

    def __init__(self, dockerfile_info: Dict):
        """
        Args:
            dockerfile_info: Словарь информации о Dockerfile (из DockerfileParser)
        """
        self.dockerfile_info = dockerfile_info

    def _format_build_args(self) -> str:
        """
        Форматирует build args для docker build команды

        Пример:
        {'VERSION': '1.0', 'ENV': None}
        → '--build-arg VERSION=1.0 --build-arg ENV=$CI_COMMIT_SHA'
        """
        build_args = self.dockerfile_info.get('build_args', {})

        if not build_args:
            return ""

        args_list = []
        for name, default_value in build_args.items():
            if default_value:
                # Если есть дефолтное значение, используем его
                args_list.append(f'--build-arg {name}={default_value}')
            else:
                # Если нет дефолта, берём из переменной окружения CI
                args_list.append(f'--build-arg {name}=$CI_COMMIT_SHA')

        return ' '.join(args_list)

    def generate(self) -> str:
        """Генерирует build stage YAML"""

        template = Template(self.BUILD_TEMPLATE)

        build_stage = template.render(
            build_args=self.dockerfile_info.get('build_args', {}),
            build_args_string=self._format_build_args(),
        )

        return build_stage

    def get_output_string(self) -> str:
        """Возвращает готовую строку YAML для добавления в конфиг"""
        return self.generate()
