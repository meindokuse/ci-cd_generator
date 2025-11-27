# src/project_analyzer.py

import os
import glob
import json
import re
from typing import Dict, List
from jinja2 import Template

from src.env_analyzer import EnvAnalyzer


class ProjectAnalyzer:
    """Анализ проекта с определением стратегии сборки"""

    LANGUAGE_MARKERS = {
        'python': {
            'high': ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile'],
            'medium': ['*.py']
        },
        'go': {
            'high': ['go.mod'],
            'medium': ['*.go']
        },
        'node': {
            'high': ['package.json'],
            'medium': ['*.js', '*.ts', '*.tsx']
        },
        'typescript': {
            'high': ['tsconfig.json'],
            'medium': ['*.ts', '*.tsx']
        },
        'java': {
            'high': ['pom.xml', 'build.gradle'],
            'medium': ['*.java']
        },
        'kotlin': {
            'high': ['pom.xml', 'build.gradle', 'build.gradle.kts'],
            'medium': ['*.kt']
        },
        'php': {
            'high': ['composer.json'],
            'medium': ['*.php']
        },
        'rust': {
            'high': ['Cargo.toml'],
            'medium': ['*.rs']
        },
        'ruby': {
            'high': ['Gemfile'],
            'medium': ['*.rb']
        },
    }

    # Фреймворки для каждого языка
    FRAMEWORK_DETECTION = {
        'python': {
            'Django': ['django', 'Django'],
            'Flask': ['flask', 'Flask'],
            'FastAPI': ['fastapi', 'FastAPI'],
            'Tornado': ['tornado'],
            'Pyramid': ['pyramid'],
        },
        'go': {
            'Gin': ['gin-gonic/gin', 'github.com/gin-gonic/gin'],
            'Echo': ['labstack/echo', 'github.com/labstack/echo'],
            'Fiber': ['gofiber/fiber', 'github.com/gofiber/fiber'],
            'Chi': ['go-chi/chi', 'github.com/go-chi/chi'],
            'Beego': ['beego/beego', 'github.com/beego/beego'],
            'Gorilla Mux': ['gorilla/mux', 'github.com/gorilla/mux'],
        },
        'node': {
            'Express': ['express'],
            'NestJS': ['@nestjs/core'],
            'Koa': ['koa'],
            'Fastify': ['fastify'],
            'Next.js': ['next'],
        },
        'typescript': {
            'Express': ['express'],
            'NestJS': ['@nestjs/core'],
            'Angular': ['@angular/core'],
            'React': ['react'],
            'Vue': ['vue'],
            'Next.js': ['next'],
        },
        'java': {
            'Spring Boot': ['spring-boot', 'org.springframework.boot'],
            'Spring': ['springframework'],
            'Quarkus': ['quarkus'],
            'Micronaut': ['micronaut'],
            'Vert.x': ['vertx'],
        },
        'kotlin': {
            'Spring Boot': ['spring-boot'],
            'Ktor': ['ktor', 'io.ktor'],
            'Micronaut': ['micronaut'],
            'Quarkus': ['quarkus'],
        },
    }

    DOCKERFILE_TEMPLATES = {
        'python': """FROM python:{{ version }}-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:{{ version }}-slim
RUN useradd -m -u 1000 appuser
WORKDIR /app
COPY --from=builder /usr/local/lib/python{{ version_short }}/site-packages /usr/local/lib/python{{ version_short }}/site-packages
COPY --chown=appuser:appuser . .
EXPOSE 3000
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD python -c "import http.client; http.client.HTTPConnection('127.0.0.1', 3000).request('GET', '/'); exit(0)"
CMD ["python", "-m", "main"]
""",

        'go': """FROM golang:{{ version }}-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o app .

FROM alpine:latest
RUN apk --no-cache add ca-certificates
RUN adduser -D -u 1000 appuser
WORKDIR /home/appuser
COPY --from=builder --chown=appuser:appuser /app/app .
EXPOSE 3000
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1
CMD ["./app"]
""",

        'node': """FROM node:{{ version }}-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

FROM node:{{ version }}-alpine
RUN adduser -D -u 1000 appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/node_modules ./node_modules
COPY --chown=appuser:appuser . .
EXPOSE 3000
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1
CMD ["npm", "start"]
""",

        'typescript': """FROM node:{{ version }}-alpine as builder
WORKDIR /app
COPY package*.json tsconfig.json ./
RUN npm ci
RUN npm run build

FROM node:{{ version }}-alpine
RUN adduser -D -u 1000 appuser
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY --from=builder --chown=appuser:appuser /app/dist ./dist
EXPOSE 3000
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1
CMD ["npm", "start"]
""",

        'java': """FROM maven:3.9-eclipse-temurin-{{ version }} as builder
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline
COPY . .
RUN mvn clean package -DskipTests

FROM eclipse-temurin:{{ version }}-jre-alpine
RUN adduser -D -u 1000 appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/target/*.jar app.jar
EXPOSE 3000
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget --no-verbose --tries=1 --spider http://localhost:3000/actuator/health || exit 1
CMD ["java", "-jar", "app.jar"]
""",

        'kotlin': """FROM maven:3.9-eclipse-temurin-{{ version }} as builder
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline
COPY . .
RUN mvn clean package -DskipTests

FROM eclipse-temurin:{{ version }}-jre-alpine
RUN adduser -D -u 1000 appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/target/*.jar app.jar
EXPOSE 3000
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget --no-verbose --tries=1 --spider http://localhost:3000/actuator/health || exit 1
CMD ["java", "-jar", "app.jar"]
""",

        'php': """FROM php:{{ version }}-fpm-alpine
WORKDIR /app
COPY composer.json composer.lock ./
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer && \
    composer install --no-interaction --no-dev

FROM php:{{ version }}-fpm-alpine
RUN adduser -D -u 1000 appuser
WORKDIR /app
COPY --from=0 --chown=appuser:appuser /app ./
EXPOSE 3000
USER appuser
CMD ["php", "-S", "0.0.0.0:3000"]
""",

        'rust': """FROM rust:{{ version }} as builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/target/release/app .
EXPOSE 3000
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD curl -f http://localhost:3000/health || exit 1
CMD ["./app"]
""",

        'ruby': """FROM ruby:{{ version }}-alpine
WORKDIR /app
COPY Gemfile Gemfile.lock ./
RUN gem install bundler && bundle install

RUN adduser -D -u 1000 appuser
COPY --chown=appuser:appuser . .
EXPOSE 3000
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1
CMD ["rails", "server", "-b", "0.0.0.0", "-p", "3000"]
""",
    }

    def __init__(self, project_path: str = ".", docker_gen: bool = False):
        """
        Args:
            project_path: Путь к проекту
            docker_gen: Генерировать ли Dockerfile если его нет
        """
        self.project_path = project_path
        self.docker_gen = docker_gen
        self.data = {}
        self._analyze()

    def _analyze(self):
        """Главный метод анализа проекта"""
        print("🔍 Анализирую проект...")

        # 1. Определяем язык
        self.data['language_info'] = self._detect_language()
        language = self.data['language_info']['language']

        if language == 'unknown':
            raise ValueError("❌ Не удалось определить язык проекта!")

        # 2. Определяем версию
        self.data['version'] = self._detect_version(language)

        # 3. Определяем фреймворк
        self.data['framework'] = self._detect_framework(language)

        # 4. Определяем топ зависимостей
        self.data['dependencies'] = self._detect_dependencies(language)

        # 5. Проверяем Dockerfile
        self.data['dockerfile_exists'] = os.path.exists(
            os.path.join(self.project_path, "Dockerfile")
        )

        # 6. Проверяем docker-compose.yml
        self.data['docker_compose_exists'] = self._check_docker_compose()

        if self.data['docker_compose_exists']:
            self.data['docker_compose_info'] = self._parse_docker_compose()

            # Определяем: monorepo или нет
            services_with_build = self._extract_services_with_build()

            if len(services_with_build) > 1:
                self.data['is_monorepo'] = True
                self.data['services'] = services_with_build
                print(f"✅ Обнаружен Monorepo ({len(services_with_build)} сервисов)")
                for svc in services_with_build:
                    print(f"   → {svc['name']} ({svc['path']})")
            else:
                self.data['is_monorepo'] = False
                self.data['services'] = []
        else:
            self.data['is_monorepo'] = False
            self.data['services'] = []

        # 7. Генерируем Dockerfile если нужно
        if not self.data['dockerfile_exists'] and self.docker_gen:
            print(f"   🔨 Генерирую Dockerfile для {language}:{self.data['version']}...")
            self._generate_dockerfile(language)
            self.data['dockerfile_exists'] = True

        # 8. Определяем базовый образ
        if self.data['dockerfile_exists']:
            self.data['dockerfile_info'] = self._parse_dockerfile()
            self.data['base_image'] = self.data['dockerfile_info']['final_image']
        else:
            self.data['dockerfile_info'] = None
            self.data['base_image'] = self._get_build_image(language)

        # 9. Определяем артефакты
        self.data['artifact_paths'] = self._detect_artifact_paths(language)

        # ========== 10. НОВОЕ: Анализируем переменные окружения ==========
        self.env_analyzer = EnvAnalyzer(self.project_path)
        self.data['env_summary'] = self.env_analyzer.get_summary()

        # ============ РАСШИРЕННЫЙ ВЫВОД ============
        print(f"\n{'=' * 70}")
        print("📋 АНАЛИЗ ПРОЕКТА")
        print(f"{'=' * 70}")
        print(f"✅ Язык: {language}")
        print(f"✅ Версия: {self.data['version']}")

        # Вывод фреймворка
        if self.data.get('framework'):
            print(f"✅ Фреймворк: {self.data['framework']}")
        else:
            print(f"⚠️  Фреймворк: Не обнаружен (будет определён SonarQube)")

        # Вывод топ зависимостей
        if self.data.get('dependencies'):
            deps_count = len(self.data['dependencies'])
            print(f"✅ Основные зависимости ({deps_count}):")
            for dep in self.data['dependencies'][:5]:
                print(f"   → {dep}")
            if deps_count > 5:
                print(f"   ... и ещё {deps_count - 5}")

        print(f"✅ Dockerfile: {'Найден ✅' if self.data['dockerfile_exists'] else 'Не найден ❌'}")
        print(f"✅ docker-compose.yml: {'Найден ✅' if self.data['docker_compose_exists'] else 'Не найден ❌'}")

        if self.data.get('is_monorepo'):
            print(f"✅ Тип проекта: Monorepo ({len(self.data['services'])} сервисов)")

        print(f"{'=' * 70}\n")

    def _detect_framework(self, language: str) -> str:
        """Определяет используемый фреймворк"""
        if language not in self.FRAMEWORK_DETECTION:
            return None

        frameworks = self.FRAMEWORK_DETECTION[language]

        if language == 'python':
            return self._detect_python_framework(frameworks)
        elif language in ['node', 'typescript']:
            return self._detect_node_framework(frameworks)
        elif language in ['java', 'kotlin']:
            return self._detect_java_framework(frameworks)
        elif language == 'go':
            return self._detect_go_framework(frameworks)

        return None

    def _detect_go_framework(self, frameworks: Dict) -> str:
        """Определяет Go фреймворк"""
        go_mod = os.path.join(self.project_path, "go.mod")
        if os.path.exists(go_mod):
            with open(go_mod, 'r', encoding='utf-8') as f:
                content = f.read()
                for framework, markers in frameworks.items():
                    if any(marker in content for marker in markers):
                        return framework
        return None

    def _detect_python_framework(self, frameworks: Dict) -> str:
        """Определяет Python фреймворк"""
        req_file = os.path.join(self.project_path, "requirements.txt")
        if os.path.exists(req_file):
            with open(req_file, 'r', encoding='utf-8') as f:
                content = f.read().lower()
                for framework, markers in frameworks.items():
                    if any(marker.lower() in content for marker in markers):
                        return framework

        # Проверяем pyproject.toml
        pyproject = os.path.join(self.project_path, "pyproject.toml")
        if os.path.exists(pyproject):
            with open(pyproject, 'r', encoding='utf-8') as f:
                content = f.read().lower()
                for framework, markers in frameworks.items():
                    if any(marker.lower() in content for marker in markers):
                        return framework
        return None

    def _detect_node_framework(self, frameworks: Dict) -> str:
        """Определяет Node.js/TypeScript фреймворк"""
        pkg_json = os.path.join(self.project_path, "package.json")
        if os.path.exists(pkg_json):
            try:
                with open(pkg_json, 'r', encoding='utf-8') as f:
                    pkg = json.load(f)
                    deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
                    for framework, markers in frameworks.items():
                        if any(marker in deps for marker in markers):
                            return framework
            except:
                pass
        return None

    def _detect_java_framework(self, frameworks: Dict) -> str:
        """Определяет Java/Kotlin фреймворк"""
        # Проверяем pom.xml
        pom_xml = os.path.join(self.project_path, "pom.xml")
        if os.path.exists(pom_xml):
            with open(pom_xml, 'r', encoding='utf-8') as f:
                content = f.read()
                for framework, markers in frameworks.items():
                    if any(marker in content for marker in markers):
                        return framework

        # Проверяем build.gradle
        for gradle_file in ['build.gradle', 'build.gradle.kts']:
            gradle_path = os.path.join(self.project_path, gradle_file)
            if os.path.exists(gradle_path):
                with open(gradle_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for framework, markers in frameworks.items():
                        if any(marker in content for marker in markers):
                            return framework
        return None

    def _detect_dependencies(self, language: str) -> List[str]:
        """Определяет основные зависимости проекта"""
        deps = []

        if language == 'python':
            req_file = os.path.join(self.project_path, "requirements.txt")
            if os.path.exists(req_file):
                with open(req_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            dep = line.split('==')[0].split('>=')[0].split('~=')[0]
                            deps.append(dep)

        elif language in ['node', 'typescript']:
            pkg_json = os.path.join(self.project_path, "package.json")
            if os.path.exists(pkg_json):
                try:
                    with open(pkg_json, 'r', encoding='utf-8') as f:
                        pkg = json.load(f)
                        deps = list(pkg.get('dependencies', {}).keys())
                except:
                    pass

        elif language == 'go':
            go_mod = os.path.join(self.project_path, "go.mod")
            if os.path.exists(go_mod):
                with open(go_mod, 'r', encoding='utf-8') as f:
                    in_require = False
                    for line in f:
                        line = line.strip()

                        if line.startswith('require ('):
                            in_require = True
                            continue

                        if in_require:
                            if line == ')':
                                break
                            if line and not line.startswith('//'):
                                dep = line.split()[0] if line.split() else None
                                if dep:
                                    deps.append(dep)

                        elif line.startswith('require ') and '(' not in line:
                            dep = line.replace('require', '').strip().split()[0]
                            deps.append(dep)

        elif language in ['java', 'kotlin']:
            # Maven pom.xml
            pom_xml = os.path.join(self.project_path, "pom.xml")
            if os.path.exists(pom_xml):
                with open(pom_xml, 'r', encoding='utf-8') as f:
                    content = f.read()
                    artifacts = re.findall(r'<artifactId>(.*?)</artifactId>', content)
                    deps = artifacts[:20]

        return deps[:10]  # Топ 10

    def _get_build_image(self, language: str) -> str:
        """Возвращает образ для сборки артефактов"""
        images = {
            'python': f"python:{self.data['version']}-slim",
            'go': f"golang:{self.data['version']}-alpine",
            'node': f"node:{self.data['version']}-alpine",
            'typescript': f"node:{self.data['version']}-alpine",
            'java': f"maven:3.9-eclipse-temurin-{self.data['version']}",
            'kotlin': f"maven:3.9-eclipse-temurin-{self.data['version']}",
            'php': f"php:{self.data['version']}-cli",
            'rust': f"rust:{self.data['version']}",
            'ruby': f"ruby:{self.data['version']}-alpine",
        }
        return images.get(language, 'alpine:latest')

    def _detect_artifact_paths(self, language: str) -> Dict:
        """Определяет пути к артефактам"""
        paths = {
            'python': {
                'build_command': 'python setup.py bdist_wheel',
                'artifact_path': 'dist/*.whl',
                'artifact_name': '*.whl',
                'artifact_type': 'wheel'
            },
            'go': {
                'build_command': 'go build -o app .',
                'artifact_path': 'app',
                'artifact_name': 'app',
                'artifact_type': 'binary'
            },
            'node': {
                'build_command': 'npm run build && npm pack',
                'artifact_path': '*.tgz',
                'artifact_name': '*.tgz',
                'artifact_type': 'npm'
            },
            'typescript': {
                'build_command': 'npm run build && npm pack',
                'artifact_path': '*.tgz',
                'artifact_name': '*.tgz',
                'artifact_type': 'npm'
            },
            'java': {
                'build_command': 'mvn clean package',
                'artifact_path': 'target/*.jar',
                'artifact_name': '*.jar',
                'artifact_type': 'jar'
            },
            'kotlin': {
                'build_command': 'mvn clean package',
                'artifact_path': 'target/*.jar',
                'artifact_name': '*.jar',
                'artifact_type': 'jar'
            },
            'php': {
                'build_command': 'composer install --no-dev',
                'artifact_path': 'vendor/',
                'artifact_name': 'vendor',
                'artifact_type': 'composer'
            },
            'rust': {
                'build_command': 'cargo build --release',
                'artifact_path': 'target/release/app',
                'artifact_name': 'app',
                'artifact_type': 'binary'
            },
            'ruby': {
                'build_command': 'gem build *.gemspec',
                'artifact_path': '*.gem',
                'artifact_name': '*.gem',
                'artifact_type': 'gem'
            },
        }

        return paths.get(language, {
            'build_command': 'echo "No build command"',
            'artifact_path': '*',
            'artifact_name': '*',
            'artifact_type': 'unknown'
        })

    def _detect_language(self) -> Dict:
        """Определяет язык проекта"""
        priority = {'high': 3, 'medium': 2}
        detections = {}

        for language, markers in self.LANGUAGE_MARKERS.items():
            for marker in markers['high']:
                if self._file_exists(marker):
                    detections[language] = ('high', marker)
                    break

            if language not in detections:
                for marker in markers['medium']:
                    if self._file_exists(marker):
                        detections[language] = ('medium', marker)
                        break

        if not detections:
            return {
                'language': 'unknown',
                'marker': None,
                'confidence': 'none'
            }

        best = max(detections.items(),
                   key=lambda x: priority.get(x[1][0], 0))

        return {
            'language': best[0],
            'marker': best[1][1],
            'confidence': best[1][0]
        }

    def _file_exists(self, pattern: str) -> bool:
        """Проверяет существование файла или паттерна"""
        if '*' in pattern:
            return bool(glob.glob(os.path.join(self.project_path, pattern)))
        return os.path.exists(os.path.join(self.project_path, pattern))

    def _detect_version(self, language: str) -> str:
        """Определяет версию языка"""
        if language == 'python':
            return self._detect_python_version()
        elif language == 'go':
            return self._detect_go_version()
        elif language in ['node', 'typescript']:
            return self._detect_node_version()
        elif language in ['java', 'kotlin']:
            return self._detect_java_version()
        elif language == 'php':
            return self._detect_php_version()
        elif language == 'rust':
            return self._detect_rust_version()
        elif language == 'ruby':
            return self._detect_ruby_version()
        return "latest"

    def _detect_python_version(self) -> str:
        req_file = os.path.join(self.project_path, "requirements.txt")
        if os.path.exists(req_file):
            with open(req_file, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'python_requires.*?(3\.\d+)', content)
                if match:
                    return match.group(1)
        return "3.11"

    def _detect_go_version(self) -> str:
        go_mod = os.path.join(self.project_path, "go.mod")
        if os.path.exists(go_mod):
            with open(go_mod, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('go '):
                        return line.split()[1].strip()
        return "1.21"

    def _detect_node_version(self) -> str:
        pkg_json = os.path.join(self.project_path, "package.json")
        if os.path.exists(pkg_json):
            try:
                with open(pkg_json, 'r', encoding='utf-8') as f:
                    pkg = json.load(f)
                    if 'engines' in pkg and 'node' in pkg['engines']:
                        match = re.search(r'\d+', pkg['engines']['node'])
                        if match:
                            return match.group()
            except:
                pass
        return "20"

    def _detect_java_version(self) -> str:
        pom_xml = os.path.join(self.project_path, "pom.xml")
        if os.path.exists(pom_xml):
            with open(pom_xml, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'<source>(1\.\d+|11|17|21)</source>', content)
                if match:
                    return match.group(1)
        return "17"

    def _detect_php_version(self) -> str:
        composer = os.path.join(self.project_path, "composer.json")
        if os.path.exists(composer):
            try:
                with open(composer, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'require' in data and 'php' in data['require']:
                        match = re.search(r'\d+\.\d+', data['require']['php'])
                        if match:
                            return match.group()
            except:
                pass
        return "8.2"

    def _detect_rust_version(self) -> str:
        rust_toolchain = os.path.join(self.project_path, "rust-toolchain")
        if os.path.exists(rust_toolchain):
            with open(rust_toolchain, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return "latest"

    def _detect_ruby_version(self) -> str:
        ruby_version = os.path.join(self.project_path, ".ruby-version")
        if os.path.exists(ruby_version):
            with open(ruby_version, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return "3.2"

    def _generate_dockerfile(self, language: str):
        """Генерирует Dockerfile"""
        version = self.data['version']
        template_str = self.DOCKERFILE_TEMPLATES.get(
            language,
            f"FROM alpine:latest\nWORKDIR /app\nCOPY . .\nEXPOSE 3000\nCMD [\"/bin/sh\"]\n"
        )

        template = Template(template_str)
        version_short = '.'.join(version.split('.')[:2])

        dockerfile_content = template.render(
            version=version,
            version_short=version_short,
            port=3000
        )

        dockerfile_path = os.path.join(self.project_path, "Dockerfile")
        with open(dockerfile_path, 'w', encoding='utf-8') as f:
            f.write(dockerfile_content)

        print(f"   ✅ Dockerfile создан: {dockerfile_path}")

    def _parse_dockerfile(self) -> Dict:
        """Парсит Dockerfile"""
        from dockerfile_parser import DockerfileParser
        parser = DockerfileParser(os.path.join(self.project_path, "Dockerfile"))
        return parser.get_summary()

    def _check_docker_compose(self) -> bool:
        """Проверяет существование docker-compose файлов"""
        compose_files = [
            'docker-compose.yml',
            'docker-compose.yaml',
            'compose.yml',
            'compose.yaml'
        ]

        for filename in compose_files:
            if os.path.exists(os.path.join(self.project_path, filename)):
                return True

        return False

    def _parse_docker_compose(self) -> Dict:
        """Парсит docker-compose.yml"""
        import yaml

        compose_files = [
            'docker-compose.yml',
            'docker-compose.yaml',
            'compose.yml',
            'compose.yaml'
        ]

        for filename in compose_files:
            filepath = os.path.join(self.project_path, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        compose_data = yaml.safe_load(f)

                    services = compose_data.get('services', {})

                    return {
                        'filename': filename,
                        'services': list(services.keys()),
                        'service_count': len(services),
                        'has_build': any('build' in svc for svc in services.values()),
                        'has_image': any('image' in svc for svc in services.values()),
                        'networks': list(compose_data.get('networks', {}).keys()),
                        'volumes': list(compose_data.get('volumes', {}).keys()),
                    }
                except Exception as e:
                    print(f"⚠️  Не удалось распарсить {filename}: {e}")
                    return {
                        'filename': filename,
                        'services': [],
                        'service_count': 0,
                        'has_build': False,
                        'has_image': False,
                        'networks': [],
                        'volumes': [],
                    }

        return {}

    def _extract_services_with_build(self) -> List[Dict]:
        """Извлекает сервисы с build директивой из docker-compose.yml"""
        import yaml

        compose_files = [
            'docker-compose.yml',
            'docker-compose.yaml',
            'compose.yml',
            'compose.yaml'
        ]

        for filename in compose_files:
            filepath = os.path.join(self.project_path, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        compose_data = yaml.safe_load(f)

                    services = compose_data.get('services', {})
                    services_with_build = []

                    for service_name, service_config in services.items():
                        if 'build' in service_config:
                            build_path = service_config['build']

                            # build может быть строкой или объектом
                            if isinstance(build_path, dict):
                                build_path = build_path.get('context', '.')

                            # Проверяем существование Dockerfile
                            dockerfile_path = os.path.join(
                                self.project_path,
                                build_path,
                                'Dockerfile'
                            )

                            if os.path.exists(dockerfile_path):
                                services_with_build.append({
                                    'name': service_name,
                                    'path': build_path,
                                    'dockerfile': dockerfile_path
                                })

                    return services_with_build

                except Exception as e:
                    print(f"⚠️  Ошибка парсинга {filename}: {e}")

        return []

    def get_summary(self) -> Dict:
        """Возвращает сводку"""
        return {
            'language': self.data['language_info']['language'],
            'version': self.data['version'],
            'framework': self.data.get('framework'),
            'dependencies': self.data.get('dependencies', []),
            'dockerfile_exists': self.data['dockerfile_exists'],
            'dockerfile_info': self.data.get('dockerfile_info'),
            'docker_compose_exists': self.data.get('docker_compose_exists', False),
            'docker_compose_info': self.data.get('docker_compose_info'),
            'is_monorepo': self.data.get('is_monorepo', False),
            'services': self.data.get('services', []),
            'base_image': self.data['base_image'],
            'artifact_paths': self.data.get('artifact_paths'),
            'language_info': self.data['language_info'],
        }
