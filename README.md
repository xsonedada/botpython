# 🤖 — Support Bot

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
Создайте файл .env в корне проекта:

```bash
BOT_TOKEN=ваш_токен_от_@BotFather
ADMIN_IDS=123456789,987654321  # ID менеджеров (через запятую)
WEBHOOK_URL=                   # если используется вебхук (опционально)
DATABASE_URL=sqlite:///support.db
```
4. Запустите бота
```bash
python bot.py
```
