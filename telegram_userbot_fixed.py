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

# Имя сессии для Railway (отдельная сессия!)
SESSION_NAME = 'railway_session'

# Папка для сохранения медиафайлов
MEDIA_FOLDER = 'saved_media'

# ID владельца аккаунта (будет установлен при запуске)
OWNER_ID = None


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
    
    print(f'🔍 Проверка сохранения для чата {chat_id}:')
    print(f'   save_private: {config["save_private"]}')
    print(f'   save_groups: {config["save_groups"]}')
    print(f'   save_channels: {config["save_channels"]}')
    print(f'   is_private: {is_private}, is_group: {is_group}')
    
    # Проверка личных сообщений
    if is_private and config['save_private']:
        print(f'   ✅ Сохраняем (личный чат)')
        return True
    
    # Проверка групп
    if is_group and config['save_groups']:
        print(f'   ✅ Сохраняем (группа)')
        return True
    
    # Проверка каналов
    if chat_id_str in config['save_channels']:
        print(f'   ✅ Сохраняем (в списке каналов)')
        return True
    
    print(f'   ❌ НЕ сохраняем')
    return False


def add_deleted_message(chat_id, message_data):
    """Добавление удаленного сообщения в БД"""
    db = load_deleted_messages_db()
    chat_key = str(chat_id)
    
    if chat_key not in db:
        db[chat_key] = []
    
    db[chat_key].append(message_data)
    
    # Ограничение: храним последние 500 удаленных сообщений на чат
    if len(db[chat_key]) > 500:
        db[chat_key] = db[chat_key][-500:]
    
    save_deleted_messages_db(db)


def get_deleted_messages(chat_id, limit=50):
    """Получение удаленных сообщений из чата"""
    db = load_deleted_messages_db()
    chat_key = str(chat_id)
    
    if chat_key not in db:
        return []
    
    return db[chat_key][-limit:]


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
        # Создаем папку если не существует
        Path(media_folder).mkdir(parents=True, exist_ok=True)
        
        # Генерируем уникальное имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        chat_id = message.chat_id
        msg_id = message.id
        
        # Определяем тип медиа и расширение
        if message.photo:
            extension = 'jpg'
            media_type = 'photo'
        elif message.video:
            extension = 'mp4'
            media_type = 'video'
        elif message.document:
            # Пытаемся получить расширение из имени файла
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
        
        # Скачиваем файл
        await message.download_media(filepath)
        
        print(f'💾 Сохранен файл: {filename}')
        return filepath
        
    except Exception as e:
        print(f'⚠️ Ошибка сохранения медиа: {e}')
        return None


# Загрузка базы данных
db = load_db()
messages_cache = {}  # Кеш для отслеживания сообщений


# ============ РАБОТА С AI API (С REASONING) ============
async def get_ai_response(messages):
    """
    Получение ответа от AI API с поддержкой reasoning (рассуждений)
    messages - список сообщений в формате [{'role': 'user/assistant', 'content': 'текст', 'reasoning_details': ...}]
    """
    try:
        timeout = aiohttp.ClientTimeout(total=120)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                'model': MODEL_NAME,
                'messages': messages,
                'temperature': 0.7,
                'max_tokens': 2048,
                'reasoning': {'enabled': True}  # Включаем reasoning для Gemini
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
                print(f'📥 Ответ API (статус {resp.status}): {response_text[:200]}...')

                if resp.status == 200:
                    result = json.loads(response_text)
                    message = result.get('choices', [{}])[0].get('message', {})
                    content = message.get('content', '')
                    reasoning_details = message.get('reasoning_details')  # Сохраняем reasoning
                    
                    if content:
                        # Возвращаем контент и reasoning_details для сохранения в историю
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


# ============ РАБОТА С МЕДИАФАЙЛАМИ ============
async def transcribe_voice(voice_data):
    """Обработка голосовых сообщений (заглушка)"""
    return '[получено голосовое сообщение]'


async def analyze_photo(photo_data):
    """Обработка изображений (заглушка)"""
    return '[получено изображение]'


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
    
    # Сохраняем reasoning_details для сообщений ассистента
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


