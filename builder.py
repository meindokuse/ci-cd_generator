#!/usr/bin/env python3
"""
Упрощенный сборочный скрипт
"""

import os
import subprocess
import sys
from pathlib import Path


def build_simple():
    # Пути
    src_dir = Path("src")
    dist_dir = Path("dist")

    # Создаем папку dist если нет
    dist_dir.mkdir(exist_ok=True)

    # Ищем основной скрипт
    main_script = None
    for script in ["main.py", "app.py"]:
        if (src_dir / script).exists():
            main_script = src_dir / script
            break

    if not main_script:
        print("❌ Не найден main.py или app.py в папке src")
        return False

    print(f"🔨 Сборка {main_script}...")

    # Команда PyInstaller
    cmd = [
        'pyinstaller',
        '--onefile',
        '--clean',
        '--distpath', str(dist_dir),
        '--name', main_script.stem,
        str(main_script)
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Сборка завершена! Исполняемый файл в папке: {dist_dir}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка сборки: {e}")
        return False
    except FileNotFoundError:
        print("❌ PyInstaller не установлен. Установите: pip install pyinstaller")
        return False


if __name__ == "__main__":
    success = build_simple()
    sys.exit(0 if success else 1)