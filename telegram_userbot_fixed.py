import asyncio
import json
import os
import sys
import base64
import ssl
from datetime import datetime, timedelta
from pathlib import Path
import aiohttp
from telethon import TelegramClient, events
from telethon.errors import RPCError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, InputPeerSelf

# ============ КОНФИГУРАЦИЯ ============
API_ID = int(os.environ.get('API_ID', '39678712'))
API_HASH = os.environ.get('API_HASH', '3089ac53d532e75deb5dd641e4863d49')
PHONE = os.environ.get('PHONE', '+919036205120')

# Новое API
AI_API_URL = 'https://api.onlysq.ru/ai/openai/chat/completions'
AI_API_KEY = 'openai'  # Базовый ключ
MODEL_NAME = 'gpt-5-mini'

# Файлы БД
DB_FILE = 'messages.json'
ACTIVE_CHATS_FILE = 'active_chats.json'
DELETED_MESSAGES_DB = 'deleted_messages.json'
SAVER_CONFIG_FILE = 'saver_config.json'
MESSAGES_STORAGE_DB = 'messages_storage.json'
ANIMATION_CONFIG_FILE = 'animation_config.json'
MUTE_CONFIG_FILE = 'mute_config.json'
TEMP_SELECTION_FILE = 'temp_selection.json'
AI_CONFIG_FILE = 'ai_config.json'  # Новый файл конфига ИИ
MUTED_USERS_DB = 'muted_users_db.json'  # База заглушенных пользователей

SESSION_NAME = 'railway_session'
MEDIA_FOLDER = 'saved_media'
OWNER_ID = None

last_command_message = {}
COMMAND_PREFIXES = ['.saver', '.deleted', '.aiconfig', '.aistop', '.aiclear', '.anim', '.замолчи', '.говори', '.del', '.список']

# Глобальное состояние
user_selection_state = {}

# ============ ФУНКЦИИ БД ============
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_db(data):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def load_ai_config():
    """Загрузка конфигурации ИИ"""
    if os.path.exists(AI_CONFIG_FILE):
        try:
            with open(AI_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        'enabled': False,  # Включен ли ИИ глобально
        'personality': 'отвечай как обычный человек, кратко и по делу',
        'style': 'casual',  # casual, formal, funny
        'lowercase': True,  # Писать с маленькой буквы
        'auto_reply_all': False,  # Отвечать всем автоматически
        'voice_enabled': True,  # Обрабатывать голосовые
        'photo_enabled': True,  # Обрабатывать фото
        'max_history': 20  # Сколько сообщений истории хранить
    }

