#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
from pathlib import Path


def build_project():
    # Пути
    src_dir = Path("src")
    dist_dir = Path("dist")
    build_dir = Path("build")

    # Проверяем наличие main.py
    main_script = src_dir / "main.py"
    if not main_script.exists():
        print("❌ Ошибка: main.py не найден в папке src")
        return False

    print("🔨 Сборка проекта...")
    print(f"   Главный скрипт: {main_script}")

    # Очистка предыдущих сборок
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # Создаем папку dist
    dist_dir.mkdir(exist_ok=True)

    # Команда PyInstaller
    cmd = [
        'pyinstaller',
        '--onefile',  # Один exe файл
        '--clean',  # Очистка временных файлов
        '--distpath', str(dist_dir),
        '--workpath', str(build_dir),
        '--name', 'Generator',
        str(main_script)
    ]

    # Добавляем все .py файлы из src как скрытые импорты
    for py_file in src_dir.glob("*.py"):
        if py_file != main_script:
            cmd.extend(['--hidden-import', py_file.stem])

    # Добавляем дополнительные файлы из src
    for file_type in ['*.json', '*.yaml', '*.yml', '*.ini']:
        for config_file in src_dir.glob(file_type):
            cmd.extend(['--add-data', f'{config_file};.'])

    # Добавляем папки с данными
    for data_dir in ['data', 'templates', 'config']:
        data_path = src_dir / data_dir
        if data_path.exists():
            cmd.extend(['--add-data', f'{data_path};{data_dir}'])

    print("   Команда сборки:")
    print("   " + " ".join(cmd))

    # Запуск сборки
    try:
        print("   🚀 Запуск PyInstaller...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("   ✅ Сборка завершена успешно!")

        # Проверяем результат
        exe_path = dist_dir / "Generator.exe"
        dist_path = dist_dir / "Generator"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"   📦 Создан: {exe_path.name} ({size_mb:.1f} MB)")
            return True
        elif dist_path.exists():
            size_mb = dist_path.stat().st_size / (1024 * 1024)
            print(f"   📦 Создан: {dist_path.name} ({size_mb:.1f} MB)")
            return True
        else:
            print("   ❌ Исполняемый файл не создан")
            return False

    except subprocess.CalledProcessError as e:
        print(f"   ❌ Ошибка сборки: {e}")
        if e.stderr:
            print(f"   Подробности: {e.stderr}")
        return False
    except FileNotFoundError:
        print("   ❌ PyInstaller не установлен")
        print("   Установите: pip install pyinstaller")
        return False


if __name__ == "__main__":
    success = build_project()

    if success:
        print("\n🎉 Приложение успешно собрано!")
        print("📁 Файл: dist/Generator.exe")
    else:
        print("\n💥 Сборка не удалась")
        sys.exit(1)