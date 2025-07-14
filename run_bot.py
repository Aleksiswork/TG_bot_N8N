#!/usr/bin/env python3
"""
Wrapper script for running the Telegram bot with better console handling
"""
import sys
import os
import subprocess
import signal
import time
import threading
from pathlib import Path


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print(f"\nПолучен сигнал {signum}, останавливаем бота...")
    sys.exit(0)


def run_bot():
    """Run the bot with proper signal handling"""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()

    # Change to the bot directory
    os.chdir(script_dir)

    # Check if virtual environment exists
    venv_path = script_dir / "venv"
    if not venv_path.exists():
        print("Виртуальное окружение не найдено. Создайте его командой:")
        print("   python -m venv venv")
        print("   venv\\Scripts\\activate")
        print("   pip install -r requirements.txt")
        return 1

    # Determine Python executable
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"

    if not python_exe.exists():
        print(f"Python не найден в {python_exe}")
        return 1

    # Check if main.py exists
    main_py = script_dir / "main.py"
    if not main_py.exists():
        print("main.py не найден")
        return 1

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("Запуск бота...")
    print("Для остановки нажмите Ctrl+C")
    print("-" * 50)

    # Run the bot with proper environment
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'  # Disable output buffering

    # Use subprocess with proper signal handling
    process = subprocess.Popen(
        [str(python_exe), str(main_py)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )

    # Monitor the process
    try:
        while True:
            if process.stdout is None:
                break
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.rstrip())

    except KeyboardInterrupt:
        print("\nПолучен сигнал остановки...")
        process.terminate()

        # Wait for graceful shutdown
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print("Принудительное завершение...")
            process.kill()
            process.wait()

    return process.returncode


if __name__ == "__main__":
    try:
        exit_code = run_bot()
        sys.exit(exit_code)
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        sys.exit(1)
