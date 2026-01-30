import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import aiohttp
from telethon import TelegramClient, events
from telethon.errors import RPCError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

# ============ КОНФИГУРАЦИЯ ============
# Telegram API (получить на https://my.telegram.org)
API_ID = int(os.environ.get('API_ID', '39678712'))
API_HASH = os.environ.get('API_HASH', '3089ac53d532e75deb5dd641e4863d49')
PHONE = os.environ.get('PHONE', '+919036205120')

# OpenRouter API
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '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')
MODEL_NAME = os.environ.get('MODEL_NAME', 'google/gemini-3-flash-preview')

# Команда активации AI
ACTIVATION_COMMAND = 'Ai Edem'

# Файлы базы данных
DB_FILE = 'messages.json'
ACTIVE_CHATS_FILE = 'active_chats.json'
DELETED_MESSAGES_DB = 'deleted_messages.json'
SAVER_CONFIG_FILE = 'saver_config.json'
MESSAGES_STORAGE_DB = 'messages_storage.json'  # НОВАЯ БД для всех сообщений

# Имя сессии для Railway (отдельная сессия!)
SESSION_NAME = 'railway_session'

# Папка для сохранения медиафайлов
MEDIA_FOLDER = 'saved_media'

# ID владельца аккаунта (будет установлен при запуске)
OWNER_ID = None

# НОВОЕ: Трекинг команд для умного удаления
last_command_message = {}  # {chat_id: message_id}

# НОВОЕ: Список команд для фильтрации
COMMAND_PREFIXES = ['.saver', 'ai stop', 'ai clear', 'ai edem']


# ============ РАБОТА С БАЗОЙ ДАННЫХ ============
def load_db():
    """Загрузка истории сообщений"""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'⚠️ Ошибка загрузки БД: {e}')
            return {}
    return {}


