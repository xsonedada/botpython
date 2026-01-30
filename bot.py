import logging
import random
import string
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
import asyncio
from aiogram.types import FSInputFile

# Конфигурация
BOT_TOKEN = "8213844298:AAHbMtsO6WBT7nzfd7DkwMRLmSBJzruk-3E"
WEBSITE_URL = "https://www.realtimegroup.ru/"
ADMIN_IDS = [724770396]  # ID всех администраторов
DATA_FILE = "bot_data.json"  # Файл для сохранения данных

# Хранилище данных
active_support_requests: Dict[int, Dict] = {}
user_sessions: Dict[int, Dict] = {}
admin_sessions: Dict[int, Dict] = {}
promo_codes: Dict[str, Dict] = {}
notifications: List[Dict] = []
surveys: Dict[str, Dict] = {}
broadcast_subscribers: Dict[int, bool] = {}
admin_ratings: Dict[int, Dict] = {}

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация aiogram
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Состояния для FSM
class BroadcastStates(StatesGroup):
    waiting_for_message = State()

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
                content = f.read().strip()
                if not content:
                    logger.info(f"Файл {DATA_FILE} пустой, используются значения по умолчанию")
                    return
                
                data = json.loads(content)
            
            # Преобразуем ключи из строк в int для user_sessions
            user_sessions = {}
            if 'user_sessions' in data:
                for user_id_str, user_data in data['user_sessions'].items():
                    try:
                        user_id = int(user_id_str)
                        # Преобразуем строки обратно в datetime
                        for key in ['last_active', 'registered_at', 'promo_received_at']:
                            if key in user_data and user_data[key]:
                                try:
                                    if isinstance(user_data[key], str):
                                        user_data[key] = datetime.fromisoformat(user_data[key])
                                except:
                                    user_data[key] = datetime.now()
                        user_sessions[user_id] = user_data
                    except ValueError:
                        continue
            
            # Загружаем промо-коды
            promo_codes = {}
            if 'promo_codes' in data:
                for code, code_data in data['promo_codes'].items():
                    # Преобразуем строки дат обратно в datetime
                    for key in ['created_at']:
                        if key in code_data and code_data[key] and isinstance(code_data[key], str):
                            try:
                                code_data[key] = datetime.fromisoformat(code_data[key])
                            except:
                                code_data[key] = datetime.now()
                    promo_codes[code] = code_data
            
            notifications = data.get('notifications', [])
            surveys = data.get('surveys', {})
            
            # Преобразуем ключи из строк в int для broadcast_subscribers
            broadcast_subscribers = {}
            if 'broadcast_subscribers' in data:
                for user_id_str, is_subscribed in data['broadcast_subscribers'].items():
                    try:
                        user_id = int(user_id_str)
                        broadcast_subscribers[user_id] = is_subscribed
                    except ValueError:
                        continue
            
            # Преобразуем ключи из строк в int для admin_ratings
            admin_ratings = {}
            if 'admin_ratings' in data:
                for admin_id_str, rating_data in data['admin_ratings'].items():
                    try:
                        admin_id = int(admin_id_str)
                        # Преобразуем строки дат обратно в datetime
                        for key in ['last_updated']:
                            if key in rating_data and rating_data[key] and isinstance(rating_data[key], str):
                                try:
                                    rating_data[key] = datetime.fromisoformat(rating_data[key])
                                except:
                                    rating_data[key] = datetime.now()
                        admin_ratings[admin_id] = rating_data
                    except ValueError:
                        continue
            
            logger.info(f"Данные загружены из {DATA_FILE}")
            logger.info(f"Пользователей: {len(user_sessions)}")
            logger.info(f"Промо-кодов: {len(promo_codes)}")
            logger.info(f"Подписчиков рассылки: {len([v for v in broadcast_subscribers.values() if v])}")
            logger.info(f"Администраторов с рейтингом: {len(admin_ratings)}")
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON в файле {DATA_FILE}: {e}")
        # Создаем новый файл с корректными данными
        save_data()
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
    
    save_data()

