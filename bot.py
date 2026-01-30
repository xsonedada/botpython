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
broadcast_subscribers: Dict[int, bool] = {}  # Подписчики рассылки (по умолчанию все включены)
admin_ratings: Dict[int, Dict] = {}  # Рейтинги администраторов: admin_id -> {'avg_rating': X, 'total_reviews': Y}

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
            'notifications': notifications[-100:],
            'surveys': surveys,
            'broadcast_subscribers': broadcast_subscribers,
            'admin_ratings': admin_ratings
        }
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=str, ensure_ascii=False, indent=2)
        
        logger.info(f"Данные сохранены в {DATA_FILE}")
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

def load_data():
    """Загрузка данных из файла"""
    global user_sessions, promo_codes, notifications, surveys, broadcast_subscribers, admin_ratings
    
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
            broadcast_subscribers = data.get('broadcast_subscribers', {})
            admin_ratings = data.get('admin_ratings', {})
            
            logger.info(f"Данные загружены из {DATA_FILE}")
            logger.info(f"Пользователей: {len(user_sessions)}")
            logger.info(f"Промо-кодов: {len(promo_codes)}")
            logger.info(f"Подписчиков рассылки: {len([v for v in broadcast_subscribers.values() if v])}")
            logger.info(f"Администраторов с рейтингом: {len(admin_ratings)}")
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")

def add_notification(message: str, level: str = "info"):
    """Добавление системного уведомления"""
    notifications.append({
        'message': message,
        'level': level,
        'time': datetime.now()
    })