def save_ai_config(config):
    try:
        with open(AI_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except:
        pass

def load_muted_users_db():
    """Загрузка базы заглушенных пользователей"""
    if os.path.exists(MUTED_USERS_DB):
        try:
            with open(MUTED_USERS_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_muted_users_db(data):
    try:
        with open(MUTED_USERS_DB, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def mute_user_new(user_id, user_name, chat_id=None):
    """Заглушить пользователя глобально"""
    db = load_muted_users_db()
    user_key = str(user_id)
    db[user_key] = {
        'user_name': user_name,
        'user_id': user_id,
        'muted_at': datetime.now().isoformat(),
        'chat_id': chat_id
    }
    save_muted_users_db(db)

def unmute_user_new(user_id):
    """Разглушить пользователя"""
    db = load_muted_users_db()
    user_key = str(user_id)
    if user_key in db:
        user_info = db.pop(user_key)
        save_muted_users_db(db)
        return user_info
    return None

def is_user_muted_new(user_id):
    """Проверить заглушен ли пользователь"""
    db = load_muted_users_db()
    return str(user_id) in db

def get_all_muted_users():
    """Получить всех заглушенных"""
    db = load_muted_users_db()
    return db

def load_animation_config():
    if os.path.exists(ANIMATION_CONFIG_FILE):
        try:
            with open(ANIMATION_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_animation_config(config):
    try:
        with open(ANIMATION_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_animation_settings(chat_id):
    config = load_animation_config()
    chat_key = str(chat_id)
    if chat_key in config:
        settings = config[chat_key]
        return {
            'mode': settings.get('mode'),
            'duration': settings.get('duration', 40),
            'interval': settings.get('interval', 0.5)
        }
    return {'mode': None, 'duration': 40, 'interval': 0.5}

def set_animation_mode(chat_id, mode):
    config = load_animation_config()
    chat_key = str(chat_id)
    if chat_key not in config:
        config[chat_key] = {'duration': 40, 'interval': 0.5}
    config[chat_key]['mode'] = mode
    save_animation_config(config)

def load_mute_config():
    if os.path.exists(MUTE_CONFIG_FILE):
        try:
            with open(MUTE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_mute_config(config):
    try:
        with open(MUTE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except:
        pass

def mute_user(chat_id, user_id, user_name):
    config = load_mute_config()
    chat_key = str(chat_id)
    if chat_key not in config:
        config[chat_key] = {}
    config[chat_key][str(user_id)] = {
        'user_name': user_name,
        'muted_at': datetime.now().isoformat()
    }
    save_mute_config(config)

def unmute_user(chat_id, user_id):
    config = load_mute_config()
    chat_key = str(chat_id)
    if chat_key in config and str(user_id) in config[chat_key]:
        user_info = config[chat_key].pop(str(user_id))
        save_mute_config(config)
        return user_info
    return None

def is_user_muted(chat_id, user_id):
    config = load_mute_config()
    chat_key = str(chat_id)
    return chat_key in config and str(user_id) in config[chat_key]

def get_muted_users(chat_id):
    config = load_mute_config()
    chat_key = str(chat_id)
    return config.get(chat_key, {})

# ============ АНИМАЦИОННЫЕ ФУНКЦИИ ============
async def animate_rainbow(message_obj, text, duration=40, interval=0.5):
    frames_count = int(duration / interval)
    colors = ['🔴', '🟠', '🟡', '🟢', '🔵', '🟣', '🟤']
    for frame in range(frames_count):
        color_bar = ''.join([colors[(i+frame)%len(colors)] for i in range(len(colors))])
        progress = int((frame / frames_count) * 10)
        bar = '▰' * progress + '▱' * (10 - progress)
        try:
            await message_obj.edit(f'{color_bar}\n{text}\n{bar}')
            await asyncio.sleep(interval)
        except:
            break
    try:
        await message_obj.edit(f'🌈 {text}')
    except:
        pass

async def animate_caps(message_obj, text, duration=40, interval=0.5):
    frames_count = int(duration / interval)
    try:
        await message_obj.edit(text)
        await asyncio.sleep(interval)
    except:
        pass
    
    for frame in range(1, frames_count - 1):
        if frame % 2 == 1:
            new_text = ''.join([c.upper() if i % 2 == 1 else c.lower() for i, c in enumerate(text)])
        else:
            new_text = ''.join([c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(text)])
        try:
            await message_obj.edit(new_text)
            await asyncio.sleep(interval)
        except:
            break
    
    try:
        await message_obj.edit(text)
    except:
        pass

async def run_animation(message_obj, text, anim_type, duration=40, interval=0.5):
    animations = {
        'rainbow': animate_rainbow,
        'caps': animate_caps
    }
    if anim_type in animations:
        await animations[anim_type](message_obj, text, duration, interval)

# ============ ОСТАЛЬНЫЕ БАЗОВЫЕ ФУНКЦИИ ============
def load_active_chats():
    if os.path.exists(ACTIVE_CHATS_FILE):
        try:
            with open(ACTIVE_CHATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_active_chats(data):
    try:
        with open(ACTIVE_CHATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def is_chat_active(chat_id):
    return str(chat_id) in load_active_chats() and load_active_chats()[str(chat_id)]

def activate_chat(chat_id):
    chats = load_active_chats()
    chats[str(chat_id)] = True
    save_active_chats(chats)

def deactivate_chat(chat_id):
    chats = load_active_chats()
    chats[str(chat_id)] = False
    save_active_chats(chats)

def load_messages_storage():
    if os.path.exists(MESSAGES_STORAGE_DB):
        try:
            with open(MESSAGES_STORAGE_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_messages_storage(data):
    try:
        with open(MESSAGES_STORAGE_DB, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def store_message_immediately(chat_id, message_data):
    storage = load_messages_storage()
    chat_key = str(chat_id)
    if chat_key not in storage:
        storage[chat_key] = []
    storage[chat_key].append(message_data)
    if len(storage[chat_key]) > 1000:
        storage[chat_key] = storage[chat_key][-1000:]
    save_messages_storage(storage)
    return True

def get_stored_message(chat_id, message_id):
    storage = load_messages_storage()
    if chat_id:
        chat_key = str(chat_id)
        if chat_key in storage:
            for msg in storage[chat_key]:
                if msg.get('message_id') == message_id:
                    return msg
    for chat_key, messages in storage.items():
        for msg in messages:
            if msg.get('message_id') == message_id:
                return msg
    return None

def is_command_message(text):
    if not text:
        return False
    text_lower = text.lower().strip()
    return any(text_lower.startswith(prefix.lower()) for prefix in COMMAND_PREFIXES)

def load_deleted_messages_db():
    if os.path.exists(DELETED_MESSAGES_DB):
        try:
            with open(DELETED_MESSAGES_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_deleted_messages_db(data):
    try:
        with open(DELETED_MESSAGES_DB, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def load_saver_config():
    if os.path.exists(SAVER_CONFIG_FILE):
        try:
            with open(SAVER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'save_text' not in config:
                    config['save_text'] = True
                if 'save_voice' not in config:
                    config['save_voice'] = True
                if 'save_ttl_media' not in config:
                    config['save_ttl_media'] = False
                return config
        except:
            pass
    return {
        'save_private': False, 
        'save_groups': False, 
        'save_channels': [], 
        'save_media': True, 
        'save_ttl': True,
        'save_text': True,
        'save_voice': True,
        'save_ttl_media': False
    }

def save_saver_config(config):
    try:
        with open(SAVER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except:
        pass

def should_save_message(chat_id, is_private, is_group):
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
    if is_user_muted(chat_id, message_data.get('sender_id')):
        return
        
    if is_command_message(message_data.get('text', '')):
        return
    
    config = load_saver_config()
    
    if not config.get('save_text', True):
        if not (message_data.get('has_photo') or message_data.get('has_video') or 
                message_data.get('has_document') or message_data.get('has_voice')):
            return
    
    if not config.get('save_media', True) and message_data.get('has_photo'):
        return
    
    if not config.get('save_media', True) and message_data.get('has_video'):
        return
    
    if not config.get('save_media', True) and message_data.get('has_document'):
        return
    
    if not config.get('save_voice', True) and message_data.get('has_voice'):
        return
    
    db = load_deleted_messages_db()
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []
    db[chat_key].append(message_data)
    if len(db[chat_key]) > 1000:
        db[chat_key] = db[chat_key][-1000:]
    save_deleted_messages_db(db)

def get_all_senders_with_deleted():
    db = load_deleted_messages_db()
    sender_stats = {}
    
    for chat_key, messages in db.items():
        for msg in messages:
            sender_id = msg.get('sender_id')
            if sender_id is None or sender_id == OWNER_ID:
                continue
            sender_name = msg.get('sender_name', 'Неизвестно')
            if sender_id not in sender_stats:
                sender_stats[sender_id] = {'name': sender_name, 'count': 0}
            sender_stats[sender_id]['count'] += 1
    
    sorted_senders = sorted(sender_stats.items(), key=lambda x: x[1]['count'], reverse=True)
    return [(sid, data['name'], data['count']) for sid, data in sorted_senders]

def get_deleted_messages(chat_id=None, limit=None, sender_id=None, message_type=None):
    db = load_deleted_messages_db()
    messages = []
    
    chat_keys = [str(chat_id)] if chat_id is not None else db.keys()
    
    for ck in chat_keys:
        if ck not in db:
            continue
        for msg in db[ck]:
            if is_command_message(msg.get('text', '')):
                continue
            if sender_id is not None and msg.get('sender_id') != sender_id:
                continue
                
            if message_type == 'photo' and not msg.get('has_photo'):
                continue
            if message_type == 'video' and not msg.get('has_video'):
                continue
            if message_type == 'document' and not msg.get('has_document'):
                continue
            if message_type == 'voice' and not msg.get('has_voice'):
                continue
            if message_type == 'text' and (msg.get('has_photo') or msg.get('has_video') or 
                                          msg.get('has_document') or msg.get('has_voice')):
                continue
                
            messages.append(msg)
    
    messages.sort(key=lambda x: x.get('deleted_at', ''), reverse=True)
    if limit:
        messages = messages[:limit]
    return messages

def clear_deleted_messages_by_type(chat_id, message_type, target_chat_id=None, sender_id=None):
    db = load_deleted_messages_db()
    
    if message_type == 'all_global':
        db.clear()
        save_deleted_messages_db(db)
        return True
    
    if sender_id is not None:
        for chat_key in db:
            db[chat_key] = [m for m in db[chat_key] if m.get('sender_id') != sender_id]
        save_deleted_messages_db(db)
        return True
    
    target = str(target_chat_id) if target_chat_id is not None else str(chat_id)
    
    if target not in db:
        return False
    
    messages = db[target]
    
    if message_type == 'all':
        db[target] = []
    elif message_type == 'photo':
        db[target] = [m for m in messages if not m.get('has_photo')]
    elif message_type == 'video':
        db[target] = [m for m in messages if not m.get('has_video')]
    elif message_type == 'document':
        db[target] = [m for m in messages if not m.get('has_document')]
    elif message_type == 'voice':
        db[target] = [m for m in messages if not m.get('has_voice')]
    elif message_type == 'text':
        db[target] = [m for m in messages if (m.get('has_photo') or m.get('has_video') or 
                                              m.get('has_document') or m.get('has_voice'))]
    
    save_deleted_messages_db(db)
    return True

def save_temp_selection(chat_id, users_list):
    chat_key = str(chat_id)
    if chat_key not in user_selection_state:
        user_selection_state[chat_key] = {}
    user_selection_state[chat_key]['users'] = users_list
    user_selection_state[chat_key]['timestamp'] = datetime.now()

def load_temp_selection(chat_id):
    chat_key = str(chat_id)
    if chat_key not in user_selection_state:
        return None
    data = user_selection_state[chat_key]
    if datetime.now() > data['timestamp'] + timedelta(minutes=5):
        del user_selection_state[chat_key]
        return None
    return data['users']

async def save_media_file(message, media_folder=MEDIA_FOLDER):
    try:
        Path(media_folder).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        chat_id, msg_id = message.chat_id, message.id
        
        if message.photo:
            ext, mtype = 'jpg', 'photo'
        elif message.video:
            ext, mtype = 'mp4', 'video'
        elif message.voice:
            ext, mtype = 'ogg', 'voice'
        elif message.document:
            ext = 'bin'
            if hasattr(message.document, 'attributes'):
                for attr in message.document.attributes:
                    if hasattr(attr, 'file_name') and '.' in attr.file_name:
                        ext = attr.file_name.split('.')[-1]
                        break
            mtype = 'document'
        else:
            return None
            
        filename = f'{mtype}_{chat_id}_{msg_id}_{timestamp}.{ext}'
        filepath = os.path.join(media_folder, filename)
        await message.download_media(filepath)
        print(f'💾 Сохранен: {filename}')
        return filepath
    except Exception as e:
        print(f'⚠️ Ошибка сохранения медиа: {e}')
        return None

db = load_db()

if os.path.exists(TEMP_SELECTION_FILE):
    try:
        with open(TEMP_SELECTION_FILE, 'r', encoding='utf-8') as f:
            loaded_state = json.load(f)
            for k, v in loaded_state.items():
                if 'timestamp' in v and isinstance(v['timestamp'], str):
                    try:
                        v['timestamp'] = datetime.fromisoformat(v['timestamp'])
                    except:
                        v['timestamp'] = datetime.now()
            user_selection_state = loaded_state
    except:
        user_selection_state = {}
else:
    user_selection_state = {}

# ============ ФУНКЦИИ ИИ ============
async def transcribe_voice(voice_path):
    """Транскрибация голосового сообщения"""
    try:
        # Используем простой подход - возвращаем заглушку
        # В реальности нужно использовать speech-to-text API
        return "[голосовое сообщение - транскрипция недоступна]"
    except Exception as e:
        print(f'❌ Ошибка транскрипции: {e}')
        return "[голосовое сообщение]"

async def describe_photo(photo_path):
    """Описание фото через Vision API"""
    try:
        # Конвертируем фото в base64
        with open(photo_path, 'rb') as f:
            photo_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Отправляем на API для анализа
        # В API OnlySQ возможно нет vision, поэтому возвращаем заглушку
        return "[фотография]"
    except Exception as e:
        print(f'❌ Ошибка описания фото: {e}')
        return "[фотография]"

async def get_ai_response(messages, config=None):
    """Получение ответа от ИИ через новое API"""
    try:
        if config is None:
            config = load_ai_config()
        
        # Добавляем системный промпт
        system_prompt = config.get('personality', 'отвечай как обычный человек, кратко и по делу')
        
        # Формируем сообщения
        api_messages = [{'role': 'system', 'content': system_prompt}]
        api_messages.extend(messages)
        
        # Создаем SSL context без проверки сертификатов
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=120)) as session:
            payload = {
                'model': MODEL_NAME,
                'request': {
                    'messages': api_messages
                }
            }
            headers = {
                'Authorization': f'Bearer {AI_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            async with session.post(AI_API_URL, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    message = result.get('choices', [{}])[0].get('message', {})
                    content = message.get('content', '').strip() or 'хз'
                    
                    # Применяем lowercase если нужно
                    if config.get('lowercase', True):
                        # Делаем первую букву маленькой
                        if content and content[0].isupper():
                            content = content[0].lower() + content[1:]
                    
                    return content
                else:
                    error_text = await resp.text()
                    print(f'❌ API ошибка {resp.status}: {error_text}')
                    return 'что-то не так с апи'
    except Exception as e:
        print(f'❌ API ошибка: {e}')
        import traceback
        traceback.print_exc()
        return 'не смог ответить'

def get_chat_history(chat_id, limit=10):
    """Получить историю чата"""
    config = load_ai_config()
    max_history = config.get('max_history', 20)
    limit = min(limit, max_history)
    
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []
    
    filtered = [msg for msg in db[chat_key] if not (msg.get('role') == 'assistant' and 'ошибка' in msg.get('content', '').lower())]
    return filtered[-limit:]

def save_message(chat_id, role, content):
    """Сохранить сообщение в историю"""
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []
    
    if role == 'assistant' and 'ошибка' in content.lower():
        return
    
    message = {'role': role, 'content': content}
    db[chat_key].append(message)
    
    config = load_ai_config()
    max_history = config.get('max_history', 20)
    
    if len(db[chat_key]) > max_history * 2:
        db[chat_key] = db[chat_key][-max_history * 2:]
    
    save_db(db)

def clear_chat_history(chat_id):
    """Очистить историю чата"""
    chat_key = str(chat_id)
    if chat_key in db:
        db[chat_key] = []
        save_db(db)

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def delete_previous_command(chat_id):
    """Удалить предыдущее командное сообщение"""
    if chat_id in last_command_message:
        try:
            msg_ids = last_command_message[chat_id]
            await client.delete_messages(chat_id, msg_ids if isinstance(msg_ids, list) else [msg_ids])
        except:
            pass

async def register_command_message(chat_id, message_id):
    """Зарегистрировать командное сообщение для удаления"""
    last_command_message[chat_id] = message_id

async def forward_to_saved(media_path, caption_text=""):
    """Пересылка медиа в избранное"""
    try:
        if not media_path or not os.path.exists(media_path):
            print(f'⚠️ Файл не найден: {media_path}')
            return False
        
        await client.send_file('me', media_path, caption=caption_text)
        print(f'📤 Переслано в избранное: {os.path.basename(media_path)}')
        return True
    except Exception as e:
        print(f'⚠️ Ошибка пересылки в избранное: {e}')
        import traceback
        traceback.print_exc()
        return False

# ============ ОБРАБОТЧИКИ КОМАНД ============
async def handle_aiconfig_commands(event, message_text):
    """Обработка команд настройки ИИ"""
    chat_id = event.chat_id
    
    # Команды работают только в Saved Messages
    if chat_id != OWNER_ID:
        return False
    
    await delete_previous_command(chat_id)
    
    if message_text.lower() == '.aiconfig help':
        help_text = '''🤖 **ПАНЕЛЬ УПРАВЛЕНИЯ ИИ**

📋 **ОСНОВНЫЕ НАСТРОЙКИ**
┣‣ `.aiconfig status` - 📊 Показать статус
┣‣ `.aiconfig on/off` - 🔌 Вкл/выкл ИИ
┣‣ `.aiconfig auto on/off` - 🤖 Авто-ответ всем
┣‣ `.aiconfig voice on/off` - 🎤 Голосовые
┣‣ `.aiconfig photo on/off` - 📷 Фото

⚙️ **КОНФИГУРАЦИЯ**
┣‣ `.aiconfig show` - 📄 Показать конфиг
┣‣ `.aiconfig edit` - ✏️ Редактировать
┣‣ `.aiconfig reset` - 🔄 Сброс
┣‣ Отправьте JSON файл - загрузка конфига

💡 **СТИЛЬ**
┣‣ `.aiconfig style casual` - 😎 Непринужденный
┣‣ `.aiconfig style formal` - 🎩 Формальный
┣‣ `.aiconfig style funny` - 😄 Смешной
┣‣ `.aiconfig lowercase on/off` - 🔡 Маленькие буквы

📝 **ЛИЧНОСТЬ**
┣‣ `.aiconfig personality <текст>` - Задать личность

🗑️ **УПРАВЛЕНИЕ**
┣‣ `.aistop` - ❌ Выключить в чате
┣‣ `.aiclear` - 🗑️ Очистить историю'''
        
        msg = await event.respond(help_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.aiconfig status':
        config = load_ai_config()
        status_text = f'''🤖 **СТАТУС ИИ:**

🔌 Состояние: {"✅ ВКЛЮЧЕН" if config['enabled'] else "❌ ВЫКЛЮЧЕН"}
🤖 Авто-ответ: {"✅" if config['auto_reply_all'] else "❌"}
🎤 Голосовые: {"✅" if config['voice_enabled'] else "❌"}
📷 Фото: {"✅" if config['photo_enabled'] else "❌"}
🔡 Маленькие буквы: {"✅" if config['lowercase'] else "❌"}

🎭 Стиль: **{config['style']}**
📊 История: {config['max_history']} сообщений
🧠 Личность: {config['personality'][:100]}...'''
        
        msg = await event.respond(status_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.aiconfig on', '.aiconfig off']:
        config = load_ai_config()
        config['enabled'] = 'on' in message_text.lower()
        save_ai_config(config)
        
        msg = await event.respond(f'{"✅ ИИ включен" if config["enabled"] else "❌ ИИ выключен"}')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.aiconfig auto on', '.aiconfig auto off']:
        config = load_ai_config()
        config['auto_reply_all'] = 'on' in message_text.lower()
        save_ai_config(config)
        
        msg = await event.respond(f'{"✅ Авто-ответ всем включен" if config["auto_reply_all"] else "❌ Авто-ответ всем выключен"}')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.aiconfig voice on', '.aiconfig voice off']:
        config = load_ai_config()
        config['voice_enabled'] = 'on' in message_text.lower()
        save_ai_config(config)
        
        msg = await event.respond(f'{"✅ Обработка голосовых включена" if config["voice_enabled"] else "❌ Обработка голосовых выключена"}')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.aiconfig photo on', '.aiconfig photo off']:
        config = load_ai_config()
        config['photo_enabled'] = 'on' in message_text.lower()
        save_ai_config(config)
        
        msg = await event.respond(f'{"✅ Обработка фото включена" if config["photo_enabled"] else "❌ Обработка фото выключена"}')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.aiconfig lowercase on', '.aiconfig lowercase off']:
        config = load_ai_config()
        config['lowercase'] = 'on' in message_text.lower()
        save_ai_config(config)
        
        msg = await event.respond(f'{"✅ Маленькие буквы включены" if config["lowercase"] else "❌ Маленькие буквы выключены"}')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.aiconfig style '):
        parts = message_text.split(maxsplit=2)
        if len(parts) < 3:
            msg = await event.respond('❌ Формат: `.aiconfig style <casual|formal|funny>`')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        
        style = parts[2].lower()
        if style not in ['casual', 'formal', 'funny']:
            msg = await event.respond('❌ Доступные стили: casual, formal, funny')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        
        config = load_ai_config()
        config['style'] = style
        save_ai_config(config)
        
        msg = await event.respond(f'✅ Стиль изменен на **{style}**')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.aiconfig personality '):
        personality = message_text[len('.aiconfig personality '):].strip()
        if not personality:
            msg = await event.respond('❌ Укажите текст личности')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        
        config = load_ai_config()
        config['personality'] = personality
        save_ai_config(config)
        
        msg = await event.respond(f'✅ Личность обновлена:\n{personality[:200]}')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.aiconfig show':
        config = load_ai_config()
        config_text = json.dumps(config, ensure_ascii=False, indent=2)
        
        msg = await event.respond(f'```json\n{config_text}\n```')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.aiconfig reset':
        default_config = {
            'enabled': False,
            'personality': 'отвечай как обычный человек, кратко и по делу',
            'style': 'casual',
            'lowercase': True,
            'auto_reply_all': False,
            'voice_enabled': True,
            'photo_enabled': True,
            'max_history': 20
        }
        save_ai_config(default_config)
        
        msg = await event.respond('🔄 Конфигурация сброшена')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    return False

async def handle_mute_commands_new(event, message_text):
    """Обработка команд заглушки/разглушки (УЛУЧШЕННАЯ ВЕРСИЯ)"""
    chat_id = event.chat_id
    
    # Команды работают только в Saved Messages
    if chat_id != OWNER_ID:
        return False
    
    await delete_previous_command(chat_id)
    
    # Показать список заглушенных
    if message_text.lower() == '.список':
        muted = get_all_muted_users()
        if not muted:
            msg = await event.respond('📭 Нет заглушенных пользователей')
        else:
            list_text = f'🔇 **ЗАГЛУШЕННЫЕ ({len(muted)}):**\n\n'
            for i, (user_id, info) in enumerate(muted.items(), 1):
                list_text += f'{i}. {info.get("user_name", "?")} (ID: `{user_id}`)\n'
                list_text += f'   📅 {info.get("muted_at", "")[:16]}\n\n'
            list_text += '\n💡 Чтобы разглушить:\n'
            list_text += '• Ответьте на сообщение командой `.говори`\n'
            list_text += '• Или используйте `.говори <ID>`'
            
            msg = await event.respond(list_text)
        
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    # Заглушить пользователя
    if message_text.lower() == '.замолчи':
        # Проверяем есть ли ответ на сообщение
        if event.reply_to_msg_id:
            try:
                reply_msg = await event.get_reply_message()
                user_id = reply_msg.sender_id
                sender = await reply_msg.get_sender()
                user_name = getattr(sender, 'first_name', 'Неизвестно')
                if hasattr(sender, 'username') and sender.username:
                    user_name += f' (@{sender.username})'
                
                # Глобальная заглушка
                mute_user_new(user_id, user_name, reply_msg.chat_id)
                
                msg = await event.respond(f'🔇 **{user_name}** заглушен глобально!\n\n💡 Его сообщения теперь игнорируются везде\n📝 Разглушить: `.говори` (ответом) или `.говори {user_id}`')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            except Exception as e:
                msg = await event.respond(f'❌ Ошибка: {e}')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
        else:
            msg = await event.respond('❌ Ответьте на сообщение пользователя!')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
    
    # Разглушить пользователя
    if message_text.lower().startswith('.говори'):
        # Вариант 1: Ответ на сообщение
        if event.reply_to_msg_id:
            try:
                reply_msg = await event.get_reply_message()
                user_id = reply_msg.sender_id
                user_info = unmute_user_new(user_id)
                
                if user_info:
                    msg = await event.respond(f'🔊 **{user_info.get("user_name")}** разглушен!\n\n💡 Сообщения снова обрабатываются')
                else:
                    msg = await event.respond('⚠️ Пользователь не был заглушен!')
                
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            except Exception as e:
                msg = await event.respond(f'❌ Ошибка: {e}')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
        
        # Вариант 2: Указан ID
        parts = message_text.split()
        if len(parts) >= 2:
            try:
                user_id = int(parts[1])
                user_info = unmute_user_new(user_id)
                
                if user_info:
                    msg = await event.respond(f'🔊 **{user_info.get("user_name")}** разглушен!\n\n💡 Сообщения снова обрабатываются')
                else:
                    msg = await event.respond(f'⚠️ Пользователь {user_id} не был заглушен!')
                
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            except ValueError:
                msg = await event.respond('❌ Неверный формат ID!')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
        else:
            msg = await event.respond('❌ Используйте: `.говори <ID>` или ответьте на сообщение')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
    
    return False

async def handle_saver_commands(event, message_text):
    chat_id = event.chat_id
    await delete_previous_command(chat_id)
    
    if message_text.lower() == '.saver help':
        help_text = '''🔧 **ПАНЕЛЬ УПРАВЛЕНИЯ СОХРАНЕНИЕМ СООБЩЕНИЙ**

💡 *Этот бот сохраняет удалённые сообщения в чатах, где включена функция сохранения.*

📋 **ОСНОВНЫЕ НАСТРОЙКИ**
┣‣ `.saver status` - 📊 Показать текущий статус
┣‣ `.saver private on/off` - 🔓 Личные чаты
┣‣ `.saver groups on/off` - 👥 Группы
┣‣ `.saver add` - ➕ Добавить этот чат
┣‣ `.saver remove` - ➖ Удалить этот чат

🗑️ **УПРАВЛЕНИЕ УДАЛЁННЫМИ**
┣‣ `.saver show` - 📄 Последние 10 удалённых
┣‣ `.saver all` - 👥 Все пользователи
┣‣ `.saver user <номер>` - 📂 Все сообщения

🧹 **ОЧИСТКА**
┣‣ `.saver clear all` - 🗑️ Вся база
┣‣ `.saver clear text` - 📝 Только текст
┣‣ `.saver clear photo` - 🖼️ Только фото
┣‣ `.saver clear voice` - 🎤 Только ГС
┣‣ `.saver clear user <номер>` - 👤 Пользователя

⚙️ **ТИПЫ СОХРАНЕНИЯ**
┣‣ `.saver text on/off` - 📝 Текст
┣‣ `.saver media on/off` - 🖼️ Медиа
┣‣ `.saver voice on/off` - 🎤 Голосовые
┣‣ `.saver ttl on/off` - ⏱️ Скоротечные

💡 *Фото, голосовые и скоротечные медиа при удалении автоматически пересылаются в избранное!*

🎬 **ДОПОЛНИТЕЛЬНО**
┣‣ `.anim help` - 🎞️ Анимации
┣‣ `.замолчи` - 🔇 Заглушить
┣‣ `.список` - 📋 Список заглушенных
┣‣ `.del` - 🗑️ Удалить меню'''
        msg = await event.respond(help_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.saver status':
        config = load_saver_config()
        is_private, is_group = event.is_private, event.is_group
        is_saved = should_save_message(chat_id, is_private, is_group)
        status_text = f'📊 **СТАТУС СОХРАНЕНИЯ:**\n\n'
        status_text += f'📍 Текущий чат: {"✅ ВКЛ" if is_saved else "❌ ВЫКЛ"}\n'
        status_text += f'💬 Личные: {"✅" if config["save_private"] else "❌"}\n'
        status_text += f'👥 Группы: {"✅" if config["save_groups"] else "❌"}\n'
        status_text += f'📑 Каналы: {len(config["save_channels"])} шт.\n\n'
        status_text += f'**ТИПЫ:**\n'
        status_text += f'📝 Текст: {"✅" if config.get("save_text", True) else "❌"}\n'
        status_text += f'🖼️ Медиа: {"✅" if config.get("save_media", True) else "❌"}\n'
        status_text += f'🎤 Голосовые: {"✅" if config.get("save_voice", True) else "❌"}\n'
        status_text += f'⏱️ Скоротечные: {"✅" if config.get("save_ttl_media", False) else "❌"}\n\n'
        status_text += f'💡 *При удалении медиа автоматически пересылается в избранное*'
        msg = await event.respond(status_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.saver text on', '.saver text off']:
        config = load_saver_config()
        config['save_text'] = 'on' in message_text
        save_saver_config(config)
        msg = await event.respond(f'{"✅" if config["save_text"] else "❌"} Сохранение текста')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.saver media on', '.saver media off']:
        config = load_saver_config()
        config['save_media'] = 'on' in message_text
        save_saver_config(config)
        msg = await event.respond(f'{"✅" if config["save_media"] else "❌"} Сохранение медиа\n\n💡 При удалении медиа автоматически пересылается в избранное')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.saver voice on', '.saver voice off']:
        config = load_saver_config()
        config['save_voice'] = 'on' in message_text
        save_saver_config(config)
        msg = await event.respond(f'{"✅" if config["save_voice"] else "❌"} Сохранение голосовых\n\n💡 При удалении ГС автоматически пересылается в избранное')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.saver ttl on', '.saver ttl off']:
        config = load_saver_config()
        config['save_ttl_media'] = 'on' in message_text
        save_saver_config(config)
        ttl_status = "✅ ВКЛЮЧЕНО" if config['save_ttl_media'] else "❌ ВЫКЛЮЧЕНО"
        ttl_help = "\n\n💡 Скоротечные фото/видео будут сохраняться и пересылаться в избранное автоматически" if config['save_ttl_media'] else ""
        msg = await event.respond(f'⏱️ Сохранение скоротечных медиа: {ttl_status}{ttl_help}')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.saver private on', '.saver private off']:
        config = load_saver_config()
        config['save_private'] = 'on' in message_text
        save_saver_config(config)
        msg = await event.respond(f'{"✅" if config["save_private"] else "❌"} Личные чаты')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.saver groups on', '.saver groups off']:
        config = load_saver_config()
        config['save_groups'] = 'on' in message_text
        save_saver_config(config)
        msg = await event.respond(f'{"✅" if config["save_groups"] else "❌"} Группы')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.saver add':
        config = load_saver_config()
        chat_id_str = str(chat_id)
        if chat_id_str not in config['save_channels']:
            config['save_channels'].append(chat_id_str)
            save_saver_config(config)
            msg = await event.respond(f'✅ Чат добавлен!')
        else:
            msg = await event.respond(f'⚠️ Уже добавлен!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.saver remove':
        config = load_saver_config()
        chat_id_str = str(chat_id)
        if chat_id_str in config['save_channels']:
            config['save_channels'].remove(chat_id_str)
            save_saver_config(config)
            msg = await event.respond(f'❌ Чат удален!')
        else:
            msg = await event.respond(f'⚠️ Не был добавлен!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.saver show':
        msgs = get_deleted_messages(limit=10)
        if not msgs:
            msg = await event.respond('📭 Нет удаленных сообщений')
        else:
            response = f'🗑️ **Последние {len(msgs)} удалённых:**\n\n'
            for i, m in enumerate(msgs, 1):
                sender = m.get('sender_name', 'Неизвестно')
                text_type = "📝"
                if m.get('has_photo'): text_type = "🖼️"
                elif m.get('has_video'): text_type = "🎥"
                elif m.get('has_document'): text_type = "📄"
                elif m.get('has_voice'): text_type = "🎤"
                response += f'{i}. {text_type} {sender}\n'
                response += f'   Чат: `{m.get("chat_id")}` | {m.get("deleted_at", "")[:16]}\n'
                response += f'   {m.get("text", "")[:50]}\n\n'
            response += '\n💡 *Медиа отправлено в избранное*'
            msg = await event.respond(response)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.saver clear all':
        db = load_deleted_messages_db()
        db.clear()
        save_deleted_messages_db(db)
        msg = await event.respond('🗑️ Вся база очищена!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.saver clear text':
        clear_deleted_messages_by_type(chat_id, 'text')
        msg = await event.respond('🗑️ Текстовые сообщения очищены!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.saver clear photo':
        clear_deleted_messages_by_type(chat_id, 'photo')
        msg = await event.respond('🗑️ Фото очищены!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.saver clear voice':
        clear_deleted_messages_by_type(chat_id, 'voice')
        msg = await event.respond('🗑️ Голосовые очищены!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.saver clear user '):
        try:
            parts = message_text.split()
            if len(parts) < 4:
                msg = await event.respond('❌ Формат: `.saver clear user <номер>`')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            
            index = int(parts[3]) - 1
            users = load_temp_selection(chat_id)
            if users is None:
                msg = await event.respond('⚠️ Сначала вызовите `.saver all`')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            
            if 0 <= index < len(users):
                sender_id = users[index]['sender_id']
                sender_name = users[index]['name']
                clear_deleted_messages_by_type(chat_id, None, None, sender_id)
                msg = await event.respond(f'🗑️ Сообщения **{sender_name}** удалены!')
            else:
                msg = await event.respond('❌ Неверный номер')
            
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        except Exception as e:
            msg = await event.respond(f'❌ Ошибка: {e}')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
    
    if message_text.lower() == '.saver all':
        if not event.is_private:
            msg = await event.respond('❌ Команда доступна ТОЛЬКО в личном чате!')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
            
        senders = get_all_senders_with_deleted()
        if not senders:
            msg = await event.respond('📭 Нет пользователей с удалёнными')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
            
        users_list = [{'sender_id': sid, 'name': name} for sid, name, cnt in senders]
        save_temp_selection(chat_id, users_list)
        
        response = '👥 **ПОЛЬЗОВАТЕЛИ С УДАЛЁННЫМИ:**\n\n'
        for i, (sid, name, cnt) in enumerate(senders, 1):
            response += f'{i}. {name} — 🗑️ {cnt} шт.\n'
        response += '\n🔢 Введите номер или `.saver user <номер>`\n💡 *Медиа отправлено в избранное*'
        
        msg = await event.respond(response)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.saver user '):
        try:
            parts = message_text.split()
            if len(parts) < 3:
                msg = await event.respond('❌ Формат: `.saver user <номер>`')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
                
            index = int(parts[2]) - 1
            users = load_temp_selection(chat_id)
            if users is None:
                msg = await event.respond('⚠️ Сначала вызовите `.saver all`')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            if 0 <= index < len(users):
                sender_id = users[index]['sender_id']
                sender_name = users[index]['name']
                msgs = get_deleted_messages(sender_id=sender_id)
                if not msgs:
                    text = f'📭 У **{sender_name}** нет удалённых'
                else:
                    text = f'🗑️ **{sender_name}** (ВСЕГО: {len(msgs)} шт.):\n\n'
                    display_msgs = msgs[:30]
                    for i, m in enumerate(display_msgs, 1):
                        text_type = "📝"
                        if m.get('has_photo'): text_type = "🖼️"
                        elif m.get('has_video'): text_type = "🎥"
                        elif m.get('has_document'): text_type = "📄"
                        elif m.get('has_voice'): text_type = "🎤"
                        text += f'{i}. {text_type} [{m.get("deleted_at", "")[:16]}]\n'
                        text += f'   Чат: `{m.get("chat_id")}`\n'
                        text += f'   {m.get("text", "")[:50]}\n\n'
                    if len(msgs) > 30:
                        text += f'\n...ещё {len(msgs)-30} сообщений\n'
                        text += f'💾 Всего в базе: {len(msgs)}\n'
                    text += '\n💡 *Медиа отправлено в избранное*'
                msg = await event.respond(text)
            else:
                msg = await event.respond('❌ Неверный номер')
            
            user_selection_state.pop(str(chat_id), None)
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        except Exception as e:
            msg = await event.respond(f'❌ Ошибка: {e}')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
    
    return False

async def handle_digit_selection(event, message_text):
    chat_id = event.chat_id
    
    if not message_text.strip().isdigit():
        return False
        
    users = load_temp_selection(chat_id)
    if users is None:
        return False
        
    try:
        index = int(message_text.strip()) - 1
        if 0 <= index < len(users):
            sender_id = users[index]['sender_id']
            sender_name = users[index]['name']
            msgs = get_deleted_messages(sender_id=sender_id)
            
            if not msgs:
                text = f'📭 У **{sender_name}** нет удалённых'
            else:
                text = f'🗑️ **{sender_name}** (ВСЕГО: {len(msgs)} шт.):\n\n'
                display_msgs = msgs[:30]
                for i, m in enumerate(display_msgs, 1):
                    text_type = "📝"
                    if m.get('has_photo'): text_type = "🖼️"
                    elif m.get('has_video'): text_type = "🎥"
                    elif m.get('has_document'): text_type = "📄"
                    elif m.get('has_voice'): text_type = "🎤"
                    text += f'{i}. {text_type} [{m.get("deleted_at", "")[:16]}]\n'
                    text += f'   Чат: `{m.get("chat_id")}`\n'
                    text += f'   {m.get("text", "")[:50]}\n\n'
                if len(msgs) > 30:
                    text += f'\n...ещё {len(msgs)-30} сообщений\n'
                    text += f'💾 Всего в базе: {len(msgs)}\n'
                text += '\n💡 *Медиа отправлено в избранное*'
                    
            msg = await event.respond(text)
            user_selection_state.pop(str(chat_id), None)
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        else:
            msg = await event.respond('❌ Неверный номер')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
    except:
        return False

async def handle_animation_commands(event, message_text):
    chat_id = event.chat_id
    await delete_previous_command(chat_id)
    
    if message_text.lower() == '.anim help':
        help_text = '''🎬 **КОМАНДЫ АНИМАЦИЙ**

**ТИПЫ:**
• rainbow 🌈 - радужная анимация
• caps 🔤 - чередование регистра

**ИСПОЛЬЗОВАНИЕ:**
`.anim <тип> текст`
Пример: `.anim rainbow Привет!`

**НАСТРОЙКИ:**
• `.anim mode <тип>` - авто-анимация
• `.anim mode off` - выключить
• `.anim duration <сек>` - длительность
• `.anim interval <сек>` - интервал
• `.anim status` - показать настройки

💡 Команда в тексте удаляется автоматически'''
        msg = await event.respond(help_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.anim status':
        settings = get_animation_settings(chat_id)
        mode = settings['mode']
        status_text = f'🎬 **Статус:**\n'
        status_text += f'Режим: **{mode.upper() if mode else "ВЫКЛ"}**\n'
        status_text += f'⏱️ Длительность: {settings["duration"]} сек\n'
        status_text += f'⏲️ Интервал: {settings["interval"]} сек'
        msg = await event.respond(status_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.anim duration '):
        try:
            duration = float(message_text.split()[2])
            config = load_animation_config()
            chat_key = str(chat_id)
            if chat_key not in config:
                config[chat_key] = {'mode': None, 'interval': 0.5}
            config[chat_key]['duration'] = duration
            save_animation_config(config)
            msg = await event.respond(f'✅ Длительность: {duration} сек')
        except:
            msg = await event.respond('❌ Неверный формат')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.anim interval '):
        try:
            interval = float(message_text.split()[2])
            config = load_animation_config()
            chat_key = str(chat_id)
            if chat_key not in config:
                config[chat_key] = {'mode': None, 'duration': 40}
            config[chat_key]['interval'] = interval
            save_animation_config(config)
            msg = await event.respond(f'✅ Интервал: {interval} сек')
        except:
            msg = await event.respond('❌ Неверный формат')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.anim mode '):
        parts = message_text.split(maxsplit=2)
        if len(parts) < 3:
            msg = await event.respond('❌ Формат: `.anim mode <тип>`')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
            
        mode = parts[2].lower()
        if mode == 'off':
            set_animation_mode(chat_id, None)
            msg = await event.respond('❌ Режим ВЫКЛЮЧЕН')
        elif mode in ['rainbow', 'caps']:
            set_animation_mode(chat_id, mode)
            msg = await event.respond(f'✅ Режим **{mode.upper()}** включен!')
        else:
            msg = await event.respond('❌ Неизвестный режим!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.anim '):
        parts = message_text.split(maxsplit=2)
        if len(parts) >= 3:
            anim_type, text = parts[1].lower(), parts[2]
            if anim_type in ['rainbow', 'caps']:
                await event.delete()
                settings = get_animation_settings(chat_id)
                animation_msg = await event.respond('🎬 Запуск...')
                await run_animation(animation_msg, text, anim_type, settings['duration'], settings['interval'])
                return True
    
    return False

# ============ ОБРАБОТЧИКИ СОБЫТИЙ ============
@client.on(events.NewMessage(incoming=True, from_users=None))
async def immediate_save_handler(event):
    """Сохранение входящих сообщений"""
    try:
        chat_id, message_id, sender_id = event.chat_id, event.message.id, event.sender_id
        
        if OWNER_ID and sender_id == OWNER_ID:
            return
        
        # Проверка на глобальную заглушку
        if is_user_muted_new(sender_id):
            print(f'🔇 Глобально заглушенный {sender_id} - удаляем MSG {message_id}')
            try:
                await client.delete_messages(chat_id, message_id)
                print(f'✅ Удалено!')
            except Exception as e:
                print(f'⚠️ Ошибка удаления: {e}')
            return
        
        # Старая проверка заглушки по чату
        if is_user_muted(chat_id, sender_id):
            print(f'🔇 Заглушенный в чате {sender_id} - удаляем MSG {message_id}')
            try:
                await client.delete_messages(chat_id, message_id)
                print(f'✅ Удалено!')
            except Exception as e:
                print(f'⚠️ Ошибка удаления: {e}')
            return
        
        is_private, is_group = event.is_private, event.is_group
        if not should_save_message(chat_id, is_private, is_group):
            return
        
        sender = await event.get_sender()
        sender_name = getattr(sender, 'first_name', 'Неизвестно')
        if hasattr(sender, 'username') and sender.username:
            sender_name += f' (@{sender.username})'
        
        is_ttl_media = False
        if hasattr(event.message, 'media'):
            if hasattr(event.message.media, 'photo') and event.message.media.photo:
                if hasattr(event.message.media, 'ttl_seconds') and event.message.media.ttl_seconds:
                    is_ttl_media = True
                    print(f'⏱️ Обнаружено скоротечное ФОТО! TTL: {event.message.media.ttl_seconds}с')
            elif hasattr(event.message.media, 'document') and event.message.media.document:
                if hasattr(event.message.media, 'ttl_seconds') and event.message.media.ttl_seconds:
                    is_ttl_media = True
                    print(f'⏱️ Обнаружено скоротечное ВИДЕО! TTL: {event.message.media.ttl_seconds}с')
        
        config = load_saver_config()
        
        save_this_media = config.get('save_media', True)
        if is_ttl_media and config.get('save_ttl_media', False):
            save_this_media = True
            print(f'💾 Сохраняем скоротечное медиа (настройка включена)')
        
        message_data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'sender_id': sender_id,
            'sender_name': sender_name,
            'text': event.message.message or '',
            'date': event.message.date.isoformat() if event.message.date else None,
            'has_photo': bool(event.message.photo),
            'has_video': bool(event.message.video),
            'has_document': bool(event.message.document),
            'has_voice': bool(event.message.voice),
            'is_ttl': is_ttl_media,
            'media_path': None
        }
        
        if save_this_media and (event.message.photo or event.message.video or 
                                event.message.document or event.message.voice or is_ttl_media):
            if is_ttl_media:
                print(f'📥 Скачиваем скоротечное медиа...')
            message_data['media_path'] = await save_media_file(event.message)
        
        store_message_immediately(chat_id, message_data)
    except Exception as e:
        print(f'❌ Ошибка сохранения: {e}')
        import traceback
        traceback.print_exc()

@client.on(events.MessageDeleted)
async def deleted_message_handler(event):
    """Обработка удаленных сообщений"""
    try:
        chat_id, deleted_ids = event.chat_id, event.deleted_ids
        print(f'🗑️ Удалено {len(deleted_ids)} сообщений')
        for message_id in deleted_ids:
            message_data = get_stored_message(chat_id, message_id)
            if message_data:
                real_chat_id = message_data.get('chat_id')
                message_data['deleted_at'] = datetime.now().isoformat()
                
                config = load_saver_config()
                should_forward = False
                caption_prefix = ""
                media_path = message_data.get('media_path')
                
                if message_data.get('has_photo') and config.get('save_media', True):
                    should_forward = True
                    caption_prefix = "🖼️ Удалённое фото"
                elif message_data.get('has_video') and config.get('save_media', True):
                    should_forward = True
                    caption_prefix = "🎥 Удалённое видео"
                elif message_data.get('has_voice') and config.get('save_voice', True):
                    should_forward = True
                    caption_prefix = "🎤 Удалённое ГС"
                elif message_data.get('is_ttl') and config.get('save_ttl_media', False):
                    should_forward = True
                    caption_prefix = "⏱️ Скоротечное медиа"
                
                if should_forward and media_path:
                    sender_name = message_data.get('sender_name', 'Неизвестно')
                    msg_text = message_data.get('text', '')
                    full_caption = f"{caption_prefix}\n👤 От: {sender_name}\n🗑️ Удалено: {message_data.get('deleted_at', '')[:16]}"
                    if msg_text:
                        full_caption += f"\n📝 Текст: {msg_text[:100]}"
                    
                    print(f'📤 Пересылаем в избранное: {media_path}')
                    await forward_to_saved(media_path, full_caption)
                
                add_deleted_message(real_chat_id, message_data)
    except Exception as e:
        print(f'❌ Ошибка обработки удаленного: {e}')
        import traceback
        traceback.print_exc()

@client.on(events.NewMessage(incoming=True))
async def incoming_handler(event):
    """Обработка входящих сообщений для ИИ"""
    try:
        chat_id = event.chat_id
        sender_id = event.sender_id
        
        # Пропускаем собственные сообщения
        if sender_id == OWNER_ID:
            return
        
        # Проверка глобальной заглушки
        if is_user_muted_new(sender_id):
            return
        
        config = load_ai_config()
        
        # Проверяем включен ли ИИ
        if not config.get('enabled', False):
            return
        
        # Проверяем режим авто-ответа
        if not config.get('auto_reply_all', False):
            return
        
        message_text = event.message.message or ''
        
        # Игнорируем команды
        if is_command_message(message_text):
            return
        
        # Обработка голосовых
        if event.message.voice and config.get('voice_enabled', True):
            voice_path = await save_media_file(event.message)
            if voice_path:
                transcription = await transcribe_voice(voice_path)
                message_text = f"[голосовое: {transcription}]"
        
        # Обработка фото
        if event.message.photo and config.get('photo_enabled', True):
            photo_path = await save_media_file(event.message)
            if photo_path:
                description = await describe_photo(photo_path)
                if message_text:
                    message_text = f"{message_text} [фото: {description}]"
                else:
                    message_text = f"[фото: {description}]"
        
        if not message_text or message_text == 'сообщение без текста':
            return
        
        # Сохраняем сообщение
        save_message(chat_id, 'user', message_text)
        
        # Получаем историю
        history = get_chat_history(chat_id)
        
        # Получаем ответ от ИИ
        response_content = await get_ai_response(history, config)
        
        if response_content and 'ошибка' not in response_content.lower():
            save_message(chat_id, 'assistant', response_content)
            await event.respond(response_content)
    except RPCError as e:
        if 'TOPIC_CLOSED' in str(e) or 'CHAT_WRITE_FORBIDDEN' in str(e):
            pass
    except Exception as e:
        print(f'❌ Ошибка входящего: {e}')

@client.on(events.NewMessage(outgoing=True))
async def outgoing_handler(event):
    """Обработка исходящих сообщений"""
    try:
        chat_id = event.chat_id
        message_text = event.message.message or ''
        
        # Проверка на загрузку конфига из JSON файла
        if event.message.document and chat_id == OWNER_ID:
            # Проверяем расширение файла
            filename = ''
            if hasattr(event.message.document, 'attributes'):
                for attr in event.message.document.attributes:
                    if hasattr(attr, 'file_name'):
                        filename = attr.file_name
                        break
            
            if filename.endswith('.json'):
                # Скачиваем файл
                file_path = await save_media_file(event.message)
                if file_path:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            new_config = json.load(f)
                        
                        # Сохраняем конфиг
                        save_ai_config(new_config)
                        
                        msg = await event.respond('✅ Конфигурация загружена из файла!')
                        await event.delete()
                        await register_command_message(chat_id, msg.id)
                        return
                    except Exception as e:
                        msg = await event.respond(f'❌ Ошибка загрузки конфига: {e}')
                        await event.delete()
                        await register_command_message(chat_id, msg.id)
                        return
        
        # Команда удаления последнего меню
        if message_text.lower() == '.del':
            await delete_previous_command(chat_id)
            await event.delete()
            return
        
        # Проверяем выбор цифрой
        if await handle_digit_selection(event, message_text):
            return
        
        # Команды ИИ конфига
        if message_text.lower().startswith('.aiconfig'):
            if await handle_aiconfig_commands(event, message_text):
                return
        
        # Новые команды заглушки
        if message_text.lower().startswith('.замолчи') or message_text.lower().startswith('.говори') or message_text.lower() == '.список':
            if await handle_mute_commands_new(event, message_text):
                return
        
        if message_text.lower().startswith('.saver'):
            if await handle_saver_commands(event, message_text):
                return
        
        if message_text.lower().startswith('.anim'):
            if await handle_animation_commands(event, message_text):
                return
        
        # Команды управления ИИ в чате
        if message_text.lower() == '.aistop':
            await delete_previous_command(chat_id)
            deactivate_chat(chat_id)
            msg = await event.respond('❌ ИИ выключен в этом чате')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return
        
        if message_text.lower() == '.aiclear':
            await delete_previous_command(chat_id)
            clear_chat_history(chat_id)
            msg = await event.respond('🗑️ История очищена!')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return
        
        # Анимации
        settings = get_animation_settings(chat_id)
        if settings['mode'] and message_text.strip():
            if not message_text.startswith('.') and not message_text.lower().startswith('ai '):
                print(f'🎬 Автоанимация {settings["mode"]}')
                await run_animation(event.message, message_text, settings['mode'], settings['duration'], settings['interval'])
                return
    except Exception as e:
        print(f'❌ Ошибка исходящего: {e}')

# ============ ГЛАВНАЯ ФУНКЦИЯ ============
async def main():
    global OWNER_ID
    print('🚀 Запуск Telegram Userbot...')
    print(f'📝 Сессия: {SESSION_NAME}.session')
    
    Path(MEDIA_FOLDER).mkdir(parents=True, exist_ok=True)
    
    if not os.path.exists(f'{SESSION_NAME}.session'):
        print(f'❌ Файл сессии не найден!')
        sys.exit(1)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print('❌ Сессия не авторизована!')
            sys.exit(1)
        
        me = await client.get_me()
        OWNER_ID = me.id
        
        print(f'✅ Userbot запущен!')
        print(f'👤 Аккаунт: {me.username or me.first_name} (ID: {OWNER_ID})')
        print(f'🤖 AI: {MODEL_NAME}')
        print(f'🔗 API: {AI_API_URL}')
        print(f'\n🆕 ВОЗМОЖНОСТИ:')
        print('🤖 Авто-ответы от ИИ (включается через .aiconfig)')
        print('🎤 Обработка голосовых сообщений')
        print('📷 Анализ фотографий')
        print('⚡ Мгновенное сохранение удаленных')
        print('🎬 2 типа анимаций (rainbow, caps)')
        print('🔇 Глобальная заглушка пользователей')
        print('🗑️ Тонкая очистка по типам')
        print('📤 Автопересылка медиа в избранное')
        print('⏱️ Сохранение скоротечных медиа')
        print('⚙️ JSON конфигурация ИИ')
        print('\n📝 ОСНОВНЫЕ КОМАНДЫ:')
        print('   .aiconfig help - 🤖 Меню ИИ')
        print('   .saver help    - 📚 Меню сохранения')
        print('   .anim help     - 🎞️ Анимации')
        print('   .замолчи       - 🔇 Заглушить')
        print('   .говори <ID>   - 🔊 Разглушить')
        print('   .список        - 📋 Заглушенные')
        print('   .del           - 🗑️ Удалить меню')
        print('\n💡 ОСОБЕННОСТИ:')
        print('   • Все команды работают в избранном')
        print('   • JSON файл можно отправить для загрузки конфига')
        print('   • Заглушка работает глобально по всем чатам')
        print('   • ИИ пишет с маленькой буквы как человек')
        print('   • SSL сертификаты не проверяются')
        print('\n🎧 Слушаю...\n')
        
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
        try:
            with open(TEMP_SELECTION_FILE, 'w', encoding='utf-8') as f:
                json.dump(user_selection_state, f, default=str, ensure_ascii=False, indent=2)
        except:
            pass
    except Exception as e:
        print(f'\n❌ Критическая ошибка: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