# ============ ОБРАБОТЧИКИ КОМАНД УПРАВЛЕНИЯ СОХРАНЕНИЕМ (ТОЛЬКО ДЛЯ ВЛАДЕЛЬЦА) ============
async def handle_saver_commands(event, message_text):
    """Обработка команд управления сохранением удаленных сообщений"""
    
    chat_id = event.chat_id
    
    # Показать статус сохранения
    if message_text.lower() == '.saver status':
        config = load_saver_config()
        chat_id_str = str(chat_id)
        
        # Определяем тип чата
        is_private = event.is_private
        is_group = event.is_group
        chat_type = "личный" if is_private else "группа" if is_group else "канал"
        
        # Проверяем, сохраняется ли текущий чат
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
        
        if not is_saved:
            status_text += '\n⚠️ **Для включения сохранения в этом чате:**\n'
            if is_private:
                status_text += '• Используйте: `.saver private on`\n'
            elif is_group:
                status_text += '• Используйте: `.saver groups on`\n'
            else:
                status_text += '• Используйте: `.saver add`\n'
        
        msg = await event.respond(status_text)
        # Удаляем команду и ответ через 5 секунд
        await asyncio.sleep(5)
        try:
            await event.delete()
            await msg.delete()
        except:
            pass
        return True
    
    # Включить сохранение личных сообщений
    if message_text.lower() == '.saver private on':
        config = load_saver_config()
        config['save_private'] = True
        save_saver_config(config)
        msg = await event.respond('✅ Сохранение удаленных сообщений из **личных чатов** включено!')
        await asyncio.sleep(3)
        try:
            await event.delete()
            await msg.delete()
        except:
            pass
        return True
    
    # Выключить сохранение личных сообщений
    if message_text.lower() == '.saver private off':
        config = load_saver_config()
        config['save_private'] = False
        save_saver_config(config)
        msg = await event.respond('❌ Сохранение удаленных сообщений из **личных чатов** выключено!')
        await asyncio.sleep(3)
        try:
            await event.delete()
            await msg.delete()
        except:
            pass
        return True
    
    # Включить сохранение групп
    if message_text.lower() == '.saver groups on':
        config = load_saver_config()
        config['save_groups'] = True
        save_saver_config(config)
        msg = await event.respond('✅ Сохранение удаленных сообщений из **групп** включено!')
        await asyncio.sleep(3)
        try:
            await event.delete()
            await msg.delete()
        except:
            pass
        return True
    
    # Выключить сохранение групп
    if message_text.lower() == '.saver groups off':
        config = load_saver_config()
        config['save_groups'] = False
        save_saver_config(config)
        msg = await event.respond('❌ Сохранение удаленных сообщений из **групп** выключено!')
        await asyncio.sleep(3)
        try:
            await event.delete()
            await msg.delete()
        except:
            pass
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
        await asyncio.sleep(3)
        try:
            await event.delete()
            await msg.delete()
        except:
            pass
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
        await asyncio.sleep(3)
        try:
            await event.delete()
            await msg.delete()
        except:
            pass
        return True
    
    # Показать удаленные сообщения
    if message_text.lower() == '.saver show':
        deleted_msgs = get_deleted_messages(chat_id, limit=10)
        
        if not deleted_msgs:
            msg = await event.respond('📭 Нет сохраненных удаленных сообщений в этом чате.')
            await asyncio.sleep(3)
            try:
                await event.delete()
                await msg.delete()
            except:
                pass
            return True
        
        response = f'🗑️ **Последние {len(deleted_msgs)} удаленных сообщений:**\n\n'
        
        for i, msg_data in enumerate(deleted_msgs[-10:], 1):
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
        
        msg = await event.respond(response)
        await asyncio.sleep(10)
        try:
            await event.delete()
            await msg.delete()
        except:
            pass
        return True
    
    # Очистить сохраненные удаленные сообщения
    if message_text.lower() == '.saver clear':
        clear_deleted_messages(chat_id)
        msg = await event.respond('🗑️ Все сохраненные удаленные сообщения из этого чата очищены!')
        await asyncio.sleep(3)
        try:
            await event.delete()
            await msg.delete()
        except:
            pass
        return True
    
    # Помощь по командам
    if message_text.lower() == '.saver help':
        help_text = '''📚 **Команды управления сохранением удаленных сообщений:**

**Управление:**
• `.saver status` - показать текущий статус
• `.saver private on/off` - вкл/выкл личные чаты
• `.saver groups on/off` - вкл/выкл группы
• `.saver add` - добавить текущий чат в отслеживание
• `.saver remove` - удалить текущий чат из отслеживания

**Просмотр:**
• `.saver show` - показать последние 10 удаленных сообщений
• `.saver clear` - очистить сохраненные удаленные сообщения

**Что сохраняется:**
✅ Текст сообщений
✅ Фотографии и видео
✅ Документы и файлы
✅ Скоротечные фото (TTL)
✅ Информация об отправителе
✅ Время удаления

_Команды видны только вам и автоматически удаляются._'''
        
        msg = await event.respond(help_text)
        await asyncio.sleep(15)
        try:
            await event.delete()
            await msg.delete()
        except:
            pass
        return True
    
    return False