def get_main_keyboard():
    """Возвращает основную клавиатуру"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Получить промо-код")],
            [KeyboardButton(text="🆘 Связаться с поддержкой")],
            [KeyboardButton(text="📢 Управление рассылкой"), KeyboardButton(text="ℹ️ Информация")]
        ],
        resize_keyboard=True
    )

# ========== ОБРАБОТЧИКИ КОМАНД ==========

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    user = message.from_user
    
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
        if is_new_user:
            greeting += "\n\n🎉 Добро пожаловать! Вы новый пользователь бота!"
    
    welcome_text = (
        f"{greeting}\n\n"
        "Выберите действие из меню ниже:\n\n"
        "• 🎁 Получить промо-код - получить промо-код\n"
        "• 🆘 Связаться с поддержкой - получить помощь специалиста\n"
        "• 📢 Управление рассылкой - настройки уведомлений\n"
        "• ℹ️ Информация - о возможностях бота"
    )
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())
    save_data()

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    user_id = message.from_user.id
    
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
            "/broadcast - управление рассылкой\n"
            "/ratings - рейтинги администраторов\n"
            "/help - эта справка\n\n"
            "🎯 Функции:\n"
            "• Принятие запросов в поддержку\n"
            "• Создание промо-кодов\n"
            "• Просмотр статистики\n"
            "• Управление пользователями\n"
            "• Управление рассылкой\n"
            "• Рейтинги администраторов"
        )
    else:
        help_text = (
            "📚 *Помощь*\n\n"
            "🎯 Основные функции:\n"
            "• 🎁 Получить промо-код - получить промо-код\n"
            "• 🆘 Связаться с поддержкой - получить помощь специалиста\n"
            "• 📢 Управление рассылкой - настройки уведомлений\n"
            "• ℹ️ Информация - о возможностях бота\n\n"
            "📋 Команды:\n"
            "/start - главное меню\n"
            "/broadcast - управление рассылкой\n"
            "/status - статус вашего запроса\n"
            "/cancel - отменить запрос\n"
            "/help - эта справка\n\n"
            "⭐ После обращения в поддержку вы можете оценить работу специалиста.\n"
            "📢 Рассылка включена по умолчанию, можно отписаться в настройках."
        )
    
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

@router.message(F.text == "🎁 Получить промо-код")
async def get_promo_code_handler(message: Message):
    """Выдача промо-кода"""
    user_id = message.from_user.id
    
    # Обновляем счетчик сообщений
    if user_id in user_sessions:
        user_sessions[user_id]['total_messages'] += 1
    
    if is_admin(user_id):
        await message.answer("Вы администратор. Используйте /promo для управления промо-кодами.", reply_markup=get_main_keyboard())
        return
    
    # Проверяем, использовал ли уже промо-код
    if user_sessions.get(user_id, {}).get('promo_used', False):
        await message.answer(
            "❌ Вы уже использовали промо-код.\n"
            "Один пользователь может получить только один промо-код.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Ищем активный промо-код
    active_promo = None
    for code, data in promo_codes.items():
        if data.get('uses_left', 0) > 0:
            active_promo = code
            break
    
    if not active_promo:
        await message.answer(
            "❌ В настоящее время нет доступных промо-кодов.\n"
            "Попробуйте позже или свяжитесь с поддержкой.",
            reply_markup=get_main_keyboard()
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
    
    await message.answer(promo_message, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())
    save_data()

@router.message(F.text == "🆘 Связаться с поддержкой")
async def call_support_handler(message: Message):
    """Вызов поддержки"""
    user_id = message.from_user.id
    
    # Обновляем счетчик сообщений и запросов
    if user_id in user_sessions:
        user_sessions[user_id]['total_messages'] += 1
        user_sessions[user_id]['support_requests'] = user_sessions[user_id].get('support_requests', 0) + 1
    
    if is_admin(user_id):
        await message.answer("Вы администратор. Используйте /admin для управления поддержкой.", reply_markup=get_main_keyboard())
        return
    
    if user_id in active_support_requests:
        request = active_support_requests[user_id]
        if request['status'] == 'waiting':
            await message.answer("⏳ Ваш запрос уже в очереди. Специалист скоро подключится.", reply_markup=get_main_keyboard())
        elif request['status'] == 'active':
            await message.answer("✅ Вы уже общаетесь со специалистом.\nПишите ваши вопросы прямо здесь.", reply_markup=get_main_keyboard())
        return
    
    active_support_requests[user_id] = {
        'chat_id': message.chat.id,
        'status': 'waiting',
        'user_info': user_sessions.get(user_id, {}),
        'created_at': datetime.now(),
        'messages': [],
        'rating_given': False
    }
    
    await message.answer(
        "🆘 *Запрос отправлен!*\n\n"
        "Ваш запрос принят в обработку. Специалист поддержки скоро с вами свяжется.\n"
        "Ожидайте подключения...\n\n"
        "Используйте /status для проверки статуса.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard()
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
    
    keyboard_buttons = []
    for admin_id in ADMIN_IDS:
        try:
            admin_info = admin_sessions.get(admin_id, {})
            admin_name = admin_info.get('first_name', f'Админ {admin_id}')
            
            rating_text = ""
            if admin_id in admin_ratings:
                rating = admin_ratings[admin_id].get('avg_rating', 0)
                reviews = admin_ratings[admin_id].get('total_reviews', 0)
                rating_text = f" ⭐ {rating:.1f} ({reviews})"
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"✅ {admin_name}{rating_text}",
                    callback_data=f"accept_{user_id}_{admin_id}"
                )
            ])
        except Exception as e:
            logger.error(f"Ошибка создания кнопки для админа {admin_id}: {e}")
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Отклонить запрос", callback_data=f"reject_{user_id}")
    ])
    
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    sent_messages = []
    for admin_id in ADMIN_IDS:
        try:
            msg = await message.bot.send_message(
                chat_id=admin_id,
                text=notification_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=inline_keyboard
            )
            sent_messages.append((admin_id, msg.message_id))
        except Exception as e:
            logger.error(f"Не удалось отправить админу {admin_id}: {e}")
    
    active_support_requests[user_id]['notification_messages'] = sent_messages
    add_notification(f"Новый запрос в поддержку от пользователя {user_info.get('first_name', 'Unknown')} (ID: {user_id})")

@router.message(F.text == "📢 Управление рассылкой")
async def broadcast_settings_handler(message: Message):
    """Настройки рассылки для пользователей"""
    user_id = message.from_user.id
    
    is_subscribed = broadcast_subscribers.get(user_id, True)
    
    if is_subscribed:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔕 Отписаться от рассылки", callback_data="broadcast_unsubscribe")]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подписаться на рассылку", callback_data="broadcast_subscribe")]
        ])
    
    status_text = "✅ Подписан" if is_subscribed else "🔕 Не подписан"
    
    message_text = (
        f"📢 *Управление рассылкой*\n\n"
        f"Текущий статус: {status_text}\n\n"
        f"Рассылка включает:\n"
        f"• Новые промо-коды\n"
        f"• Важные объявления\n"
        f"• Обновления бота\n"
        f"• Специальные предложения\n\n"
        f"Вы можете изменить настройки ниже:"
    )
    
    await message.answer(message_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

@router.message(F.text == "ℹ️ Информация")
async def info_handler(message: Message):
    """Информация о боте"""
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

    try:
        # Используйте локальный файл вместо URL
        photo = FSInputFile("bot_info.png")  # Укажите путь к вашему фото
        
        await message.answer_photo(
            photo=photo,
            caption=info_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка отправки фото: {e}")
        # Если не удалось отправить фото, отправляем только текст
        await message.answer(
            info_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard()
        )
    
    await message.answer(info_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

# ========== ОБРАБОТЧИКИ КОМАНД ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ==========

@router.message(Command("status"))
async def status_command(message: Message):
    """Проверка статуса запроса"""
    user_id = message.from_user.id
    
    if user_id not in active_support_requests:
        await message.answer(
            "📭 У вас нет активных запросов в поддержку.\n"
            "Используйте кнопку '🆘 Связаться с поддержкой' для создания запроса.",
            reply_markup=get_main_keyboard()
        )
        return
    
    request = active_support_requests[user_id]
    
    if request['status'] == 'waiting':
        wait_time = datetime.now() - request['created_at']
        minutes = int(wait_time.total_seconds() // 60)
        
        status_text = (
            f"⏳ *Статус запроса:* В очереди\n\n"
            f"⌛ Ожидание: {minutes} минут\n"
            f"📅 Создан: {request['created_at'].strftime('%H:%M:%S')}\n\n"
            f"Ваш запрос находится в очереди. Специалист скоро подключится."
        )
    
    elif request['status'] == 'active':
        admin_name = request.get('admin_name', 'Специалист')
        active_time = datetime.now() - request.get('admin_accepted_at', request['created_at'])
        minutes = int(active_time.total_seconds() // 60)
        
        status_text = (
            f"✅ *Статус запроса:* В работе\n\n"
            f"👨‍💻 Специалист: {admin_name}\n"
            f"⏱️ В работе: {minutes} минут\n"
            f"📅 Начат: {request.get('admin_accepted_at', request['created_at']).strftime('%H:%M:%S')}\n\n"
            f"Вы общаетесь со специалистом поддержки."
        )
    
    await message.answer(status_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

@router.message(Command("cancel"))
async def cancel_command(message: Message):
    """Отмена запроса в поддержку"""
    user_id = message.from_user.id
    
    if user_id not in active_support_requests:
        await message.answer("❌ У вас нет активных запросов для отмены.", reply_markup=get_main_keyboard())
        return
    
    request = active_support_requests[user_id]
    
    # Если запрос уже в работе, уведомляем администратора
    if request['status'] == 'active' and 'admin_id' in request:
        admin_id = request['admin_id']
        try:
            await message.bot.send_message(
                chat_id=admin_id,
                text=f"❌ Пользователь отменил запрос в поддержку (ID: {user_id})",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить администратора об отмене: {e}")
        
        # Убираем из активных чатов администратора
        if admin_id in admin_sessions:
            admin_sessions[admin_id]['active_chats'] = [
                chat for chat in admin_sessions[admin_id]['active_chats'] 
                if chat != user_id
            ]
    
    # Удаляем запрос
    del active_support_requests[user_id]
    
    await message.answer(
        "✅ Ваш запрос в поддержку отменен.\n\n"
        "Если у вас возникнут вопросы, вы можете создать новый запрос.",
        reply_markup=get_main_keyboard()
    )
    
    add_notification(f"Пользователь {user_id} отменил запрос в поддержку")

# ========== ОБРАБОТЧИКИ КОМАНД ДЛЯ АДМИНИСТРАТОРОВ ==========

@router.message(Command("admin"))
async def admin_command(message: Message):
    """Панель администратора"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ У вас нет прав доступа.", reply_markup=get_main_keyboard())
        return
    
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Активные запросы", callback_data="show_active"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")
        ],
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="show_users"),
            InlineKeyboardButton(text="🎁 Промо-коды", callback_data="show_promo")
        ],
        [
            InlineKeyboardButton(text="📢 Управление рассылкой", callback_data="show_broadcast"),
            InlineKeyboardButton(text="⭐ Рейтинги", callback_data="show_ratings")
        ]
    ])
    
    # Статистика
    active_requests = len([r for r in active_support_requests.values() if r['status'] == 'waiting'])
    active_chats = len([r for r in active_support_requests.values() if r['status'] == 'active'])
    
    admin_text = (
        f"👑 *Панель администратора*\n\n"
        f"📊 *Краткая статистика:*\n"
        f"• 👥 Пользователей: {len(user_sessions)}\n"
        f"• 🆘 Ожидающих запросов: {active_requests}\n"
        f"• 💬 Активных чатов: {active_chats}\n"
        f"• 🎁 Промо-кодов: {len(promo_codes)}\n"
        f"• 📢 Подписчиков: {len([v for v in broadcast_subscribers.values() if v])}\n\n"
        f"Выберите раздел для управления:"
    )
    
    await message.answer(admin_text, parse_mode=ParseMode.MARKDOWN, reply_markup=inline_keyboard)

