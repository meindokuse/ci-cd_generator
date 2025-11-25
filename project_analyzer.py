# project_analyzer.py

import os
import glob
import json
import re
from pathlib import Path
from typing import Dict, Optional, List
from jinja2 import Template


class ProjectAnalyzer:
    """
    Единый класс для анализа проекта:
    - Определение языка
    - Определение версии
    - Генерация/парсинг Dockerfile
    - Все данные хранятся в одном месте
    """

    # Приоритеты определения языков
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

    # Шаблоны Dockerfile для каждого языка
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
EXPOSE {{ port }}
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD python -c "import http.client; http.client.HTTPConnection('127.0.0.1', {{ port }}).request('GET', '/'); exit(0)"
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
EXPOSE {{ port }}
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget --no-verbose --tries=1 --spider http://localhost:{{ port }}/health || exit 1
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
EXPOSE {{ port }}
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget --no-verbose --tries=1 --spider http://localhost:{{ port }}/health || exit 1
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
EXPOSE {{ port }}
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget --no-verbose --tries=1 --spider http://localhost:{{ port }}/actuator/health || exit 1
CMD ["java", "-jar", "app.jar"]
""",

        'php': """FROM php:{{ version }}-fpm-alpine
WORKDIR /app
COPY composer.json composer.lock ./
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer && \\
    composer install --no-interaction --no-dev

FROM php:{{ version }}-fpm-alpine
RUN adduser -D -u 1000 appuser
WORKDIR /app
COPY --from=0 --chown=appuser:appuser /app ./
EXPOSE {{ port }}
USER appuser
CMD ["php", "-S", "0.0.0.0:{{ port }}"]
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
EXPOSE {{ port }}
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD curl -f http://localhost:{{ port }}/health || exit 1
CMD ["./app"]
""",

        'ruby': """FROM ruby:{{ version }}-alpine
WORKDIR /app
COPY Gemfile Gemfile.lock ./
RUN gem install bundler && bundle install

RUN adduser -D -u 1000 appuser
COPY --chown=appuser:appuser . .
EXPOSE {{ port }}
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget --no-verbose --tries=1 --spider http://localhost:{{ port }}/ || exit 1
CMD ["rails", "server", "-b", "0.0.0.0", "-p", "{{ port }}"]
""",
    }

    def __init__(self, project_path: str = "."):
        self.project_path = project_path
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

        # 3. Проверяем/генерируем Dockerfile
        self.data['dockerfile_exists'] = os.path.exists(
            os.path.join(self.project_path, "Dockerfile")
        )

        if self.data['dockerfile_exists']:
            self.data['dockerfile_info'] = self._parse_dockerfile()
        else:
            self.data['dockerfile_info'] = self._generate_dockerfile(language)

        # 4. Определяем порт
        self.data['port'] = self.data['dockerfile_info'].get('primary_port', 3000)

        # 5. Извлекаем базовый образ
        self.data['base_image'] = self.data['dockerfile_info']['final_image']

        print("✅ Анализ завершён\n")

    # ===== ОПРЕДЕЛЕНИЕ ЯЗЫКА =====

    def _detect_language(self) -> Dict:
        """Определяет язык проекта"""
        priority = {'high': 3, 'medium': 2}
        detections = {}

        for language, markers in self.LANGUAGE_MARKERS.items():
            # Проверяем high priority
            for marker in markers['high']:
                if self._file_exists(marker):
                    detections[language] = ('high', marker)
                    break

            # Если не нашли high, проверяем medium
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

        # Выбираем язык с наивысшим приоритетом
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

    # ===== ОПРЕДЕЛЕНИЕ ВЕРСИИ =====

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
        """Определяет версию Python"""
        req_file = os.path.join(self.project_path, "requirements.txt")
        if os.path.exists(req_file):
            with open(req_file, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'python_requires.*?(3\.\d+)', content)
                if match:
                    return match.group(1)
        return "3.11"

    def _detect_go_version(self) -> str:
        """Определяет версию Go"""
        go_mod = os.path.join(self.project_path, "go.mod")
        if os.path.exists(go_mod):
            with open(go_mod, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('go '):
                        return line.split()[1].strip()
        return "1.21"

    def _detect_node_version(self) -> str:
        """Определяет версию Node.js"""
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
        """Определяет версию Java"""
        pom_xml = os.path.join(self.project_path, "pom.xml")
        if os.path.exists(pom_xml):
            with open(pom_xml, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'<source>(1\.\d+|11|17|21)</source>', content)
                if match:
                    return match.group(1)
        return "17"

    def _detect_php_version(self) -> str:
        """Определяет версию PHP"""
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
        """Определяет версию Rust"""
        rust_toolchain = os.path.join(self.project_path, "rust-toolchain")
        if os.path.exists(rust_toolchain):
            with open(rust_toolchain, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return "latest"

    def _detect_ruby_version(self) -> str:
        """Определяет версию Ruby"""
        ruby_version = os.path.join(self.project_path, ".ruby-version")
        if os.path.exists(ruby_version):
            with open(ruby_version, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return "3.2"

    # ===== DOCKERFILE =====

    def _parse_dockerfile(self) -> Dict:
        """Парсит существующий Dockerfile"""
        from dockerfile_parser import DockerfileParser

        parser = DockerfileParser(os.path.join(self.project_path, "Dockerfile"))
        return parser.get_summary()

    def _generate_dockerfile(self, language: str) -> Dict:
        """Генерирует Dockerfile и возвращает информацию о нём"""
        version = self.data['version']
        port = 3000

        template_str = self.DOCKERFILE_TEMPLATES.get(
            language,
            f"# Generated Dockerfile for {language}\nFROM alpine:latest\nWORKDIR /app\nCOPY . .\nEXPOSE {port}\nCMD [\"/bin/sh\"]\n"
        )

        template = Template(template_str)
        version_short = '.'.join(version.split('.')[:2])

        dockerfile_content = template.render(
            version=version,
            version_short=version_short,
            port=port
        )

        # Сохраняем Dockerfile
        dockerfile_path = os.path.join(self.project_path, "Dockerfile")
        with open(dockerfile_path, 'w', encoding='utf-8') as f:
            f.write(dockerfile_content)

        print(f"✅ Dockerfile сгенерирован ({language}:{version})")

        # Парсим сгенерированный Dockerfile
        from dockerfile_parser import DockerfileParser
        parser = DockerfileParser(dockerfile_path)
        return parser.get_summary()

    # ===== GETTERS =====

    def get_language(self) -> str:
        """Возвращает язык"""
        return self.data['language_info']['language']

    def get_version(self) -> str:
        """Возвращает версию языка"""
        return self.data['version']

    def get_base_image(self) -> str:
        """Возвращает базовый образ Docker"""
        return self.data['base_image']

    def get_port(self) -> int:
        """Возвращает порт приложения"""
        return self.data['port']

    def get_dockerfile_info(self) -> Dict:
        """Возвращает всю информацию о Dockerfile"""
        return self.data['dockerfile_info']

    def get_summary(self) -> Dict:
        """Возвращает полную сводку"""
        return {
            'language': self.get_language(),
            'version': self.get_version(),
            'base_image': self.get_base_image(),
            'port': self.get_port(),
            'dockerfile_exists': self.data['dockerfile_exists'],
            'dockerfile_info': self.get_dockerfile_info(),
            'language_info': self.data['language_info'],
        }
