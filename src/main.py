#!/usr/bin/env python3

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from project_analyzer import ProjectAnalyzer
from final_ci_generator import FinalCIGenerator


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
    """
    Определяет дефолтные значения если флаги не переданы

    Логика:
    - Если Dockerfile есть → docker-registry + server
    - Если Dockerfile нет → nexus + github

    Returns:
        (sync_target, deploy_target)
    """
    if dockerfile_exists:
        return ('docker-registry', 'server')
    else:
        return ('nexus', 'github')


def main():
    parser = argparse.ArgumentParser(
        description='Генератор GitLab CI/CD конфигов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ОПЦИОНАЛЬНЫЕ ФЛАГИ:

  --sync={docker-registry|nexus|artifactory|gitlab-artifacts}
    Где хранить артефакты сборки
    (default: docker-registry если Dockerfile есть, иначе nexus)

  --docker-gen={true|false}
    Генерировать ли Dockerfile если его нет (default: false)

  --deploy={server|github}
    Что делать после сборки
    (default: server если Dockerfile есть, иначе github)

ПРИМЕРЫ:

  # Без флагов: автоопределение
  python main.py
  # Если Dockerfile есть:   --sync docker-registry --deploy server
  # Если Dockerfile нет:    --sync nexus --deploy github

  # Явно Docker Registry + Server Deploy
  python main.py --sync docker-registry --deploy server

  # Docker с автогенерацией
  python main.py --docker-gen=true --sync docker-registry --deploy server

  # Явно Nexus + GitHub Releases
  python main.py --sync nexus --deploy github

  # GitLab Artifacts + GitHub Releases
  python main.py --sync gitlab-artifacts --deploy github

  # Только синхронизация (без deploy)
  python main.py --sync nexus
  python main.py --sync artifactory
  python main.py --sync gitlab-artifacts

  # Только build (без deploy)
  python main.py --sync docker-registry
        """
    )

    parser.add_argument('--sync',
                        choices=['docker-registry', 'nexus', 'artifactory', 'gitlab-artifacts'],
                        default=None,  # ← None = автоопределение
                        help='Где синхронизировать артефакты (опционально, автоопределение)')

    parser.add_argument('--docker-gen',
                        type=lambda x: x.lower() == 'true',
                        default=False,
                        help='Генерировать ли Dockerfile если его нет')

    parser.add_argument('--deploy',
                        choices=['server', 'github'],
                        default=None,  # ← None = автоопределение
                        help='Что делать после сборки (опционально, автоопределение)')

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("🚀 ГЕНЕРАТОР GITLAB CI/CD")
    print("=" * 70 + "\n")

    try:
        # Анализ проекта
        print("ШАГ 1: Анализ проекта")
        print("-" * 70)

        analyzer = ProjectAnalyzer(".", docker_gen=args.docker_gen)
        summary = analyzer.get_summary()

        dockerfile_exists = summary['dockerfile_exists']
        language = summary['language']

        print(f"✅ Язык: {language}")
        print(f"✅ Dockerfile: {'Найден ✅' if dockerfile_exists else 'Не найден ❌'}")
        print()

        # Автоопределение если флаги не переданы
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
            print(f"✅ --sync: {args.sync} (явно указано)")
            print(f"✅ --deploy: {args.deploy} (явно указано)")

        print()

        # Валидация
        print("ШАГ 3: Валидация комбинации флагов")
        print("-" * 70)

        try:
            validate_flags(args, dockerfile_exists)
            print("✅ Комбинация флагов валидна\n")
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
        generator.save(".gitlab-ci.yml")

        # Итоги
        print("ШАГ 6: Итоги")
        print("-" * 70)
        generator.print_summary()

        print("\n" + "=" * 70)
        print("✅ ВСЁ ГОТОВО!")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