@router.message(Command("active"))
async def show_active_requests_command(message: Message):
    """Показать активные запросы"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    waiting_requests = [r for r in active_support_requests.values() if r['status'] == 'waiting']
    active_chats = [r for r in active_support_requests.values() if r['status'] == 'active']
    
    if not waiting_requests and not active_chats:
        await message.answer("📭 Нет активных запросов или чатов в поддержке.")
        return
    
    message_lines = ["🆘 *Активные запросы в поддержку:*\n\n"]
    
    if waiting_requests:
        message_lines.append("*📋 Ожидающие запросы:*")
        for i, (uid, request) in enumerate([(k, v) for k, v in active_support_requests.items() if v['status'] == 'waiting'], 1):
            user_info = request['user_info']
            wait_time = datetime.now() - request['created_at']
            minutes = int(wait_time.total_seconds() // 60)
            
            message_lines.extend([
                f"{i}. 👤 *{user_info.get('first_name', 'Пользователь')}*",
                f"   🆔 ID: {uid}",
                f"   📛 @{user_info.get('username', 'нет')}",
                f"   ⏱️ Ожидает: {minutes} мин.",
                f"   ────────"
            ])
    
    if active_chats:
        message_lines.append("\n*💬 Активные чаты:*")
        for i, (uid, request) in enumerate([(k, v) for k, v in active_support_requests.items() if v['status'] == 'active'], 1):
            user_info = request['user_info']
            admin_id = request.get('admin_id')
            admin_info = admin_sessions.get(admin_id, {}) if admin_id else {}
            admin_name = admin_info.get('first_name', f'Админ {admin_id}') if admin_id else 'Неизвестно'
            
            active_time = datetime.now() - request.get('admin_accepted_at', request['created_at'])
            minutes = int(active_time.total_seconds() // 60)
            
            message_lines.extend([
                f"{i}. 👤 *{user_info.get('first_name', 'Пользователь')}*",
                f"   🆔 ID: {uid}",
                f"   👨‍💻 Специалист: {admin_name}",
                f"   ⏱️ В работе: {minutes} мин.",
                f"   ────────"
            ])
    
    message_text = "\n".join(message_lines)
    await message.answer(message_text, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("stats"))
async def stats_command(message: Message):
    """Статистика бота"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    # Общая статистика
    total_users = len(user_sessions)
    total_messages = sum(user.get('total_messages', 0) for user in user_sessions.values())
    total_support_requests = sum(user.get('support_requests', 0) for user in user_sessions.values())
    total_promo_received = sum(user.get('promo_received', 0) for user in user_sessions.values())
    
    # Статистика по датам
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    
    new_users_today = len([
        user for user_id, user in user_sessions.items()
        if user.get('registered_at', datetime.now()).date() == today
    ])
    
    new_users_week = len([
        user for user_id, user in user_sessions.items()
        if user.get('registered_at', datetime.now()).date() >= week_ago
    ])
    
    # Активные пользователи
    active_today = len([
        user_id for user_id, user in user_sessions.items()
        if user.get('last_active', datetime.now()).date() == today
    ])
    
    # Промо-коды
    active_promo = len([code for code, data in promo_codes.items() if data.get('uses_left', 0) > 0])
    used_promo = len([code for code, data in promo_codes.items() if data.get('uses_left', 0) <= 0])
    
    # Поддержка
    waiting_requests = len([r for r in active_support_requests.values() if r['status'] == 'waiting'])
    active_chats = len([r for r in active_support_requests.values() if r['status'] == 'active'])
    
    # Рассылка
    subscribed_users = len([v for v in broadcast_subscribers.values() if v])
    
    stats_text = (
        f"📊 *Статистика бота*\n\n"
        
        f"👥 *Пользователи:*\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Новых сегодня: {new_users_today}\n"
        f"• Новых за неделю: {new_users_week}\n"
        f"• Активных сегодня: {active_today}\n\n"
        
        f"📨 *Активность:*\n"
        f"• Всего сообщений: {total_messages}\n"
        f"• Запросов в поддержку: {total_support_requests}\n"
        f"• Получено промо-кодов: {total_promo_received}\n\n"
        
        f"🎁 *Промо-коды:*\n"
        f"• Всего промо-кодов: {len(promo_codes)}\n"
        f"• Активных: {active_promo}\n"
        f"• Использованных: {used_promo}\n\n"
        
        f"🆘 *Поддержка:*\n"
        f"• Ожидающих запросов: {waiting_requests}\n"
        f"• Активных чатов: {active_chats}\n\n"
        
        f"📢 *Рассылка:*\n"
        f"• Подписчиков: {subscribed_users}/{total_users}\n"
        f"• Охват: {subscribed_users/total_users*100:.1f}%"
    )
    
    await message.answer(stats_text, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("users"))
