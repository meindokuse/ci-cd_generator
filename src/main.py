#!/usr/bin/env python3
"""
Генератор CI/CD конфига для GitLab
Поддерживает: Python, Go, Node, Java, PHP, Rust, Ruby

Процесс:
1. ProjectAnalyzer анализирует проект (язык, версия, Dockerfile)
2. FinalCIGenerator генерирует все stage'и
3. Сохраняет .gitlab-ci.yml и Dockerfile (если его не было)
"""

import sys
import os

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from project_analyzer import ProjectAnalyzer
from final_ci_generator import FinalCIGenerator


def main():
    print("\n" + "=" * 70)
    print("🚀 ГЕНЕРАТОР GITLAB CI/CD")
    print("=" * 70 + "\n")

    try:
        # ===== ШАГ 1: АНАЛИЗ ПРОЕКТА =====
        print("ШАГ 1: Анализ проекта")
        print("-" * 70)

        analyzer = ProjectAnalyzer("..")
        summary = analyzer.get_summary()

        print(f"✅ Язык: {summary['language']}")
        print(f"✅ Версия: {summary['version']}")
        print(f"✅ Образ: {summary['base_image']}")
        print(f"✅ Порт: {summary['port']}")
        print(f"✅ Dockerfile: {'Найден' if summary['dockerfile_exists'] else 'Сгенерирован'}")
        print()

        # ===== ШАГ 2: ГЕНЕРАЦИЯ CI/CD =====
        print("ШАГ 2: Генерация CI/CD конфига")
        print("-" * 70)

        generator = FinalCIGenerator(analyzer)
        generator.generate_all_stages()

        # ===== ШАГ 3: СОХРАНЕНИЕ =====
        print("ШАГ 3: Сохранение файлов")
        print("-" * 70)

        generator.save(".gitlab-ci.yml")

        # ===== ШАГ 4: СВОДКА =====
        print("ШАГ 4: Итоги")
        print("-" * 70)

        generator.print_summary()

        # ===== ЗАВЕРШЕНИЕ =====
        print("\n" + "=" * 70)
        print("✅ ВСЁ ГОТОВО!")
        print("=" * 70)

        print("\n📋 Что было сделано:")
        print("   ✅ Определён язык проекта")
        print("   ✅ Определена версия языка")
        if not summary['dockerfile_exists']:
            print("   ✅ Сгенерирован Dockerfile")
        print("   ✅ Сгенерирован Build stage")
        print("   ✅ Сгенерирован Lint stage")
        print("   ✅ Сгенерирован Security stage")
        print("   ✅ Собран .gitlab-ci.yml")

        print("\n📂 Файлы:")
        if not summary['dockerfile_exists']:
            print("   📄 Dockerfile (сгенерирован)")
        print("   📄 .gitlab-ci.yml (сгенерирован)")

        print("\n🎯 Дальнейшие шаги:")
        print("   1. Проверьте .gitlab-ci.yml")
        if not summary['dockerfile_exists']:
            print("   2. Проверьте Dockerfile")
        print("   3. Закоммитьте файлы:")
        print("      git add .gitlab-ci.yml Dockerfile")
        print("      git commit -m 'Auto-generated CI/CD config'")
        print("      git push origin main")
        print("   4. Смотрите CI/CD → Pipelines")
        print("\n")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
