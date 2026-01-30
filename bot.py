import logging
import re
import random
import string
from datetime import datetime
from typing import Dict, List
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode

# Конфигурация
BOT_TOKEN = "8213844298:AAHbMtsO6WBT7nzfd7DkwMRLmSBJzruk-3E"
WEBSITE_URL = "https://www.realtimegroup.ru/"
ADMIN_IDS = [724770396]  # ID всех администраторов (добавьте свои)

# Хранилище данных
active_support_requests: Dict[int, Dict] = {}
user_sessions: Dict[int, Dict] = {}
admin_sessions: Dict[int, Dict] = {}
promo_codes: Dict[str, Dict] = {}  # promo_code -> {'uses_left': X, 'created_by': admin_id}

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    keyboard = [
        [KeyboardButton("🎁 Получить промо-код")],
        [KeyboardButton("🆘 Связаться с поддержкой")],
        [KeyboardButton("ℹ️ Информация")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # Сохраняем информацию о пользователе
    user_data = {
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'last_active': datetime.now(),
        'promo_used': False,
        'registered_at': datetime.now(),
        'total_messages': 0,
        'support_requests': 0
    }
    
    # Если пользователь уже есть, обновляем только last_active
    if user_id in user_sessions:
        user_sessions[user_id]['last_active'] = datetime.now()
    else:
        user_sessions[user_id] = user_data
        logger.info(f"Новый пользователь: {user_id} ({user.username})")
    
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
    
    await update.message.reply_text(
        f"{greeting}\n\n"
        "Доступные функции:\n"
        "• 🎁 Получить промо-код - получить промо-код\n"
        "• 🆘 Связаться с поддержкой - получить помощь\n"
        "• ℹ️ Информация - о возможностях бота",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        help_text = (
            "👑 *Панель администратора*\n\n"
            "Команды:\n"
            "/start - главное меню\n"
            "/admin - управление поддержкой\n"
            "/active - активные запросы\n"
            "/stats - статистика\n"
            "/users - просмотр пользователей\n"
            "/promo - управление промо-кодами\n"
            "/help - эта справка\n\n"
            "Как отвечать пользователям:\n"
            "1. Нажмите 'Принять' на запросе\n"
            "2. Пишите сообщения - бот будет отправлять их от своего имени\n"
            "3. Используйте /close для завершения чата"
        )
    else:
        help_text = (
            "📚 *Помощь*\n\n"
            "Основные функции:\n"
            "• 🎁 Получить промо-код - получить промо-код\n"
            "• 🆘 Связаться с поддержкой - получить помощь специалиста\n\n"
            "Команды:\n"
            "/start - главное меню\n"
            "/status - статус вашего запроса\n"
            "/cancel - отменить запрос\n"
            "/help - эта справка"
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
    
    # Помечаем, что пользователь использовал промо-код
    if user_id in user_sessions:
        user_sessions[user_id]['promo_used'] = True
        user_sessions[user_id]['promo_received_at'] = datetime.now()
        user_sessions[user_id]['promo_code'] = active_promo
    
    await update.message.reply_text(
        f"🎉 *Ваш промо-код:* `{active_promo}`\n\n"
        f"Используйте его на нашем сайте!\n"
        f"Срок действия: бессрочно\n"
        f"Осталось использований: {promo_codes[active_promo]['uses_left']}",
        parse_mode=ParseMode.MARKDOWN
    )

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Обновляем счетчик сообщений для пользователя
    if user_id in user_sessions:
        user_sessions[user_id]['total_messages'] += 1
        user_sessions[user_id]['last_active'] = datetime.now()
    
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
    
    elif message_text == "ℹ️ Информация":
        await update.message.reply_text(
            "🤖 *Информация о боте*\n\n"
            "Этот бот предоставляет:\n"
            "• 🎁 Промо-коды для скидок\n"
            "• Техническую поддержку\n"
            "• Связь со специалистами\n\n"
            "Специалисты подключаются к чату в рабочее время.",
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
            [KeyboardButton("🆘 Связаться с поддержкой")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Выберите действие из меню 👇",
            reply_markup=reply_markup
        )

async def handle_close_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /close_123456789"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    command_text = update.message.text
    
    # Извлекаем ID пользователя из команды /close_123456789
    match = re.search(r'/close_(\d+)', command_text)
    if match:
        try:
            target_user_id = int(match.group(1))
            await close_chat(update, context, target_user_id)
            return
        except ValueError:
            pass
    
    # Если просто /close, показываем меню
    if command_text == '/close':
        await show_close_menu(update, context)
        return
    
    await update.message.reply_text(
        "❌ Неверный формат команды.\n"
        "Использование: /close <user_id>\n"
        "Или: /close_123456789"
    )

async def close_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: int):
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

async def show_close_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню закрытия чатов"""
    user_id = update.effective_user.id
    
    active_chats = []
    for uid, request in active_support_requests.items():
        if request.get('admin_id') == user_id and request['status'] == 'active':
            active_chats.append(uid)
    
    if not active_chats:
        await update.message.reply_text(
            "📭 У вас нет активных чатов.\n\n"
            "Использование:\n"
            "/close <user_id> - закрыть конкретный чат\n"
            "/close_123456789 - закрыть чат (альтернативный формат)\n"
            "/admin - просмотреть активные чаты"
        )
        return
    
    # Показываем список чатов с кнопками для закрытия
    keyboard = []
    for chat_id in active_chats:
        user_info = active_support_requests.get(chat_id, {}).get('user_info', {})
        user_name = user_info.get('first_name', f'ID: {chat_id}')
        
        keyboard.append([
            InlineKeyboardButton(
                f"🔒 Закрыть чат с {user_name}",
                callback_data=f"close_chat_{chat_id}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💬 *Ваши активные чаты:*\n\n"
        "Выберите чат для закрытия:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка inline-кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
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
            
            # Добавляем кнопку для быстрого закрытия чата
            close_keyboard = [[
                InlineKeyboardButton(
                    "🔒 Закрыть этот чат", 
                    callback_data=f"close_chat_{target_user_id}"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(close_keyboard)
            
            await query.edit_message_text(
                f"✅ Вы приняли запрос от пользователя.\n\n"
                f"Теперь все ваши сообщения будут отправляться пользователю от имени бота.\n"
                f"Используйте кнопку ниже или команду /close_{target_user_id} для завершения чата.",
                reply_markup=reply_markup
            )
            
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="✅ *Специалист поддержки подключился к чату!*\n\n"
                         "Теперь вы можете задавать вопросы. Все сообщения будут отправляться специалисту.",
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
    
    # Отклонить запрос
    elif data.startswith('reject_'):
        target_user_id = int(data.split('_')[1])
        
        if target_user_id in active_support_requests:
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="❌ Ваш запрос в поддержку был отклонен.\n"
                         "Пожалуйста, попробуйте позже или уточните ваш вопрос."
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя: {e}")
            
            del active_support_requests[target_user_id]
        
        await query.edit_message_text("❌ Запрос отклонен.")
    
    # Закрыть чат через кнопку
    elif data.startswith('close_chat_'):
        target_user_id = int(data.split('_')[2])
        
        if target_user_id not in active_support_requests:
            await query.edit_message_text("❌ Чат уже закрыт.")
            return
        
        request = active_support_requests[target_user_id]
        
        # Проверяем, может ли этот администратор закрыть чат
        if request.get('admin_id') != user_id:
            await query.edit_message_text("❌ Вы не можете закрыть этот чат.")
            return
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🔒 *Чат с поддержкой завершен*\n\n"
                     "Специалист завершил сессию. Если у вас остались вопросы, "
                     "вы можете создать новый запрос.",
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
        del active_support_requests[target_user_id]
        await query.edit_message_text(f"✅ Чат с пользователем {target_user_id} успешно закрыт.")
    
    # Обновить админ панель
    elif data == "refresh_admin":
        await update_admin_panel(query, context)
    
    # Управление промо-кодами
    elif data.startswith('promo_'):
        await handle_promo_callback(query, context, data)
    
    # Просмотр пользователей
    elif data.startswith('users_'):
        await handle_users_callback(query, context, data)

async def update_admin_panel(query, context):
    """Обновление админ панели"""
    user_id = query.from_user.id
    
    if user_id not in admin_sessions:
        admin_sessions[user_id] = {
            'username': query.from_user.username,
            'first_name': query.from_user.first_name,
            'active_chats': []
        }
    
    waiting_count = sum(1 for req in active_support_requests.values() 
                       if req['status'] == 'waiting')
    active_count = sum(1 for req in active_support_requests.values() 
                      if req['status'] == 'active')
    
    admin_active_chats = []
    for uid, request in active_support_requests.items():
        if request.get('admin_id') == user_id and request['status'] == 'active':
            admin_active_chats.append(uid)
    
    keyboard = []
    
    if waiting_count > 0:
        keyboard.append([
            InlineKeyboardButton(f"📥 Запросы в ожидании ({waiting_count})", 
                               callback_data="show_waiting")
        ])
    
    if admin_active_chats:
        keyboard.append([
            InlineKeyboardButton(f"💬 Мои активные чаты ({len(admin_active_chats)})", 
                               callback_data="show_my_chats")
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("👥 Пользователи", callback_data="users_menu")],
        [InlineKeyboardButton("🎁 Промо-коды", callback_data="promo_menu")],
        [InlineKeyboardButton("📊 Вся статистика", callback_data="show_stats")],
        [InlineKeyboardButton("👥 Все активные чаты", callback_data="show_all_active")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_admin")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👑 *Панель администратора*\n\n"
        f"📈 Ваша статистика:\n"
        f"• 📥 Ожидающих запросов: {waiting_count}\n"
        f"• 💬 Ваших активных чатов: {len(admin_active_chats)}\n"
        f"• 👥 Всего активных чатов: {active_count}\n"
        f"• 👤 Всего пользователей: {len(user_sessions)}\n\n"
        f"Выберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def handle_promo_callback(query, context, data):
    """Обработка промо-кодов через callback"""
    user_id = query.from_user.id
    
    if data == "promo_menu":
        # Меню промо-кодов
        active_promos = sum(1 for promo in promo_codes.values() if promo.get('uses_left', 0) > 0)
        total_promos = len(promo_codes)
        
        keyboard = [
            [InlineKeyboardButton("➕ Создать промо-код", callback_data="promo_create")],
            [InlineKeyboardButton("📋 Список промо-кодов", callback_data="promo_list")],
            [InlineKeyboardButton("🗑 Удалить промо-код", callback_data="promo_delete")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="refresh_admin")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎁 *Управление промо-кодами*\n\n"
            f"📊 Статистика:\n"
            f"• Всего промо-кодов: {total_promos}\n"
            f"• Активных: {active_promos}\n\n"
            f"Выберите действие:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif data == "promo_create":
        # Создание промо-кода
        promo_code = generate_promo_code()
        
        # Предлагаем выбрать количество использований
        keyboard = [
            [InlineKeyboardButton("1 использование", callback_data=f"promo_create_{promo_code}_1")],
            [InlineKeyboardButton("5 использований", callback_data=f"promo_create_{promo_code}_5")],
            [InlineKeyboardButton("10 использований", callback_data=f"promo_create_{promo_code}_10")],
            [InlineKeyboardButton("50 использований", callback_data=f"promo_create_{promo_code}_50")],
            [InlineKeyboardButton("100 использований", callback_data=f"promo_create_{promo_code}_100")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="promo_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎁 *Создание промо-кода*\n\n"
            f"Сгенерирован код: `{promo_code}`\n\n"
            f"Выберите количество использований:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif data.startswith("promo_create_"):
        # Сохранение промо-кода с выбранным количеством использований
        parts = data.split('_')
        if len(parts) >= 4:
            promo_code = parts[2]
            uses = int(parts[3])
            
            promo_codes[promo_code] = {
                'uses_left': uses,
                'total_uses': uses,
                'created_at': datetime.now(),
                'created_by': user_id,
                'used_by': []
            }
            
            await query.edit_message_text(
                f"✅ Промо-код создан!\n\n"
                f"🎁 Код: `{promo_code}`\n"
                f"📊 Использований: {uses}\n"
                f"👑 Создал: {query.from_user.first_name}\n"
                f"⏰ Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                parse_mode=ParseMode.MARKDOWN
            )
    
    elif data == "promo_list":
        # Список промо-кодов
        if not promo_codes:
            await query.edit_message_text("📭 Нет созданных промо-кодов.")
            return
        
        message_text = "📋 *Список промо-кодов:*\n\n"
        
        for code, data in list(promo_codes.items())[:10]:  # Показываем первые 10
            created_by = data.get('created_by', 'Неизвестно')
            created_at = data.get('created_at', datetime.now()).strftime('%Y-%m-%d')
            uses_left = data.get('uses_left', 0)
            total_uses = data.get('total_uses', 0)
            
            status = "✅ Активен" if uses_left > 0 else "❌ Завершен"
            
            message_text += (
                f"🎁 `{code}`\n"
                f"📊 {uses_left}/{total_uses} использований\n"
                f"📅 Создан: {created_at}\n"
                f"👤 Создал: {created_by}\n"
                f"📈 Статус: {status}\n"
                f"────────\n"
            )
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="promo_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif data == "promo_delete":
        # Удаление промо-кода
        if not promo_codes:
            await query.edit_message_text("📭 Нет промо-кодов для удаления.")
            return
        
        keyboard = []
        for code in list(promo_codes.keys())[:10]:  # Показываем первые 10 для удаления
            keyboard.append([
                InlineKeyboardButton(f"🗑 {code}", callback_data=f"promo_delete_{code}")
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="promo_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🗑 *Удаление промо-кода*\n\n"
            "Выберите промо-код для удаления:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif data.startswith("promo_delete_"):
        # Удаление конкретного промо-кода
        code = data.split('_')[2]
        
        if code in promo_codes:
            del promo_codes[code]
            await query.edit_message_text(f"✅ Промо-код `{code}` удален.")
        else:
            await query.edit_message_text(f"❌ Промо-код `{code}` не найден.")

async def handle_users_callback(query, context, data):
    """Обработка пользователей через callback"""
    user_id = query.from_user.id
    
    if data == "users_menu":
        # Меню пользователей
        total_users = len(user_sessions)
        active_today = sum(1 for user in user_sessions.values() 
                          if (datetime.now() - user.get('last_active', datetime.now())).days == 0)
        with_promo = sum(1 for user in user_sessions.values() 
                        if user.get('promo_used', False))
        
        keyboard = [
            [InlineKeyboardButton("📋 Список пользователей", callback_data="users_list")],
            [InlineKeyboardButton("📊 Статистика пользователей", callback_data="users_stats")],
            [InlineKeyboardButton("🔍 Поиск пользователя", callback_data="users_search")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="refresh_admin")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"👥 *Управление пользователями*\n\n"
            f"📊 Статистика:\n"
            f"• Всего пользователей: {total_users}\n"
            f"• Активных сегодня: {active_today}\n"
            f"• Получили промо-код: {with_promo}\n\n"
            f"Выберите действие:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif data == "users_list":
        # Список пользователей
        if not user_sessions:
            await query.edit_message_text("📭 Нет зарегистрированных пользователей.")
            return
        
        # Сортируем по дате регистрации (новые первые)
        sorted_users = sorted(user_sessions.items(), 
                            key=lambda x: x[1].get('registered_at', datetime.min), 
                            reverse=True)
        
        message_text = "📋 *Список пользователей:*\n\n"
        
        for user_id, user_data in list(sorted_users)[:15]:  # Показываем первые 15
            username = user_data.get('username', 'нет')
            first_name = user_data.get('first_name', 'Неизвестно')
            last_active = user_data.get('last_active', datetime.now())
            days_ago = (datetime.now() - last_active).days
            promo_used = "✅" if user_data.get('promo_used', False) else "❌"
            reg_date = user_data.get('registered_at', datetime.now()).strftime('%Y-%m-%d')
            
            message_text += (
                f"👤 *{first_name}* (@{username})\n"
                f"🆔 ID: `{user_id}`\n"
                f"📅 Зарегистрирован: {reg_date}\n"
                f"⏰ Был(а): {days_ago} дн. назад\n"
                f"🎁 Промо-код: {promo_used}\n"
                f"📨 Сообщений: {user_data.get('total_messages', 0)}\n"
                f"────────\n"
            )
        
        # Добавляем пагинацию если много пользователей
        keyboard = []
        if len(sorted_users) > 15:
            keyboard.append([InlineKeyboardButton("📄 Следующие 15", callback_data="users_list_2")])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="users_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif data == "users_stats":
        # Статистика пользователей
        total_users = len(user_sessions)
        
        # Подсчет по дням активности
        today = datetime.now().date()
        active_today = 0
        active_week = 0
        active_month = 0
        
        for user_data in user_sessions.values():
            last_active = user_data.get('last_active', datetime.now()).date()
            days_diff = (today - last_active).days
            
            if days_diff == 0:
                active_today += 1
            if days_diff <= 7:
                active_week += 1
            if days_diff <= 30:
                active_month += 1
        
        # Пользователи с промо-кодами
        with_promo = sum(1 for user in user_sessions.values() 
                        if user.get('promo_used', False))
        
        # Среднее количество сообщений
        total_messages = sum(user.get('total_messages', 0) for user in user_sessions.values())
        avg_messages = total_messages / total_users if total_users > 0 else 0
        
        # Пользователи с запросами в поддержку
        with_support = sum(1 for user in user_sessions.values() 
                          if user.get('support_requests', 0) > 0)
        
        message_text = (
            f"📊 *Статистика пользователей*\n\n"
            f"👥 Всего пользователей: *{total_users}*\n\n"
            f"📈 Активность:\n"
            f"• Активных сегодня: {active_today}\n"
            f"• Активных за неделю: {active_week}\n"
            f"• Активных за месяц: {active_month}\n\n"
            f"🎁 Промо-коды:\n"
            f"• Получили промо-код: {with_promo}\n"
            f"• Без промо-кода: {total_users - with_promo}\n\n"
            f"💬 Взаимодействие:\n"
            f"• Всего сообщений: {total_messages}\n"
            f"• Среднее на пользователя: {avg_messages:.1f}\n"
            f"• Обращались в поддержку: {with_support}\n"
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="users_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif data == "users_search":
        # Поиск пользователя
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="users_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔍 *Поиск пользователя*\n\n"
            "Для поиска пользователя используйте команду:\n"
            "/finduser <id> - найти по ID\n"
            "/finduser @username - найти по username\n\n"
            "Пример:\n"
            "/finduser 123456789\n"
            "/finduser @username",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    if user_id not in admin_sessions:
        admin_sessions[user_id] = {
            'username': update.effective_user.username,
            'first_name': update.effective_user.first_name,
            'active_chats': []
        }
    
    waiting_count = sum(1 for req in active_support_requests.values() 
                       if req['status'] == 'waiting')
    active_count = sum(1 for req in active_support_requests.values() 
                      if req['status'] == 'active')
    
    admin_active_chats = []
    for uid, request in active_support_requests.items():
        if request.get('admin_id') == user_id and request['status'] == 'active':
            admin_active_chats.append(uid)
    
    keyboard = []
    
    if waiting_count > 0:
        keyboard.append([
            InlineKeyboardButton(f"📥 Запросы в ожидании ({waiting_count})", 
                               callback_data="show_waiting")
        ])
    
    if admin_active_chats:
        keyboard.append([
            InlineKeyboardButton(f"💬 Мои активные чаты ({len(admin_active_chats)})", 
                               callback_data="show_my_chats")
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("👥 Пользователи", callback_data="users_menu")],
        [InlineKeyboardButton("🎁 Промо-коды", callback_data="promo_menu")],
        [InlineKeyboardButton("📊 Вся статистика", callback_data="show_stats")],
        [InlineKeyboardButton("👥 Все активные чаты", callback_data="show_all_active")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_admin")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👑 *Панель администратора*\n\n"
        f"📈 Ваша статистика:\n"
        f"• 📥 Ожидающих запросов: {waiting_count}\n"
        f"• 💬 Ваших активных чатов: {len(admin_active_chats)}\n"
        f"• 👥 Всего активных чатов: {active_count}\n"
        f"• 👤 Всего пользователей: {len(user_sessions)}\n\n"
        f"Выберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр пользователей (команда)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    if context.args:
        # Поиск пользователя
        search_term = ' '.join(context.args)
        
        found_users = []
        
        # Ищем по ID
        if search_term.isdigit():
            target_id = int(search_term)
            if target_id in user_sessions:
                found_users.append((target_id, user_sessions[target_id]))
        
        # Ищем по username (без @)
        else:
            search_term = search_term.lower().replace('@', '')
            for uid, user_data in user_sessions.items():
                username = user_data.get('username', '').lower()
                first_name = user_data.get('first_name', '').lower()
                
                if search_term in username or search_term in first_name:
                    found_users.append((uid, user_data))
        
        if found_users:
            message_text = "🔍 *Результаты поиска:*\n\n"
            
            for uid, user_data in found_users[:5]:  # Показываем первые 5
                username = user_data.get('username', 'нет')
                first_name = user_data.get('first_name', 'Неизвестно')
                last_active = user_data.get('last_active', datetime.now())
                days_ago = (datetime.now() - last_active).days
                promo_used = "✅" if user_data.get('promo_used', False) else "❌"
                reg_date = user_data.get('registered_at', datetime.now()).strftime('%Y-%m-%d')
                
                message_text += (
                    f"👤 *{first_name}* (@{username})\n"
                    f"🆔 ID: `{uid}`\n"
                    f"📅 Зарегистрирован: {reg_date}\n"
                    f"⏰ Был(а): {days_ago} дн. назад\n"
                    f"🎁 Промо-код: {promo_used}\n"
                    f"📨 Сообщений: {user_data.get('total_messages', 0)}\n"
                    f"🆘 Запросов в поддержку: {user_data.get('support_requests', 0)}\n"
                    f"────────\n"
                )
            
            if len(found_users) > 5:
                message_text += f"\n*... и еще {len(found_users) - 5} пользователей*"
            
            await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ Пользователи не найдены.")
    
    else:
        # Общая статистика пользователей
        total_users = len(user_sessions)
        active_today = sum(1 for user in user_sessions.values() 
                          if (datetime.now() - user.get('last_active', datetime.now())).days == 0)
        with_promo = sum(1 for user in user_sessions.values() 
                        if user.get('promo_used', False))
        
        await update.message.reply_text(
            f"👥 *Статистика пользователей*\n\n"
            f"📊 Основные данные:\n"
            f"• Всего пользователей: {total_users}\n"
            f"• Активных сегодня: {active_today}\n"
            f"• Получили промо-код: {with_promo}\n\n"
            f"Использование:\n"
            "/users - эта статистика\n"
            "/users <id/имя> - поиск пользователя\n"
            "/admin - графический интерфейс",
            parse_mode=ParseMode.MARKDOWN
        )

async def finduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск пользователя (альтернативная команда)"""
    await users_command(update, context)

async def show_active_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные запросы"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    if not active_support_requests:
        await update.message.reply_text("📭 Нет активных запросов.")
        return
    
    waiting_requests = []
    active_requests = []
    
    for uid, request in active_support_requests.items():
        if request['status'] == 'waiting':
            waiting_requests.append((uid, request))
        elif request['status'] == 'active':
            active_requests.append((uid, request))
    
    message_text = ""
    
    if waiting_requests:
        message_text += "⏳ *Запросы в ожидании:*\n\n"
        for uid, request in waiting_requests[:5]:
            user_info = request.get('user_info', {})
            wait_time = (datetime.now() - request['created_at']).seconds // 60
            message_text += (
                f"👤 {user_info.get('first_name', 'Пользователь')}\n"
                f"⏰ Ожидает: {wait_time} мин.\n"
                f"🆔 ID: {uid}\n"
                f"────────\n"
            )
    
    if active_requests:
        message_text += "\n💬 *Активные чаты:*\n\n"
        for uid, request in active_requests[:5]:
            user_info = request.get('user_info', {})
            admin_id = request.get('admin_id')
            admin_name = "Неизвестно"
            
            if admin_id and admin_id in admin_sessions:
                admin_name = admin_sessions[admin_id].get('first_name', f'Админ {admin_id}')
            
            message_text += (
                f"👤 {user_info.get('first_name', 'Пользователь')}\n"
                f"🛠 Специалист: {admin_name}\n"
                f"🆔 ID: {uid}\n"
                f"────────\n"
            )
    
    if not message_text:
        message_text = "📭 Нет активных запросов."
    
    await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка статуса запроса"""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        await update.message.reply_text(
            "Вы администратор. Используйте /admin для управления."
        )
        return
    
    if user_id in active_support_requests:
        request = active_support_requests[user_id]
        
        if request['status'] == 'waiting':
            wait_time = (datetime.now() - request['created_at']).seconds // 60
            await update.message.reply_text(
                f"⏳ Ваш запрос в очереди.\n"
                f"Ожидание: {wait_time} минут\n"
                f"Специалист скоро подключится."
            )
        elif request['status'] == 'active':
            await update.message.reply_text(
                "✅ Вы общаетесь со специалистом поддержки.\n"
                "Пишите ваши вопросы прямо здесь."
            )
    else:
        await update.message.reply_text(
            "📭 У вас нет активных запросов.\n"
            "Нажмите '🆘 Связаться с поддержкой', чтобы создать запрос."
        )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена запроса"""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        await update.message.reply_text(
            "Вы администратор. Используйте /admin для управления."
        )
        return
    
    if user_id in active_support_requests:
        request = active_support_requests[user_id]
        
        if request['status'] == 'active' and 'admin_id' in request:
            admin_id = request['admin_id']
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"👤 Пользователь ID: {user_id} завершил чат."
                )
                if admin_id in admin_sessions:
                    admin_sessions[admin_id]['active_chats'] = [
                        chat for chat in admin_sessions[admin_id]['active_chats'] 
                        if chat != user_id
                    ]
            except Exception as e:
                logger.error(f"Не удалось уведомить администратора: {e}")
        
        del active_support_requests[user_id]
        await update.message.reply_text(
            "✅ Запрос в поддержку отменен.\n"
            "Вы можете создать новый запрос при необходимости."
        )
    else:
        await update.message.reply_text("❌ У вас нет активных запросов.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    waiting_count = sum(1 for req in active_support_requests.values() 
                       if req['status'] == 'waiting')
    active_count = sum(1 for req in active_support_requests.values() 
                      if req['status'] == 'active')
    total_users = len(user_sessions)
    
    # Статистика по промо-кодам
    total_promos = len(promo_codes)
    active_promos = sum(1 for promo in promo_codes.values() if promo.get('uses_left', 0) > 0)
    used_promos = sum(promo.get('total_uses', 0) - promo.get('uses_left', 0) for promo in promo_codes.values())
    
    # Статистика пользователей
    active_today = sum(1 for user in user_sessions.values() 
                      if (datetime.now() - user.get('last_active', datetime.now())).days == 0)
    with_promo = sum(1 for user in user_sessions.values() 
                    if user.get('promo_used', False))
    total_messages = sum(user.get('total_messages', 0) for user in user_sessions.values())
    
    online_admins = 0
    for admin_id in ADMIN_IDS:
        if admin_id in admin_sessions:
            online_admins += 1
    
    await update.message.reply_text(
        f"📊 *Статистика бота*\n\n"
        f"👥 Пользователи:\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Активных сегодня: {active_today}\n"
        f"• Получили промо-код: {with_promo}\n"
        f"• Всего сообщений: {total_messages}\n\n"
        f"🆘 Поддержка:\n"
        f"• Запросов в ожидании: {waiting_count}\n"
        f"• Активных чатов: {active_count}\n\n"
        f"🎁 Промо-коды:\n"
        f"• Всего промо-кодов: {total_promos}\n"
        f"• Активных: {active_promos}\n"
        f"• Использовано раз: {used_promos}\n\n"
        f"👑 Администраторы:\n"
        f"• Всего администраторов: {len(ADMIN_IDS)}\n"
        f"• Сейчас онлайн: {online_admins}",
        parse_mode=ParseMode.MARKDOWN
    )

async def promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление промо-кодами (команда)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    # Создание промо-кода через команду
    if context.args:
        if context.args[0] == "create":
            if len(context.args) >= 2:
                try:
                    uses = int(context.args[1])
                    promo_code = generate_promo_code()
                    
                    promo_codes[promo_code] = {
                        'uses_left': uses,
                        'total_uses': uses,
                        'created_at': datetime.now(),
                        'created_by': user_id,
                        'used_by': []
                    }
                    
                    await update.message.reply_text(
                        f"✅ Промо-код создан!\n\n"
                        f"🎁 Код: `{promo_code}`\n"
                        f"📊 Использований: {uses}\n"
                        f"👑 Создал: {update.effective_user.first_name}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except ValueError:
                    await update.message.reply_text(
                        "❌ Неверное количество использований.\n"
                        "Пример: /promo create 10"
                    )
            else:
                await update.message.reply_text(
                    "❌ Укажите количество использований.\n"
                    "Пример: /promo create 10"
                )
        elif context.args[0] == "list":
            if not promo_codes:
                await update.message.reply_text("📭 Нет созданных промо-кодов.")
                return
            
            message_text = "📋 *Список промо-кодов:*\n\n"
            
            for code, data in promo_codes.items():
                created_by = data.get('created_by', 'Неизвестно')
                uses_left = data.get('uses_left', 0)
                total_uses = data.get('total_uses', 0)
                
                status = "✅ Активен" if uses_left > 0 else "❌ Завершен"
                
                message_text += (
                    f"🎁 `{code}` - {uses_left}/{total_uses} использований ({status})\n"
                )
            
            await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)
        
        elif context.args[0] == "delete":
            if len(context.args) >= 2:
                code = context.args[1]
                if code in promo_codes:
                    del promo_codes[code]
                    await update.message.reply_text(f"✅ Промо-код `{code}` удален.")
                else:
                    await update.message.reply_text(f"❌ Промо-код `{code}` не найден.")
            else:
                await update.message.reply_text(
                    "❌ Укажите промо-код для удаления.\n"
                    "Пример: /promo delete ABC123"
                )
    else:
        # Если команда без аргументов, показываем справку
        await update.message.reply_text(
            "🎁 *Управление промо-кодами*\n\n"
            "Команды:\n"
            "/promo create <количество> - создать промо-код\n"
            "/promo list - список промо-кодов\n"
            "/promo delete <код> - удалить промо-код\n\n"
            "Или используйте /admin для графического интерфейса.",
            parse_mode=ParseMode.MARKDOWN
        )

async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений от администраторов"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    if update.message and not update.message.reply_to_message:
        active_chats = []
        for uid, request in active_support_requests.items():
            if request.get('admin_id') == user_id and request['status'] == 'active':
                active_chats.append(uid)
        
        if active_chats:
            await update.message.reply_text(
                f"💬 У вас {len(active_chats)} активных чатов.\n"
                f"Ваши сообщения будут отправляться пользователям от имени бота.\n\n"
                f"Используйте /close для завершения чата."
            )
        else:
            await update.message.reply_text(
                "👑 Вы администратор.\n"
                "Используйте /admin для управления поддержкой и промо-кодами."
            )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=True)

def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("active", show_active_requests))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("promo", promo_command))
    application.add_handler(CommandHandler("users", users_command))
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
    print("🎁 Система промо-кодов активирована")
    print("👥 Система пользователей активирована")
    print("Ожидание сообщений...")
    
    application.run_polling()

if __name__ == '__main__':
    main()