async def users_command(message: Message):
    """Просмотр пользователей"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    if not user_sessions:
        await message.answer("📭 Нет зарегистрированных пользователей.")
        return
    
    # Сортируем пользователей по дате регистрации
    sorted_users = sorted(
        user_sessions.items(),
        key=lambda x: x[1].get('registered_at', datetime.now()),
        reverse=True
    )
    
    message_lines = ["👥 *Список пользователей:*\n\n"]
    
    for i, (uid, user_data) in enumerate(sorted_users[:20], 1):
        username = user_data.get('username', 'нет')
        first_name = user_data.get('first_name', 'Пользователь')
        last_name = user_data.get('last_name', '')
        registered = user_data.get('registered_at', datetime.now())
        last_active = user_data.get('last_active', datetime.now())
        
        # Рассчитываем активность
        days_since_active = (datetime.now() - last_active).days
        activity_status = "🟢" if days_since_active == 0 else "🟡" if days_since_active <= 7 else "🔴"
        
        # Статистика пользователя
        total_messages = user_data.get('total_messages', 0)
        support_requests = user_data.get('support_requests', 0)
        promo_received = user_data.get('promo_received', 0)
        
        message_lines.extend([
            f"{i}. {activity_status} *{first_name}* {last_name}",
            f"   📛 @{username}",
            f"   🆔 ID: {uid}",
            f"   📅 Регистрация: {registered.strftime('%Y-%m-%d')}",
            f"   📝 Сообщений: {total_messages}",
            f"   🆘 Запросов: {support_requests}",
            f"   🎁 Промо-кодов: {promo_received}",
            f"   ────────"
        ])
    
    if len(sorted_users) > 20:
        message_lines.append(f"\n... и еще {len(sorted_users) - 20} пользователей")
    
    message_text = "\n".join(message_lines)
    await message.answer(message_text, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("promo"))
async def promo_command(message: Message):
    """Управление промо-кодами"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    # Проверяем аргументы команды
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if args:
        action = args[0].lower()
        
        if action == "create":
            if len(args) >= 2:
                try:
                    uses = int(args[1])
                    code = generate_promo_code()
                    
                    promo_codes[code] = {
                        'uses_left': uses,
                        'total_uses': uses,
                        'created_at': datetime.now(),
                        'created_by': user_id,
                        'used_by': []
                    }
                    
                    save_data()
                    
                    await message.answer(
                        f"✅ Создан новый промо-код:\n\n"
                        f"🎁 Код: `{code}`\n"
                        f"📊 Использований: {uses}\n"
                        f"⏰ Создан: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    add_notification(f"Администратор {user_id} создал промо-код {code} ({uses} использований)")
                    
                except ValueError:
                    await message.answer(
                        "❌ Неверный формат количества использований.\n"
                        "Используйте: /promo create <количество>"
                    )
            else:
                await message.answer(
                    "❌ Укажите количество использований.\n"
                    "Используйте: /promo create <количество>"
                )
            return
        
        elif action == "delete":
            if len(args) >= 2:
                code = args[1].upper()
                
                if code in promo_codes:
                    del promo_codes[code]
                    save_data()
                    
                    await message.answer(f"✅ Промо-код `{code}` удален.")
                    add_notification(f"Администратор {user_id} удалил промо-код {code}")
                else:
                    await message.answer(f"❌ Промо-код `{code}` не найден.")
            else:
                await message.answer(
                    "❌ Укажите промо-код для удаления.\n"
                    "Используйте: /promo delete <код>"
                )
            return
    
    # Показываем список промо-кодов
    if not promo_codes:
        await message.answer(
            "📭 Нет созданных промо-кодов.\n\n"
            "Доступные команды:\n"
            "• /promo create <количество> - создать новый промо-код\n"
            "• /promo delete <код> - удалить промо-код"
        )
        return
    
    message_lines = ["🎁 *Список промо-кодов:*\n\n"]
    
    for i, (code, data) in enumerate(promo_codes.items(), 1):
        uses_left = data.get('uses_left', 0)
        total_uses = data.get('total_uses', 0)
        created_at = data.get('created_at', datetime.now())
        created_by = data.get('created_by', 'Неизвестно')
        
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except:
                created_at = datetime.now()
        
        status = "🟢 Активен" if uses_left > 0 else "🔴 Использован"
        used_by = data.get('used_by', [])
        
        message_lines.extend([
            f"{i}. {status} - `{code}`",
            f"   📊 {uses_left}/{total_uses} использований",
            f"   📅 Создан: {created_at.strftime('%Y-%m-%d')}",
            f"   👤 Создал: {created_by}",
            f"   👥 Использовали: {len(used_by)} пользователей",
            f"   ────────"
        ])
    
    message_text = "\n".join(message_lines)
    await message.answer(message_text, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("broadcastadmin"))
async def broadcast_admin_command(message: Message, state: FSMContext):
    """Управление рассылкой для администраторов"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if args:
        # Отправка рассылки через команду
        broadcast_text = ' '.join(args)
        
        await message.answer(
            f"📢 Начинаю рассылку...\n"
            f"Получателей: {len([v for v in broadcast_subscribers.values() if v])}"
        )
        
        sent, failed = await send_broadcast(message.bot, broadcast_text)
        
        await message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"📊 Результаты:\n"
            f"• Отправлено: {sent}\n"
            f"• Не удалось: {failed}\n"
            f"• Всего получателей: {len(broadcast_subscribers)}"
        )
        
        add_notification(f"Администратор {user_id} отправил рассылку ({sent} получателей)")
        return
    
    # Показываем статистику рассылки
    await show_broadcast_stats(message)

async def send_broadcast(bot: Bot, text: str) -> tuple[int, int]:
    """Отправка рассылки"""
    sent = 0
    failed = 0
    
    for uid, is_subscribed in broadcast_subscribers.items():
        if is_subscribed:
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN
                )
                sent += 1
            except Exception as e:
                logger.error(f"Не удалось отправить рассылку пользователю {uid}: {e}")
                failed += 1
    
    return sent, failed

async def show_broadcast_stats(message: Message):
    """Показать статистику рассылки"""
    total_users = len(broadcast_subscribers)
    subscribed = len([v for v in broadcast_subscribers.values() if v])
    unsubscribed = total_users - subscribed
    
    stats_text = (
        f"📢 *Управление рассылкой*\n\n"
        f"📊 *Статистика:*\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Подписано: {subscribed}\n"
        f"• Отписано: {unsubscribed}\n"
        f"• Охват: {subscribed/total_users*100:.1f}%\n\n"
        f"Для отправки рассылки используйте:\n"
        f"/broadcastadmin <текст сообщения>"
    )
    
    await message.answer(stats_text, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("ratings"))
async def ratings_command(message: Message):
    """Просмотр рейтингов администраторов"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    if not admin_ratings:
        await message.answer(
            "📭 Рейтингов пока нет.\n\n"
            "Рейтинги появятся после того, как пользователи оценят работу администраторов."
        )
        return
    
    # Сортируем администраторов по рейтингу
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
        if isinstance(last_updated, datetime):
            days_ago = (datetime.now() - last_updated).days
        else:
            try:
                days_ago = (datetime.now() - datetime.fromisoformat(last_updated)).days
            except:
                days_ago = 0
        
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
    
    await message.answer(message_text + stats_text, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("close"))
async def close_command(message: Message):
    """Закрытие чата администратором"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ У вас нет прав доступа.", reply_markup=get_main_keyboard())
        return
    
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        # Показываем активные чаты администратора
        active_chats = []
        for uid, request in active_support_requests.items():
            if request.get('admin_id') == user_id and request['status'] == 'active':
                active_chats.append(uid)
        
        if not active_chats:
            await message.answer("📭 У вас нет активных чатов для закрытия.")
            return
        
        message_lines = ["💬 *Ваши активные чаты:*\n\n"]
        
        for i, chat_id in enumerate(active_chats, 1):
            request = active_support_requests[chat_id]
            user_info = request.get('user_info', {})
            user_name = user_info.get('first_name', f'ID: {chat_id}')
            
            message_lines.extend([
                f"{i}. 👤 {user_name} (ID: {chat_id})",
                f"   Используйте: /close {chat_id}",
                f"   ────────"
            ])
        
        message_text = "\n".join(message_lines)
        await message.answer(message_text, parse_mode=ParseMode.MARKDOWN)
        return
    
    # Закрываем конкретный чат
    try:
        target_user_id = int(args[0])
        if target_user_id in active_support_requests:
            request = active_support_requests[target_user_id]
            
            # Уведомляем пользователя
            try:
                await message.bot.send_message(
                    chat_id=target_user_id,
                    text="🔒 *Чат с поддержкой завершен*\n\n"
                         "Специалист завершил сессию. Спасибо за обращение!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_main_keyboard()
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
            await message.answer(f"✅ Чат с пользователем {user_name} (ID: {target_user_id}) успешно закрыт.")
        else:
            await message.answer("❌ Чат не найден.")
    except ValueError:
        await message.answer(
            "❌ Неверный формат ID пользователя.\n"
            "Используйте: /close <ID пользователя>"
        )
    except Exception as e:
        logger.error(f"Ошибка при закрытии чата: {e}")
        await message.answer("❌ Произошла ошибка при закрытии чата.")

# ========== ОБРАБОТЧИКИ CALLBACK ЗАПРОСОВ ==========

@router.callback_query()
async def callback_handler(callback: CallbackQuery):
    """Обработка всех callback запросов"""
    data = callback.data
    user_id = callback.from_user.id
    
    # Оценка администратора пользователем
    if data.startswith('rate_'):
        parts = data.split('_')
        if len(parts) >= 3:
            target_user_id = int(parts[1])
            rating = int(parts[2])
            
            if target_user_id in active_support_requests:
                request = active_support_requests[target_user_id]
                
                if request.get('rating_given', False):
                    await callback.answer("❌ Вы уже оценили этот чат ранее.")
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
                        await callback.bot.send_message(
                            chat_id=admin_id,
                            text=f"⭐ *Новая оценка!*\n\n"
                                 f"Пользователь оценил ваш ответ на {rating}/5\n"
                                 f"Спасибо за качественную работу!",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Не удалось уведомить администратора об оценке: {e}")
                    
                    await callback.message.edit_text(
                        f"✅ Спасибо за оценку {rating} ⭐!\n\n"
                        f"Ваша оценка поможет нам улучшить качество поддержки."
                    )
                    
                    # Закрываем чат после оценки
                    if target_user_id in active_support_requests:
                        del active_support_requests[target_user_id]
                    
                    add_notification(f"Пользователь {target_user_id} оценил администратора {admin_id} на {rating}/5")
                    return
            
            await callback.answer("❌ Чат не найден или уже закрыт.")
        return
    
    # Обработка управления рассылкой для пользователей
    if data == "broadcast_subscribe":
        broadcast_subscribers[user_id] = True
        save_data()
        
        await callback.message.edit_text(
            "✅ Вы подписались на рассылку!\n\n"
            "Теперь вы будете получать:\n"
            "• Новые промо-коды\n"
            "• Важные объявления\n"
            "• Обновления бота\n"
            "• Специальные предложения"
        )
        await callback.answer()
        return
    
    elif data == "broadcast_unsubscribe":
        broadcast_subscribers[user_id] = False
        save_data()
        
        await callback.message.edit_text(
            "🔕 Вы отписались от рассылки.\n\n"
            "Вы больше не будете получать уведомления.\n"
            "Вы можете подписаться снова в любое время."
        )
        await callback.answer()
        return
    
    # Проверка прав для административных действий
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет прав для этого действия.")
        return
    
    # Принять запрос
    if data.startswith('accept_'):
        parts = data.split('_')
        if len(parts) >= 3:
            target_user_id = int(parts[1])
            admin_selector_id = int(parts[2]) if len(parts) > 2 else user_id
            
            if admin_selector_id != user_id:
                await callback.answer("❌ Этот запрос предназначен для другого администратора.")
                return
            
            if target_user_id not in active_support_requests:
                await callback.answer("❌ Запрос уже обработан.")
                return
            
            request = active_support_requests[target_user_id]
            
            request.update({
                'status': 'active',
                'admin_id': user_id,
                'admin_accepted_at': datetime.now(),
                'admin_name': callback.from_user.first_name
            })
            
            if user_id not in admin_sessions:
                admin_sessions[user_id] = {
                    'username': callback.from_user.username,
                    'first_name': callback.from_user.first_name,
                    'active_chats': []
                }
            admin_sessions[user_id]['active_chats'].append(target_user_id)
            
            # Добавляем кнопку для закрытия чата с оценкой
            close_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔒 Завершить чат и запросить оценку", 
                    callback_data=f"close_with_rating_{target_user_id}"
                )]
            ])
            
            accept_message = (
                f"✅ Вы приняли запрос от пользователя.\n\n"
                f"Теперь все ваши сообщения будут отправляться пользователю от имени бота.\n\n"
                f"*Совет:*\n"
                f"• Отвечайте вежливо и профессионально\n"
                f"• Решайте проблемы пользователя\n"
                f"• После решения завершите чат кнопкой ниже\n\n"
                f"Пользователь сможет оценить вашу работу."
            )
            
            await callback.message.edit_text(
                accept_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=close_keyboard
            )
            
            try:
                await callback.bot.send_message(
                    chat_id=target_user_id,
                    text="✅ *Специалист поддержки подключился к чату!*\n\n"
                         "Теперь вы можете задавать вопросы. Все сообщения будут отправляться специалисту.\n\n"
                         "После решения вопроса специалист завершит чат и вы сможете оценить качество помощи.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_main_keyboard()
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя: {e}")
            
            # Обновляем уведомления других администраторов
            if 'notification_messages' in request:
                for admin_id, message_id in request['notification_messages']:
                    try:
                        if admin_id != user_id:
                            await callback.bot.edit_message_text(
                                chat_id=admin_id,
                                message_id=message_id,
                                text="❌ Этот запрос уже принят другим специалистом.",
                                parse_mode=ParseMode.MARKDOWN
                            )
                    except Exception as e:
                        logger.error(f"Не удалось обновить уведомление: {e}")
        
        await callback.answer()
        return
    
    # Закрыть чат с запросом оценки
    elif data.startswith('close_with_rating_'):
        parts = data.split('_')
        if len(parts) >= 4:
            target_user_id = int(parts[3])
            
            if target_user_id not in active_support_requests:
                await callback.answer("❌ Чат уже закрыт.")
                return
            
            request = active_support_requests[target_user_id]
            
            # Проверяем, может ли этот администратор закрыть чат
            if request.get('admin_id') != user_id:
                await callback.answer("❌ Вы не можете закрыть этот чат.")
                return
            
            # Отправляем пользователю форму оценки
            rating_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="⭐ 1", callback_data=f"rate_{target_user_id}_1"),
                    InlineKeyboardButton(text="⭐ 2", callback_data=f"rate_{target_user_id}_2"),
                    InlineKeyboardButton(text="⭐ 3", callback_data=f"rate_{target_user_id}_3"),
                    InlineKeyboardButton(text="⭐ 4", callback_data=f"rate_{target_user_id}_4"),
                    InlineKeyboardButton(text="⭐ 5", callback_data=f"rate_{target_user_id}_5")
                ]
            ])
            
            try:
                await callback.bot.send_message(
                    chat_id=target_user_id,
                    text="🔒 *Чат с поддержкой завершен*\n\n"
                         "Пожалуйста, оцените работу специалиста:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=rating_keyboard
                )
            except Exception as e:
                logger.error(f"Не удалось отправить форму оценки пользователю: {e}")
            
            # Обновляем информацию об администраторе
            if user_id in admin_sessions:
                admin_sessions[user_id]['active_chats'] = [
                    chat for chat in admin_sessions[user_id]['active_chats'] 
                    if chat != target_user_id
                ]
            
            await callback.message.edit_text(
                f"✅ Чат с пользователем {target_user_id} завершен.\n"
                f"Пользователю отправлена форма для оценки."
            )
        
        await callback.answer()
        return
    
    # Отклонить запрос
    elif data.startswith('reject_'):
        target_user_id = int(data.split('_')[1])
        
        if target_user_id not in active_support_requests:
            await callback.answer("❌ Запрос уже обработан.")
            return
        
        try:
            await callback.bot.send_message(
                chat_id=target_user_id,
                text="❌ Ваш запрос в поддержку был отклонен специалистом.\n\n"
                     "Пожалуйста, попробуйте позже или свяжитесь другим способом.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя об отклонении: {e}")
        
        # Удаляем запрос
        del active_support_requests[target_user_id]
        
        await callback.message.edit_text(f"✅ Запрос от пользователя {target_user_id} отклонен.")
        
        # Обновляем уведомления других администраторов
        if target_user_id in active_support_requests:
            request = active_support_requests[target_user_id]
            if 'notification_messages' in request:
                for admin_id, message_id in request['notification_messages']:
                    try:
                        await callback.bot.edit_message_text(
                            chat_id=admin_id,
                            message_id=message_id,
                            text="❌ Этот запрос был отклонен другим специалистом.",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Не удалось обновить уведомление: {e}")
        
        add_notification(f"Администратор {user_id} отклонил запрос от пользователя {target_user_id}")
        await callback.answer()
        return
    
    # Обработка админ-меню
    elif data == "show_active":
        await show_active_requests_callback(callback)
    elif data == "show_stats":
        await stats_command_callback(callback)
    elif data == "show_users":
        await users_command_callback(callback)
    elif data == "show_promo":
        await promo_command_callback(callback)
    elif data == "show_broadcast":
        await broadcast_admin_command_callback(callback)
    elif data == "show_ratings":
        await ratings_command_callback(callback)
    elif data == "refresh_admin":
        await admin_command_callback(callback)
    elif data == "send_broadcast":
        await callback.message.edit_text(
            "📝 *Отправка рассылки*\n\n"
            "Введите текст для рассылки:\n"
            "(просто отправьте сообщение с текстом)",
            parse_mode=ParseMode.MARKDOWN
        )
        await callback.answer()
        # Используем FSM для ожидания текста рассылки
        from aiogram.fsm.context import FSMContext
        await dp.storage.set_state(chat=user_id, state=BroadcastStates.waiting_for_message)
        await dp.storage.update_data(chat=user_id, data={"awaiting_broadcast": True})
    
    elif data in ["promo_create", "promo_delete"]:
        await callback.answer("Используйте команду /promo с соответствующими аргументами")
    
    await callback.answer()

async def show_active_requests_callback(callback: CallbackQuery):
    """Показать активные запросы для callback"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    waiting_requests = [r for r in active_support_requests.values() if r['status'] == 'waiting']
    active_chats = [r for r in active_support_requests.values() if r['status'] == 'active']
    
    if not waiting_requests and not active_chats:
        await callback.message.edit_text("📭 Нет активных запросов или чатов в поддержке.")
        return
    
    message_lines = ["🆘 *Активные запросы в поддержку:*\n\n"]
    
    if waiting_requests:
        message_lines.append("*📋 Ожидающие запросы:*")
        for i, (uid, request) in enumerate([(k, v) for k, v in active_support_requests.items() if v['status'] == 'waiting'], 1):
            user_info = request['user_info']
            wait_time = datetime.now() - request['created_at']
            minutes = int(wait_time.total_seconds() // 60)
            
            message_lines.extend([
                f"{i}. 👤 *{user_info.get('first_name', 'Пользователь')}*",
                f"   🆔 ID: {uid}",
                f"   📛 @{user_info.get('username', 'нет')}",
                f"   ⏱️ Ожидает: {minutes} мин.",
                f"   ────────"
            ])
    
    if active_chats:
        message_lines.append("\n*💬 Активные чаты:*")
        for i, (uid, request) in enumerate([(k, v) for k, v in active_support_requests.items() if v['status'] == 'active'], 1):
            user_info = request['user_info']
            admin_id = request.get('admin_id')
            admin_info = admin_sessions.get(admin_id, {}) if admin_id else {}
            admin_name = admin_info.get('first_name', f'Админ {admin_id}') if admin_id else 'Неизвестно'
            
            active_time = datetime.now() - request.get('admin_accepted_at', request['created_at'])
            minutes = int(active_time.total_seconds() // 60)
            
            message_lines.extend([
                f"{i}. 👤 *{user_info.get('first_name', 'Пользователь')}*",
                f"   🆔 ID: {uid}",
                f"   👨‍💻 Специалист: {admin_name}",
                f"   ⏱️ В работе: {minutes} мин.",
                f"   ────────"
            ])
    
    message_text = "\n".join(message_lines)
    
    # Добавляем кнопки управления
    inline_keyboard = []
    for uid, request in active_support_requests.items():
        if request['status'] == 'waiting':
            user_info = request['user_info']
            inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"✅ Принять {user_info.get('first_name', f'ID {uid}')}",
                    callback_data=f"accept_{uid}_{user_id}"
                )
            ])
    
    # Кнопка возврата
    inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="refresh_admin")
    ])
    
    if inline_keyboard:
        inline_reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
        await callback.message.edit_text(
            message_text, 
            parse_mode=ParseMode.MARKDOWN, 
            reply_markup=inline_reply_markup
        )
    else:
        inline_keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="refresh_admin")]]
        inline_reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
        await callback.message.edit_text(
            message_text, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=inline_reply_markup
        )

