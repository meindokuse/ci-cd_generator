# src/env_analyzer.py

import os
import re
from typing import Dict, List


class EnvAnalyzer:
    """Анализирует .env файлы и генерирует GitLab CI/CD переменные"""

    # Паттерны для определения типа переменной
    SENSITIVE_PATTERNS = [
        r'.*password.*',
        r'.*secret.*',
        r'.*key.*',
        r'.*token.*',
        r'.*api.*key.*',
        r'.*private.*',
        r'.*credential.*',
        r'.*auth.*',
    ]

    DATABASE_PATTERNS = [
        r'.*database.*',
        r'.*db.*',
        r'.*postgres.*',
        r'.*mysql.*',
        r'.*mongo.*',
        r'.*redis.*',
    ]

    def __init__(self, project_path: str = "."):
        self.project_path = project_path
        self.env_vars = {}
        self.env_files = []
        self._analyze()

    def _analyze(self):
        """Находим и парсим все .env файлы"""
        print("🔍 Анализирую переменные окружения...")

        # Ищем .env файлы
        env_patterns = [
            '.env',
            '.env.example',
            '.env.local',
            '.env.development',
            '.env.production',
            '.env.test',
        ]

        for pattern in env_patterns:
            env_path = os.path.join(self.project_path, pattern)
            if os.path.exists(env_path):
                self.env_files.append(pattern)
                self._parse_env_file(env_path, pattern)

        if self.env_vars:
            print(f"✅ Найдено переменных окружения: {len(self.env_vars)}")
            for var_name, var_info in list(self.env_vars.items())[:5]:
                print(f"   → {var_name} ({var_info['type']})")
            if len(self.env_vars) > 5:
                print(f"   ... и ещё {len(self.env_vars) - 5}")
        else:
            print("⚠️  Переменные окружения не найдены")
            print("   💡 Рекомендуется создать .env.example")

    def _parse_env_file(self, filepath: str, filename: str):
        """Парсит .env файл"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Пропускаем комментарии и пустые строки
                    if not line or line.startswith('#'):
                        continue

                    # Парсим KEY=VALUE
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")

                        # Определяем тип переменной
                        var_type = self._classify_variable(key, value)

                        self.env_vars[key] = {
                            'value': value if not self._is_sensitive(key) else '***',
                            'type': var_type,
                            'source': filename,
                            'line': line_num,
                            'is_sensitive': self._is_sensitive(key),
                            'is_required': self._is_required(key),
                        }
        except Exception as e:
            print(f"⚠️  Ошибка парсинга {filepath}: {e}")

    def _classify_variable(self, key: str, value: str) -> str:
        """Определяет тип переменной"""
        key_lower = key.lower()

        if self._is_sensitive(key):
            return 'secret'
        elif any(re.match(pattern, key_lower) for pattern in self.DATABASE_PATTERNS):
            return 'database'
        elif key_lower.startswith('ci_') or key_lower.startswith('gitlab_'):
            return 'ci'
        elif key_lower in ['debug', 'environment', 'env', 'node_env']:
            return 'config'
        elif key_lower.endswith('_url') or key_lower.endswith('_endpoint'):
            return 'url'
        elif key_lower.endswith('_port'):
            return 'port'
        else:
            return 'general'

    def _is_sensitive(self, key: str) -> bool:
        """Проверяет, является ли переменная чувствительной"""
        key_lower = key.lower()
        return any(re.match(pattern, key_lower) for pattern in self.SENSITIVE_PATTERNS)

    def _is_required(self, key: str) -> bool:
        """Определяет, обязательна ли переменная"""
        required_vars = [
            'DATABASE_URL',
            'DATABASE_HOST',
            'DB_HOST',
            'POSTGRES_HOST',
            'REDIS_URL',
            'SECRET_KEY',
            'JWT_SECRET',
        ]
        return key.upper() in required_vars

    def generate_gitlab_variables_documentation(self) -> str:
        """Генерирует документацию для GitLab CI/CD переменных"""
        if not self.env_vars:
            return ""

        doc = "# GitLab CI/CD Variables\n\n"
        doc += "## Требуемые переменные окружения\n\n"
        doc += "Добавьте следующие переменные в GitLab:\n\n"
        doc += "**Путь:** `Settings → CI/CD → Variables`\n\n"

        # Группируем по типам
        by_type = {}
        for var_name, var_info in self.env_vars.items():
            var_type = var_info['type']
            if var_type not in by_type:
                by_type[var_type] = []
            by_type[var_type].append((var_name, var_info))

        # Выводим по группам
        type_names = {
            'secret': '🔒 Секреты',
            'database': '🗄️ База данных',
            'url': '🔗 URL endpoints',
            'config': '⚙️ Конфигурация',
            'ci': '🔄 CI/CD',
            'port': '🔌 Порты',
            'general': '📋 Общие',
        }

        for var_type, vars_list in sorted(by_type.items()):
            doc += f"### {type_names.get(var_type, var_type.title())}\n\n"
            doc += "| Variable | Type | Protected | Masked | Example |\n"
            doc += "|----------|------|-----------|--------|----------|\n"

            for var_name, var_info in vars_list:
                protected = '✅' if var_info['is_sensitive'] else '❌'
                masked = '✅' if var_info['is_sensitive'] else '❌'
                example = var_info['value'] if not var_info['is_sensitive'] else '<SET_YOUR_VALUE>'

                doc += f"| `{var_name}` | Variable | {protected} | {masked} | `{example}` |\n"

            doc += "\n"

        # Инструкция
        doc += "---\n\n"
        doc += "## Как добавить переменные в GitLab\n\n"
        doc += "1. Откройте ваш проект в GitLab\n"
        doc += "2. Перейдите: **Settings → CI/CD**\n"
        doc += "3. Разверните секцию **Variables**\n"
        doc += "4. Нажмите **Add variable**\n"
        doc += "5. Заполните:\n"
        doc += "   - **Key**: Имя переменной (например, `DATABASE_URL`)\n"
        doc += "   - **Value**: Значение переменной\n"
        doc += "   - **Type**: `Variable`\n"
        doc += "   - **Protect variable**: ✅ для чувствительных данных\n"
        doc += "   - **Mask variable**: ✅ для секретов (они не будут видны в логах)\n"
        doc += "6. Нажмите **Add variable**\n\n"

        return doc

    def generate_gitlab_ci_env_section(self) -> str:
        """Генерирует секцию variables для .gitlab-ci.yml"""
        if not self.env_vars:
            return ""

        # Только НЕ-чувствительные переменные идут в .gitlab-ci.yml
        non_sensitive = {
            k: v for k, v in self.env_vars.items()
            if not v['is_sensitive'] and v['type'] in ['config', 'general', 'port']
        }

        if not non_sensitive:
            return ""

        yml = "variables:\n"
        yml += "  # Non-sensitive environment variables\n"
        for var_name, var_info in non_sensitive.items():
            yml += f"  {var_name}: \"{var_info['value']}\"\n"

        yml += "\n  # Sensitive variables (passwords, secrets, keys) should be set in:\n"
        yml += "  # GitLab → Settings → CI/CD → Variables\n"
        yml += "  # See GITLAB_VARIABLES.md for details\n"

        return yml

    def generate_env_example(self) -> str:
        """Генерирует .env.example файл"""
        if not self.env_vars:
            return ""

        content = "# Environment Variables Example\n"
        content += "# Copy this file to .env and fill in your values\n"
        content += "# DO NOT COMMIT .env TO GIT!\n\n"

        # Группируем по типам
        by_type = {}
        for var_name, var_info in self.env_vars.items():
            var_type = var_info['type']
            if var_type not in by_type:
                by_type[var_type] = []
            by_type[var_type].append((var_name, var_info))

        type_names = {
            'secret': 'Secrets (DO NOT COMMIT REAL VALUES)',
            'database': 'Database Configuration',
            'url': 'Service URLs',
            'config': 'Application Configuration',
            'ci': 'CI/CD Configuration',
            'port': 'Ports',
            'general': 'General Settings',
        }

        for var_type, vars_list in sorted(by_type.items()):
            content += f"# {type_names.get(var_type, var_type.title())}\n"

            for var_name, var_info in vars_list:
                if var_info['is_sensitive']:
                    content += f"{var_name}=<YOUR_{var_name}_HERE>\n"
                else:
                    content += f"{var_name}={var_info['value']}\n"

            content += "\n"

        return content

    def get_summary(self) -> Dict:
        """Возвращает сводку"""
        return {
            'env_files': self.env_files,
            'total_vars': len(self.env_vars),
            'sensitive_vars': len([v for v in self.env_vars.values() if v['is_sensitive']]),
            'required_vars': len([v for v in self.env_vars.values() if v['is_required']]),
            'variables': self.env_vars,
        }
