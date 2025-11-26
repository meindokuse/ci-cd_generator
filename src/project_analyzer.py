# project_analyzer.py

import os
import glob
import json
import re
from typing import Dict
from jinja2 import Template


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
            'medium': ['*.js', '*.ts']
        },
        'java': {
            'high': ['pom.xml', 'build.gradle'],
            'medium': ['*.java']
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

        # 3. Проверяем Dockerfile
        self.data['dockerfile_exists'] = os.path.exists(
            os.path.join(self.project_path, "Dockerfile")
        )

        # 4. Генерируем Dockerfile если нужно
        if not self.data['dockerfile_exists'] and self.docker_gen:
            print(f"   🔨 Генерирую Dockerfile для {language}:{self.data['version']}...")
            self._generate_dockerfile(language)
            self.data['dockerfile_exists'] = True

        # 5. Определяем базовый образ
        if self.data['dockerfile_exists']:
            self.data['dockerfile_info'] = self._parse_dockerfile()
            self.data['base_image'] = self.data['dockerfile_info']['final_image']
        else:
            self.data['dockerfile_info'] = None
            self.data['base_image'] = self._get_build_image(language)

        # 6. Определяем артефакты
        self.data['artifact_paths'] = self._detect_artifact_paths(language)

        print(f"✅ Язык: {language}")
        print(f"✅ Версия: {self.data['version']}")
        print(f"✅ Dockerfile: {'Найден ✅' if self.data['dockerfile_exists'] else 'Не найден ❌'}")
        print("✅ Анализ завершён\n")

    def _get_build_image(self, language: str) -> str:
        """Возвращает образ для сборки артефактов"""
        images = {
            'python': f"python:{self.data['version']}-slim",
            'go': f"golang:{self.data['version']}-alpine",
            'node': f"node:{self.data['version']}-alpine",
            'java': f"maven:3.9-eclipse-temurin-{self.data['version']}",
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
            'java': {
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
        elif language == 'node':
            return self._detect_node_version()
        elif language == 'java':
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

    def get_summary(self) -> Dict:
        """Возвращает сводку"""
        return {
            'language': self.data['language_info']['language'],
            'version': self.data['version'],
            'dockerfile_exists': self.data['dockerfile_exists'],
            'dockerfile_info': self.data.get('dockerfile_info'),
            'base_image': self.data['base_image'],
            'artifact_paths': self.data.get('artifact_paths'),
            'language_info': self.data['language_info'],
        }
