#!/usr/bin/env python3
"""
Простой скрипт запуска бота без зависания терминала
"""
import subprocess
import sys
import signal
import os
import time


def signal_handler(signum, frame):
    """Обработчик сигналов для принудительного завершения"""
    print(f"\nПолучен сигнал {signum}, принудительно завершаем...")
    os._exit(0)


def main():
    """Главная функция"""
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("Запуск бота через простой скрипт...")
    print("Для остановки нажмите Ctrl+C")

    try:
        # Запускаем бот с флагом --simple
        result = subprocess.run([sys.executable, "main.py", "--simple"],
                                capture_output=False,
                                text=True)

        if result.returncode != 0:
            print(f"Бот завершился с ошибкой: {result.returncode}")
            return result.returncode

    except KeyboardInterrupt:
        print("\nПолучен сигнал остановки")
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        return 1
    finally:
        print("🏁 Скрипт завершен")

    return 0


if __name__ == "__main__":
    sys.exit(main())
