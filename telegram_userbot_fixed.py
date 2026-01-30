import asyncio
import json
import os
import sys
import random
import string
from datetime import datetime
from pathlib import Path

import aiohttp
from telethon import TelegramClient, events
from telethon.errors import RPCError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

# ============ КОНФИГУРАЦИЯ ============
API_ID = int(os.environ.get('API_ID', '39678712'))
API_HASH = os.environ.get('API_HASH', '3089ac53d532e75deb5dd641e4863d49')
PHONE = os.environ.get('PHONE', '+919036205120')

OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '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')
MODEL_NAME = os.environ.get('MODEL_NAME', 'google/gemini-3-flash-preview')

ACTIVATION_COMMAND = 'Ai Edem'

DB_FILE = 'messages.json'
ACTIVE_CHATS_FILE = 'active_chats.json'
DELETED_MESSAGES_DB = 'deleted_messages.json'
SAVER_CONFIG_FILE = 'saver_config.json'
MESSAGES_STORAGE_DB = 'messages_storage.json'
ANIMATION_CONFIG_FILE = 'animation_config.json'
MUTE_CONFIG_FILE = 'mute_config.json'

SESSION_NAME = 'railway_session'
MEDIA_FOLDER = 'saved_media'
OWNER_ID = None

last_command_message = {}
COMMAND_PREFIXES = ['.saver', 'ai stop', 'ai clear', 'ai edem', '.anim', '.замолчи', '.говори']

# ============ БАЗОВЫЕ ФУНКЦИИ БД ============
def load_db():
    """Загрузка основной БД сообщений для AI"""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_db(data):
    """Сохранение основной БД"""
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(data, f)
    except:
        pass