def update_admin_rating(admin_id: int, rating: int):
    """Обновление рейтинга администратора"""
    if admin_id not in admin_ratings:
        admin_ratings[admin_id] = {
            'total_rating': rating,
            'total_reviews': 1,
            'avg_rating': rating,
            'last_updated': datetime.now()
        }
    else:
        admin_data = admin_ratings[admin_id]
        admin_data['total_rating'] += rating
        admin_data['total_reviews'] += 1
        admin_data['avg_rating'] = admin_data['total_rating'] / admin_data['total_reviews']
        admin_data['last_updated'] = datetime.now()
    
    # Сохраняем данные
    save_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    keyboard = [
        [KeyboardButton("🎁 Получить промо-код")],
        [KeyboardButton("🆘 Связаться с поддержкой")],
        [KeyboardButton("📢 Управление рассылкой"), KeyboardButton("ℹ️ Информация")]
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
            'promo_received': 0
        }
        user_sessions[user_id] = user_data
        
        # По умолчанию включаем рассылку для новых пользователей
        broadcast_subscribers[user_id] = True
        
        # Добавляем уведомление о новом пользователе
        add_notification(f"Новый пользователь: {user.first_name} (@{user.username}) ID: {user_id}")
        
        logger.info(f"Новый пользователь: {user_id} ({user.username})")
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
    
    welcome_text = (
        f"{greeting}\n\n"
        "Доступные функции:\n"
        "• 🎁 Получить промо-код - получить промо-код\n"
        "• 🆘 Связаться с поддержкой - получить помощь специалиста\n"
        "• 📢 Управление рассылкой - настройки уведомлений\n"
        "• ℹ️ Информация - о возможностях бота"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    # Сохраняем данные
    save_data()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        help_text_lines = [
            "👑 *Панель администратора*\n\n",
            "📋 Основные команды:",
            "/start - главное меню",
            "/admin - управление поддержкой",
            "/active - активные запросы",
            "/stats - статистика",
            "/users - просмотр пользователей",
            "/promo - управление промо-кодами",
            "/broadcast - управление рассылкой",
            "/ratings - рейтинги администраторов",
            "/notify - уведомления",
            "/survey - управление опросами",
            "/backup - резервное копирование",
            "/help - эта справка\n\n",
            
            "🎯 Функции:",
            "• Принятие запросов в поддержку",
            "• Создание промо-кодов",
            "• Просмотр статистики",
            "• Управление пользователями",
            "• Создание опросов",
            "• Система уведомлений",
            "• Управление рассылкой",
            "• Рейтинги администраторов"
        ]
        help_text = "\n".join(help_text_lines)
    else:
        help_text_lines = [
            "📚 *Помощь*\n\n",
            "🎯 Основные функции:",
            "• 🎁 Получить промо-код - получить промо-код",
            "• 🆘 Связаться с поддержкой - получить помощь специалиста",
            "• 📢 Управление рассылкой - настройки уведомлений",
            "• ℹ️ Информация - о возможностях бота\n\n",
            
            "📋 Команды:",
            "/start - главное меню",
            "/broadcast - управление рассылкой",
            "/status - статус вашего запроса",
            "/cancel - отменить запрос",
            "/help - эта справка\n\n",
            
            "⭐ После обращения в поддержку вы можете оценить работу специалиста.",
            "📢 Рассылка включена по умолчанию, можно отписаться в настройках."
        ]
        help_text = "\n".join(help_text_lines)
    
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
    
    # Добавляем уведомление
    user_info = user_sessions.get(user_id, {})
    add_notification(f"Пользователь {user_info.get('first_name', 'Unknown')} получил промо-код {active_promo}")
    
    promo_message = (
        f"🎉 *Ваш промо-код:* `{active_promo}`\n\n"
        f"Используйте его на нашем сайте!\n"
        f"Срок действия: бессрочно\n"
        f"Осталось использований: {promo_codes[active_promo]['uses_left']}"
    )
    
    await update.message.reply_text(promo_message, parse_mode=ParseMode.MARKDOWN)
    
    save_data()

async def call_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вызов поддержки"""
    user_id = update.effective_user.id
    
    # Обновляем счетчик сообщений и запросов
    if user_id in user_sessions:
        user_sessions[user_id]['total_messages'] += 1
        user_sessions[user_id]['support_requests'] = user_sessions[user_id].get('support_requests', 0) + 1
    
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
        'messages': [],
        'rating_given': False  # Флаг, что пользователь уже оценил этот чат
    }
    
    await update.message.reply_text(
        "🆘 *Запрос отправлен!*\n\n"
        "Ваш запрос принят в обработку. Специалист поддержки скоро с вами свяжется.\n"
        "Ожидайте подключения...\n\n"
        "Используйте /status для проверки статуса.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    user_info = user_sessions.get(user_id, {})
    notification_text_lines = [
        f"🆘 *Новый запрос в поддержку!*\n\n",
        f"👤 Пользователь: {user_info.get('first_name', 'Пользователь')}",
        f"📛 Username: @{user_info.get('username', 'нет')}",
        f"🆔 ID: {user_id}",
        f"📅 Зарегистрирован: {user_info.get('registered_at', datetime.now()).strftime('%Y-%m-%d')}",
        f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n",
        f"Кто примет запрос?"
    ]
    notification_text = "\n".join(notification_text_lines)
    
    keyboard = []
    for admin_id in ADMIN_IDS:
        try:
            admin_info = admin_sessions.get(admin_id, {})
            admin_name = admin_info.get('first_name', f'Админ {admin_id}')
            
            # Добавляем рейтинг администратора, если есть
            rating_text = ""
            if admin_id in admin_ratings:
                rating = admin_ratings[admin_id].get('avg_rating', 0)
                reviews = admin_ratings[admin_id].get('total_reviews', 0)
                rating_text = f" ⭐ {rating:.1f} ({reviews})"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ {admin_name}{rating_text}",
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

async def close_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: int, with_rating: bool = False):
    """Закрытие конкретного чата"""
    user_id = update.effective_user.id
    
    if target_user_id not in active_support_requests:
        await update.message.reply_text("❌ Чат не найден.")
        return
    
    request = active_support_requests[target_user_id]
    
    # Проверяем, может ли администратор закрыть этот чат
    if request.get('admin_id') != user_id:
        await update.message.reply_text(
            "❌ Вы не можете закрыть этот чат.\n"
            "Этот чат ведет другой специалист."
        )
        return
    
    # Если закрытие с рейтингом (от пользователя)
    if with_rating and 'admin_id' in request:
        admin_id = request['admin_id']
        
        # Показываем пользователю форму оценки
        keyboard = [
            [
                InlineKeyboardButton("⭐ 1", callback_data=f"rate_{target_user_id}_1"),
                InlineKeyboardButton("⭐ 2", callback_data=f"rate_{target_user_id}_2"),
                InlineKeyboardButton("⭐ 3", callback_data=f"rate_{target_user_id}_3"),
                InlineKeyboardButton("⭐ 4", callback_data=f"rate_{target_user_id}_4"),
                InlineKeyboardButton("⭐ 5", callback_data=f"rate_{target_user_id}_5")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🔒 *Чат с поддержкой завершен*\n\n"
                     "Пожалуйста, оцените работу специалиста:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Не удалось отправить форму оценки пользователю: {e}")
        
        # Обновляем информацию об администраторе
        if user_id in admin_sessions:
            admin_sessions[user_id]['active_chats'] = [
                chat for chat in admin_sessions[user_id]['active_chats'] 
                if chat != target_user_id
            ]
        
        await update.message.reply_text(
            f"✅ Чат с пользователем {target_user_id} завершен.\n"
            f"Пользователю отправлена форма для оценки."
        )
        return
    
    # Обычное закрытие (от администратора)
    # Уведомляем пользователя
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text="🔒 *Чат с поддержкой завершен*\n\n"
                 "Специалист завершил сессию. Спасибо за обращение!",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя: {e}")
    
    # Обновляем информацию об администраторе
    if user_id in admin_sessions:
        admin_sessions[user_id]['active_chats'] = [
            chat for chat in admin_sessions[user_id]['active_chats'] 
            if chat != target_user_id
        ]
    
    # Удаляем запрос
    user_info = request.get('user_info', {})
    user_name = user_info.get('first_name', f'ID: {target_user_id}')
    
    del active_support_requests[target_user_id]
    await update.message.reply_text(
        f"✅ Чат с пользователем {user_name} (ID: {target_user_id}) успешно закрыт."
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка inline-кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Оценка администратора пользователем
    if data.startswith('rate_'):
        parts = data.split('_')
        if len(parts) >= 3:
            target_user_id = int(parts[1])
            rating = int(parts[2])
            
            # Проверяем, существует ли еще чат и есть ли admin_id
            if target_user_id in active_support_requests:
                request = active_support_requests[target_user_id]
                
                # Проверяем, не оценивал ли уже пользователь этот чат
                if request.get('rating_given', False):
                    await query.edit_message_text("❌ Вы уже оценили этот чат ранее.")
                    return
                
                if 'admin_id' in request:
                    admin_id = request['admin_id']
                    
                    # Обновляем рейтинг администратора
                    update_admin_rating(admin_id, rating)
                    
                    # Получаем информацию об администраторе
                    admin_info = admin_sessions.get(admin_id, {})
                    admin_name = admin_info.get('first_name', f'Админ {admin_id}')
                    
                    # Отмечаем, что пользователь уже оценил этот чат
                    request['rating_given'] = True
                    request['rating_value'] = rating
                    
                    # Уведомляем администратора об оценке
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=f"⭐ *Новая оценка!*\n\n"
                                 f"Пользователь оценил ваш ответ на {rating}/5\n"
                                 f"Спасибо за качественную работу!",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Не удалось уведомить администратора об оценке: {e}")
                    
                    # Обновляем сообщение пользователю
                    await query.edit_message_text(
                        f"✅ Спасибо за оценку {rating} ⭐!\n\n"
                        f"Ваша оценка поможет нам улучшить качество поддержки."
                    )
                    
                    # Закрываем чат после оценки
                    if target_user_id in active_support_requests:
                        # Удаляем запрос
                        del active_support_requests[target_user_id]
                    
                    # Добавляем уведомление
                    add_notification(f"Пользователь {target_user_id} оценил администратора {admin_id} на {rating}/5")
                    
                    return
            
            await query.edit_message_text("❌ Чат не найден или уже закрыт.")
        return
    
    # Обработка управления рассылкой для пользователей
    if data == "broadcast_subscribe":
        broadcast_subscribers[user_id] = True
        save_data()
        
        await query.edit_message_text(
            "✅ Вы подписались на рассылку!\n\n"
            "Теперь вы будете получать:\n"
            "• Новые промо-коды\n"
            "• Важные объявления\n"
            "• Обновления бота\n"
            "• Специальные предложения"
        )
        return
    
    elif data == "broadcast_unsubscribe":
        broadcast_subscribers[user_id] = False
        save_data()
        
        await query.edit_message_text(
            "🔕 Вы отписались от рассылки.\n\n"
            "Вы больше не будете получать уведомления.\n"
            "Вы можете подписаться снова в любое время."
        )
        return
    
    # Проверка прав для административных действий
    if not is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав для этого действия.")
        return
    
    # Принять запрос
    if data.startswith('accept_'):
        parts = data.split('_')
        if len(parts) >= 3:
            target_user_id = int(parts[1])
            admin_selector_id = int(parts[2]) if len(parts) > 2 else user_id
            
            if admin_selector_id != user_id:
                await query.edit_message_text(
                    f"❌ Этот запрос предназначен для другого администратора."
                )
                return
            
            if target_user_id not in active_support_requests:
                await query.edit_message_text("❌ Запрос уже обработан.")
                return
            
            request = active_support_requests[target_user_id]
            
            request.update({
                'status': 'active',
                'admin_id': user_id,
                'admin_accepted_at': datetime.now(),
                'admin_name': query.from_user.first_name
            })
            
            if user_id not in admin_sessions:
                admin_sessions[user_id] = {
                    'username': query.from_user.username,
                    'first_name': query.from_user.first_name,
                    'active_chats': []
                }
            admin_sessions[user_id]['active_chats'].append(target_user_id)
            
            # Добавляем кнопку для закрытия чата с оценкой
            close_keyboard = [[
                InlineKeyboardButton(
                    "🔒 Завершить чат и запросить оценку", 
                    callback_data=f"close_with_rating_{target_user_id}"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(close_keyboard)
            
            accept_message = (
                f"✅ Вы приняли запрос от пользователя.\n\n"
                f"Теперь все ваши сообщения будут отправляться пользователю от имени бота.\n\n"
                f"*Совет:*\n"
                f"• Отвечайте вежливо и профессионально\n"
                f"• Решайте проблемы пользователя\n"
                f"• После решения завершите чат кнопкой ниже\n\n"
                f"Пользователь сможет оценить вашу работу."
            )
            
            await query.edit_message_text(
                accept_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="✅ *Специалист поддержки подключился к чату!*\n\n"
                         "Теперь вы можете задавать вопросы. Все сообщения будут отправляться специалисту.\n\n"
                         "После решения вопроса специалист завершит чат и вы сможете оценить качество помощи.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя: {e}")
            
            # Обновляем уведомления других администраторов
            if 'notification_messages' in request:
                for admin_id, message_id in request['notification_messages']:
                    try:
                        if admin_id != user_id:
                            await context.bot.edit_message_text(
                                chat_id=admin_id,
                                message_id=message_id,
                                text="❌ Этот запрос уже принят другим специалистом.",
                                parse_mode=ParseMode.MARKDOWN
                            )
                    except Exception as e:
                        logger.error(f"Не удалось обновить уведомление: {e}")
    
    # Закрыть чат с запросом оценки
    elif data.startswith('close_with_rating_'):
        target_user_id = int(data.split('_')[3])
        
        if target_user_id not in active_support_requests:
            await query.edit_message_text("❌ Чат уже закрыт.")
            return
        
        request = active_support_requests[target_user_id]
        
        # Проверяем, может ли этот администратор закрыть чат
        if request.get('admin_id') != user_id:
            await query.edit_message_text("❌ Вы не можете закрыть этот чат.")
            return
        
        # Закрываем чат с запросом оценки
        await close_chat(query, context, target_user_id, with_rating=True)
    
    # Остальная обработка кнопок...
    # (обработка reject_, close_chat_, refresh_admin, promo_, users_ и т.д.)

async def ratings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр рейтингов администраторов"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    if not admin_ratings:
        await update.message.reply_text(
            "📭 Рейтингов пока нет.\n\n"
            "Рейтинги появятся после того, как пользователи оценят работу администраторов."
        )
        return
    
    # Сортируем администраторов по рейтингу (от высшего к низшему)
    sorted_admins = sorted(
        admin_ratings.items(),
        key=lambda x: x[1].get('avg_rating', 0),
        reverse=True
    )
    
    message_lines = ["🏆 *Рейтинги администраторов:*\n\n"]
    
    for i, (admin_id, rating_data) in enumerate(sorted_admins, 1):
        admin_info = admin_sessions.get(admin_id, {})
        admin_name = admin_info.get('first_name', f'Админ {admin_id}')
        username = admin_info.get('username', 'нет')
        
        avg_rating = rating_data.get('avg_rating', 0)
        total_reviews = rating_data.get('total_reviews', 0)
        last_updated = rating_data.get('last_updated', datetime.now())
        
        # Формируем звезды для визуализации
        stars = "⭐" * int(avg_rating)
        if avg_rating % 1 >= 0.5:
            stars += "✨"
        
        # Рассчитываем сколько дней назад было обновление
        days_ago = (datetime.now() - last_updated).days if isinstance(last_updated, datetime) else 0
        
        message_lines.extend([
            f"{i}. *{admin_name}* (@{username})",
            f"   Рейтинг: {avg_rating:.1f}/5 {stars}",
            f"   Отзывов: {total_reviews}",
            f"   Последняя оценка: {days_ago} дн. назад",
            f"   ID: {admin_id}",
            f"   ────────"
        ])
    
    message_text = "\n".join(message_lines)
    
    # Статистика
    total_admins = len(admin_ratings)
    avg_all_rating = sum(r['avg_rating'] for r in admin_ratings.values()) / total_admins if total_admins > 0 else 0
    total_reviews = sum(r['total_reviews'] for r in admin_ratings.values())
    
    stats_text = (
        f"\n📊 *Статистика:*\n"
        f"• Всего администраторов с рейтингом: {total_admins}\n"
        f"• Средний рейтинг: {avg_all_rating:.1f}/5\n"
        f"• Всего оценок: {total_reviews}\n"
        f"• Администраторов без оценок: {len(ADMIN_IDS) - total_admins}"
    )
    
    await update.message.reply_text(
        message_text + stats_text,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Обновляем счетчик сообщений для пользователя
    if user_id in user_sessions:
        user_sessions[user_id]['total_messages'] += 1
        user_sessions[user_id]['last_active'] = datetime.now()
    
    # Обработка команд с подчеркиванием
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
                
                if target_user_id in user_sessions:
                    user_sessions[target_user_id]['total_messages'] += 1
                
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
    
    elif message_text == "📢 Управление рассылкой":
        await broadcast_settings_command(update, context)
    
    elif message_text == "ℹ️ Информация":
        info_text = (
            "🤖 *Информация о боте*\n\n"
            "Этот бот предоставляет:\n"
            "• 🎁 Промо-коды для скидок\n"
            "• 🆘 Техническую поддержку\n"
            "• 📢 Управление рассылкой\n\n"
            "📢 *Рассылка:*\n"
            "• Включена по умолчанию\n"
            "• Можно отписаться в настройках\n"
            "• Информирует о новостях и акциях\n\n"
            "⭐ *Оценка поддержки:*\n"
            "• После обращения вы можете оценить работу специалиста\n"
            "• Оценка помогает улучшить качество поддержки\n\n"
            "Специалисты подключаются к чату в рабочее время."
        )
        await update.message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN)
    
    # Если пользователь в активном чате с поддержкой
    elif user_id in active_support_requests:
        request = active_support_requests[user_id]
        if request['status'] == 'active' and 'admin_id' in request:
            admin_id = request['admin_id']
            
            try:
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
            [KeyboardButton("📢 Управление рассылкой")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Выберите действие из меню 👇",
            reply_markup=reply_markup
        )
    
    # Сохраняем данные
    save_data()

# ... (остальные функции остаются аналогичными, но без достижений)

def main():
    """Запуск бота"""
    # Загружаем данные при старте
    load_data()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды для пользователей
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast", broadcast_settings_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Команды для администраторов
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("active", show_active_requests))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("promo", promo_command))
    application.add_handler(CommandHandler("broadcastadmin", broadcast_admin_command))
    application.add_handler(CommandHandler("ratings", ratings_command))
    
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
    print(f"📢 Подписчиков рассылки: {len([v for v in broadcast_subscribers.values() if v])}")
    print(f"⭐ Администраторов с рейтингом: {len(admin_ratings)}")
    print("💾 Автосохранение данных включено")
    print("📊 Система рейтинга администраторов активирована")
    print("Ожидание сообщений...")
    
    application.run_polling()

if __name__ == '__main__':
    main()