async def stats_command_callback(callback: CallbackQuery):
    """Статистика бота для callback"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    # Общая статистика
    total_users = len(user_sessions)
    total_messages = sum(user.get('total_messages', 0) for user in user_sessions.values())
    total_support_requests = sum(user.get('support_requests', 0) for user in user_sessions.values())
    total_promo_received = sum(user.get('promo_received', 0) for user in user_sessions.values())
    
    # Статистика по датам
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    
    new_users_today = len([
        user for user_id, user in user_sessions.items()
        if user.get('registered_at', datetime.now()).date() == today
    ])
    
    new_users_week = len([
        user for user_id, user in user_sessions.items()
        if user.get('registered_at', datetime.now()).date() >= week_ago
    ])
    
    # Активные пользователи
    active_today = len([
        user_id for user_id, user in user_sessions.items()
        if user.get('last_active', datetime.now()).date() == today
    ])
    
    # Промо-коды
    active_promo = len([code for code, data in promo_codes.items() if data.get('uses_left', 0) > 0])
    used_promo = len([code for code, data in promo_codes.items() if data.get('uses_left', 0) <= 0])
    
    # Поддержка
    waiting_requests = len([r for r in active_support_requests.values() if r['status'] == 'waiting'])
    active_chats = len([r for r in active_support_requests.values() if r['status'] == 'active'])
    
    # Рассылка
    subscribed_users = len([v for v in broadcast_subscribers.values() if v])
    
    stats_text = (
        f"📊 *Статистика бота*\n\n"
        
        f"👥 *Пользователи:*\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Новых сегодня: {new_users_today}\n"
        f"• Новых за неделю: {new_users_week}\n"
        f"• Активных сегодня: {active_today}\n\n"
        
        f"📨 *Активность:*\n"
        f"• Всего сообщений: {total_messages}\n"
        f"• Запросов в поддержку: {total_support_requests}\n"
        f"• Получено промо-кодов: {total_promo_received}\n\n"
        
        f"🎁 *Промо-коды:*\n"
        f"• Всего промо-кодов: {len(promo_codes)}\n"
        f"• Активных: {active_promo}\n"
        f"• Использованных: {used_promo}\n\n"
        
        f"🆘 *Поддержка:*\n"
        f"• Ожидающих запросов: {waiting_requests}\n"
        f"• Активных чатов: {active_chats}\n\n"
        
        f"📢 *Рассылка:*\n"
        f"• Подписчиков: {subscribed_users}/{total_users}\n"
        f"• Охват: {subscribed_users/total_users*100:.1f}%"
    )
    
    # Кнопка возврата
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="refresh_admin")]
    ])
    
    await callback.message.edit_text(
        stats_text, 
        parse_mode=ParseMode.MARKDOWN, 
        reply_markup=inline_keyboard
    )

async def users_command_callback(callback: CallbackQuery):
    """Просмотр пользователей для callback"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    if not user_sessions:
        await callback.message.edit_text("📭 Нет зарегистрированных пользователей.")
        return
    
    # Сортируем пользователей по дате регистрации
    sorted_users = sorted(
        user_sessions.items(),
        key=lambda x: x[1].get('registered_at', datetime.now()),
        reverse=True
    )
    
    message_lines = ["👥 *Список пользователей:*\n\n"]
    
    for i, (uid, user_data) in enumerate(sorted_users[:20], 1):
        username = user_data.get('username', 'нет')
        first_name = user_data.get('first_name', 'Пользователь')
        last_name = user_data.get('last_name', '')
        registered = user_data.get('registered_at', datetime.now())
        last_active = user_data.get('last_active', datetime.now())
        
        # Рассчитываем активность
        days_since_active = (datetime.now() - last_active).days
        activity_status = "🟢" if days_since_active == 0 else "🟡" if days_since_active <= 7 else "🔴"
        
        # Статистика пользователя
        total_messages = user_data.get('total_messages', 0)
        support_requests = user_data.get('support_requests', 0)
        promo_received = user_data.get('promo_received', 0)
        
        message_lines.extend([
            f"{i}. {activity_status} *{first_name}* {last_name}",
            f"   📛 @{username}",
            f"   🆔 ID: {uid}",
            f"   📅 Регистрация: {registered.strftime('%Y-%m-%d')}",
            f"   📝 Сообщений: {total_messages}",
            f"   🆘 Запросов: {support_requests}",
            f"   🎁 Промо-кодов: {promo_received}",
            f"   ────────"
        ])
    
    if len(sorted_users) > 20:
        message_lines.append(f"\n... и еще {len(sorted_users) - 20} пользователей")
    
    message_text = "\n".join(message_lines)
    
    # Кнопки для управления
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="refresh_admin")]
    ])
    
    await callback.message.edit_text(
        message_text, 
        parse_mode=ParseMode.MARKDOWN, 
        reply_markup=inline_keyboard
    )