# ============ ОБРАБОТЧИК НОВЫХ СООБЩЕНИЙ (для кеширования) ============
@client.on(events.NewMessage)
async def cache_message_handler(event):
    """Кеширование сообщений для отслеживания удаления"""
    try:
        chat_id = event.chat_id
        message_id = event.message.id
        
        # Проверяем, нужно ли сохранять сообщения из этого чата
        is_private = event.is_private
        is_group = event.is_group
        
        should_save = should_save_message(chat_id, is_private, is_group)
        
        print(f'📨 Новое сообщение {message_id} в чате {chat_id}')
        print(f'   Тип: {"личный" if is_private else "группа" if is_group else "канал"}')
        print(f'   Сохранение: {"✅ ВКЛ" if should_save else "❌ ВЫКЛ"}')
        
        if not should_save:
            return
        
        # Получаем информацию о сообщении
        sender = await event.get_sender()
        sender_name = getattr(sender, 'first_name', 'Неизвестно')
        if hasattr(sender, 'username') and sender.username:
            sender_name += f' (@{sender.username})'
        
        message_data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'sender_id': event.sender_id,
            'sender_name': sender_name,
            'text': event.message.message or '',
            'date': event.message.date.isoformat() if event.message.date else None,
            'has_photo': bool(event.message.photo),
            'has_video': bool(event.message.video),
            'has_document': bool(event.message.document),
            'is_ttl': bool(event.message.ttl_period),
            'media_path': None
        }
        
        # Сохраняем медиафайлы если включено
        config = load_saver_config()
        if config['save_media'] and (event.message.photo or event.message.video or event.message.document):
            media_path = await save_media_file(event.message)
            message_data['media_path'] = media_path
        
        # Сохраняем в кеш
        cache_key = f'{chat_id}_{message_id}'
        messages_cache[cache_key] = message_data
        
        # Ограничиваем размер кеша
        if len(messages_cache) > 1000:
            # Удаляем старые записи
            old_keys = list(messages_cache.keys())[:500]
            for key in old_keys:
                del messages_cache[key]
        
    except Exception as e:
        print(f'⚠️ Ошибка кеширования сообщения: {e}')


# ============ ОБРАБОТЧИК УДАЛЕННЫХ СООБЩЕНИЙ ============
@client.on(events.MessageDeleted)
async def deleted_message_handler(event):
    """Обработка удаленных сообщений"""
    try:
        chat_id = event.chat_id
        deleted_ids = event.deleted_ids
        
        print(f'🗑️ Обнаружено удаление {len(deleted_ids)} сообщений в чате {chat_id}')
        
        for message_id in deleted_ids:
            cache_key = f'{chat_id}_{message_id}'
            
            if cache_key in messages_cache:
                message_data = messages_cache[cache_key]
                message_data['deleted_at'] = datetime.now().isoformat()
                
                # Сохраняем в базу удаленных сообщений
                add_deleted_message(chat_id, message_data)
                
                print(f'💾 Сохранено удаленное сообщение: {message_id} от {message_data["sender_name"]}')
                
                # Удаляем из кеша
                del messages_cache[cache_key]
        
    except Exception as e:
        print(f'⚠️ Ошибка обработки удаленного сообщения: {e}')


