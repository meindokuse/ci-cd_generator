# src/main.py

import os
import sys
import argparse
import tempfile
import shutil
from git import Repo
from project_analyzer import ProjectAnalyzer
from final_ci_generator import FinalCIGenerator


def main():
    parser = argparse.ArgumentParser(description='GitLab CI/CD Generator')
    parser.add_argument('--repo', help='Git repository URL or local path')
    parser.add_argument('--sync', default='docker-registry',
                        choices=['docker-registry', 'nexus', 's3', 'artifactory', 'gitlab-artifacts'],
                        help='Artifact sync target')
    parser.add_argument('--deploy', default='server',
                        choices=['server', 'k8s', 'github'],
                        help='Deployment target')
    parser.add_argument('--docker-gen', action='store_true',
                        help='Generate Dockerfile if missing')
    parser.add_argument('--output', default='/output',
                        help='Output directory')

    args = parser.parse_args()

    print("=" * 70)
    print("🚀 ГЕНЕРАТОР GITLAB CI/CD")
    print("=" * 70)

    # Шаг 0: Клонирование репозитория (если URL)
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

    # Шаг 1: Анализ проекта
    print("\nШАГ 1: Анализ проекта")
    print("-" * 70)

    try:
        analyzer = ProjectAnalyzer(project_path, docker_gen=args.docker_gen)
        summary = analyzer.get_summary()

        print(f"\n✅ Язык: {summary['language']}")
        print(f"✅ Dockerfile: {'Найден ✅' if summary['dockerfile_exists'] else 'Не найден ❌'}")

    except Exception as e:
        print(f"\n❌ Ошибка анализа: {e}")
        sys.exit(1)

    # Шаг 2: Определение конфигурации
    print("\nШАГ 2: Определение конфигурации")
    print("-" * 70)
    print(f"✅ --sync: {args.sync}")
    print(f"✅ --deploy: {args.deploy}")

    # Шаг 3: Валидация
    print("\nШАГ 3: Валидация")
    print("-" * 70)

    if not summary['dockerfile_exists']:
        print("❌ Dockerfile не найден!")
        if not args.docker_gen:
            print("   💡 Используйте --docker-gen для автоматической генерации")
            sys.exit(1)

    print("✅ Валидация пройдена")

    # Шаг 4: Генерация CI/CD
    print("\nШАГ 4: Генерация CI/CD")
    print("-" * 70)

    generator = FinalCIGenerator(analyzer, args.sync, args.deploy)
    generator.generate_all_stages()

    # Шаг 5: Сохранение
    print("\nШАГ 5: Сохранение")
    print("-" * 70)

    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    # Сохраняем .gitlab-ci.yml
    output_path = os.path.join(output_dir, '.gitlab-ci.yml')
    generator.save(output_path)

    # ========== НОВОЕ: Генерируем документацию по переменным ==========
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

    # Шаг 6: Итоги
    print("\nШАГ 6: Итоги")
    print("-" * 70)

    generator.print_summary()

    print()
    print("=" * 70)
    print("✅ ВСЁ ГОТОВО!")
    print(f"📁 Результат: {output_path}")

    # ========== НОВОЕ: Вывод дополнительных файлов ==========
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
        shutil.rmtree(temp_dir)
        print(f"\n🧹 Временная директория удалена: {temp_dir}")


if __name__ == '__main__':
    main()
