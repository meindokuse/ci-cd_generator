#!/usr/bin/env python3

import sys
import os
import argparse
import subprocess
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from project_analyzer import ProjectAnalyzer
from final_ci_generator import FinalCIGenerator


def clone_repository(git_url: str, target_dir: str) -> bool:
    """Клонирует git репозиторий"""
    try:
        print(f"📥 Клонирую репозиторий: {git_url}")
        subprocess.run(
            ['git', 'clone', '--depth', '1', git_url, target_dir],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ Репозиторий склонирован в {target_dir}\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка клонирования: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Git не установлен!")
        return False


def validate_flags(args, dockerfile_exists: bool):
    """Валидирует комбинацию флагов"""

    # Правило 1: docker-registry требует Docker
    if args.sync == 'docker-registry':
        if not dockerfile_exists and not args.docker_gen:
            raise ValueError(
                "❌ --sync docker-registry требует Dockerfile!\n"
                "   Используйте --docker-gen=true для автогенерации"
            )

    # Правило 2: Если есть Dockerfile, нельзя nexus/artifactory
    if dockerfile_exists and args.sync in ['nexus', 'artifactory']:
        raise ValueError(
            "❌ Конфликт: Dockerfile + --sync nexus/artifactory!\n"
            "   Docker стратегия требует --sync docker-registry\n"
            "   Удалите Dockerfile или используйте --sync docker-registry"
        )

    # Правило 3: docker-gen + nexus/artifactory = конфликт
    if args.docker_gen and args.sync in ['nexus', 'artifactory']:
        raise ValueError(
            "❌ --docker-gen=true + --sync nexus/artifactory = конфликт!\n"
            "   --docker-gen генерирует Dockerfile\n"
            "   Используйте --sync docker-registry"
        )

    # Правило 4: server deploy требует docker-registry
    if args.deploy == 'server' and args.sync != 'docker-registry':
        raise ValueError(
            "❌ --deploy server требует --sync docker-registry\n"
            "   (server deploy работает только с Docker образами)"
        )

    # Правило 5: github deploy + docker-registry = несовместимо
    if args.deploy == 'github' and args.sync == 'docker-registry':
        raise ValueError(
            "❌ --deploy github + --sync docker-registry = несовместимо!\n"
            "   GitHub Releases для артефактов, не образов\n"
            "   Используйте --sync nexus/artifactory/gitlab-artifacts"
        )


def detect_defaults(dockerfile_exists: bool) -> tuple:
    """Определяет дефолтные значения"""
    if dockerfile_exists:
        return ('docker-registry', 'server')
    else:
        return ('nexus', 'github')


def main():
    parser = argparse.ArgumentParser(
        description='Генератор GitLab CI/CD конфигов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ПРИМЕРЫ:

  # Локальный проект (текущая директория)
  python main.py

  # Git репозиторий
  python main.py --repo https://gitlab.com/myuser/myproject.git

  # С флагами
  python main.py --repo https://gitlab.com/myuser/myproject.git --sync docker-registry --deploy server

  # Автогенерация Dockerfile
  python main.py --repo https://gitlab.com/myuser/myproject.git --docker-gen=true
        """
    )

    parser.add_argument('--repo',
                        type=str,
                        default=None,
                        help='URL Git репозитория (опционально, по умолчанию текущая директория)')

    parser.add_argument('--sync',
                        choices=['docker-registry', 'nexus', 'artifactory', 'gitlab-artifacts'],
                        default=None,
                        help='Где синхронизировать артефакты')

    parser.add_argument('--docker-gen',
                        type=lambda x: x.lower() == 'true',
                        default=False,
                        help='Генерировать ли Dockerfile')

    parser.add_argument('--deploy',
                        choices=['server', 'github'],
                        default=None,
                        help='Что делать после сборки')

    parser.add_argument('--output',
                        type=str,
                        default='.gitlab-ci.yml',
                        help='Путь к выходному файлу (default: .gitlab-ci.yml)')

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("🚀 ГЕНЕРАТОР GITLAB CI/CD")
    print("=" * 70 + "\n")

    temp_dir = None
    project_path = "."

    try:
        # Если передан --repo, клонируем во временную директорию
        if args.repo:
            temp_dir = tempfile.mkdtemp(prefix='cicd_gen_')
            project_path = temp_dir

            print("ШАГ 0: Клонирование репозитория")
            print("-" * 70)
            if not clone_repository(args.repo, project_path):
                sys.exit(1)

        # Анализ проекта
        print("ШАГ 1: Анализ проекта")
        print("-" * 70)

        analyzer = ProjectAnalyzer(project_path, docker_gen=args.docker_gen)
        summary = analyzer.get_summary()

        dockerfile_exists = summary['dockerfile_exists']
        language = summary['language']

        print(f"✅ Язык: {language}")
        print(f"✅ Dockerfile: {'Найден ✅' if dockerfile_exists else 'Не найден ❌'}")
        print()

        # Автоопределение
        print("ШАГ 2: Определение конфигурации")
        print("-" * 70)

        if args.sync is None or args.deploy is None:
            print("🔍 Автоопределение параметров...")
            default_sync, default_deploy = detect_defaults(dockerfile_exists)

            if args.sync is None:
                args.sync = default_sync
                print(f"   → --sync: {args.sync} (автоопределение)")
            else:
                print(f"   → --sync: {args.sync} (явно указано)")

            if args.deploy is None:
                args.deploy = default_deploy
                print(f"   → --deploy: {args.deploy} (автоопределение)")
            else:
                print(f"   → --deploy: {args.deploy} (явно указано)")
        else:
            print(f"✅ --sync: {args.sync}")
            print(f"✅ --deploy: {args.deploy}")

        print()

        # Валидация
        print("ШАГ 3: Валидация")
        print("-" * 70)

        try:
            validate_flags(args, dockerfile_exists)
            print("✅ Валидация пройдена\n")
        except ValueError as e:
            print(f"\n{e}\n")
            sys.exit(1)

        # Генерация
        print("ШАГ 4: Генерация CI/CD")
        print("-" * 70)

        generator = FinalCIGenerator(analyzer, args.sync, args.deploy)
        generator.generate_all_stages()

        # Сохранение
        print("ШАГ 5: Сохранение")
        print("-" * 70)

        # Если работали с временной директорией, сохраняем в текущую
        if temp_dir:
            output_path = args.output
        else:
            output_path = os.path.join(project_path, args.output)

        generator.save(output_path)

        # Итоги
        print("ШАГ 6: Итоги")
        print("-" * 70)
        generator.print_summary()

        print("\n" + "=" * 70)
        print("✅ ВСЁ ГОТОВО!")
        print(f"📁 Результат: {output_path}")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        # Очищаем временную директорию
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"🧹 Временная директория удалена: {temp_dir}")


if __name__ == "__main__":
    main()
