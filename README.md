# 🤖 — Support Bot for TELEGRAM

Бот для автоматизации службы поддержки интернет-магазина. Клиенты пишут в бота, менеджеры отвечают через удобную админ-панель.

## 📦 Возможности

- 🔄 Обработка входящих сообщений от пользователей
- 👨‍💼 Админ-панель для операторов поддержки в TG
- 📊 Статусы тикетов (открыт/закрыт/в работе)
- 📎 Отправка файлов, текста, кнопок

## 🛠 Технологии

- Python 3.10+
- Aiogram
- База данных: [SQLite/PostgreSQL]

## 🚀 Быстрый старт

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/xsonedada/botpython.git
cd botpython
```
2. Установите зависимости
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate     # Windows

pip install -r requirements.txt
```
3. Настройте переменные окружения
В BOT.PY укажите данные, требующиеся для работы бота

```bash
BOT_TOKEN = ""
WEBSITE_URL = ""
INFO_PHOTO_URL = ""
START_PHOTO_URL = "" 
ADMIN_IDS = []  # ID всех администраторов
DATA_FILE = "bot_data.json"  # Файл для сохранения данных -> по просьбе есть возможность переделать под pgsql
```
4. Запустите бота
```bash
python bot.py
```
