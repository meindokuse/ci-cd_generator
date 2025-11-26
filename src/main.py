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


def main():
    parser = argparse.ArgumentParser(
        description='Генератор GitLab CI/CD конфигов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ОБЯЗАТЕЛЬНЫЕ ФЛАГИ:

  --sync={docker-registry|nexus|artifactory|gitlab-artifacts}
    Где хранить артефакты сборки

ОПЦИОНАЛЬНЫЕ ФЛАГИ:

  --docker-gen={true|false}
    Генерировать ли Dockerfile если его нет (default: false)

  --deploy={server|github}
    Что делать после сборки (опционально)

ПРИМЕРЫ:

  # Docker Registry + Deploy на сервер
  python main.py --sync docker-registry --deploy server

  # Docker с автогенерацией
  python main.py --docker-gen=true --sync docker-registry --deploy server

  # Nexus + GitHub Releases
  python main.py --sync nexus --deploy github

  # GitLab Artifacts + GitHub Releases
  python main.py --sync gitlab-artifacts --deploy github

  # Только синхронизация (без deploy)
  python main.py --sync nexus
  python main.py --sync artifactory
  python main.py --sync gitlab-artifacts
        """
    )

    parser.add_argument('--sync',
                       required=True,
                       choices=['docker-registry', 'nexus', 'artifactory', 'gitlab-artifacts'],
                       help='Где синхронизировать артефакты (ОБЯЗАТЕЛЬНО)')

    parser.add_argument('--docker-gen',
                       type=lambda x: x.lower() == 'true',
                       default=False,
                       help='Генерировать ли Dockerfile если его нет')

    parser.add_argument('--deploy',
                       choices=['server', 'github'],
                       help='Что делать после сборки (опционально)')

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

        print(f"✅ --sync: {args.sync}")
        if args.deploy:
            print(f"✅ --deploy: {args.deploy}")
        print()

        # Валидация
        print("ШАГ 2: Валидация комбинации флагов")
        print("-" * 70)

        try:
            validate_flags(args, summary['dockerfile_exists'])
            print("✅ Комбинация флагов валидна\n")
        except ValueError as e:
            print(f"\n{e}\n")
            sys.exit(1)

        # Генерация
        print("ШАГ 3: Генерация CI/CD")
        print("-" * 70)

        generator = FinalCIGenerator(analyzer, args.sync, args.deploy)
        generator.generate_all_stages()

        # Сохранение
        print("ШАГ 4: Сохранение")
        print("-" * 70)
        generator.save(".gitlab-ci.yml")

        # Итоги
        print("ШАГ 5: Итоги")
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
