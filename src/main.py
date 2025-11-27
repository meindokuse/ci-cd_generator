# src/main.py

import os
import sys
import argparse
import tempfile
import shutil
from git import Repo
from project_analyzer import ProjectAnalyzer
from final_ci_generator import FinalCIGenerator

# ============ ВАЛИДАЦИЯ КОМБИНАЦИЙ ============

VALID_COMBINATIONS = {
    # sync → deploy
    'docker-registry': ['server', 'k8s'],
    'nexus': ['server', 'github'],
    'artifactory': ['server', 'github'],
    'gitlab-artifacts': ['server', 'github'],
}


def validate_combination(sync: str, deploy: str) -> bool:
    """Проверяет валидность комбинации sync + deploy"""
    if sync not in VALID_COMBINATIONS:
        return False

    return deploy in VALID_COMBINATIONS[sync]


def suggest_valid_deploy(sync: str) -> list:
    """Возвращает список валидных deploy для данного sync"""
    return VALID_COMBINATIONS.get(sync, [])


# ============ АВТООПРЕДЕЛЕНИЕ ============

def auto_detect_sync_deploy(analyzer: ProjectAnalyzer) -> dict:
    """Автоматически определяет sync и deploy на основе анализа проекта"""

    summary = analyzer.get_summary()

    # По умолчанию
    sync = 'docker-registry'
    deploy = 'server'

    # Если есть Dockerfile → docker-registry
    if summary.get('dockerfile_exists'):
        sync = 'docker-registry'
        deploy = 'server'

    # Если есть docker-compose.yml → определённо server deploy
    if summary.get('docker_compose_exists'):
        sync = 'docker-registry'
        deploy = 'server'

    # Если monorepo → docker-registry + server
    if summary.get('is_monorepo'):
        sync = 'docker-registry'
        deploy = 'server'

    # Если артефакты (jar, whl, tgz) → nexus + github
    artifact_type = summary.get('artifact_paths', {}).get('artifact_type')
    if artifact_type in ['jar', 'wheel', 'npm', 'gem']:
        sync = 'nexus'
        deploy = 'github'

    return {
        'sync': sync,
        'deploy': deploy,
        'reason': f"Автоопределено на основе анализа проекта"
    }


# ============ MAIN ============

