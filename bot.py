import logging
import re
import random
import string
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode

# Конфигурация
BOT_TOKEN = "8213844298:AAHbMtsO6WBT7nzfd7DkwMRLmSBJzruk-3E"
WEBSITE_URL = "https://www.realtimegroup.ru/"
ADMIN_IDS = [724770396]  # ID всех администраторов (добавьте свои)
DATA_FILE = "bot_data.json"  # Файл для сохранения данных

# Хранилище данных (загружаются из файла при старте)
active_support_requests: Dict[int, Dict] = {}
user_sessions: Dict[int, Dict] = {}
admin_sessions: Dict[int, Dict] = {}
promo_codes: Dict[str, Dict] = {}
notifications: List[Dict] = []  # Система уведомлений
surveys: Dict[str, Dict] = {}  # Опросы для пользователей

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def generate_promo_code(length=8):
    """Генерация промо-кода"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def save_data():
    """Сохранение данных в файл"""
    try:
        data = {
            'user_sessions': user_sessions,
            'promo_codes': promo_codes,
            'notifications': notifications[-100:],  # Сохраняем последние 100 уведомлений
            'surveys': surveys
        }
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=str, ensure_ascii=False, indent=2)
        
        logger.info(f"Данные сохранены в {DATA_FILE}")
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

def load_data():
    """Загрузка данных из файла"""
    global user_sessions, promo_codes, notifications, surveys
    
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            user_sessions = data.get('user_sessions', {})
            # Преобразуем строки обратно в datetime
            for user_id, user_data in user_sessions.items():
                for key in ['last_active', 'registered_at', 'promo_received_at']:
                    if key in user_data and user_data[key]:
                        try:
                            user_data[key] = datetime.fromisoformat(user_data[key])
                        except:
                            user_data[key] = datetime.now()
            
            promo_codes = data.get('promo_codes', {})
            notifications = data.get('notifications', [])
            surveys = data.get('surveys', {})
            
            logger.info(f"Данные загружены из {DATA_FILE}")
            logger.info(f"Пользователей: {len(user_sessions)}")
            logger.info(f"Промо-кодов: {len(promo_codes)}")
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")

def add_notification(message: str, level: str = "info"):
    """Добавление системного уведомления"""
    notifications.append({
        'message': message,
        'level': level,
        'time': datetime.now()
    })

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    keyboard = [
        [KeyboardButton("🎁 Получить промо-код")],
        [KeyboardButton("🆘 Связаться с поддержкой")],
        [KeyboardButton("📊 Моя статистика")],
        [KeyboardButton("❓ Опросы"), KeyboardButton("ℹ️ Информация")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # Проверяем, новый ли пользователь
    is_new_user = user_id not in user_sessions
    
    # Сохраняем/обновляем информацию о пользователе
    if is_new_user:
        user_data = {
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'last_active': datetime.now(),
            'registered_at': datetime.now(),
            'promo_used': False,
            'total_messages': 0,
            'support_requests': 0,
            'promo_received': 0,
            'rating': 0,
            'achievements': []
        }
        user_sessions[user_id] = user_data
        
        # Добавляем уведомление о новом пользователе
        add_notification(f"Новый пользователь: {user.first_name} (@{user.username}) ID: {user_id}")
        
        logger.info(f"Новый пользователь: {user_id} ({user.username})")
        
        # Автоматически даем достижение "Новичок"
        if 'newbie' not in user_data['achievements']:
            user_data['achievements'].append('newbie')
    else:
        user_sessions[user_id]['last_active'] = datetime.now()
        user_sessions[user_id]['username'] = user.username
        user_sessions[user_id]['first_name'] = user.first_name
        user_sessions[user_id]['last_name'] = user.last_name
    
    if is_admin(user_id):
        greeting = f"👑 Привет, администратор {user.first_name}!"
        if user_id not in admin_sessions:
            admin_sessions[user_id] = {
                'username': user.username,
                'first_name': user.first_name,
                'active_chats': []
            }
    else:
        greeting = f"👋 Привет, {user.first_name}!"
        
        # Приветствие для нового пользователя
        if is_new_user:
            greeting += "\n\n🎉 Добро пожаловать! Вы новый пользователь бота!"
    
    await update.message.reply_text(
        f"{greeting}\n\n"
        "Доступные функции:\n"
        "• 🎁 Получить промо-код - получить промо-код\n"
        "• 🆘 Связаться с поддержкой - получить помощь\n"
        "• 📊 Моя статистика - ваша активность\n"
        "• ❓ Опросы - участвовать в опросах\n"
        "• ℹ️ Информация - о возможностях бота",
        reply_markup=reply_markup
    )
    
    # Сохраняем данные
    save_data()

async def my_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика пользователя"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ Ваши данные не найдены. Используйте /start")
        return
    
    user_data = user_sessions[user_id]
    
    # Вычисляем активность
    last_active = user_data.get('last_active', datetime.now())
    days_since_active = (datetime.now() - last_active).days
    hours_since_active = (datetime.now() - last_active).seconds // 3600
    
    # Считаем уровень активности
    activity_level = "🟢 Высокая" if days_since_active == 0 else "🟡 Средняя" if days_since_active < 7 else "🔴 Низкая"
    
    # Считаем рейтинг (основывается на активности)
    rating = user_data.get('rating', 0)
    
    # Достижения
    achievements = user_data.get('achievements', [])
    achievements_text = ""
    if achievements:
        achievements_dict = {
            'newbie': "👶 Новичок",
            'active': "💬 Активный",
            'promo': "🎁 Получил промо",
            'supporter': "🆘 Обращался в поддержку",
            'veteran': "🏆 Ветеран (более 30 дней)"
        }
        for ach in achievements:
            if ach in achievements_dict:
                achievements_text += f"• {achievements_dict[ach]}\n"
    
    message = (
        f"📊 *Ваша статистика*\n\n"
        f"👤 *Информация:*\n"
        f"• Имя: {user_data.get('first_name', 'Неизвестно')}\n"
        f"• Username: @{user_data.get('username', 'нет')}\n"
        f"• ID: `{user_id}`\n"
        f"• Дата регистрации: {user_data.get('registered_at', datetime.now()).strftime('%d.%m.%Y')}\n\n"
        
        f"📈 *Активность:*\n"
        f"• Уровень активности: {activity_level}\n"
        f"• Последняя активность: {hours_since_active} ч. назад\n"
        f"• Всего сообщений: {user_data.get('total_messages', 0)}\n"
        f"• Запросов в поддержку: {user_data.get('support_requests', 0)}\n"
        f"• Получено промо-кодов: {user_data.get('promo_received', 0)}\n"
        f"• Рейтинг: ⭐ {rating}/10\n\n"
        
        f"🏆 *Достижения:*\n{achievements_text if achievements_text else '• Пока нет достижений\n'}"
    )
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def surveys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Опросы для пользователей"""
    user_id = update.effective_user.id
    
    if not surveys:
        await update.message.reply_text(
            "📭 В настоящее время нет активных опросов.\n"
            "Проверьте позже!"
        )
        return
    
    # Показываем доступные опросы
    keyboard = []
    for survey_id, survey_data in surveys.items():
        if survey_data.get('active', True):
            # Проверяем, не проходил ли уже пользователь этот опрос
            if user_id not in survey_data.get('participants', []):
                survey_name = survey_data.get('name', f'Опрос {survey_id}')
                keyboard.append([
                    InlineKeyboardButton(f"📝 {survey_name}", callback_data=f"survey_{survey_id}")
                ])
    
    if not keyboard:
        await update.message.reply_text(
            "✅ Вы уже прошли все доступные опросы!\n"
            "Спасибо за участие!"
        )
        return
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 *Доступные опросы:*\n\n"
        "Выберите опрос для участия:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        help_text = (
            "👑 *Панель администратора*\n\n"
            "📋 Основные команды:\n"
            "/start - главное меню\n"
            "/admin - управление поддержкой\n"
            "/active - активные запросы\n"
            "/stats - статистика\n"
            "/users - просмотр пользователей\n"
            "/promo - управление промо-кодами\n"
            "/notify - уведомления\n"
            "/survey - управление опросами\n"
            "/backup - резервное копирование\n"
            "/help - эта справка\n\n"
            
            "🎯 Функции:\n"
            "• Принятие запросов в поддержку\n"
            "• Создание промо-кодов\n"
            "• Просмотр статистики\n"
            "• Управление пользователями\n"
            "• Создание опросов\n"
            "• Система уведомлений"
        )
    else:
        help_text = (
            "📚 *Помощь*\n\n"
            "🎯 Основные функции:\n"
            "• 🎁 Получить промо-код - получить промо-код\n"
            "• 🆘 Связаться с поддержкой - получить помощь специалиста\n"
            "• 📊 Моя статистика - ваша активность\n"
            "• ❓ Опросы - участвовать в опросах\n\n"
            
            "📋 Команды:\n"
            "/start - главное меню\n"
            "/mystats - ваша статистика\n"
            "/status - статус вашего запроса\n"
            "/cancel - отменить запрос\n"
            "/help - эта справка\n\n"
            
            "ℹ️ Дополнительно:\n"
            "• Один пользователь = один промо-код\n"
            "• Опросы помогают улучшить бота\n"
            "• За активность начисляется рейтинг"
        )
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def get_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдача промо-кода"""
    user_id = update.effective_user.id
    
    # Обновляем счетчик сообщений
    if user_id in user_sessions:
        user_sessions[user_id]['total_messages'] += 1
    
    if is_admin(user_id):
        await update.message.reply_text(
            "Вы администратор. Используйте /promo для управления промо-кодами."
        )
        return
    
    # Проверяем, использовал ли уже промо-код
    if user_sessions.get(user_id, {}).get('promo_used', False):
        await update.message.reply_text(
            "❌ Вы уже использовали промо-код.\n"
            "Один пользователь может получить только один промо-код."
        )
        return
    
    # Ищем активный промо-код
    active_promo = None
    for code, data in promo_codes.items():
        if data.get('uses_left', 0) > 0:
            active_promo = code
            break
    
    if not active_promo:
        await update.message.reply_text(
            "❌ В настоящее время нет доступных промо-кодов.\n"
            "Попробуйте позже или свяжитесь с поддержкой."
        )
        return
    
    # Выдаем промо-код
    promo_codes[active_promo]['uses_left'] -= 1
    promo_codes[active_promo]['used_by'] = promo_codes[active_promo].get('used_by', []) + [user_id]
    
    # Обновляем информацию о пользователе
    if user_id in user_sessions:
        user_sessions[user_id]['promo_used'] = True
        user_sessions[user_id]['promo_received_at'] = datetime.now()
        user_sessions[user_id]['promo_code'] = active_promo
        user_sessions[user_id]['promo_received'] = user_sessions[user_id].get('promo_received', 0) + 1
        
        # Даем достижение за получение промо-кода
        if 'promo' not in user_sessions[user_id]['achievements']:
            user_sessions[user_id]['achievements'].append('promo')
        
        # Увеличиваем рейтинг
        user_sessions[user_id]['rating'] = min(10, user_sessions[user_id].get('rating', 0) + 2)
    
    # Добавляем уведомление
    user_info = user_sessions.get(user_id, {})
    add_notification(f"Пользователь {user_info.get('first_name', 'Unknown')} получил промо-код {active_promo}")
    
    await update.message.reply_text(
        f"🎉 *Ваш промо-код:* `{active_promo}`\n\n"
        f"Используйте его на нашем сайте!\n"
        f"Срок действия: бессрочно\n"
        f"Осталось использований: {promo_codes[active_promo]['uses_left']}",
        parse_mode=ParseMode.MARKDOWN
    )
    
    save_data()

async def call_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вызов поддержки"""
    user_id = update.effective_user.id
    
    # Обновляем счетчик сообщений и запросов
    if user_id in user_sessions:
        user_sessions[user_id]['total_messages'] += 1
        user_sessions[user_id]['support_requests'] = user_sessions[user_id].get('support_requests', 0) + 1
        
        # Даем достижение за обращение в поддержку
        if 'supporter' not in user_sessions[user_id]['achievements']:
            user_sessions[user_id]['achievements'].append('supporter')
        
        # Увеличиваем рейтинг
        user_sessions[user_id]['rating'] = min(10, user_sessions[user_id].get('rating', 0) + 1)
    
    if is_admin(user_id):
        await update.message.reply_text(
            "Вы администратор. Используйте /admin для управления поддержкой."
        )
        return
    
    if user_id in active_support_requests:
        request = active_support_requests[user_id]
        if request['status'] == 'waiting':
            await update.message.reply_text(
                "⏳ Ваш запрос уже в очереди. Специалист скоро подключится."
            )
        elif request['status'] == 'active':
            await update.message.reply_text(
                "✅ Вы уже общаетесь со специалистом.\n"
                "Пишите ваши вопросы прямо здесь."
            )
        return
    
    active_support_requests[user_id] = {
        'chat_id': update.effective_chat.id,
        'status': 'waiting',
        'user_info': user_sessions.get(user_id, {}),
        'created_at': datetime.now(),
        'messages': []
    }
    
    await update.message.reply_text(
        "🆘 *Запрос отправлен!*\n\n"
        "Ваш запрос принят в обработку. Специалист поддержки скоро с вами свяжется.\n"
        "Ожидайте подключения...\n\n"
        "Используйте /status для проверки статуса.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    user_info = user_sessions.get(user_id, {})
    notification_text = (
        f"🆘 *Новый запрос в поддержку!*\n\n"
        f"👤 Пользователь: {user_info.get('first_name', 'Пользователь')}\n"
        f"📛 Username: @{user_info.get('username', 'нет')}\n"
        f"🆔 ID: {user_id}\n"
        f"📅 Зарегистрирован: {user_info.get('registered_at', datetime.now()).strftime('%Y-%m-%d')}\n"
        f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"Кто примет запрос?"
    )
    
    keyboard = []
    for admin_id in ADMIN_IDS:
        try:
            admin_info = admin_sessions.get(admin_id, {})
            admin_name = admin_info.get('first_name', f'Админ {admin_id}')
            
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ {admin_name}",
                    callback_data=f"accept_{user_id}_{admin_id}"
                )
            ])
        except Exception as e:
            logger.error(f"Ошибка создания кнопки для админа {admin_id}: {e}")
    
    keyboard.append([
        InlineKeyboardButton("❌ Отклонить запрос", callback_data=f"reject_{user_id}")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    sent_messages = []
    for admin_id in ADMIN_IDS:
        try:
            message = await context.bot.send_message(
                chat_id=admin_id,
                text=notification_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            sent_messages.append((admin_id, message.message_id))
        except Exception as e:
            logger.error(f"Не удалось отправить админу {admin_id}: {e}")
    
    active_support_requests[user_id]['notification_messages'] = sent_messages
    
    # Добавляем уведомление
    add_notification(f"Новый запрос в поддержку от пользователя {user_info.get('first_name', 'Unknown')} (ID: {user_id})")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Обновляем счетчик сообщений для пользователя
    if user_id in user_sessions:
        user_sessions[user_id]['total_messages'] += 1
        user_sessions[user_id]['last_active'] = datetime.now()
        
        # Проверяем достижения по активности
        days_registered = (datetime.now() - user_sessions[user_id].get('registered_at', datetime.now())).days
        if days_registered >= 30 and 'veteran' not in user_sessions[user_id]['achievements']:
            user_sessions[user_id]['achievements'].append('veteran')
        
        if user_sessions[user_id]['total_messages'] >= 10 and 'active' not in user_sessions[user_id]['achievements']:
            user_sessions[user_id]['achievements'].append('active')
    
    # Обработка команд с подчеркиванием (например, /close_123456789)
    if message_text.startswith('/'):
        if message_text.startswith('/close_'):
            await handle_close_command(update, context)
            return
    
    # Администраторы
    if is_admin(user_id):
        target_user_id = None
        for uid, request in active_support_requests.items():
            if request.get('admin_id') == user_id and request['status'] == 'active':
                target_user_id = uid
                break
        
        if target_user_id:
            # Отправляем сообщение от имени бота (не пересылаем)
            try:
                user_info = active_support_requests[target_user_id].get('user_info', {})
                user_name = user_info.get('first_name', 'Пользователь')
                
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"💬 *Специалист поддержки:*\n{message_text}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                active_support_requests[target_user_id]['messages'].append({
                    'from': 'admin',
                    'time': datetime.now(),
                    'text': message_text,
                    'admin_id': user_id
                })
                
                # Обновляем счетчик сообщений для пользователя
                if target_user_id in user_sessions:
                    user_sessions[target_user_id]['total_messages'] += 1
                
                # Подтверждаем отправку администратору
                await update.message.reply_text(
                    f"✅ Сообщение отправлено пользователю {user_name}",
                    reply_to_message_id=update.message.message_id
                )
                
            except Exception as e:
                await update.message.reply_text(
                    "❌ Не удалось отправить сообщение пользователю."
                )
                logger.error(f"Ошибка отправки сообщения: {e}")
            return
    
    # Обычные пользователи
    if message_text == "🎁 Получить промо-код":
        await get_promo_code(update, context)
    
    elif message_text == "🆘 Связаться с поддержкой":
        await call_support(update, context)
    
    elif message_text == "📊 Моя статистика":
        await my_stats_command(update, context)
    
    elif message_text == "❓ Опросы":
        await surveys_command(update, context)
    
    elif message_text == "ℹ️ Информация":
        await update.message.reply_text(
            "🤖 *Информация о боте*\n\n"
            "Этот бот предоставляет:\n"
            "• 🎁 Промо-коды для скидок\n"
            "• 🆘 Техническую поддержку\n"
            "• 📊 Систему статистики\n"
            "• ❓ Опросы для улучшения сервиса\n"
            "• ⭐ Рейтинговую систему\n"
            "• 🏆 Достижения\n\n"
            "Специалисты подключаются к чату в рабочее время.\n"
            "За активность начисляется рейтинг и достижения!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Если пользователь в активном чате с поддержкой
    elif user_id in active_support_requests:
        request = active_support_requests[user_id]
        if request['status'] == 'active' and 'admin_id' in request:
            admin_id = request['admin_id']
            
            try:
                # Отправляем сообщение администратору от имени бота
                user_info = user_sessions.get(user_id, {})
                user_name = user_info.get('first_name', 'Пользователь')
                
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"👤 *{user_name}:*\n{message_text}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                request['messages'].append({
                    'from': 'user',
                    'time': datetime.now(),
                    'text': message_text
                })
                
            except Exception as e:
                await update.message.reply_text(
                    "❌ Специалист временно недоступен. Попробуйте позже."
                )
                logger.error(f"Ошибка отправки админу: {e}")
    
    else:
        # Показываем меню
        keyboard = [
            [KeyboardButton("🎁 Получить промо-код")],
            [KeyboardButton("🆘 Связаться с поддержкой")],
            [KeyboardButton("📊 Моя статистика")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Выберите действие из меню 👇",
            reply_markup=reply_markup
        )
    
    # Сохраняем данные
    save_data()

# ... (остальные функции остаются аналогичными предыдущей версии, но с добавлением save_data() в конце)

async def notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Уведомления для администраторов"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    if not context.args:
        # Показываем последние уведомления
        recent_notifications = notifications[-10:]  # Последние 10 уведомлений
        
        if not recent_notifications:
            await update.message.reply_text("📭 Нет уведомлений.")
            return
        
        message_text = "📢 *Последние уведомления:*\n\n"
        
        for i, note in enumerate(recent_notifications[::-1], 1):  # Сначала новые
            time_str = note.get('time', datetime.now()).strftime('%H:%M')
            level_icon = "🔵" if note.get('level') == 'info' else "🟡" if note.get('level') == 'warning' else "🔴"
            
            message_text += f"{i}. {level_icon} {note.get('message', '')} ({time_str})\n"
        
        keyboard = [
            [InlineKeyboardButton("🗑 Очистить уведомления", callback_data="clear_notifications")],
            [InlineKeyboardButton("📊 Статистика уведомлений", callback_data="notify_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return
    
    # Отправка уведомления всем администраторам
    message = ' '.join(context.args)
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📢 *Системное уведомление:*\n{message}",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")
    
    add_notification(f"Отправлено уведомление: {message}")
    await update.message.reply_text(f"✅ Уведомление отправлено {len(ADMIN_IDS)} администраторам.")
    
    save_data()

async def survey_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление опросами для администраторов"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    if not context.args:
        # Меню управления опросами
        active_surveys = sum(1 for s in surveys.values() if s.get('active', True))
        total_surveys = len(surveys)
        
        keyboard = [
            [InlineKeyboardButton("➕ Создать опрос", callback_data="survey_create")],
            [InlineKeyboardButton("📋 Список опросов", callback_data="survey_list")],
            [InlineKeyboardButton("📊 Результаты опросов", callback_data="survey_results")],
            [InlineKeyboardButton("⬅️ Назад в админку", callback_data="refresh_admin")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📊 *Управление опросами*\n\n"
            f"Статистика:\n"
            f"• Всего опросов: {total_surveys}\n"
            f"• Активных: {active_surveys}\n\n"
            f"Выберите действие:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return
    
    # Создание опроса через команду
    if context.args[0] == "create":
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Неверный формат.\n"
                "Пример: /survey create \"Название опроса\" \"Вопрос1\" \"Вопрос2\" ..."
            )
            return
        
        # Парсим аргументы
        try:
            survey_name = context.args[1].strip('"')
            questions = []
            
            for arg in context.args[2:]:
                if arg.startswith('"') and arg.endswith('"'):
                    questions.append(arg.strip('"'))
            
            if not questions:
                await update.message.reply_text("❌ Добавьте хотя бы один вопрос.")
                return
            
            survey_id = f"survey_{len(surveys) + 1}_{int(datetime.now().timestamp())}"
            
            surveys[survey_id] = {
                'name': survey_name,
                'questions': questions,
                'created_at': datetime.now(),
                'created_by': user_id,
                'active': True,
                'participants': [],
                'answers': {}
            }
            
            add_notification(f"Создан новый опрос: {survey_name}")
            
            await update.message.reply_text(
                f"✅ Опрос создан!\n\n"
                f"📝 Название: {survey_name}\n"
                f"❓ Вопросов: {len(questions)}\n"
                f"🆔 ID: {survey_id}\n"
                f"👑 Создал: {update.effective_user.first_name}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            save_data()
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка создания опроса: {e}")

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Резервное копирование данных"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    # Создаем резервную копию
    backup_data = {
        'timestamp': datetime.now().isoformat(),
        'user_count': len(user_sessions),
        'promo_count': len(promo_codes),
        'survey_count': len(surveys),
        'notification_count': len(notifications)
    }
    
    # Сохраняем текущие данные
    save_data()
    
    # Создаем файл резервной копии
    backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, default=str, ensure_ascii=False, indent=2)
        
        # Отправляем информацию о резервной копии
        await update.message.reply_text(
            f"✅ *Резервная копия создана!*\n\n"
            f"📊 Статистика:\n"
            f"• Пользователей: {backup_data['user_count']}\n"
            f"• Промо-кодов: {backup_data['promo_count']}\n"
            f"• Опросов: {backup_data['survey_count']}\n"
            f"• Уведомлений: {backup_data['notification_count']}\n\n"
            f"💾 Файл: {backup_filename}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        add_notification(f"Создана резервная копия: {backup_filename}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка создания резервной копии: {e}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка сообщений всем пользователям"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 *Рассылка сообщений*\n\n"
            "Использование:\n"
            "/broadcast <текст сообщения>\n\n"
            "Пример:\n"
            "/broadcast Всем привет! Новые промо-коды уже доступны!",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    message = ' '.join(context.args)
    total_users = len(user_sessions)
    sent_count = 0
    failed_count = 0
    
    # Подтверждение
    keyboard = [
        [InlineKeyboardButton("✅ Да, отправить", callback_data=f"confirm_broadcast_{user_id}"),
         InlineKeyboardButton("❌ Отмена", callback_data="cancel_broadcast")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📢 *Подтвердите рассылку:*\n\n"
        f"{message}\n\n"
        f"Получателей: {total_users}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    # Сохраняем сообщение для подтверждения
    context.user_data['broadcast_message'] = message

def main():
    """Запуск бота"""
    # Загружаем данные при старте
    load_data()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды для пользователей
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("mystats", my_stats_command))
    application.add_handler(CommandHandler("surveys", surveys_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Команды для администраторов
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("active", show_active_requests))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("promo", promo_command))
    application.add_handler(CommandHandler("notify", notify_command))
    application.add_handler(CommandHandler("survey", survey_admin_command))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("finduser", finduser_command))
    
    # Отдельный обработчик для команды /close
    application.add_handler(CommandHandler("close", handle_close_command))
    
    # Callback-обработчики
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    print("🤖 Бот запущен!")
    print(f"👑 Администраторов: {len(ADMIN_IDS)}")
    print(f"👥 Загружено пользователей: {len(user_sessions)}")
    print(f"🎁 Загружено промо-кодов: {len(promo_codes)}")
    print("🎯 Система достижений активирована")
    print("📊 Система рейтинга активирована")
    print("❓ Система опросов активирована")
    print("💾 Автосохранение данных включено")
    print("Ожидание сообщений...")
    
    application.run_polling()

if __name__ == '__main__':
    main()
