# src/deploy/deploy_generator.py

from jinja2 import Template


class DeployStageGenerator:
    """Генератор Deploy stage с поддержкой переменных окружения"""

    # Docker Registry → Server Deploy (с передачей ENV в docker run)
    DOCKER_REGISTRY_SERVER_DEPLOY = """deploy:
  stage: deploy
  image: alpine:latest
  before_script:
    - echo "================================================"
    - echo "DEPLOY STAGE - Docker Registry → Server"
    - echo "================================================"
    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_rsa
    - chmod 600 ~/.ssh/id_rsa
    - ssh-keyscan -p $SSH_PORT -H $DEPLOY_HOST >> ~/.ssh/known_hosts
  script:
    - echo "🚀 Deploying to server..."
    - echo "   Server: $DEPLOY_HOST"
    - echo "   Image: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA"
    - echo ""

    # ========== НОВОЕ: Генерируем docker run с переменными окружения ==========
    - |
      # Формируем список -e переменных окружения
      ENV_VARS=""
      {% if env_vars %}
      # Добавляем все переменные окружения в docker run
      {% for var_name in env_vars %}
      if [ ! -z "${{ var_name }}" ]; then
        ENV_VARS="$ENV_VARS -e {{ var_name }}='${{ var_name }}'"
      fi
      {% endfor %}
      {% endif %}

      echo "🔐 Environment variables for deployment:"
      {% if env_vars %}
      {% for var_name in env_vars %}
      echo "   → {{ var_name }}"
      {% endfor %}
      {% else %}
      echo "   (no environment variables)"
      {% endif %}
      echo ""

      # Deploy на сервер
      ssh -p $SSH_PORT $DEPLOY_USER@$DEPLOY_HOST "
        # Логин в Docker Registry
        docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY

        # Pull новый образ
        docker pull $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

        # Останавливаем старый контейнер
        docker stop {{ container_name }} || true
        docker rm {{ container_name }} || true

        # Запускаем новый контейнер с переменными окружения
        docker run -d \
          --name {{ container_name }} \
          --restart unless-stopped \
          -p {{ host_port }}:{{ container_port }} \
          $ENV_VARS \
          $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

        # Проверяем статус
        docker ps | grep {{ container_name }}
      "

    - echo ""
    - echo "✅ Deployment complete!"
    - echo "   Container: {{ container_name }}"
    - echo "   URL: http://$DEPLOY_HOST:{{ host_port }}"
  environment:
    name: production
    url: http://$DEPLOY_HOST:{{ host_port }}
  only:
    - main
  when: manual
  tags:
    - docker
"""

    # Docker Registry → Kubernetes Deploy (с передачей ENV в k8s deployment)
    DOCKER_REGISTRY_K8S_DEPLOY = """deploy:
  stage: deploy
  image: bitnami/kubectl:latest
  before_script:
    - echo "================================================"
    - echo "DEPLOY STAGE - Docker Registry → Kubernetes"
    - echo "================================================"
    - echo "🔧 Configuring kubectl..."
    - mkdir -p ~/.kube
    - echo "$KUBE_CONFIG" | base64 -d > ~/.kube/config
    - kubectl version --client
  script:
    - echo "🚀 Deploying to Kubernetes..."
    - echo "   Namespace: $K8S_NAMESPACE"
    - echo "   Image: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA"
    - echo ""

    # ========== НОВОЕ: Создаём Secret с переменными окружения ==========
    {% if env_vars %}
    - echo "🔐 Creating Kubernetes Secret with environment variables..."
    - |
      # Удаляем старый secret
      kubectl delete secret {{ app_name }}-env --namespace=$K8S_NAMESPACE || true

      # Создаём новый secret со всеми переменными
      kubectl create secret generic {{ app_name }}-env \
        --namespace=$K8S_NAMESPACE \
      {% for var_name in env_vars %}
        --from-literal={{ var_name }}="${{ var_name }}" \
      {% endfor %}
        --dry-run=client -o yaml | kubectl apply -f -
    - echo ""
    {% endif %}

    # Генерируем deployment manifest
    - |
      cat > deployment.yaml <<EOF
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: {{ app_name }}
        namespace: $K8S_NAMESPACE
      spec:
        replicas: {{ replicas }}
        selector:
          matchLabels:
            app: {{ app_name }}
        template:
          metadata:
            labels:
              app: {{ app_name }}
          spec:
            containers:
            - name: {{ app_name }}
              image: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
              ports:
              - containerPort: {{ container_port }}
              {% if env_vars %}
              # Инжектим переменные из Secret
              envFrom:
              - secretRef:
                  name: {{ app_name }}-env
              {% endif %}
              livenessProbe:
                httpGet:
                  path: /health
                  port: {{ container_port }}
                initialDelaySeconds: 30
                periodSeconds: 10
              readinessProbe:
                httpGet:
                  path: /health
                  port: {{ container_port }}
                initialDelaySeconds: 5
                periodSeconds: 5
      ---
      apiVersion: v1
      kind: Service
      metadata:
        name: {{ app_name }}
        namespace: $K8S_NAMESPACE
      spec:
        type: LoadBalancer
        selector:
          app: {{ app_name }}
        ports:
        - port: 80
          targetPort: {{ container_port }}
      EOF

    - echo "📦 Applying deployment..."
    - kubectl apply -f deployment.yaml

    - echo ""
    - echo "⏳ Waiting for rollout..."
    - kubectl rollout status deployment/{{ app_name }} --namespace=$K8S_NAMESPACE --timeout=5m

    - echo ""
    - echo "✅ Deployment complete!"
    - kubectl get pods --namespace=$K8S_NAMESPACE -l app={{ app_name }}
    - kubectl get service {{ app_name }} --namespace=$K8S_NAMESPACE
  environment:
    name: production
    kubernetes:
      namespace: $K8S_NAMESPACE
  only:
    - main
  when: manual
  tags:
    - docker
"""

    def __init__(self, config: dict, sync_target: str, deploy_target: str = None):
        self.config = config
        self.sync_target = sync_target
        self.deploy_target = deploy_target

        # ========== НОВОЕ: Получаем список переменных окружения ==========
        self.env_vars = []
        if config.get('env_summary', {}).get('variables'):
            self.env_vars = list(config['env_summary']['variables'].keys())

    def generate(self) -> str:
        """Генерирует deploy stage"""

        if not self.deploy_target:
            return "# No deployment target specified\n"

        # Определяем имя приложения из проекта
        app_name = self.config.get('language', 'app')

        if self.sync_target == 'docker-registry' and self.deploy_target == 'server':
            template = Template(self.DOCKER_REGISTRY_SERVER_DEPLOY)
            return template.render(
                container_name=app_name,
                host_port=80,
                container_port=8080,
                env_vars=self.env_vars,  # ← НОВОЕ
            )

        elif self.sync_target == 'docker-registry' and self.deploy_target == 'k8s':
            template = Template(self.DOCKER_REGISTRY_K8S_DEPLOY)
            return template.render(
                app_name=app_name,
                container_port=8080,
                replicas=3,
                env_vars=self.env_vars,  # ← НОВОЕ
            )

        else:
            return f"# Unsupported deployment: {self.sync_target} → {self.deploy_target}\n"