# ============ ОБРАБОТЧИК ВХОДЯЩИХ СООБЩЕНИЙ ОТ ДРУГИХ (для AI ответов) ============
@client.on(events.NewMessage(incoming=True))
async def incoming_handler(event):
    """Обработчик входящих сообщений от других пользователей - только для AI ответов"""
    try:
        chat_id = event.chat_id
        
        # Проверяем, активен ли AI в этом чате
        if not is_chat_active(chat_id):
            return
        
        message_text = event.message.message or ''
        
        # Обработка медиа
        if event.message.voice:
            try:
                voice_file = await event.message.download_media(bytes)
                message_text = await transcribe_voice(voice_file)
            except Exception as e:
                print(f'⚠️ Ошибка обработки голоса: {e}')
                message_text = '[голосовое сообщение]'

        elif event.message.photo:
            try:
                photo_file = await event.message.download_media(bytes)
                photo_desc = await analyze_photo(photo_file)
                message_text = f'{message_text} {photo_desc}' if message_text else photo_desc
            except Exception as e:
                print(f'⚠️ Ошибка обработки фото: {e}')

        elif (event.message.document and
              event.message.document.mime_type and
              event.message.document.mime_type.startswith('image/')):
            try:
                doc_file = await event.message.download_media(bytes)
                photo_desc = await analyze_photo(doc_file)
                message_text = f'{message_text} {photo_desc}' if message_text else photo_desc
            except Exception as e:
                print(f'⚠️ Ошибка обработки документа: {e}')

        if not message_text.strip():
            message_text = 'сообщение без текста'

        # Сохраняем сообщение пользователя
        save_message(chat_id, 'user', message_text)
        
        # Получаем историю с reasoning_details
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
            print(f'✅ Отправлен ответ в чат {chat_id}: {content[:50]}...')

        except RPCError as e:
            if 'TOPIC_CLOSED' in str(e) or 'CHAT_WRITE_FORBIDDEN' in str(e):
                print(f'⚠️ Чат {chat_id} закрыт для записи')
                deactivate_chat(chat_id)
            else:
                print(f'❌ RPC ошибка: {e}')

        except Exception as e:
            print(f'❌ Ошибка отправки сообщения: {type(e).__name__}: {e}')

    except Exception as e:
        print(f'❌ Критическая ошибка обработки входящего сообщения: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()


# ============ ОБРАБОТЧИК ИСХОДЯЩИХ СООБЩЕНИЙ (ваши команды) ============
@client.on(events.NewMessage(outgoing=True))
async def outgoing_handler(event):
    """Основной обработчик ВАШИХ сообщений (команды .saver и AI)"""
    try:
        chat_id = event.chat_id
        message_text = event.message.message or ''

        # ПРИОРИТЕТ 1: Проверка команд управления сохранением
        if message_text.lower().startswith('.saver'):
            handled = await handle_saver_commands(event, message_text)
            if handled:
                return

        # ПРИОРИТЕТ 2: AI команды управления
        if ACTIVATION_COMMAND.lower() in message_text.lower():
            activate_chat(chat_id)
            await event.respond(f'✅ AI-ассистент активирован! Теперь я буду отвечать на все сообщения в этом чате.\n\n'
                                f'**Команды:**\n'
                                f'• "Ai Stop" - деактивировать ассистента\n'
                                f'• "Ai Clear" - очистить историю диалога')
            return

        if 'ai stop' in message_text.lower():
            deactivate_chat(chat_id)
            await event.respond('❌ AI-ассистент деактивирован. Напишите "Ai Edem" для повторной активации.')
            return

        if 'ai clear' in message_text.lower():
            if is_chat_active(chat_id):
                clear_chat_history(chat_id)
                await event.respond('🗑️ История диалога очищена!')
            return

    except Exception as e:
        print(f'❌ Ошибка обработки исходящего сообщения: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()


# ============ ГЛАВНАЯ ФУНКЦИЯ ============
async def main():
    """Запуск userbot"""
    global OWNER_ID
    
    print('🚀 Запуск Telegram Userbot с AI + Сохранение удаленных сообщений...')
    print(f'📁 Рабочая директория: {os.getcwd()}')
    print(f'📝 Используется сессия: {SESSION_NAME}.session')
    print(f'💾 Папка для медиа: {MEDIA_FOLDER}')

    # Создаем папку для медиа
    Path(MEDIA_FOLDER).mkdir(parents=True, exist_ok=True)

    # Проверка наличия файла сессии
    session_file = f'{SESSION_NAME}.session'
    if not os.path.exists(session_file):
        print(f'\n❌ ОШИБКА: Файл сессии "{session_file}" не найден!')
        print(f'\n📋 Инструкция по созданию сессии:')
        print(f'1. Запустите локально: python create_session.py')
        print(f'2. Введите код из Telegram')
        print(f'3. Загрузите созданный файл "{session_file}" в репозиторий\n')
        sys.exit(1)

    try:
        await client.connect()
        print('✅ Подключение к Telegram установлено')

        if not await client.is_user_authorized():
            print('\n❌ ОШИБКА: Сессия не авторизована!')
            sys.exit(1)

        print('✅ Userbot успешно запущен!')
        me = await client.get_me()
        OWNER_ID = me.id  # Сохраняем ID владельца
        
        print(f'👤 Аккаунт: {me.username or me.first_name} (ID: {OWNER_ID})')
        print(f'🤖 AI Модель: {MODEL_NAME}')
        print(f'🔑 Команда активации AI: "{ACTIVATION_COMMAND}"')
        print(f'💾 Функция сохранения удаленных: АКТИВНА')
        
        config = load_saver_config()
        print(f'📊 Сохранение личных: {config["save_private"]}')
        print(f'📊 Сохранение групп: {config["save_groups"]}')
        print(f'📊 Отслеживаемых каналов: {len(config["save_channels"])}')
        
        print('\n📝 Команды управления сохранением (только для вас, автоудаляются):')
        print('   .saver help - справка')
        print('   .saver status - статус')
        print('   .saver add - добавить чат')
        print('   .saver show - показать удаленные')
        print('\n⏹️ Для остановки нажмите Ctrl+C\n')
        print('🎧 Слушаю сообщения...\n')

        await client.run_until_disconnected()

    except Exception as e:
        print(f'❌ Ошибка запуска: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ============ ЗАПУСК ПРОГРАММЫ ============
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n👋 Userbot остановлен')
    except Exception as e:
        print(f'\n❌ Критическая ошибка: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