def main():
    parser = argparse.ArgumentParser(
        description='GitLab CI/CD Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Автоопределение sync и deploy
  python main.py --repo /path/to/project

  # Явное указание sync и deploy
  python main.py --repo /path/to/project --sync docker-registry --deploy server

  # Клонирование из Git и генерация
  python main.py --repo https://github.com/user/repo.git --sync nexus --deploy github

  # Генерация Dockerfile если отсутствует
  python main.py --repo /path/to/project --docker-gen

Валидные комбинации sync → deploy:
  docker-registry  → server, k8s
  nexus            → server, github
  artifactory      → server, github
  gitlab-artifacts → server, github
        """
    )

    parser.add_argument('--repo', help='Git repository URL or local path')
    parser.add_argument('--sync', default=None,
                        choices=['docker-registry', 'nexus', 's3', 'artifactory', 'gitlab-artifacts'],
                        help='Artifact sync target (auto-detect if not specified)')
    parser.add_argument('--deploy', default=None,
                        choices=['server', 'k8s', 'github'],
                        help='Deployment target (auto-detect if not specified)')
    parser.add_argument('--docker-gen', action='store_true',
                        help='Generate Dockerfile if missing')
    parser.add_argument('--output', default='/output',
                        help='Output directory')

    args = parser.parse_args()

    print("=" * 70)
    print("🚀 ГЕНЕРАТОР GITLAB CI/CD")
    print("=" * 70)

    # ============ Шаг 0: Клонирование репозитория ============

    if args.repo and (args.repo.startswith('http') or args.repo.startswith('git@')):
        print("\nШАГ 0: Клонирование репозитория")
        print("-" * 70)
        print(f"📥 Клонирую репозиторий: {args.repo}")

        temp_dir = tempfile.mkdtemp(prefix='cicd_gen_')
        try:
            Repo.clone_from(args.repo, temp_dir)
            print(f"✅ Репозиторий склонирован в {temp_dir}")
            project_path = temp_dir
        except Exception as e:
            print(f"❌ Ошибка клонирования: {e}")
            sys.exit(1)
    elif args.repo:
        project_path = args.repo
    else:
        project_path = "."

    # ============ Шаг 1: Анализ проекта ============

    print("\nШАГ 1: Анализ проекта")
    print("-" * 70)

    try:
        analyzer = ProjectAnalyzer(project_path, docker_gen=args.docker_gen)
        print("dssdsdsdfsdfsdbfhsjNJDFHSBFSDKJFNSBDFHS ",project_path)
        summary = analyzer.get_summary()

        print(f"\n✅ Язык: {summary['language']}")
        print(f"✅ Версия: {summary['version']}")

        if summary.get('framework'):
            print(f"✅ Фреймворк: {summary['framework']}")

        print(f"✅ Dockerfile: {'Найден ✅' if summary['dockerfile_exists'] else 'Не найден ❌'}")

        if summary.get('docker_compose_exists'):
            print(f"✅ docker-compose.yml: Найден ✅")

        if summary.get('is_monorepo'):
            print(f"✅ Monorepo: {len(summary['services'])} сервисов")

    except Exception as e:
        print(f"\n❌ Ошибка анализа: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ============ Шаг 2: Определение sync и deploy ============

    print("\nШАГ 2: Определение конфигурации")
    print("-" * 70)

    # Если не указаны явно → автоопределение
    if args.sync is None or args.deploy is None:
        print("⚙️  Автоопределение sync и deploy...")
        auto_config = auto_detect_sync_deploy(analyzer)

        sync = args.sync or auto_config['sync']
        deploy = args.deploy or auto_config['deploy']

        print(f"✅ Автоопределено:")
        print(f"   → sync: {sync}")
        print(f"   → deploy: {deploy}")
        print(f"   → причина: {auto_config['reason']}")
    else:
        sync = args.sync
        deploy = args.deploy
        print(f"✅ Указано вручную:")
        print(f"   → sync: {sync}")
        print(f"   → deploy: {deploy}")

    # ============ Шаг 3: Валидация комбинации ============

    print("\nШАГ 3: Валидация")
    print("-" * 70)

    # Проверка комбинации sync + deploy
    if not validate_combination(sync, deploy):
        print(f"❌ Неверная комбинация: {sync} → {deploy}")
        print()
        print("Валидные комбинации:")
        for s, d_list in VALID_COMBINATIONS.items():
            print(f"  {s:20} → {', '.join(d_list)}")
        print()

        valid_deploys = suggest_valid_deploy(sync)
        if valid_deploys:
            print(f"💡 Для --sync {sync} доступны:")
            for d in valid_deploys:
                print(f"   --deploy {d}")

        sys.exit(1)

    print(f"✅ Комбинация {sync} → {deploy} валидна")

    # Проверка Dockerfile
    if not summary['dockerfile_exists'] and sync == 'docker-registry':
        print("⚠️  Dockerfile не найден!")
        if args.docker_gen:
            print("✅ Dockerfile будет сгенерирован автоматически")
        else:
            print("❌ Для docker-registry требуется Dockerfile")
            print("   💡 Используйте --docker-gen для автоматической генерации")
            print("   💡 Или используйте --sync nexus/artifactory/gitlab-artifacts")
            sys.exit(1)

    print("✅ Валидация пройдена")

    # ============ Шаг 4: Генерация CI/CD ============

    print("\nШАГ 4: Генерация CI/CD")
    print("-" * 70)

    try:
        generator = FinalCIGenerator(analyzer, sync, deploy)
        generator.generate_all_stages()
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ============ Шаг 5: Сохранение ============

    print("\nШАГ 5: Сохранение")
    print("-" * 70)

    output_dir = '/output'
    os.makedirs(output_dir, exist_ok=True)

    # Сохраняем .gitlab-ci.yml
    output_path = os.path.join(output_dir, '.gitlab-ci.yml')
    try:
        generator.save(output_path)
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        sys.exit(1)

    # ========== Генерируем документацию по переменным ==========
    if hasattr(analyzer, 'env_analyzer') and analyzer.env_analyzer.env_vars:
        # GITLAB_VARIABLES.md
        vars_doc = analyzer.env_analyzer.generate_gitlab_variables_documentation()
        vars_doc_path = os.path.join(output_dir, 'GITLAB_VARIABLES.md')

        with open(vars_doc_path, 'w', encoding='utf-8') as f:
            f.write(vars_doc)

        print(f"✅ Документация по переменным: {vars_doc_path}")

        # .env.example
        env_example = analyzer.env_analyzer.generate_env_example()
        env_example_path = os.path.join(output_dir, '.env.example')

        with open(env_example_path, 'w', encoding='utf-8') as f:
            f.write(env_example)

        print(f"✅ Шаблон переменных: {env_example_path}")

    # ============ Шаг 6: Итоги ============

    print("\nШАГ 6: Итоги")
    print("-" * 70)

    generator.print_summary()

    print()
    print("=" * 70)
    print("✅ ВСЁ ГОТОВО!")
    print(f"📁 Результат: {output_path}")

    # Вывод дополнительных файлов
    if hasattr(analyzer, 'env_analyzer') and analyzer.env_analyzer.env_vars:
        print(f"📁 Документация переменных: {vars_doc_path}")
        print(f"📁 Шаблон .env: {env_example_path}")
        print()
        print("💡 Не забудьте:")
        print("   1. Добавить переменные в GitLab CI/CD (см. GITLAB_VARIABLES.md)")
        print("   2. Скопировать .env.example → .env для локальной разработки")

    print("=" * 70)

    # Очистка временной директории
    if args.repo and (args.repo.startswith('http') or args.repo.startswith('git@')):
        try:
            shutil.rmtree(temp_dir)
            print(f"\n🧹 Временная директория удалена: {temp_dir}")
        except:
            pass


if __name__ == '__main__':
    main()
