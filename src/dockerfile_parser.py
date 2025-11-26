# dockerfile_parser.py

import os
from typing import Dict, List, Optional


class DockerfileParser:
    """Парсер Dockerfile"""

    def __init__(self, dockerfile_path: str):
        self.dockerfile_path = dockerfile_path
        self._validate_file()
        self.content = self._read_file()
        self.lines = self.content.split('\n')

    def _validate_file(self) -> None:
        if not os.path.exists(self.dockerfile_path):
            raise FileNotFoundError(f"❌ Dockerfile не найден: {self.dockerfile_path}")

    def _read_file(self) -> str:
        try:
            with open(self.dockerfile_path, 'r', encoding='utf-8') as f:
                return f.read()
        except IOError as e:
            raise IOError(f"❌ Не удалось прочитать Dockerfile: {e}")

    def extract_base_images(self) -> List[str]:
        """Извлекает FROM инструкции"""
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
            raise ValueError("❌ В Dockerfile нет FROM инструкции!")
        return images[-1]

    def is_multistage(self) -> bool:
        """Проверяет multi-stage build"""
        return len(self.extract_base_images()) > 1

    def extract_exposed_ports(self) -> List[int]:
        """Извлекает EXPOSE инструкции"""
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
        ports = self.extract_exposed_ports()
        return ports[0] if ports else 3000

    def get_summary(self) -> Dict:
        return {
            'base_images': self.extract_base_images(),
            'final_image': self.get_final_base_image(),
            'is_multistage': self.is_multistage(),
            'ports': self.extract_exposed_ports(),
            'primary_port': self.get_primary_port(),
        }
