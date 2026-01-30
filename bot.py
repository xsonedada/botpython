import logging
import json
from datetime import datetime
from typing import Dict, List, Optional
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode

# Конфигурация
BOT_TOKEN = "8213844298:AAHbMtsO6WBT7nzfd7DkwMRLmSBJzruk-3E"
WEBSITE_URL = "https://www.realtimegroup.ru/"
ADMIN_IDS = [724770396]  # ID всех администраторов (добавьте свои)

# Хранилище данных (в продакшене используйте БД)
active_support_requests: Dict[int, Dict] = {}  # Запросы в поддержку
user_sessions: Dict[int, Dict] = {}  # Информация о пользователях
admin_sessions: Dict[int, Dict] = {}  # Активные сессии администраторов

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Главное меню
    keyboard = [
        [KeyboardButton("🌐 Открыть сайт", web_app=WebAppInfo(url=WEBSITE_URL))],
        [KeyboardButton("🆘 Связаться с поддержкой")],
        [KeyboardButton("ℹ️ Информация")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # Сохраняем информацию о пользователе
    user_sessions[user_id] = {
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'last_active': datetime.now()
    }
    
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
        "• 🌐 Открыть сайт - запустить веб-приложение\n"
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
            "/help - эта справка\n\n"
            "Как отвечать пользователям:\n"
            "1. Нажмите 'Принять' на запросе\n"
            "2. Пишите сообщения - они будут пересылаться пользователю\n"
            "3. Используйте /close для завершения чата"
        )
    else:
        help_text = (
            "📚 *Помощь*\n\n"
            "Основные функции:\n"
            "• 🌐 Открыть сайт - запуск веб-приложения\n"
            "• 🆘 Связаться с поддержкой - получить помощь специалиста\n\n"
            "Команды:\n"
            "/start - главное меню\n"
            "/status - статус вашего запроса\n"
            "/cancel - отменить запрос\n"
            "/help - эта справка"
        )
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def call_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вызов поддержки"""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        await update.message.reply_text(
            "Вы администратор. Используйте /admin для управления поддержкой."
        )
        return
    
    # Проверяем существующий запрос
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
    
    # Создаем новый запрос
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
    
    # Отправляем уведомление всем администраторам
    user_info = user_sessions.get(user_id, {})
    notification_text = (
        f"🆘 *Новый запрос в поддержку!*\n\n"
        f"👤 Пользователь: {user_info.get('first_name', 'Пользователь')}\n"
        f"📛 Username: @{user_info.get('username', 'нет')}\n"
        f"🆔 ID: {user_id}\n"
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
    
    # Кнопка "Отклонить" для всех
    keyboard.append([
        InlineKeyboardButton("❌ Отклонить запрос", callback_data=f"reject_{user_id}")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем каждому администратору
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
    
    # Сохраняем ID сообщений для обновления
    active_support_requests[user_id]['notification_messages'] = sent_messages

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Проверяем, администратор ли это
    if is_admin(user_id):
        # Администратор может быть в чате с пользователем
        target_user_id = None
        for uid, request in active_support_requests.items():
            if request.get('admin_id') == user_id and request['status'] == 'active':
                target_user_id = uid
                break
        
        if target_user_id:
            # Пересылаем сообщение пользователю
            try:
                await update.message.forward(target_user_id)
                active_support_requests[target_user_id]['messages'].append({
                    'from': 'admin',
                    'time': datetime.now(),
                    'text': message_text
                })
            except Exception as e:
                await update.message.reply_text(
                    "❌ Не удалось отправить сообщение пользователю."
                )
                logger.error(f"Ошибка пересылки: {e}")
            return
    
    # Обработка для обычных пользователей
    if message_text == "🌐 Открыть сайт":
        keyboard = [[KeyboardButton("🌐 Открыть сайт", web_app=WebAppInfo(url=WEBSITE_URL))]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Нажмите кнопку ниже, чтобы открыть сайт 👇",
            reply_markup=reply_markup
        )
    
    elif message_text == "🆘 Связаться с поддержкой":
        await call_support(update, context)
    
    elif message_text == "ℹ️ Информация":
        await update.message.reply_text(
            "🤖 *Информация о боте*\n\n"
            "Этот бот предоставляет:\n"
            "• Доступ к сайту через мини-приложение\n"
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
                # Пересылаем сообщение администратору
                await update.message.forward(admin_id)
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
            [KeyboardButton("🌐 Открыть сайт", web_app=WebAppInfo(url=WEBSITE_URL))],
            [KeyboardButton("🆘 Связаться с поддержкой")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Выберите действие из меню 👇",
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
    
    # Принять запрос (конкретным администратором)
    if data.startswith('accept_'):
        parts = data.split('_')
        if len(parts) >= 3:
            target_user_id = int(parts[1])
            admin_selector_id = int(parts[2]) if len(parts) > 2 else user_id
            
            # Проверяем, может ли этот администратор принять запрос
            if admin_selector_id != user_id:
                await query.edit_message_text(
                    f"❌ Этот запрос предназначен для другого администратора."
                )
                return
            
            if target_user_id not in active_support_requests:
                await query.edit_message_text("❌ Запрос уже обработан.")
                return
            
            request = active_support_requests[target_user_id]
            
            # Обновляем статус
            request.update({
                'status': 'active',
                'admin_id': user_id,
                'admin_accepted_at': datetime.now(),
                'admin_name': query.from_user.first_name
            })
            
            # Обновляем информацию об администраторе
            if user_id in admin_sessions:
                admin_sessions[user_id]['active_chats'].append(target_user_id)
            
            # Уведомляем администратора
            await query.edit_message_text(
                f"✅ Вы приняли запрос от пользователя.\n\n"
                f"Теперь все ваши сообщения будут пересылаться пользователю.\n"
                f"Используйте /close_{target_user_id} для завершения чата."
            )
            
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="✅ *Специалист поддержки подключился к чату!*\n\n"
                         "Теперь вы можете задавать вопросы. Все сообщения будут отправляться специалисту.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя: {e}")
            
            # Обновляем остальные уведомления для других администраторов
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
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="❌ Ваш запрос в поддержку был отклонен.\n"
                         "Пожалуйста, попробуйте позже или уточните ваш вопрос."
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя: {e}")
            
            # Удаляем запрос
            del active_support_requests[target_user_id]
        
        await query.edit_message_text("❌ Запрос отклонен.")
    
    # Закрыть чат
    elif data.startswith('close_'):
        target_user_id = int(data.split('_')[1])
        
        if target_user_id in active_support_requests:
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
            await query.edit_message_text("✅ Чат успешно закрыт.")
        else:
            await query.edit_message_text("❌ Чат уже закрыт.")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    # Статистика
    waiting_count = sum(1 for req in active_support_requests.values() 
                       if req['status'] == 'waiting')
    active_count = sum(1 for req in active_support_requests.values() 
                      if req['status'] == 'active')
    
    # Активные чаты этого администратора
    admin_active_chats = []
    for uid, request in active_support_requests.items():
        if request.get('admin_id') == user_id and request['status'] == 'active':
            admin_active_chats.append(uid)
    
    # Создаем клавиатуру
    keyboard = []
    
    # Кнопки для активных запросов
    if waiting_count > 0:
        keyboard.append([
            InlineKeyboardButton(f"📥 Запросы в ожидании ({waiting_count})", 
                               callback_data="show_waiting")
        ])
    
    # Кнопки для активных чатов администратора
    if admin_active_chats:
        keyboard.append([
            InlineKeyboardButton(f"💬 Мои активные чаты ({len(admin_active_chats)})", 
                               callback_data="show_my_chats")
        ])
    
    # Общие кнопки
    keyboard.extend([
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
        f"• 👥 Всего активных чатов: {active_count}\n\n"
        f"Выберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def show_active_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные запросы (команда)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    if not active_support_requests:
        await update.message.reply_text("📭 Нет активных запросов.")
        return
    
    # Разделяем по статусам
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
        for uid, request in waiting_requests[:5]:  # Показываем первые 5
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
        
        # Уведомляем администратора, если есть
        if request['status'] == 'active' and 'admin_id' in request:
            admin_id = request['admin_id']
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"👤 Пользователь ID: {user_id} завершил чат."
                )
                # Обновляем информацию об администраторе
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

async def close_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрытие чата администратором"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /close <user_id>\n"
            "Пример: /close 123456789"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        
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
        del active_support_requests[target_user_id]
        await update.message.reply_text(f"✅ Чат с пользователем {target_user_id} закрыт.")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя.")

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
    
    # Считаем администраторов онлайн
    online_admins = 0
    for admin_id in ADMIN_IDS:
        if admin_id in admin_sessions:
            online_admins += 1
    
    await update.message.reply_text(
        f"📊 *Статистика бота*\n\n"
        f"👥 Пользователи:\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Активных сейчас: {len(active_support_requests)}\n\n"
        f"🆘 Поддержка:\n"
        f"• Запросов в ожидании: {waiting_count}\n"
        f"• Активных чатов: {active_count}\n\n"
        f"👑 Администраторы:\n"
        f"• Всего администраторов: {len(ADMIN_IDS)}\n"
        f"• Сейчас онлайн: {online_admins}",
        parse_mode=ParseMode.MARKDOWN
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка сообщений (только для админов)"""
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
            "/broadcast Всем привет! Это тестовая рассылка.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    message = ' '.join(context.args)
    
    # Подтверждение
    keyboard = [
        [InlineKeyboardButton("✅ Отправить", callback_data="confirm_broadcast")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_broadcast")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📢 *Подтвердите рассылку:*\n\n"
        f"{message}\n\n"
        f"Получателей: {len(user_sessions)}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    # Сохраняем сообщение
    context.user_data['broadcast_message'] = message

async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений от администраторов"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    # Если администратор пишет не в ответ на callback, показываем подсказку
    if update.message and not update.message.reply_to_message:
        # Проверяем, есть ли у администратора активные чаты
        active_chats = []
        for uid, request in active_support_requests.items():
            if request.get('admin_id') == user_id and request['status'] == 'active':
                active_chats.append(uid)
        
        if active_chats:
            await update.message.reply_text(
                f"💬 У вас {len(active_chats)} активных чатов.\n"
                f"Ваши сообщения будут отправлены пользователям.\n\n"
                f"Используйте /close <id> для завершения чата."
            )
        else:
            await update.message.reply_text(
                "👑 Вы администратор.\n"
                "Используйте /admin для управления поддержкой."
            )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    application.add_handler(CommandHandler("close", close_chat_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Callback-обработчики
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    print("🤖 Бот запущен!")
    print(f"👑 Администраторов: {len(ADMIN_IDS)}")
    print("Ожидание сообщений...")
    
    application.run_polling()

if __name__ == '__main__':
    main()