async def promo_command_callback(callback: CallbackQuery):
    """Управление промо-кодами для callback"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    # Показываем список промо-кодов
    if not promo_codes:
        message_text = (
            "📭 Нет созданных промо-кодов.\n\n"
            "Доступные команды:\n"
            "• /promo create <количество> - создать новый промо-код\n"
            "• /promo delete <код> - удалить промо-код"
        )
    else:
        message_lines = ["🎁 *Список промо-кодов:*\n\n"]
        
        for i, (code, data) in enumerate(promo_codes.items(), 1):
            uses_left = data.get('uses_left', 0)
            total_uses = data.get('total_uses', 0)
            created_at = data.get('created_at', datetime.now())
            created_by = data.get('created_by', 'Неизвестно')
            
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except:
                    created_at = datetime.now()
            
            status = "🟢 Активен" if uses_left > 0 else "🔴 Использован"
            used_by = data.get('used_by', [])
            
            message_lines.extend([
                f"{i}. {status} - `{code}`",
                f"   📊 {uses_left}/{total_uses} использований",
                f"   📅 Создан: {created_at.strftime('%Y-%m-%d')}",
                f"   👤 Создал: {created_by}",
                f"   👥 Использовали: {len(used_by)} пользователей",
                f"   ────────"
            ])
        
        message_text = "\n".join(message_lines)
    
    # Кнопки для управления
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Создать промо-код", callback_data="promo_create"),
            InlineKeyboardButton(text="🗑️ Удалить промо-код", callback_data="promo_delete")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="refresh_admin")
        ]
    ])
    
    await callback.message.edit_text(
        message_text, 
        parse_mode=ParseMode.MARKDOWN, 
        reply_markup=inline_keyboard
    )

async def broadcast_admin_command_callback(callback: CallbackQuery):
    """Управление рассылкой для администраторов для callback"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    # Показываем статистику рассылки
    total_users = len(broadcast_subscribers)
    subscribed = len([v for v in broadcast_subscribers.values() if v])
    unsubscribed = total_users - subscribed
    
    stats_text = (
        f"📢 *Управление рассылкой*\n\n"
        f"📊 *Статистика:*\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Подписано: {subscribed}\n"
        f"• Отписано: {unsubscribed}\n"
        f"• Охват: {subscribed/total_users*100:.1f}%\n\n"
        f"Для отправки рассылки нажмите кнопку ниже:"
    )
    
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Отправить рассылку", callback_data="send_broadcast"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="refresh_admin")
        ]
    ])
    
    await callback.message.edit_text(
        stats_text, 
        parse_mode=ParseMode.MARKDOWN, 
        reply_markup=inline_keyboard
    )

