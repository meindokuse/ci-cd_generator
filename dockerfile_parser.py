# dockerfile_parser.py

import os
import re
from typing import Dict, List, Optional


class DockerfileParser:
    """
    Парсер Dockerfile для извлечения информации
    Используется как для существующих, так и для сгенерированных Dockerfile
    """

    def __init__(self, dockerfile_path: str):
        self.dockerfile_path = dockerfile_path
        self._validate_file()
        self.content = self._read_file()
        self.lines = self.content.split('\n')

    def _validate_file(self) -> None:
        """Проверяет существование Dockerfile"""
        if not os.path.exists(self.dockerfile_path):
            raise FileNotFoundError(
                f"❌ Dockerfile не найден: {self.dockerfile_path}"
            )

    def _read_file(self) -> str:
        """Читает содержимое Dockerfile"""
        try:
            with open(self.dockerfile_path, 'r', encoding='utf-8') as f:
                return f.read()
        except IOError as e:
            raise IOError(f"Не удалось прочитать Dockerfile: {e}")

    def extract_base_images(self) -> List[str]:
        """Извлекает все базовые образы (FROM инструкции)"""
        images = []

        for line in self.lines:
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            if line.startswith('FROM '):
                rest = line[5:].strip()
                image = rest.split()[0] if rest.split() else None

                if image and image != 'scratch':
                    images.append(image)

        return images

    def get_final_base_image(self) -> str:
        """Возвращает финальный базовый образ"""
        images = self.extract_base_images()

        if not images:
            raise ValueError("В Dockerfile не найдено ни одной FROM инструкции!")

        return images[-1]

    def is_multistage(self) -> bool:
        """Проверяет, используется ли multi-stage build"""
        return len(self.extract_base_images()) > 1

    def extract_exposed_ports(self) -> List[int]:
        """Извлекает все порты из EXPOSE инструкций"""
        ports = []

        for line in self.lines:
            line = line.strip()

            if line.startswith('EXPOSE '):
                port_part = line[7:].strip()

                for port_str in port_part.split():
                    port_str = port_str.split('/')[0]

                    try:
                        port = int(port_str)
                        ports.append(port)
                    except ValueError:
                        pass

        return ports

    def get_primary_port(self) -> Optional[int]:
        """Возвращает основной порт приложения"""
        ports = self.extract_exposed_ports()
        return ports[0] if ports else None

    def extract_build_args(self) -> Dict[str, Optional[str]]:
        """Извлекает ARG инструкции"""
        args = {}

        for line in self.lines:
            line = line.strip()

            if line.startswith('ARG '):
                arg_part = line[4:].strip()

                if '=' in arg_part:
                    name, value = arg_part.split('=', 1)
                    args[name.strip()] = value.strip()
                else:
                    args[arg_part.strip()] = None

        return args

    def extract_env_vars(self) -> Dict[str, str]:
        """Извлекает ENV инструкции"""
        env_vars = {}

        for line in self.lines:
            line = line.strip()

            if line.startswith('ENV '):
                env_part = line[4:].strip()

                if '=' in env_part:
                    name, value = env_part.split('=', 1)
                    env_vars[name.strip()] = value.strip()
                else:
                    parts = env_part.split(None, 1)
                    if len(parts) == 2:
                        env_vars[parts[0]] = parts[1]

        return env_vars

    def has_healthcheck(self) -> bool:
        """Проверяет наличие HEALTHCHECK"""
        return any(line.strip().startswith('HEALTHCHECK') for line in self.lines)

    def extract_workdir(self) -> Optional[str]:
        """Извлекает рабочую директорию (WORKDIR)"""
        workdir = None

        for line in self.lines:
            line = line.strip()

            if line.startswith('WORKDIR '):
                workdir = line[8:].strip()

        return workdir

    def extract_entrypoint(self) -> Optional[str]:
        """Извлекает ENTRYPOINT"""
        entrypoint = None

        for line in self.lines:
            line = line.strip()

            if line.startswith('ENTRYPOINT '):
                entrypoint = line[11:].strip()

        return entrypoint

    def extract_cmd(self) -> Optional[str]:
        """Извлекает CMD"""
        cmd = None

        for line in self.lines:
            line = line.strip()

            if line.startswith('CMD '):
                cmd = line[4:].strip()

        return cmd

    def get_summary(self) -> Dict:
        """Возвращает полную сводку по Dockerfile"""
        return {
            'base_images': self.extract_base_images(),
            'final_image': self.get_final_base_image(),
            'is_multistage': self.is_multistage(),
            'ports': self.extract_exposed_ports(),
            'primary_port': self.get_primary_port(),
            'build_args': self.extract_build_args(),
            'env_vars': self.extract_env_vars(),
            'workdir': self.extract_workdir(),
            'entrypoint': self.extract_entrypoint(),
            'cmd': self.extract_cmd(),
            'has_healthcheck': self.has_healthcheck(),
        }