def load_animation_config():
    """Загрузка конфига анимаций"""
    if os.path.exists(ANIMATION_CONFIG_FILE):
        try:
            with open(ANIMATION_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_animation_config(config):
    """Сохранение конфига анимаций"""
    try:
        with open(ANIMATION_CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except:
        pass

def get_animation_settings(chat_id):
    """Получить настройки анимации для чата"""
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
    """Установить режим анимации"""
    config = load_animation_config()
    chat_key = str(chat_id)
    if chat_key not in config:
        config[chat_key] = {'duration': 40, 'interval': 0.5}
    config[chat_key]['mode'] = mode
    save_animation_config(config)

def load_mute_config():
    """Загрузка конфига заглушенных"""
    if os.path.exists(MUTE_CONFIG_FILE):
        try:
            with open(MUTE_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_mute_config(config):
    """Сохранение конфига заглушенных"""
    try:
        with open(MUTE_CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except:
        pass

def mute_user(chat_id, user_id, user_name):
    """Заглушить пользователя"""
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
    """Разглушить пользователя"""
    config = load_mute_config()
    chat_key = str(chat_id)
    if chat_key in config and str(user_id) in config[chat_key]:
        user_info = config[chat_key].pop(str(user_id))
        save_mute_config(config)
        return user_info
    return None

def is_user_muted(chat_id, user_id):
    """Проверить, заглушен ли пользователь"""
    config = load_mute_config()
    chat_key = str(chat_id)
    return chat_key in config and str(user_id) in config[chat_key]

def get_muted_users(chat_id):
    """Получить список заглушенных"""
    config = load_mute_config()
    chat_key = str(chat_id)
    return config.get(chat_key, {})

# ============ АНИМАЦИОННЫЕ ФУНКЦИИ ============
async def animate_typewriter(message_obj, text, duration=40, interval=0.5):
    frames_count = int(duration / interval)
    chars_per_frame = max(1, len(text) // frames_count)
    emojis = ['💬', '✍️', '📝', '⌨️']
    for i in range(0, len(text) + 1, chars_per_frame):
        current_text = text if i >= len(text) else text[:i] + '█'
        try:
            await message_obj.edit(f'{random.choice(emojis)} {current_text}')
            await asyncio.sleep(interval)
        except:
            break
    try:
        await message_obj.edit(f'✅ {text}')
    except:
        pass

async def animate_glitch(message_obj, text, duration=40, interval=0.5):
    glitch_chars = '₽₩€∑∏π∫ªº∆©®™℅℉№⁂※‽⁇⁈⁉‼‰‱⁀⁁⁂'
    frames_count = int(duration / interval)
    current = list('?' * len(text))
    for frame in range(frames_count):
        chars_to_reveal = max(1, len(text) // (frames_count - frame) if frame < frames_count - 1 else len(text))
        for _ in range(chars_to_reveal):
            wrong = [i for i, c in enumerate(current) if c != text[i] and text[i] != ' ']
            if wrong:
                idx = random.choice(wrong)
                if random.random() < 0.3 or frame > frames_count * 0.8:
                    current[idx] = text[idx]
                else:
                    current[idx] = random.choice(glitch_chars)
        for i, char in enumerate(text):
            if char == ' ':
                current[i] = ' '
        progress = int((frame / frames_count) * 10)
        bar = '█' * progress + '░' * (10 - progress)
        try:
            await message_obj.edit(f'⚡ {"".join(current)}\n[{bar}] {int((frame/frames_count)*100)}%')
            await asyncio.sleep(interval)
        except:
            break
    try:
        await message_obj.edit(f'✨ {text}')
    except:
        pass

async def animate_matrix(message_obj, text, duration=40, interval=0.5):
    blocks = ['█', '▓', '▒', '░', '']
    frames_count = int(duration / interval)
    states = [0] * len(text)
    emojis = ['💚', '💙', '💜', '🔮', '✨', '💫', '⚡', '🌟']
    for frame in range(frames_count):
        chars_to_advance = max(1, len(text) // (frames_count - frame) if frame < frames_count - 1 else len(text))
        for _ in range(chars_to_advance):
            hidden = [i for i, s in enumerate(states) if s < 4]
            if hidden:
                states[random.choice(hidden)] = min(4, states[random.choice(hidden)] + 1)
        current = []
        for i, char in enumerate(text):
            if char == ' ':
                current.append(' ')
            else:
                current.append(char if states[i] >= 4 else blocks[states[i]])
        progress = int((frame / frames_count) * 15)
        bar = '█' * progress + '▓' * min(5, 15-progress) + '░' * max(0, 15-progress-5)
        try:
            await message_obj.edit(f'{emojis[frame%len(emojis)]} {"".join(current)}\n╠{bar}╣ {int((frame/frames_count)*100)}%')
            await asyncio.sleep(interval)
        except:
            break
    try:
        await message_obj.edit(f'💎 {text}')
    except:
        pass

async def animate_wave(message_obj, text, duration=40, interval=0.5):
    frames_count = int(duration / interval)
    wave_chars = ['_', '▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
    emojis = ['🌊', '🌀', '💧', '💦']
    for frame in range(frames_count):
        current = []
        progress_ratio = frame / frames_count
        for i, char in enumerate(text):
            if char == ' ':
                current.append(' ')
            else:
                char_progress = (progress_ratio * len(text) - i) / 5
                char_progress = max(0, min(1, char_progress))
                if char_progress >= 1:
                    current.append(char)
                else:
                    current.append(wave_chars[int(char_progress * len(wave_chars))])
        progress = int(progress_ratio * 12)
        bar = '▰' * progress + '▱' * (12 - progress)
        try:
            await message_obj.edit(f'{emojis[frame%len(emojis)]} {"".join(current)}\n{bar} {int(progress_ratio*100)}%')
            await asyncio.sleep(interval)
        except:
            break
    try:
        await message_obj.edit(f'🌊 {text}')
    except:
        pass

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

async def animate_decrypt(message_obj, text, duration=40, interval=0.5):
    frames_count = int(duration / interval)
    all_chars = '!@#$%^&*()_+-=[]{}|;:,.<>?/~`0123456789'
    current = [random.choice(all_chars) if c != ' ' else ' ' for c in text]
    revealed = [False] * len(text)
    emojis = ['🔐', '🔓', '🔑', '🗝️']
    for frame in range(frames_count):
        chars_to_reveal = max(1, len(text) // (frames_count - frame) if frame < frames_count - 1 else len(text))
        for _ in range(chars_to_reveal):
            unrevealed = [i for i, r in enumerate(revealed) if not r and text[i] != ' ']
            if unrevealed:
                idx = random.choice(unrevealed)
                current[idx] = text[idx]
                revealed[idx] = True
        for i in range(len(text)):
            if not revealed[i] and text[i] != ' ':
                current[i] = random.choice(all_chars)
        progress = int((frame / frames_count) * 10)
        bar = '█' * progress + '░' * (10 - progress)
        try:
            await message_obj.edit(f'{emojis[frame%len(emojis)]} {"".join(current)}\n[{bar}] Расшифровка: {int((frame/frames_count)*100)}%')
            await asyncio.sleep(interval)
        except:
            break
    try:
        await message_obj.edit(f'🔓 {text}')
    except:
        pass

async def animate_loading(message_obj, text, duration=40, interval=0.5):
    frames_count = int(duration / interval)
    emojis = ['⏳', '⌛', '🔄', '⚙️', '🔧']
    words = text.split() or [text]
    current_text = []
    words_per_frame = max(1, len(words) // frames_count)
    for frame in range(frames_count):
        for _ in range(min(words_per_frame, len(words) - len(current_text))):
            if len(current_text) < len(words):
                current_text.append(words[len(current_text)])
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        progress = int((len(current_text) / len(words)) * 10)
        bar = '▰' * progress + '▱' * (10 - progress)
        try:
            await message_obj.edit(f'{emojis[frame%len(emojis)]} {spinner[frame%len(spinner)]} Загрузка...\n{" ".join(current_text)}\n{bar} {int((len(current_text)/len(words))*100)}%')
            await asyncio.sleep(interval)
        except:
            break
        if len(current_text) >= len(words):
            break
    try:
        await message_obj.edit(f'✅ {text}')
    except:
        pass

async def run_animation(message_obj, text, anim_type, duration=40, interval=0.5):
    animations = {
        'typewriter': animate_typewriter,
        'glitch': animate_glitch,
        'matrix': animate_matrix,
        'wave': animate_wave,
        'rainbow': animate_rainbow,
        'decrypt': animate_decrypt,
        'loading': animate_loading
    }
    if anim_type in animations:
        await animations[anim_type](message_obj, text, duration, interval)

# ============ ОСТАЛЬНЫЕ БАЗОВЫЕ ФУНКЦИИ ============
def load_active_chats():
    if os.path.exists(ACTIVE_CHATS_FILE):
        try:
            with open(ACTIVE_CHATS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_active_chats(data):
    try:
        with open(ACTIVE_CHATS_FILE, 'w') as f:
            json.dump(data, f)
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
            with open(MESSAGES_STORAGE_DB, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_messages_storage(data):
    try:
        with open(MESSAGES_STORAGE_DB, 'w') as f:
            json.dump(data, f)
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
            with open(DELETED_MESSAGES_DB, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_deleted_messages_db(data):
    try:
        with open(DELETED_MESSAGES_DB, 'w') as f:
            json.dump(data, f)
    except:
        pass

def load_saver_config():
    if os.path.exists(SAVER_CONFIG_FILE):
        try:
            with open(SAVER_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'save_private': False, 'save_groups': False, 'save_channels': [], 'save_media': True, 'save_ttl': True}

def save_saver_config(config):
    try:
        with open(SAVER_CONFIG_FILE, 'w') as f:
            json.dump(config, f)
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
    if is_command_message(message_data.get('text', '')):
        return
    db = load_deleted_messages_db()
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []
    db[chat_key].append(message_data)
    if len(db[chat_key]) > 1000:
        db[chat_key] = db[chat_key][-1000:]
    save_deleted_messages_db(db)

def get_deleted_messages(chat_id, limit=None, sender_id=None):
    db = load_deleted_messages_db()
    chat_key = str(chat_id)
    if chat_key not in db:
        return []
    messages = [msg for msg in db[chat_key] if not is_command_message(msg.get('text', ''))]
    if sender_id is not None:
        messages = [msg for msg in messages if msg.get('sender_id') == sender_id]
    if limit is not None:
        messages = messages[-limit:]
    return messages

def clear_deleted_messages(chat_id):
    db = load_deleted_messages_db()
    chat_key = str(chat_id)
    if chat_key in db:
        db[chat_key] = []
        save_deleted_messages_db(db)

async def save_media_file(message, media_folder=MEDIA_FOLDER):
    try:
        Path(media_folder).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        chat_id, msg_id = message.chat_id, message.id
        if message.photo:
            ext, mtype = 'jpg', 'photo'
        elif message.video:
            ext, mtype = 'mp4', 'video'
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

# Инициализация БД
db = load_db()

async def get_ai_response(messages):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
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
            async with session.post(OPENROUTER_API_URL, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    result = json.loads(await resp.text())
                    message = result.get('choices', [{}])[0].get('message', {})
                    content = message.get('content', '').strip() or 'Не понял'
                    return {'content': content, 'reasoning_details': message.get('reasoning_details')}
                else:
                    return {'content': f'Ошибка API ({resp.status})', 'reasoning_details': None}
    except Exception as e:
        print(f'❌ API ошибка: {e}')
        return {'content': 'Не смог сформировать ответ', 'reasoning_details': None}

def get_chat_history(chat_id, limit=10):
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []
    filtered = [msg for msg in db[chat_key] if not (msg.get('role') == 'assistant' and 'Ошибка' in msg.get('content', ''))]
    return filtered[-limit:]

def save_message(chat_id, role, content, reasoning_details=None):
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []
    if role == 'assistant' and 'Ошибка' in content:
        return
    message = {'role': role, 'content': content}
    if role == 'assistant' and reasoning_details:
        message['reasoning_details'] = reasoning_details
    db[chat_key].append(message)
    if len(db[chat_key]) > 100:
        db[chat_key] = db[chat_key][-100:]
    save_db(db)

def clear_chat_history(chat_id):
    chat_key = str(chat_id)
    if chat_key in db:
        db[chat_key] = []
        save_db(db)

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def delete_previous_command(chat_id):
    if chat_id in last_command_message:
        try:
            msg_ids = last_command_message[chat_id]
            await client.delete_messages(chat_id, msg_ids if isinstance(msg_ids, list) else [msg_ids])
        except:
            pass

async def register_command_message(chat_id, message_id):
    last_command_message[chat_id] = message_id

async def send_to_saved_messages(media_path, caption, message_data):
    try:
        full_caption = f"🗑️ **Удаленное сообщение**\n\n"
        full_caption += f"📅 Удалено: {message_data.get('deleted_at', 'н/д')}\n"
        full_caption += f"👤 От: {message_data.get('sender_name', 'Неизвестно')}\n"
        full_caption += f"💬 Чат ID: `{message_data.get('chat_id')}`\n\n"
        if caption:
            full_caption += f"📝 Текст: {caption}\n\n"
        full_caption += f"🔗 ID: {message_data.get('message_id')}"
        if media_path and os.path.exists(media_path):
            await client.send_file('me', media_path, caption=full_caption)
            return True
        return False
    except Exception as e:
        print(f'⚠️ Ошибка отправки: {e}')
        return False

# ============ ОБРАБОТЧИКИ КОМАНД ============
async def handle_saver_commands(event, message_text):
    chat_id = event.chat_id
    await delete_previous_command(chat_id)
    
    if message_text.lower() == '.saver status':
        config = load_saver_config()
        is_private, is_group = event.is_private, event.is_group
        is_saved = should_save_message(chat_id, is_private, is_group)
        status_text = f'📊 **Статус сохранения:**\n\n'
        status_text += f'📍 Текущий чат: {"✅ ВКЛ" if is_saved else "❌ ВЫКЛ"}\n'
        status_text += f'💬 Личные: {"✅" if config["save_private"] else "❌"}\n'
        status_text += f'👥 Группы: {"✅" if config["save_groups"] else "❌"}\n'
        msg = await event.respond(status_text)
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
        msgs = get_deleted_messages(chat_id, limit=10)
        if not msgs:
            msg = await event.respond('📭 Нет удаленных сообщений')
        else:
            response = f'🗑️ **Последние {len(msgs)} удаленных:**\n\n'
            for i, m in enumerate(msgs, 1):
                response += f'{i}. [{m.get("deleted_at", "")[:16]}] {m.get("sender_name", "")}: {m.get("text", "")[:50]}\n'
            msg = await event.respond(response)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.saver clear':
        clear_deleted_messages(chat_id)
        msg = await event.respond('🗑️ Очищено!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.saver help':
        help_text = '''📚 **Команды .saver:**
• `.saver status` - статус
• `.saver private on/off` - личные чаты
• `.saver groups on/off` - группы
• `.saver add/remove` - текущий чат
• `.saver show` - последние 10
• `.saver clear` - очистить
• `.saver help` - справка'''
        msg = await event.respond(help_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    return False

async def handle_animation_commands(event, message_text):
    chat_id = event.chat_id
    await delete_previous_command(chat_id)
    
    if message_text.lower() == '.anim help':
        help_text = '''🎬 **Команды анимаций:**

**Разовая анимация:**
• `.anim typewriter текст` - печатная машинка ⌨️
• `.anim glitch текст` - глитч ⚡
• `.anim matrix текст` - матрица 💚
• `.anim wave текст` - волна 🌊
• `.anim rainbow текст` - радуга 🌈
• `.anim decrypt текст` - расшифровка 🔐
• `.anim loading текст` - загрузка ⏳

**Режим:**
• `.anim mode <тип>` - включить
• `.anim mode off` - выключить

**Настройки:**
• `.anim duration <сек>` - длительность
• `.anim interval <сек>` - интервал
• `.anim settings` - показать настройки
• `.anim status` - статус

Пример: `.anim typewriter Привет!`'''
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
    
    if message_text.lower() == '.anim settings':
        settings = get_animation_settings(chat_id)
        msg = await event.respond(
            f'⚙️ **Настройки:**\n'
            f'⏱️ Длительность: {settings["duration"]} сек\n'
            f'⏲️ Интервал: {settings["interval"]} сек\n'
            f'🎬 Режим: {settings["mode"] or "ВЫКЛ"}'
        )
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.anim duration '):
        try:
            duration = float(message_text.split()[2])
            if 5 <= duration <= 120:
                config = load_animation_config()
                chat_key = str(chat_id)
                if chat_key not in config:
                    config[chat_key] = {'mode': None, 'interval': 0.5}
                config[chat_key]['duration'] = duration
                save_animation_config(config)
                msg = await event.respond(f'✅ Длительность: {duration} сек')
            else:
                msg = await event.respond('❌ От 5 до 120 секунд')
        except:
            msg = await event.respond('❌ Неверный формат')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.anim interval '):
        try:
            interval = float(message_text.split()[2])
            if 0.1 <= interval <= 5:
                config = load_animation_config()
                chat_key = str(chat_id)
                if chat_key not in config:
                    config[chat_key] = {'mode': None, 'duration': 40}
                config[chat_key]['interval'] = interval
                save_animation_config(config)
                msg = await event.respond(f'✅ Интервал: {interval} сек')
            else:
                msg = await event.respond('❌ От 0.1 до 5 секунд')
        except:
            msg = await event.respond('❌ Неверный формат')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.anim mode '):
        mode = message_text.split(maxsplit=2)[2].lower()
        if mode == 'off':
            set_animation_mode(chat_id, None)
            msg = await event.respond('❌ Режим ВЫКЛЮЧЕН')
        elif mode in ['typewriter', 'glitch', 'matrix', 'wave', 'rainbow', 'decrypt', 'loading']:
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
            if anim_type in ['typewriter', 'glitch', 'matrix', 'wave', 'rainbow', 'decrypt', 'loading']:
                await event.delete()
                settings = get_animation_settings(chat_id)
                animation_msg = await event.respond('🎬 Запуск...')
                await run_animation(animation_msg, text, anim_type, settings['duration'], settings['interval'])
                return True
    
    return False

async def handle_mute_commands(event, message_text):
    chat_id = event.chat_id
    await delete_previous_command(chat_id)
    
    if message_text.lower() == '.замолчи':
        if not event.reply_to_msg_id:
            msg = await event.respond('❌ Ответьте на сообщение пользователя!')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        try:
            reply_msg = await event.get_reply_message()
            user_id = reply_msg.sender_id
            sender = await reply_msg.get_sender()
            user_name = getattr(sender, 'first_name', 'Неизвестно')
            if hasattr(sender, 'username') and sender.username:
                user_name += f' (@{sender.username})'
            mute_user(chat_id, user_id, user_name)
            msg = await event.respond(f'🔇 **{user_name}** заглушен!\n\nВсе его сообщения будут удалены.\nРазглушить: `.говори`')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        except Exception as e:
            msg = await event.respond(f'❌ Ошибка: {e}')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
    
    if message_text.lower() == '.говори':
        if not event.reply_to_msg_id:
            msg = await event.respond('❌ Ответьте на сообщение пользователя!')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        try:
            reply_msg = await event.get_reply_message()
            user_id = reply_msg.sender_id
            user_info = unmute_user(chat_id, user_id)
            if user_info:
                msg = await event.respond(f'🔊 **{user_info.get("user_name")}** разглушен!')
            else:
                msg = await event.respond('⚠️ Не был заглушен!')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        except Exception as e:
            msg = await event.respond(f'❌ Ошибка: {e}')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
    
    if message_text.lower() == '.замолчи список':
        muted = get_muted_users(chat_id)
        if not muted:
            msg = await event.respond('📭 Нет заглушенных')
        else:
            list_text = f'🔇 **Заглушенные ({len(muted)}):**\n\n'
            for uid, info in muted.items():
                list_text += f'• {info.get("user_name", "?")} (ID: `{uid}`)\n'
            msg = await event.respond(list_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    return False

# ============ ОБРАБОТЧИКИ СОБЫТИЙ ============
@client.on(events.NewMessage(incoming=True, from_users=None))
async def immediate_save_handler(event):
    try:
        chat_id, message_id, sender_id = event.chat_id, event.message.id, event.sender_id
        
        if OWNER_ID and sender_id == OWNER_ID:
            return
        
        if is_user_muted(chat_id, sender_id):
            print(f'🔇 Заглушенный {sender_id} - удаляем MSG {message_id}')
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
            'is_ttl': bool(event.message.ttl_period),
            'media_path': None
        }
        
        config = load_saver_config()
        if config['save_media'] and (event.message.photo or event.message.video or event.message.document):
            message_data['media_path'] = await save_media_file(event.message)
        
        store_message_immediately(chat_id, message_data)
    except Exception as e:
        print(f'❌ Ошибка сохранения: {e}')

@client.on(events.MessageDeleted)
async def deleted_message_handler(event):
    try:
        chat_id, deleted_ids = event.chat_id, event.deleted_ids
        print(f'🗑️ Удалено {len(deleted_ids)} сообщений')
        for message_id in deleted_ids:
            message_data = get_stored_message(chat_id, message_id)
            if message_data:
                real_chat_id = message_data.get('chat_id')
                message_data['deleted_at'] = datetime.now().isoformat()
                add_deleted_message(real_chat_id, message_data)
                if message_data.get('media_path') and os.path.exists(message_data['media_path']):
                    await send_to_saved_messages(message_data['media_path'], message_data.get('text', ''), message_data)
    except Exception as e:
        print(f'❌ Ошибка обработки удаленного: {e}')

@client.on(events.NewMessage(incoming=True))
async def incoming_handler(event):
    try:
        chat_id = event.chat_id
        if not is_chat_active(chat_id):
            return
        message_text = event.message.message or 'сообщение без текста'
        save_message(chat_id, 'user', message_text)
        history = get_chat_history(chat_id)
        system_message = {
            'role': 'system',
            'content': 'Ты дружелюбный помощник. Отвечай кратко на языке пользователя.'
        }
        response = await get_ai_response([system_message] + history)
        content = response.get('content', 'Не смог ответить')
        if content and not content.startswith('Ошибка'):
            save_message(chat_id, 'assistant', content, response.get('reasoning_details'))
        await event.respond(content)
    except RPCError as e:
        if 'TOPIC_CLOSED' in str(e) or 'CHAT_WRITE_FORBIDDEN' in str(e):
            deactivate_chat(chat_id)
    except Exception as e:
        print(f'❌ Ошибка входящего: {e}')

@client.on(events.NewMessage(outgoing=True))
async def outgoing_handler(event):
    try:
        chat_id = event.chat_id
        message_text = event.message.message or ''
        
        if message_text.lower().startswith('.saver'):
            if await handle_saver_commands(event, message_text):
                return
        
        if message_text.lower().startswith('.anim'):
            if await handle_animation_commands(event, message_text):
                return
        
        if message_text.lower().startswith('.замолчи') or message_text.lower().startswith('.говори'):
            if await handle_mute_commands(event, message_text):
                return
        
        if ACTIVATION_COMMAND.lower() in message_text.lower():
            await delete_previous_command(chat_id)
            activate_chat(chat_id)
            msg = await event.respond('✅ AI активирован!\n\nКоманды:\n• "Ai Stop" - выключить\n• "Ai Clear" - очистить')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return
        
        if 'ai stop' in message_text.lower():
            await delete_previous_command(chat_id)
            deactivate_chat(chat_id)
            msg = await event.respond('❌ AI выключен')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return
        
        if 'ai clear' in message_text.lower():
            if is_chat_active(chat_id):
                await delete_previous_command(chat_id)
                clear_chat_history(chat_id)
                msg = await event.respond('🗑️ История очищена!')
                await event.delete()
                await register_command_message(chat_id, msg.id)
            return
        
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
        print(f'\n🆕 ВОЗМОЖНОСТИ:')
        print('⚡ Мгновенное сохранение удаленных')
        print('🎬 7 типов анимаций (typewriter, glitch, matrix, wave, rainbow, decrypt, loading)')
        print('⏱️ Настройка длительности и интервала')
        print('🔇 Команды .замолчи/.говори для автоудаления')
        print('\n📝 Команды:')
        print('   .saver help - управление сохранением')
        print('   .anim help - управление анимациями')
        print('   .замолчи - заглушить пользователя (ответом)')
        print('   .говори - разглушить (ответом)')
        print('   .замолчи список - список заглушенных')
        print('\n🎧 Слушаю...\n')
        
        await client.run_until_disconnected()
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        sys.exit(1)

# ============ ЗАПУСК ============
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n👋 Userbot остановлен')
    except Exception as e:
        print(f'\n❌ Критическая ошибка: {e}')
        sys.exit(1)