async def ratings_command_callback(callback: CallbackQuery):
    """Просмотр рейтингов администраторов для callback"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    if not admin_ratings:
        await callback.message.edit_text(
            "📭 Рейтингов пока нет.\n\n"
            "Рейтинги появятся после того, как пользователи оценят работу администраторов."
        )
        return
    
    # Сортируем администраторов по рейтингу
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
        if isinstance(last_updated, datetime):
            days_ago = (datetime.now() - last_updated).days
        else:
            try:
                days_ago = (datetime.now() - datetime.fromisoformat(last_updated)).days
            except:
                days_ago = 0
        
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
    
    # Кнопка возврата
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="refresh_admin")]
    ])
    
    await callback.message.edit_text(
        message_text + stats_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=inline_keyboard
    )

async def admin_command_callback(callback: CallbackQuery):
    """Панель администратора для callback"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Активные запросы", callback_data="show_active"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")
        ],
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="show_users"),
            InlineKeyboardButton(text="🎁 Промо-коды", callback_data="show_promo")
        ],
        [
            InlineKeyboardButton(text="📢 Управление рассылкой", callback_data="show_broadcast"),
            InlineKeyboardButton(text="⭐ Рейтинги", callback_data="show_ratings")
        ]
    ])
    
    # Статистика
    active_requests = len([r for r in active_support_requests.values() if r['status'] == 'waiting'])
    active_chats = len([r for r in active_support_requests.values() if r['status'] == 'active'])
    
    admin_text = (
        f"👑 *Панель администратора*\n\n"
        f"📊 *Краткая статистика:*\n"
        f"• 👥 Пользователей: {len(user_sessions)}\n"
        f"• 🆘 Ожидающих запросов: {active_requests}\n"
        f"• 💬 Активных чатов: {active_chats}\n"
        f"• 🎁 Промо-кодов: {len(promo_codes)}\n"
        f"• 📢 Подписчиков: {len([v for v in broadcast_subscribers.values() if v])}\n\n"
        f"Выберите раздел для управления:"
    )
    
    await callback.message.edit_text(
        admin_text, 
        parse_mode=ParseMode.MARKDOWN, 
        reply_markup=inline_keyboard
    )

