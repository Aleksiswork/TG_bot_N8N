# 🚀 Инструкция по настройке бота

## Шаг 1: Получение токена бота

1. Найдите @BotFather в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания бота
4. Скопируйте полученный токен

## Шаг 2: Создание файла .env

Создайте файл `.env` в корневой папке проекта:

```env
# Telegram settings
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321

# Channel settings (опционально)
CHANNEL_USERNAME=your_channel_username
CHANNEL_LINK=https://t.me/your_channel

# Files settings
FILES_DIR=files
DB_USERS_PATH=data/users.db
DB_SUBMISSIONS_PATH=data/submissions.db

# Bot settings
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=50
MAX_FILES_PER_SUBMISSION=5
MAX_SUBMISSION_LENGTH=4000
```

## Шаг 3: Настройка канала (опционально)

Если вы хотите требовать подписку на канал:

1. Создайте канал в Telegram
2. Добавьте бота как администратора канала
3. Укажите username канала в `CHANNEL_USERNAME`
4. Укажите ссылку на канал в `CHANNEL_LINK`

## Шаг 4: Установка зависимостей

```bash
pip install -r requirements.txt
```

## Шаг 5: Запуск бота

```bash
python main.py
```

## Проверка работы

1. Найдите вашего бота в Telegram
2. Отправьте команду `/start`
3. Проверьте все функции

## Возможные проблемы

### Ошибка "BOT_TOKEN не установлен"
- Проверьте файл `.env`
- Убедитесь, что токен скопирован правильно

### Ошибка "Отсутствует DB_USERS_PATH"
- Создайте папку `data/`
- Укажите правильный путь в `.env`

### Бот не отвечает
- Проверьте логи в файле `bot.log`
- Убедитесь, что бот не заблокирован

## Структура папок

```
TG_bot_N8N/
├── .env                    # Конфигурация (создать)
├── data/                   # Базы данных (создать)
│   ├── users.db
│   └── submissions.db
├── files/                  # Файлы (создать)
└── bot.log                 # Логи (создается автоматически)
``` 