def save_db(data):
    """Сохранение истории сообщений"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'⚠️ Ошибка сохранения БД: {e}')


def load_active_chats():
    """Загрузка списка активных чатов"""
    if os.path.exists(ACTIVE_CHATS_FILE):
        try:
            with open(ACTIVE_CHATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'⚠️ Ошибка загрузки активных чатов: {e}')
            return {}
    return {}


def save_active_chats(data):
    """Сохранение списка активных чатов"""
    try:
        with open(ACTIVE_CHATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'⚠️ Ошибка сохранения активных чатов: {e}')


def is_chat_active(chat_id):
    """Проверка, активен ли чат"""
    active_chats = load_active_chats()
    return str(chat_id) in active_chats and active_chats[str(chat_id)]


def activate_chat(chat_id):
    """Активация чата"""
    active_chats = load_active_chats()
    active_chats[str(chat_id)] = True
    save_active_chats(active_chats)
    print(f'✅ Чат {chat_id} активирован')


def deactivate_chat(chat_id):
    """Деактивация чата"""
    active_chats = load_active_chats()
    active_chats[str(chat_id)] = False
    save_active_chats(active_chats)
    print(f'❌ Чат {chat_id} деактивирован')


# ============ НОВОЕ: РАБОТА С ХРАНИЛИЩЕМ ВСЕХ СООБЩЕНИЙ ============
def load_messages_storage():
    """Загрузка хранилища всех сообщений"""
    if os.path.exists(MESSAGES_STORAGE_DB):
        try:
            with open(MESSAGES_STORAGE_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'⚠️ Ошибка загрузки хранилища сообщений: {e}')
            return {}
    return {}


def save_messages_storage(data):
    """Сохранение хранилища всех сообщений"""
    try:
        with open(MESSAGES_STORAGE_DB, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'⚠️ Ошибка сохранения хранилища сообщений: {e}')


def store_message_immediately(chat_id, message_data):
    """НЕМЕДЛЕННОЕ сохранение сообщения в постоянное хранилище"""
    storage = load_messages_storage()
    chat_key = str(chat_id)
    
    if chat_key not in storage:
        storage[chat_key] = []
        print(f'   📁 Создана новая запись для чата {chat_key}')
    
    storage[chat_key].append(message_data)
    
    # Ограничение: храним последние 1000 сообщений на чат
    if len(storage[chat_key]) > 1000:
        removed = len(storage[chat_key]) - 1000
        storage[chat_key] = storage[chat_key][-1000:]
        print(f'   🧹 Удалено {removed} старых сообщений (лимит 1000)')
    
    save_messages_storage(storage)
    print(f'   💾 Сообщение {message_data["message_id"]} сохранено в storage (всего в чате: {len(storage[chat_key])})')
    
    return True


def get_stored_message(chat_id, message_id):
    """Получить сохраненное сообщение по ID
    
    Если chat_id=None, ищем по всем чатам (проблема Telethon с MessageDeleted)
    """
    storage = load_messages_storage()
    
    # Если chat_id известен - ищем только в этом чате
    if chat_id is not None:
        chat_key = str(chat_id)
        
        if chat_key not in storage:
            print(f'   ⚠️ Чат {chat_key} не найден в storage')
            # Пробуем искать по всем чатам на всякий случай
            print(f'   🔍 Пробуем искать по всем чатам...')
        else:
            for msg in storage[chat_key]:
                if msg.get('message_id') == message_id:
                    print(f'   ✅ Сообщение {message_id} найдено в чате {chat_key}')
                    return msg
            
            print(f'   ⚠️ Сообщение {message_id} НЕ найдено в чате {chat_key} (всего: {len(storage[chat_key])})')
    
    # Если не нашли или chat_id=None - ищем по ВСЕМ чатам
    print(f'   🔍 Поиск сообщения {message_id} по ВСЕМ чатам...')
    
    for chat_key, messages in storage.items():
        for msg in messages:
            if msg.get('message_id') == message_id:
                print(f'   ✅ Сообщение {message_id} найдено в чате {chat_key}!')
                return msg
    
    print(f'   ❌ Сообщение {message_id} НЕ найдено ни в одном чате')
    return None


def is_command_message(text):
    """Проверка, является ли сообщение командой"""
    if not text:
        return False
    
    text_lower = text.lower().strip()
    for prefix in COMMAND_PREFIXES:
        if text_lower.startswith(prefix.lower()):
            return True
    
    return False


# ============ РАБОТА С СОХРАНЕНИЕМ УДАЛЕННЫХ СООБЩЕНИЙ ============
def load_deleted_messages_db():
    """Загрузка базы удаленных сообщений"""
    if os.path.exists(DELETED_MESSAGES_DB):
        try:
            with open(DELETED_MESSAGES_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'⚠️ Ошибка загрузки БД удаленных сообщений: {e}')
            return {}
    return {}


def save_deleted_messages_db(data):
    """Сохранение базы удаленных сообщений"""
    try:
        with open(DELETED_MESSAGES_DB, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'⚠️ Ошибка сохранения БД удаленных сообщений: {e}')


def load_saver_config():
    """Загрузка конфигурации сохранения"""
    if os.path.exists(SAVER_CONFIG_FILE):
        try:
            with open(SAVER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'⚠️ Ошибка загрузки конфигурации сохранения: {e}')
            return {
                'save_private': False,
                'save_groups': False,
                'save_channels': [],
                'save_media': True,
                'save_ttl': True
            }
    return {
        'save_private': False,
        'save_groups': False,
        'save_channels': [],
        'save_media': True,
        'save_ttl': True
    }


def save_saver_config(config):
    """Сохранение конфигурации сохранения"""
    try:
        with open(SAVER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'⚠️ Ошибка сохранения конфигурации: {e}')


def should_save_message(chat_id, is_private, is_group):
    """Проверка, нужно ли сохранять сообщения из этого чата"""
    config = load_saver_config()
    chat_id_str = str(chat_id)
    
    if is_private and config['save_private']:
        return True
    
    if is_group and config['save_groups']:
        return True
    
    if chat_id_str in config['save_channels']:
        return True
    
    return False


def add_deleted_message(chat_id, message_data):
    """Добавление удаленного сообщения в БД (БЕЗ команд)"""
    # Фильтруем команды
    if is_command_message(message_data.get('text', '')):
        print(f'🚫 Пропускаем удаленную команду: {message_data.get("text", "")[:50]}')
        return
    
    db = load_deleted_messages_db()
    chat_key = str(chat_id)
    
    if chat_key not in db:
        db[chat_key] = []
    
    db[chat_key].append(message_data)
    
    # Ограничение: храним последние 1000 удаленных сообщений на чат
    if len(db[chat_key]) > 1000:
        db[chat_key] = db[chat_key][-1000:]
    
    save_deleted_messages_db(db)


def get_deleted_messages(chat_id, limit=None, sender_id=None):
    """Получение удаленных сообщений из чата (БЕЗ команд)
    
    Args:
        chat_id: ID чата
        limit: Ограничение количества (None = все)
        sender_id: Фильтр по отправителю (None = все)
    """
    db = load_deleted_messages_db()
    chat_key = str(chat_id)
    
    if chat_key not in db:
        return []
    
    messages = db[chat_key]
    
    # Фильтруем команды
    messages = [msg for msg in messages if not is_command_message(msg.get('text', ''))]
    
    # Фильтр по отправителю
    if sender_id is not None:
        messages = [msg for msg in messages if msg.get('sender_id') == sender_id]
    
    # Применяем лимит
    if limit is not None:
        messages = messages[-limit:]
    
    return messages


def clear_deleted_messages(chat_id):
    """Очистка удаленных сообщений чата"""
    db = load_deleted_messages_db()
    chat_key = str(chat_id)
    
    if chat_key in db:
        db[chat_key] = []
        save_deleted_messages_db(db)


async def save_media_file(message, media_folder=MEDIA_FOLDER):
    """Сохранение медиафайла из сообщения"""
    try:
        Path(media_folder).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        chat_id = message.chat_id
        msg_id = message.id
        
        if message.photo:
            extension = 'jpg'
            media_type = 'photo'
        elif message.video:
            extension = 'mp4'
            media_type = 'video'
        elif message.document:
            if hasattr(message.document, 'attributes'):
                for attr in message.document.attributes:
                    if hasattr(attr, 'file_name'):
                        extension = attr.file_name.split('.')[-1] if '.' in attr.file_name else 'bin'
                        break
                else:
                    extension = 'bin'
            else:
                extension = 'bin'
            media_type = 'document'
        else:
            return None
        
        filename = f'{media_type}_{chat_id}_{msg_id}_{timestamp}.{extension}'
        filepath = os.path.join(media_folder, filename)
        
        await message.download_media(filepath)
        
        print(f'💾 Сохранен файл: {filename}')
        return filepath
        
    except Exception as e:
        print(f'⚠️ Ошибка сохранения медиа: {e}')
        return None


# Загрузка базы данных
db = load_db()


# ============ РАБОТА С AI API (С REASONING) ============
async def get_ai_response(messages):
    """Получение ответа от AI API с поддержкой reasoning"""
    try:
        timeout = aiohttp.ClientTimeout(total=120)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                'model': MODEL_NAME,
                'messages': messages,
                'temperature': 0.7,
                'max_tokens': 2048,
                'reasoning': {'enabled': True}
            }

            headers = {
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/telegram-bot',
                'X-Title': 'Telegram AI Bot'
            }

            print(f'🔄 Отправка запроса к API с reasoning...')
            async with session.post(OPENROUTER_API_URL, json=payload, headers=headers) as resp:
                response_text = await resp.text()

                if resp.status == 200:
                    result = json.loads(response_text)
                    message = result.get('choices', [{}])[0].get('message', {})
                    content = message.get('content', '')
                    reasoning_details = message.get('reasoning_details')
                    
                    if content:
                        return {
                            'content': content.strip(),
                            'reasoning_details': reasoning_details
                        }
                    return {'content': 'Не понял ваш вопрос', 'reasoning_details': None}
                else:
                    print(f'❌ API ошибка {resp.status}: {response_text}')
                    return {'content': f'Ошибка API ({resp.status}). Попробуйте позже.', 'reasoning_details': None}

    except asyncio.TimeoutError:
        print('⏱️ API таймаут')
        return {'content': 'Извините, слишком долго обрабатываю запрос', 'reasoning_details': None}
    except json.JSONDecodeError as e:
        print(f'❌ Ошибка парсинга JSON: {e}')
        return {'content': 'Ошибка обработки ответа от API', 'reasoning_details': None}
    except Exception as e:
        print(f'❌ Ошибка API: {type(e).__name__}: {e}')
        return {'content': 'Не смог сформировать ответ', 'reasoning_details': None}


# ============ РАБОТА С ИСТОРИЕЙ ЧАТА ============
def get_chat_history(chat_id, limit=10):
    """Получение истории сообщений чата с поддержкой reasoning"""
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []

    filtered_history = [
        msg for msg in db[chat_key]
        if not (msg.get('role') == 'assistant' and
                ('Ошибка API' in msg.get('content', '') or
                 'Произошла ошибка при обращении к API' in msg.get('content', '')))
    ]

    return filtered_history[-limit:]


def save_message(chat_id, role, content, reasoning_details=None):
    """Сохранение сообщения в историю с поддержкой reasoning_details"""
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []

    if role == 'assistant' and ('Ошибка API' in content or 'Произошла ошибка при обращении к API' in content):
        return

    message = {
        'role': role,
        'content': content
    }
    
    if role == 'assistant' and reasoning_details:
        message['reasoning_details'] = reasoning_details

    db[chat_key].append(message)

    if len(db[chat_key]) > 100:
        db[chat_key] = db[chat_key][-100:]

    save_db(db)


def clear_chat_history(chat_id):
    """Очистка истории чата"""
    chat_key = str(chat_id)
    if chat_key in db:
        db[chat_key] = []
        save_db(db)
        print(f'🗑️ История чата {chat_id} очищена')


# Инициализация Telegram клиента
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


# ============ НОВОЕ: УМНОЕ УДАЛЕНИЕ КОМАНД ============
async def delete_previous_command(chat_id):
    """Удаление предыдущей команды в чате"""
    if chat_id in last_command_message:
        try:
            await client.delete_messages(chat_id, last_command_message[chat_id])
            print(f'🗑️ Удалена предыдущая команда в чате {chat_id}')
        except Exception as e:
            print(f'⚠️ Не удалось удалить предыдущую команду: {e}')


async def register_command_message(chat_id, message_id):
    """Регистрация новой команды для последующего удаления"""
    last_command_message[chat_id] = message_id


# ============ НОВОЕ: ОТПРАВКА МЕДИА В ИЗБРАННОЕ ============
async def send_to_saved_messages(media_path, caption, message_data):
    """Отправка медиафайла в Избранное с информацией"""
    try:
        me = await client.get_me()
        
        full_caption = f"🗑️ **Удаленное сообщение**\n\n"
        full_caption += f"📅 Удалено: {message_data.get('deleted_at', 'н/д')}\n"
        full_caption += f"👤 От: {message_data.get('sender_name', 'Неизвестно')}\n"
        full_caption += f"💬 Чат ID: `{message_data.get('chat_id')}`\n\n"
        
        if caption:
            full_caption += f"📝 Текст: {caption}\n\n"
        
        full_caption += f"🔗 ID сообщения: {message_data.get('message_id')}"
        
        if media_path and os.path.exists(media_path):
            await client.send_file(
                'me',
                media_path,
                caption=full_caption
            )
            print(f'📤 Медиа отправлено в Избранное: {media_path}')
            return True
        else:
            print(f'⚠️ Файл не найден: {media_path}')
            return False
            
    except Exception as e:
        print(f'⚠️ Ошибка отправки в Избранное: {e}')
        return False


# ============ ОБРАБОТЧИКИ КОМАНД УПРАВЛЕНИЯ СОХРАНЕНИЕМ ============
async def handle_saver_commands(event, message_text):
    """Обработка команд управления сохранением удаленных сообщений"""
    
    chat_id = event.chat_id
    
    # НОВОЕ: Удаляем предыдущую команду перед показом новой
    await delete_previous_command(chat_id)
    
    # Показать статус сохранения
    if message_text.lower() == '.saver status':
        config = load_saver_config()
        chat_id_str = str(chat_id)
        
        is_private = event.is_private
        is_group = event.is_group
        chat_type = "личный" if is_private else "группа" if is_group else "канал"
        
        is_saved = should_save_message(chat_id, is_private, is_group)
        
        status_text = '📊 **Статус сохранения удаленных сообщений:**\n\n'
        status_text += f'📍 **Текущий чат:**\n'
        status_text += f'   Тип: {chat_type}\n'
        status_text += f'   ID: `{chat_id}`\n'
        status_text += f'   Сохранение: {"✅ ВКЛЮЧЕНО" if is_saved else "❌ ВЫКЛЮЧЕНО"}\n\n'
        status_text += f'⚙️ **Глобальные настройки:**\n'
        status_text += f'💬 Личные сообщения: {"✅ Включено" if config["save_private"] else "❌ Выключено"}\n'
        status_text += f'👥 Группы: {"✅ Включено" if config["save_groups"] else "❌ Выключено"}\n'
        status_text += f'📺 Сохранение медиа: {"✅ Включено" if config["save_media"] else "❌ Выключено"}\n'
        status_text += f'⏱️ Скоротечные фото: {"✅ Включено" if config["save_ttl"] else "❌ Выключено"}\n'
        status_text += f'\n📢 Отслеживаемые каналы: {len(config["save_channels"])}\n'
        
        if config["save_channels"]:
            status_text += '\nСписок каналов:\n'
            for channel_id in config["save_channels"][:10]:
                status_text += f'• ID: {channel_id}\n'
            if len(config["save_channels"]) > 10:
                status_text += f'... и еще {len(config["save_channels"]) - 10} каналов\n'
        
        msg = await event.respond(status_text)
        await event.delete()
        await register_command_message(chat_id, [event.id, msg.id])
        return True
    
    # Включить сохранение личных сообщений
    if message_text.lower() == '.saver private on':
        config = load_saver_config()
        config['save_private'] = True
        save_saver_config(config)
        msg = await event.respond('✅ Сохранение удаленных сообщений из **личных чатов** включено!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    # Выключить сохранение личных сообщений
    if message_text.lower() == '.saver private off':
        config = load_saver_config()
        config['save_private'] = False
        save_saver_config(config)
        msg = await event.respond('❌ Сохранение удаленных сообщений из **личных чатов** выключено!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    # Включить сохранение групп
    if message_text.lower() == '.saver groups on':
        config = load_saver_config()
        config['save_groups'] = True
        save_saver_config(config)
        msg = await event.respond('✅ Сохранение удаленных сообщений из **групп** включено!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    # Выключить сохранение групп
    if message_text.lower() == '.saver groups off':
        config = load_saver_config()
        config['save_groups'] = False
        save_saver_config(config)
        msg = await event.respond('❌ Сохранение удаленных сообщений из **групп** выключено!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    # Добавить канал для отслеживания
    if message_text.lower().startswith('.saver add'):
        config = load_saver_config()
        chat_id_str = str(chat_id)
        
        if chat_id_str not in config['save_channels']:
            config['save_channels'].append(chat_id_str)
            save_saver_config(config)
            msg = await event.respond(f'✅ Канал/чат (ID: {chat_id}) добавлен в список отслеживания!')
        else:
            msg = await event.respond(f'⚠️ Этот канал/чат уже в списке отслеживания!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    # Удалить канал из отслеживания
    if message_text.lower().startswith('.saver remove'):
        config = load_saver_config()
        chat_id_str = str(chat_id)
        
        if chat_id_str in config['save_channels']:
            config['save_channels'].remove(chat_id_str)
            save_saver_config(config)
            msg = await event.respond(f'❌ Канал/чат (ID: {chat_id}) удален из списка отслеживания!')
        else:
            msg = await event.respond(f'⚠️ Этот канал/чат не был в списке отслеживания!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    # НОВОЕ: Показать последние 10 удаленных
    if message_text.lower() == '.saver show':
        deleted_msgs = get_deleted_messages(chat_id, limit=10)
        
        if not deleted_msgs:
            msg = await event.respond(
                f'📭 Нет сохраненных удаленных сообщений в этом чате.\n\n'
                f'💡 Убедитесь что:\n'
                f'1. Сохранение включено (`.saver status`)\n'
                f'2. Сообщение было удалено ПОСЛЕ включения'
            )
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        
        response = f'🗑️ **Последние {len(deleted_msgs)} удаленных сообщений:**\n\n'
        
        for i, msg_data in enumerate(deleted_msgs, 1):
            timestamp = msg_data.get('deleted_at', 'н/д')
            sender = msg_data.get('sender_name', 'Неизвестно')
            text = msg_data.get('text', '[медиафайл]')[:100]
            media_info = ''
            
            if msg_data.get('has_photo'):
                media_info += '📷 '
            if msg_data.get('has_video'):
                media_info += '🎥 '
            if msg_data.get('has_document'):
                media_info += '📎 '
            if msg_data.get('is_ttl'):
                media_info += '⏱️ '
            
            response += f'{i}. [{timestamp}] **{sender}**: {media_info}{text}\n\n'
        
        response += '\n💡 Используйте `.saver all` для просмотра всех удаленных'
        
        msg = await event.respond(response)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    # НОВОЕ: Показать ВСЕ удаленные сообщения
    if message_text.lower() == '.saver all':
        deleted_msgs = get_deleted_messages(chat_id, limit=None)
        
        if not deleted_msgs:
            msg = await event.respond('📭 Нет сохраненных удаленных сообщений в этом чате.')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        
        # Отправляем сообщения порциями по 50
        batch_size = 50
        total_batches = (len(deleted_msgs) + batch_size - 1) // batch_size
        
        response = f'🗑️ **Все удаленные сообщения ({len(deleted_msgs)} шт.):**\n\n'
        msg = await event.respond(response)
        message_ids = [msg.id]
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(deleted_msgs))
            batch = deleted_msgs[start_idx:end_idx]
            
            batch_text = f'📄 **Часть {batch_num + 1}/{total_batches}:**\n\n'
            
            for i, msg_data in enumerate(batch, start_idx + 1):
                timestamp = msg_data.get('deleted_at', 'н/д')[:16]
                sender = msg_data.get('sender_name', 'Неизвестно')
                text = msg_data.get('text', '[медиафайл]')[:80]
                media_info = ''
                
                if msg_data.get('has_photo'):
                    media_info += '📷'
                if msg_data.get('has_video'):
                    media_info += '🎥'
                if msg_data.get('has_document'):
                    media_info += '📎'
                if msg_data.get('is_ttl'):
                    media_info += '⏱️'
                
                batch_text += f'{i}. [{timestamp}] {sender}: {media_info} {text}\n'
            
            batch_msg = await event.respond(batch_text)
            message_ids.append(batch_msg.id)
            await asyncio.sleep(0.5)
        
        await event.delete()
        await register_command_message(chat_id, message_ids)
        return True
    
    # НОВОЕ: Показать удаленные от конкретного пользователя
    if message_text.lower().startswith('.saver user '):
        try:
            # Получаем ID пользователя из команды
            parts = message_text.split()
            if len(parts) < 3:
                msg = await event.respond('❌ Используйте: `.saver user @username` или `.saver user` (ответом на сообщение)')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            
            # Если это ответ на сообщение
            if event.reply_to_msg_id:
                reply_msg = await event.get_reply_message()
                sender_id = reply_msg.sender_id
            else:
                msg = await event.respond('❌ Ответьте на сообщение пользователя')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            
            deleted_msgs = get_deleted_messages(chat_id, limit=None, sender_id=sender_id)
            
            if not deleted_msgs:
                msg = await event.respond('📭 Нет удаленных сообщений от этого пользователя.')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            
            sender_name = deleted_msgs[0].get('sender_name', 'Пользователь')
            response = f'🗑️ **Удаленные сообщения от {sender_name} ({len(deleted_msgs)} шт.):**\n\n'
            
            for i, msg_data in enumerate(deleted_msgs[-50:], 1):
                timestamp = msg_data.get('deleted_at', 'н/д')[:16]
                text = msg_data.get('text', '[медиафайл]')[:80]
                media_info = ''
                
                if msg_data.get('has_photo'):
                    media_info += '📷'
                if msg_data.get('has_video'):
                    media_info += '🎥'
                
                response += f'{i}. [{timestamp}] {media_info} {text}\n'
            
            if len(deleted_msgs) > 50:
                response += f'\n... показаны последние 50 из {len(deleted_msgs)}'
            
            msg = await event.respond(response)
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
            
        except Exception as e:
            print(f'⚠️ Ошибка .saver user: {e}')
            return True
    
    # НОВОЕ: Просмотр медиа из удаленных
    if message_text.lower().startswith('.saver media'):
        parts = message_text.split()
        
        if len(parts) < 3:
            msg = await event.respond('❌ Используйте: `.saver media 5` (номер сообщения из .saver show)')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        
        try:
            msg_index = int(parts[2]) - 1
            deleted_msgs = get_deleted_messages(chat_id, limit=None)
            
            if msg_index < 0 or msg_index >= len(deleted_msgs):
                msg = await event.respond(f'❌ Сообщение #{parts[2]} не найдено')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            
            msg_data = deleted_msgs[msg_index]
            media_path = msg_data.get('media_path')
            
            if not media_path:
                msg = await event.respond('❌ У этого сообщения нет сохраненного медиа')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            
            # Отправляем в Избранное
            caption = msg_data.get('text', '')
            success = await send_to_saved_messages(media_path, caption, msg_data)
            
            if success:
                msg = await event.respond('✅ Медиа отправлено в **Избранное**!')
            else:
                msg = await event.respond('❌ Ошибка отправки медиа')
            
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
            
        except ValueError:
            msg = await event.respond('❌ Неверный номер сообщения')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        except Exception as e:
            print(f'⚠️ Ошибка .saver media: {e}')
            msg = await event.respond(f'❌ Ошибка: {e}')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
    
    # Очистить сохраненные удаленные сообщения
    if message_text.lower() == '.saver clear':
        clear_deleted_messages(chat_id)
        msg = await event.respond('🗑️ Все сохраненные удаленные сообщения из этого чата очищены!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    # НОВОЕ: Удалить все команды в чате
    if message_text.lower() == '.saver clean':
        try:
            await delete_previous_command(chat_id)
            await event.delete()
            print(f'🧹 Все команды удалены в чате {chat_id}')
        except Exception as e:
            print(f'⚠️ Ошибка .saver clean: {e}')
        return True
    
    # НОВОЕ: Диагностика storage
    if message_text.lower() == '.saver debug':
        storage = load_messages_storage()
        chat_key = str(chat_id)
        
        debug_text = '🔍 **ДИАГНОСТИКА STORAGE:**\n\n'
        debug_text += f'🏠 **Текущий чат:** {chat_id}\n\n'
        
        if chat_key in storage and storage[chat_key]:
            messages_count = len(storage[chat_key])
            debug_text += f'📦 Сообщений в storage: **{messages_count}**\n\n'
            
            # Показываем все message_id
            debug_text += f'🔢 **Message IDs в storage:**\n'
            msg_ids = [str(msg.get('message_id', '?')) for msg in storage[chat_key]]
            debug_text += ', '.join(msg_ids[-20:])  # Последние 20
            if len(msg_ids) > 20:
                debug_text += f'\n... и еще {len(msg_ids) - 20} старых'
            
            debug_text += f'\n\n🕐 **Последние 5 сообщений:**\n'
            
            for i, msg in enumerate(storage[chat_key][-5:], 1):
                sender = msg.get('sender_name', 'н/д')
                text = msg.get('text', '')[:30]
                msg_id = msg.get('message_id', 'н/д')
                debug_text += f'{i}. MSG `{msg_id}` от {sender}\n   "{text}"\n'
        else:
            debug_text += f'❌ **Нет сообщений в storage**\n\n'
            debug_text += f'💡 Возможные причины:\n'
            debug_text += f'• Сохранение не включено\n'
            debug_text += f'• Еще не было входящих сообщений\n'
            debug_text += f'• Все сообщения были от вас\n'
        
        # Проверяем конфиг
        config = load_saver_config()
        is_private = event.is_private
        is_group = event.is_group
        should_save = should_save_message(chat_id, is_private, is_group)
        
        debug_text += f'\n⚙️ **Настройки:**\n'
        debug_text += f'• Этот чат: {"✅ Сохранение ВКЛ" if should_save else "❌ Сохранение ВЫКЛ"}\n'
        debug_text += f'• Личные чаты: {"✅" if config["save_private"] else "❌"}\n'
        debug_text += f'• Группы: {"✅" if config["save_groups"] else "❌"}\n'
        debug_text += f'• Тип чата: {"личный" if is_private else "группа" if is_group else "канал"}\n'
        debug_text += f'\n🆔 **Технические данные:**\n'
        debug_text += f'• OWNER_ID: `{OWNER_ID}`\n'
        debug_text += f'• Chat ID: `{chat_id}`\n'
        
        # Проверяем deleted_messages_db
        deleted_db = load_deleted_messages_db()
        if chat_key in deleted_db and deleted_db[chat_key]:
            debug_text += f'\n🗑️ **Удаленных сообщений сохранено:** {len(deleted_db[chat_key])}\n'
        
        msg = await event.respond(debug_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    # Помощь по командам
    if message_text.lower() == '.saver help':
        help_text = '''📚 **Команды управления сохранением:**

**Управление:**
• `.saver status` - показать статус
• `.saver private on/off` - вкл/выкл личные
• `.saver groups on/off` - вкл/выкл группы
• `.saver add` - добавить текущий чат
• `.saver remove` - удалить текущий чат

**Просмотр:**
• `.saver show` - последние 10 удаленных
• `.saver all` - ВСЕ удаленные сообщения
• `.saver user @username` - удаленные от юзера
• `.saver media N` - отправить медиа в Избранное
• `.saver clear` - очистить удаленные
• `.saver clean` - удалить все менюшки команд
• `.saver debug` - диагностика storage (отладка)

**Что сохраняется:**
✅ Текст сообщений
✅ Фото, видео, документы
✅ Скоротечные фото (TTL)
✅ Медиа отправляется в Избранное

**Новое:**
🔥 Сохранение МГНОВЕННОЕ (даже если удалено сразу)
🔥 Команды удаляются автоматически при вводе новой
🔥 Медиа доступно в Избранном
🔥 Команды НЕ показываются в истории удаленных
🔍 Используйте .saver debug если что-то не работает

_Команды автоматически удаляются._'''
        
        msg = await event.respond(help_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    return False


# ============ ОБРАБОТЧИК НОВЫХ СООБЩЕНИЙ (НЕМЕДЛЕННОЕ сохранение) ============
@client.on(events.NewMessage(incoming=True, from_users=None))
async def immediate_save_handler(event):
    """НЕМЕДЛЕННОЕ сохранение ВХОДЯЩИХ сообщений в постоянное хранилище"""
    try:
        chat_id = event.chat_id
        message_id = event.message.id
        sender_id = event.sender_id
        
        print(f'\n📨 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
        print(f'📨 НОВОЕ сообщение')
        print(f'   Chat ID: {chat_id}')
        print(f'   Message ID: {message_id}')
        print(f'   Sender ID: {sender_id}')
        print(f'   OWNER_ID: {OWNER_ID}')
        
        # ВАЖНО: Пропускаем свои сообщения
        if OWNER_ID is not None and sender_id == OWNER_ID:
            print(f'   ⏭️ Это СВОЕ сообщение - пропускаем')
            print(f'📨 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n')
            return
        
        # Проверяем, нужно ли сохранять
        is_private = event.is_private
        is_group = event.is_group
        
        print(f'   Тип: {"личный" if is_private else "группа" if is_group else "канал"}')
        
        should_save = should_save_message(chat_id, is_private, is_group)
        
        print(f'   Сохранение: {"✅ ВКЛ" if should_save else "❌ ВЫКЛ"}')
        
        if not should_save:
            print(f'   ⏭️ Сохранение выключено для этого чата')
            print(f'📨 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n')
            return
        
        # Получаем информацию о сообщении
        sender = await event.get_sender()
        sender_name = getattr(sender, 'first_name', 'Неизвестно')
        if hasattr(sender, 'username') and sender.username:
            sender_name += f' (@{sender.username})'
        
        message_text = event.message.message or ''
        
        print(f'   Отправитель: {sender_name}')
        print(f'   Текст: {message_text[:50]}{"..." if len(message_text) > 50 else ""}')
        
        message_data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'sender_id': sender_id,
            'sender_name': sender_name,
            'text': message_text,
            'date': event.message.date.isoformat() if event.message.date else None,
            'has_photo': bool(event.message.photo),
            'has_video': bool(event.message.video),
            'has_document': bool(event.message.document),
            'is_ttl': bool(event.message.ttl_period),
            'media_path': None
        }
        
        print(f'   Медиа: Фото={message_data["has_photo"]}, Видео={message_data["has_video"]}, Док={message_data["has_document"]}, TTL={message_data["is_ttl"]}')
        
        # Сохраняем медиафайлы
        config = load_saver_config()
        if config['save_media'] and (event.message.photo or event.message.video or event.message.document):
            print(f'   💾 Начинаем сохранение медиа...')
            media_path = await save_media_file(event.message)
            message_data['media_path'] = media_path
            print(f'   ✅ Медиа сохранено: {media_path}')
        
        # НЕМЕДЛЕННО сохраняем в постоянное хранилище
        store_message_immediately(chat_id, message_data)
        
        print(f'   ✅ Сообщение {message_id} СОХРАНЕНО в storage!')
        print(f'📨 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n')
        
    except Exception as e:
        print(f'❌ ОШИБКА немедленного сохранения: {e}')
        import traceback
        traceback.print_exc()


# ============ ОБРАБОТЧИК УДАЛЕННЫХ СООБЩЕНИЙ (улучшенный) ============
@client.on(events.MessageDeleted)
async def deleted_message_handler(event):
    """Обработка удаленных сообщений из постоянного хранилища"""
    try:
        chat_id = event.chat_id
        deleted_ids = event.deleted_ids
        
        print(f'\n🗑️ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
        print(f'🗑️ ОБНАРУЖЕНО УДАЛЕНИЕ')
        print(f'🗑️ event.chat_id: {chat_id}')
        print(f'🗑️ Количество удаленных ID: {len(deleted_ids)}')
        print(f'🗑️ ID: {deleted_ids}')
        
        saved_count = 0
        not_found_count = 0
        
        for message_id in deleted_ids:
            # ВАЖНО: Ищем сообщение (функция сама ищет по всем чатам если chat_id=None)
            message_data = get_stored_message(chat_id, message_id)
            
            if message_data:
                # Используем chat_id из самого сообщения (он точно правильный)
                real_chat_id = message_data.get('chat_id')
                
                print(f'   ✅ Найдено: MSG {message_id} в чате {real_chat_id}')
                print(f'      От: {message_data.get("sender_name")}')
                print(f'      Текст: {message_data.get("text", "")[:50]}')
                
                message_data['deleted_at'] = datetime.now().isoformat()
                
                # Сохраняем в базу удаленных (используем правильный chat_id)
                add_deleted_message(real_chat_id, message_data)
                saved_count += 1
                
                # Если есть медиа - отправляем в Избранное
                if message_data.get('media_path') and os.path.exists(message_data.get('media_path')):
                    caption = message_data.get('text', '')
                    print(f'      📤 Отправка медиа в Избранное...')
                    success = await send_to_saved_messages(message_data['media_path'], caption, message_data)
                    if success:
                        print(f'      ✅ Медиа отправлено в Избранное!')
                    else:
                        print(f'      ❌ Ошибка отправки медиа')
                
                print(f'   💾 Удаленное сообщение сохранено в БД')
            else:
                print(f'   ❌ НЕ НАЙДЕНО в storage: {message_id}')
                not_found_count += 1
        
        print(f'🗑️ ИТОГО: Сохранено={saved_count}, Не найдено={not_found_count}')
        print(f'🗑️ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n')
        
    except Exception as e:
        print(f'❌ КРИТИЧЕСКАЯ ОШИБКА обработки удаленного: {e}')
        import traceback
        traceback.print_exc()


# ============ ОБРАБОТЧИК ВХОДЯЩИХ СООБЩЕНИЙ (для AI ответов) ============
@client.on(events.NewMessage(incoming=True))
async def incoming_handler(event):
    """Обработчик входящих сообщений от других пользователей - только для AI ответов"""
    try:
        chat_id = event.chat_id
        
        if not is_chat_active(chat_id):
            return
        
        message_text = event.message.message or ''
        
        # Обработка медиа
        if event.message.voice:
            try:
                voice_file = await event.message.download_media(bytes)
                message_text = '[голосовое сообщение]'
            except Exception as e:
                print(f'⚠️ Ошибка обработки голоса: {e}')
                message_text = '[голосовое сообщение]'

        elif event.message.photo:
            try:
                message_text = f'{message_text} [фото]' if message_text else '[фото]'
            except Exception as e:
                print(f'⚠️ Ошибка обработки фото: {e}')

        if not message_text.strip():
            message_text = 'сообщение без текста'

        save_message(chat_id, 'user', message_text)
        
        history = get_chat_history(chat_id)

        system_message = {
            'role': 'system',
            'content': 'Ты дружелюбный и полезный ассистент. Отвечай кратко и по существу. Общайся на том же языке, что и пользователь.'
        }

        messages_for_api = [system_message] + history

        print(f'🤖 Запрос к AI с {len(history)} сообщениями в истории')
        response = await get_ai_response(messages_for_api)

        content = response.get('content', 'Не смог сформировать ответ')
        reasoning_details = response.get('reasoning_details')

        if content and not content.startswith('Ошибка'):
            save_message(chat_id, 'assistant', content, reasoning_details)

        try:
            await event.respond(content)
            print(f'✅ Отправлен ответ в чат {chat_id}')

        except RPCError as e:
            if 'TOPIC_CLOSED' in str(e) or 'CHAT_WRITE_FORBIDDEN' in str(e):
                print(f'⚠️ Чат {chat_id} закрыт для записи')
                deactivate_chat(chat_id)
            else:
                print(f'❌ RPC ошибка: {e}')

    except Exception as e:
        print(f'❌ Ошибка обработки входящего: {e}')
        import traceback
        traceback.print_exc()


# ============ ОБРАБОТЧИК ИСХОДЯЩИХ СООБЩЕНИЙ ============
@client.on(events.NewMessage(outgoing=True))
async def outgoing_handler(event):
    """Основной обработчик ВАШИХ сообщений"""
    try:
        chat_id = event.chat_id
        message_text = event.message.message or ''

        # ПРИОРИТЕТ 1: Команды сохранения
        if message_text.lower().startswith('.saver'):
            handled = await handle_saver_commands(event, message_text)
            if handled:
                return

        # ПРИОРИТЕТ 2: AI команды
        if ACTIVATION_COMMAND.lower() in message_text.lower():
            await delete_previous_command(chat_id)
            activate_chat(chat_id)
            msg = await event.respond(f'✅ AI-ассистент активирован!\n\n'
                                      f'**Команды:**\n'
                                      f'• "Ai Stop" - деактивировать\n'
                                      f'• "Ai Clear" - очистить историю')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return

        if 'ai stop' in message_text.lower():
            await delete_previous_command(chat_id)
            deactivate_chat(chat_id)
            msg = await event.respond('❌ AI деактивирован. Напишите "Ai Edem" для активации.')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return

        if 'ai clear' in message_text.lower():
            if is_chat_active(chat_id):
                await delete_previous_command(chat_id)
                clear_chat_history(chat_id)
                msg = await event.respond('🗑️ История диалога очищена!')
                await event.delete()
                await register_command_message(chat_id, msg.id)
            return

    except Exception as e:
        print(f'❌ Ошибка обработки исходящего: {e}')
        import traceback
        traceback.print_exc()


# ============ ГЛАВНАЯ ФУНКЦИЯ ============
async def main():
    """Запуск userbot"""
    global OWNER_ID
    
    print('🚀 Запуск улучшенного Telegram Userbot...')
    print(f'📁 Рабочая директория: {os.getcwd()}')
    print(f'📝 Сессия: {SESSION_NAME}.session')
    print(f'💾 Папка медиа: {MEDIA_FOLDER}')

    Path(MEDIA_FOLDER).mkdir(parents=True, exist_ok=True)

    session_file = f'{SESSION_NAME}.session'
    if not os.path.exists(session_file):
        print(f'\n❌ ОШИБКА: Файл сессии "{session_file}" не найден!')
        sys.exit(1)

    try:
        await client.connect()
        print('✅ Подключение установлено')

        if not await client.is_user_authorized():
            print('\n❌ ОШИБКА: Сессия не авторизована!')
            sys.exit(1)

        print('✅ Userbot запущен!')
        me = await client.get_me()
        OWNER_ID = me.id
        
        print(f'👤 Аккаунт: {me.username or me.first_name} (ID: {OWNER_ID})')
        print(f'🤖 AI: {MODEL_NAME}')
        print(f'🔑 Команда: "{ACTIVATION_COMMAND}"')
        
        print('\n🆕 **НОВЫЕ ВОЗМОЖНОСТИ:**')
        print('⚡ Мгновенное сохранение (даже если удалено сразу)')
        print('🗂️ Просмотр всех удаленных (.saver all)')
        print('📤 Медиа автоматически в Избранное')
        print('🧹 Умное удаление команд')
        print('🚫 Команды не показываются в истории')
        
        print('\n📝 Команды: .saver help')
        print('⏹️ Ctrl+C для остановки\n')
        print('🎧 Слушаю сообщения...\n')

        await client.run_until_disconnected()

    except Exception as e:
        print(f'❌ Ошибка: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ============ ЗАПУСК ============
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n👋 Userbot остановлен')
    except Exception as e:
        print(f'\n❌ Критическая ошибка: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