# ========== ОБРАБОТКА СООБЩЕНИЙ В АКТИВНЫХ ЧАТАХ ==========

@router.message()
async def handle_messages(message: Message, state: FSMContext):
    """Обработка всех остальных сообщений"""
    user_id = message.from_user.id
    text = message.text
    
    # Проверяем, ожидает ли администратор текст рассылки
    current_state = await state.get_state()
    if current_state == BroadcastStates.waiting_for_message and is_admin(user_id):
        # Отправляем рассылку
        await message.answer(
            f"📢 Начинаю рассылку...\n"
            f"Получателей: {len([v for v in broadcast_subscribers.values() if v])}"
        )
        
        sent, failed = await send_broadcast(message.bot, text)
        
        await message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"📊 Результаты:\n"
            f"• Отправлено: {sent}\n"
            f"• Не удалось: {failed}\n"
            f"• Всего получателей: {len(broadcast_subscribers)}"
        )
        
        add_notification(f"Администратор {user_id} отправил рассылку ({sent} получателей)")
        await state.clear()
        return
    
    # Обновляем счетчик сообщений для пользователя
    if user_id in user_sessions:
        user_sessions[user_id]['total_messages'] += 1
        user_sessions[user_id]['last_active'] = datetime.now()
    
    # Если пользователь в активном чате с поддержкой
    if user_id in active_support_requests:
        request = active_support_requests[user_id]
        if request['status'] == 'active' and 'admin_id' in request:
            admin_id = request['admin_id']
            
            try:
                user_info = user_sessions.get(user_id, {})
                user_name = user_info.get('first_name', 'Пользователь')
                
                await message.bot.send_message(
                    chat_id=admin_id,
                    text=f"👤 *{user_name}:*\n{text}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                request['messages'].append({
                    'from': 'user',
                    'time': datetime.now(),
                    'text': text
                })
                
                return
            except Exception as e:
                logger.error(f"Ошибка отправки админу: {e}")
                await message.answer(
                    "❌ Специалист временно недоступен. Попробуйте позже.",
                    reply_markup=get_main_keyboard()
                )
    
    # Если администратор пишет пользователю в активном чате
    elif is_admin(user_id):
        # Проверяем, есть ли у администратора активные чаты
        if user_id in admin_sessions and admin_sessions[user_id]['active_chats']:
            # Находим активный чат администратора
            for target_user_id in admin_sessions[user_id]['active_chats']:
                if target_user_id in active_support_requests:
                    request = active_support_requests[target_user_id]
                    if request['status'] == 'active' and request.get('admin_id') == user_id:
                        try:
                            await message.bot.send_message(
                                chat_id=target_user_id,
                                text=f"👨‍💻 *Специалист:*\n{text}",
                                parse_mode=ParseMode.MARKDOWN
                            )
                            
                            request['messages'].append({
                                'from': 'admin',
                                'time': datetime.now(),
                                'text': text
                            })
                            
                            return
                        except Exception as e:
                            logger.error(f"Ошибка отправки пользователю: {e}")
                            await message.answer(f"❌ Не удалось отправить сообщение пользователю.")
                            return
    
    # Если сообщение не распознано, показываем подсказку
    hint_text = (
        "Не понимаю ваше сообщение 😕\n\n"
        "Пожалуйста, выберите действие из меню ниже или используйте команды:\n"
        "/start - главное меню\n"
        "/help - помощь\n"
        "/status - статус запроса\n"
        "/cancel - отменить запрос"
    )
    
    await message.answer(hint_text, reply_markup=get_main_keyboard())
    
    # Сохраняем данные
    save_data()

# ========== ЗАПУСК БОТА ==========

async def main():
    """Основная функция запуска бота"""
    # Загружаем данные при старте
    load_data()
    
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)
    
    print("🤖 Бот запущен на aiogram!")
    print(f"👑 Администраторов: {len(ADMIN_IDS)}")
    print(f"👥 Загружено пользователей: {len(user_sessions)}")
    print(f"🎁 Загружено промо-кодов: {len(promo_codes)}")
    print(f"📢 Подписчиков рассылки: {len([v for v in broadcast_subscribers.values() if v])}")
    print(f"⭐ Администраторов с рейтингом: {len(admin_ratings)}")
    print("💾 Автосохранение данных включено")
    print("📊 Система рейтинга администраторов активирована")
    print("Ожидание сообщений...")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
