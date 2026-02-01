import asyncio
import json
import os
import sys
import base64
from datetime import datetime, timedelta
from pathlib import Path
import aiohttp
from telethon import TelegramClient, events
from telethon.errors import RPCError

# ============ КОНФИГУРАЦИЯ ============
API_ID = int(os.environ.get('API_ID', '39678712'))
API_HASH = os.environ.get('API_HASH', '3089ac53d532e75deb5dd641e4863d49')
PHONE = os.environ.get('PHONE', '+919036205120')

ONLYSQ_API_URL = os.environ.get('ONLYSQ_API_URL', 'https://api.onlysq.ru/v1/chat/completions')
ONLYSQ_API_KEY = os.environ.get('ONLYSQ_API_KEY', '')
MODEL_NAME = 'gemini-3-flash'

DB_FILE = 'messages.json'
DELETED_MESSAGES_DB = 'deleted_messages.json'
SAVER_CONFIG_FILE = 'saver_config.json'
MESSAGES_STORAGE_DB = 'messages_storage.json'
ANIMATION_CONFIG_FILE = 'animation_config.json'
MUTE_CONFIG_FILE = 'mute_config.json'
AI_CONFIG_FILE = 'ai_config.json'
AI_CHATS_CONFIG_FILE = 'ai_chats_config.json'

SESSION_NAME = 'railway_session'
MEDIA_FOLDER = 'saved_media'
OWNER_ID = None

last_command_message = {}
COMMAND_PREFIXES = ['.saver', '.deleted', '.anim', '.замолчи', '.говори', '.del', '.ии', '.конфиг']

user_selection_state = {}
db = {}

# ============ БАЗОВЫЕ ФУНКЦИИ БД ============
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

# ============ AI КОНФИГУРАЦИЯ ============
def load_ai_config():
    if os.path.exists(AI_CONFIG_FILE):
        try:
            with open(AI_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        'system_prompt': 'ты дружелюбный помощник. отвечай естественно, как обычный человек в переписке. используй строчные буквы, без формальностей. будь кратким и по делу.',
        'temperature': 0.8,
        'max_tokens': 1024,
        'style': 'дружелюбный',
        'description': 'Стандартная конфигурация'
    }

def save_ai_config(config):
    try:
        with open(AI_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except:
        pass

def load_ai_chats_config():
    if os.path.exists(AI_CHATS_CONFIG_FILE):
        try:
            with open(AI_CHATS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        'enabled_chats': [],
        'global_mode': False,
        'private_only': False,
        'groups_only': False,
    }

def save_ai_chats_config(config):
    try:
        with open(AI_CHATS_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except:
        pass

def should_ai_respond(chat_id, is_private, is_group):
    config = load_ai_chats_config()
    
    if config['global_mode']:
        return True
    
    if config['private_only'] and is_private:
        return True
    
    if config['groups_only'] and is_group:
        return True
    
    if str(chat_id) in config['enabled_chats']:
        return True
    
    return False


# ============ MUTE ФУНКЦИИ ============
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

def mute_user_by_id(user_id, user_name="Неизвестно"):
    config = load_mute_config()
    if 'global' not in config:
        config['global'] = {}
    config['global'][str(user_id)] = {
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

def unmute_user_by_id(user_id):
    config = load_mute_config()
    if 'global' in config and str(user_id) in config['global']:
        user_info = config['global'].pop(str(user_id))
        save_mute_config(config)
        return user_info
    return None

def is_user_muted(chat_id, user_id):
    config = load_mute_config()
    if 'global' in config and str(user_id) in config['global']:
        return True
    chat_key = str(chat_id)
    return chat_key in config and str(user_id) in config[chat_key]

def get_all_muted_users():
    config = load_mute_config()
    all_muted = {}
    
    if 'global' in config:
        for uid, info in config['global'].items():
            all_muted[uid] = {**info, 'scope': 'глобально'}
    
    for chat_id, users in config.items():
        if chat_id == 'global':
            continue
        for uid, info in users.items():
            if uid not in all_muted:
                all_muted[uid] = {**info, 'scope': f'чат {chat_id}'}
    
    return all_muted

# ============ АНИМАЦИОННЫЕ ФУНКЦИИ ============
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


# ============ SAVER ФУНКЦИИ ============
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
    
    db_del = load_deleted_messages_db()
    chat_key = str(chat_id)
    if chat_key not in db_del:
        db_del[chat_key] = []
    db_del[chat_key].append(message_data)
    if len(db_del[chat_key]) > 1000:
        db_del[chat_key] = db_del[chat_key][-1000:]
    save_deleted_messages_db(db_del)

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

async def forward_to_saved(media_path, caption_text=""):
    try:
        if not media_path or not os.path.exists(media_path):
            print(f'⚠️ Файл не найден: {media_path}')
            return False
        
        await client.send_file(
            'me',
            media_path,
            caption=caption_text
        )
        print(f'📤 Переслано в избранное: {os.path.basename(media_path)}')
        return True
    except Exception as e:
        print(f'⚠️ Ошибка пересылки: {e}')
        return False

# ============ ИИ ФУНКЦИИ ============
async def file_to_base64(filepath):
    try:
        with open(filepath, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f'❌ Ошибка конвертации в base64: {e}')
        return None

async def get_ai_response(messages, include_voice=None, include_image=None):
    try:
        config = load_ai_config()
        
        full_messages = [
            {'role': 'system', 'content': config.get('system_prompt', 'ты помощник')}
        ] + messages
        
        if include_voice or include_image:
            last_msg = full_messages[-1]
            content_parts = []
            
            if last_msg.get('content'):
                content_parts.append({
                    'type': 'text',
                    'text': last_msg['content']
                })
            
            if include_image:
                image_b64 = await file_to_base64(include_image)
                if image_b64:
                    ext = include_image.split('.')[-1].lower()
                    mime_map = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_map.get(ext, 'image/jpeg')
                    
                    content_parts.append({
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:{mime_type};base64,{image_b64}'
                        }
                    })
            
            if include_voice:
                audio_b64 = await file_to_base64(include_voice)
                if audio_b64:
                    content_parts.append({
                        'type': 'input_audio',
                        'input_audio': {
                            'data': audio_b64,
                            'format': 'ogg'
                        }
                    })
            
            if content_parts:
                full_messages[-1]['content'] = content_parts
        
        ssl_context = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(connector=ssl_context, timeout=aiohttp.ClientTimeout(total=120)) as session:
            payload = {
                'model': MODEL_NAME,
                'messages': full_messages,
                'temperature': config.get('temperature', 0.8),
                'max_tokens': config.get('max_tokens', 1024),
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            if ONLYSQ_API_KEY:
                headers['Authorization'] = f'Bearer {ONLYSQ_API_KEY}'
            
            async with session.post(ONLYSQ_API_URL, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    result = json.loads(await resp.text())
                    message = result.get('choices', [{}])[0].get('message', {})
                    content = message.get('content', '').strip()
                    
                    if not content:
                        content = 'хм...'
                    
                    return {'content': content}
                else:
                    error_text = await resp.text()
                    print(f'❌ API ошибка {resp.status}: {error_text}')
                    return {'content': 'не могу ответить сейчас...'}
    except Exception as e:
        print(f'❌ Ошибка API: {e}')
        import traceback
        traceback.print_exc()
        return {'content': 'что-то пошло не так...'}

def get_chat_history(chat_id, limit=10):
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []
    filtered = [msg for msg in db[chat_key] if not (msg.get('role') == 'assistant' and 'ошибка' in msg.get('content', '').lower())]
    return filtered[-limit:]

def save_message(chat_id, role, content):
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []
    if role == 'assistant' and 'ошибка' in content.lower():
        return
    message = {'role': role, 'content': content}
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


# ============ ОБРАБОТЧИКИ КОМАНД ============

async def handle_ai_config_commands(event, message_text):
    chat_id = event.chat_id
    await delete_previous_command(chat_id)
    
    if message_text.lower() in ['.конфиг', '.конфиг помощь']:
        help_text = '''⚙️ **НАСТРОЙКА ЛИЧНОСТИ ИИ**

📋 **ПРОСМОТР:**
• `.конфиг показать` - текущая
• `.конфиг список` - все сохраненные

📝 **ЗАГРУЗКА:**
• `.конфиг загрузить` (ответ на JSON)

🗑️ **УПРАВЛЕНИЕ:**
• `.конфиг сброс` - стандартная
• `.конфиг удалить` - удалить

**Пример JSON:**
```json
{
  "system_prompt": "ты саркастичный бот",
  "temperature": 0.9,
  "max_tokens": 2048,
  "style": "саркастичный",
  "description": "Саркастичный стиль"
}
```'''
        msg = await event.respond(help_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.конфиг показать':
        config = load_ai_config()
        text = f'''⚙️ **ТЕКУЩАЯ КОНФИГУРАЦИЯ:**

🎭 Стиль: **{config.get("style", "стандартный")}**
📝 {config.get("description", "—")}

🌡️ Temperature: `{config.get("temperature", 0.8)}`
📏 Max tokens: `{config.get("max_tokens", 1024)}`

💬 **Системный промпт:**
```
{config.get("system_prompt", "—")[:200]}...
```'''
        msg = await event.respond(text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.конфиг сброс':
        default_config = {
            'system_prompt': 'ты дружелюбный помощник. отвечай естественно, как обычный человек в переписке. используй строчные буквы, без формальностей. будь кратким и по делу.',
            'temperature': 0.8,
            'max_tokens': 1024,
            'style': 'дружелюбный',
            'description': 'Стандартная конфигурация'
        }
        save_ai_config(default_config)
        msg = await event.respond('✅ Конфигурация сброшена!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.конфиг удалить':
        if os.path.exists(AI_CONFIG_FILE):
            os.remove(AI_CONFIG_FILE)
            msg = await event.respond('🗑️ Конфигурация удалена!')
        else:
            msg = await event.respond('⚠️ Уже удалена')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.конфиг загрузить':
        if not event.reply_to_msg_id:
            msg = await event.respond('❌ Ответьте на JSON файл!')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        
        try:
            reply_msg = await event.get_reply_message()
            if reply_msg.document:
                file_path = await reply_msg.download_media(file=MEDIA_FOLDER)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    new_config = json.load(f)
                
                required_fields = ['system_prompt', 'temperature', 'max_tokens']
                for field in required_fields:
                    if field not in new_config:
                        msg = await event.respond(f'❌ Нет поля: {field}')
                        await event.delete()
                        await register_command_message(chat_id, msg.id)
                        os.remove(file_path)
                        return True
                
                save_ai_config(new_config)
                
                style = new_config.get('style', 'custom')
                desc = new_config.get('description', '—')
                msg = await event.respond(f'✅ Загружено!\n\n🎭 **{style}**\n📝 {desc}')
                
                os.remove(file_path)
            else:
                msg = await event.respond('❌ Нужен JSON файл!')
                
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        except json.JSONDecodeError:
            msg = await event.respond('❌ Неверный JSON!')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        except Exception as e:
            msg = await event.respond(f'❌ Ошибка: {e}')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
    
    return False

async def handle_ai_chats_commands(event, message_text):
    chat_id = event.chat_id
    await delete_previous_command(chat_id)
    
    if message_text.lower() in ['.ии', '.ии помощь']:
        help_text = '''🤖 **УПРАВЛЕНИЕ ИИ**

📊 **СТАТУС:**
• `.ии статус` - настройки

🌍 **РЕЖИМЫ:**
• `.ии везде вкл/выкл` - глобально
• `.ии личные вкл/выкл` - только ЛС
• `.ии группы вкл/выкл` - только группы

💬 **ЭТОТ ЧАТ:**
• `.ии вкл/выкл` - здесь

📋 **ДРУГОЕ:**
• `.ии список` - активные чаты
• `.ии очистить` - история
• `.ии очистить все` - вся история

⚙️ `.конфиг` - личность ИИ'''
        msg = await event.respond(help_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.ии статус':
        config = load_ai_chats_config()
        ai_config = load_ai_config()
        is_private, is_group = event.is_private, event.is_group
        is_active = should_ai_respond(chat_id, is_private, is_group)
        
        text = f'''📊 **СТАТУС ИИ:**

💬 Этот чат: {"✅ ВКЛ" if is_active else "❌ ВЫКЛ"}

🌍 **РЕЖИМЫ:**
• Везде: {"✅" if config["global_mode"] else "❌"}
• Личные: {"✅" if config["private_only"] else "❌"}
• Группы: {"✅" if config["groups_only"] else "❌"}

📋 Активных: {len(config["enabled_chats"])}

🎭 **ЛИЧНОСТЬ:**
**{ai_config.get("style", "стандартный")}**'''
        msg = await event.respond(text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.ии везде вкл', '.ии везде выкл']:
        config = load_ai_chats_config()
        config['global_mode'] = 'вкл' in message_text
        save_ai_chats_config(config)
        msg = await event.respond(f'{"🌍 ВКЛ" if config["global_mode"] else "❌ ВЫКЛ"}')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.ии личные вкл', '.ии личные выкл']:
        config = load_ai_chats_config()
        config['private_only'] = 'вкл' in message_text
        if config['private_only']:
            config['groups_only'] = False
        save_ai_chats_config(config)
        msg = await event.respond(f'{"✅ Только ЛС" if config["private_only"] else "❌ ВЫКЛ"}')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() in ['.ии группы вкл', '.ии группы выкл']:
        config = load_ai_chats_config()
        config['groups_only'] = 'вкл' in message_text
        if config['groups_only']:
            config['private_only'] = False
        save_ai_chats_config(config)
        msg = await event.respond(f'{"✅ Только группы" if config["groups_only"] else "❌ ВЫКЛ"}')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.ии вкл':
        config = load_ai_chats_config()
        chat_id_str = str(chat_id)
        if chat_id_str not in config['enabled_chats']:
            config['enabled_chats'].append(chat_id_str)
            save_ai_chats_config(config)
            msg = await event.respond('✅ ИИ ВКЛ!')
        else:
            msg = await event.respond('⚠️ Уже ВКЛ!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.ии выкл':
        config = load_ai_chats_config()
        chat_id_str = str(chat_id)
        if chat_id_str in config['enabled_chats']:
            config['enabled_chats'].remove(chat_id_str)
            save_ai_chats_config(config)
            msg = await event.respond('❌ ИИ ВЫКЛ!')
        else:
            msg = await event.respond('⚠️ Уже ВЫКЛ!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.ии список':
        config = load_ai_chats_config()
        if not config['enabled_chats']:
            text = '📭 Нет активных'
        else:
            text = f'📋 **Активные ({len(config["enabled_chats"])}):**\n\n'
            for cid in config['enabled_chats']:
                text += f'• `{cid}`\n'
        msg = await event.respond(text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.ии очистить':
        clear_chat_history(chat_id)
        msg = await event.respond('🗑️ История очищена!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.ии очистить все':
        global db
        db = {}
        save_db(db)
        msg = await event.respond('🗑️ Вся история очищена!')
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    return False


async def handle_mute_commands(event, message_text):
    chat_id = event.chat_id
    await delete_previous_command(chat_id)
    
    if message_text.lower() in ['.замолчи', '.замолчи помощь']:
        help_text = '''🔇 **ЗАГЛУШКА**

**ЗАГЛУШИТЬ:**
• `.замолчи` (ответ)
• `.замолчи @username`
• `.замолчи <ID>`

**РАЗГЛУШИТЬ:**
• `.говори` (ответ)
• `.говори @username`
• `.говори <ID>`
• `.говори <номер>` (из списка)

**ПРОСМОТР:**
• `.замолчи список`

💡 *Заглушенные:*
• Сообщения удаляются автоматически
• Не сохраняются
• ИИ игнорирует'''
        msg = await event.respond(help_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.замолчи список':
        all_muted = get_all_muted_users()
        if not all_muted:
            msg = await event.respond('📭 Нет заглушенных')
        else:
            text = f'🔇 **Заглушенные ({len(all_muted)}):**\n\n'
            for i, (uid, info) in enumerate(all_muted.items(), 1):
                scope = info.get('scope', '?')
                name = info.get('user_name', 'Неизвестно')
                text += f'{i}. {name}\n'
                text += f'   ID: `{uid}` | {scope}\n\n'
            text += '\n🔊 `.говори <номер>`'
            msg = await event.respond(text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.замолчи' and event.reply_to_msg_id:
        try:
            reply_msg = await event.get_reply_message()
            user_id = reply_msg.sender_id
            sender = await reply_msg.get_sender()
            user_name = getattr(sender, 'first_name', 'Неизвестно')
            if hasattr(sender, 'username') and sender.username:
                user_name += f' (@{sender.username})'
            
            mute_user(chat_id, user_id, user_name)
            msg = await event.respond(f'🔇 **{user_name}** заглушен!\n\n💡 Сообщения удаляются\n`.говори` - разглушить')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        except Exception as e:
            msg = await event.respond(f'❌ Ошибка: {e}')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
    
    if message_text.lower().startswith('.замолчи '):
        parts = message_text.split(maxsplit=1)
        if len(parts) < 2:
            return False
        
        target = parts[1].strip()
        
        if target.isdigit():
            user_id = int(target)
            user_name = f"ID: {user_id}"
            mute_user_by_id(user_id, user_name)
            msg = await event.respond(f'🔇 `{user_id}` заглушен глобально!')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
        
        if target.startswith('@'):
            try:
                username = target[1:]
                user = await client.get_entity(username)
                user_id = user.id
                user_name = getattr(user, 'first_name', 'Неизвестно')
                if hasattr(user, 'username') and user.username:
                    user_name += f' (@{user.username})'
                
                mute_user_by_id(user_id, user_name)
                msg = await event.respond(f'🔇 **{user_name}** заглушен глобально!')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            except Exception as e:
                msg = await event.respond(f'❌ Не найден: {e}')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
    
    if message_text.lower().startswith('.говори'):
        if event.reply_to_msg_id and message_text.lower() == '.говори':
            try:
                reply_msg = await event.get_reply_message()
                user_id = reply_msg.sender_id
                
                user_info = unmute_user_by_id(user_id)
                if not user_info:
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
        
        parts = message_text.split(maxsplit=1)
        if len(parts) >= 2:
            target = parts[1].strip()
            
            if target.isdigit():
                try:
                    index = int(target) - 1
                    all_muted = get_all_muted_users()
                    muted_list = list(all_muted.items())
                    
                    if 0 <= index < len(muted_list):
                        user_id = muted_list[index][0]
                        user_info = muted_list[index][1]
                        
                        unmute_user_by_id(int(user_id))
                        msg = await event.respond(f'🔊 **{user_info.get("user_name")}** разглушен!')
                    else:
                        msg = await event.respond('❌ Неверный номер')
                    
                    await event.delete()
                    await register_command_message(chat_id, msg.id)
                    return True
                except:
                    pass
            
            if target.isdigit():
                user_id = int(target)
                user_info = unmute_user_by_id(user_id)
                if user_info:
                    msg = await event.respond(f'🔊 `{user_id}` разглушен!')
                else:
                    msg = await event.respond('⚠️ Не был заглушен!')
                await event.delete()
                await register_command_message(chat_id, msg.id)
                return True
            
            if target.startswith('@'):
                try:
                    username = target[1:]
                    user = await client.get_entity(username)
                    user_id = user.id
                    
                    user_info = unmute_user_by_id(user_id)
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
    
    return False

async def handle_animation_commands(event, message_text):
    chat_id = event.chat_id
    await delete_previous_command(chat_id)
    
    if message_text.lower() == '.anim help':
        help_text = '''🎬 **АНИМАЦИИ**

**ТИПЫ:**
• rainbow 🌈
• caps 🔤

**ИСПОЛЬЗОВАНИЕ:**
`.anim <тип> текст`

**НАСТРОЙКИ:**
• `.anim mode <тип>` - авто
• `.anim mode off` - выкл
• `.anim status` - статус'''
        msg = await event.respond(help_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower() == '.anim status':
        settings = get_animation_settings(chat_id)
        mode = settings['mode']
        status_text = f'''🎬 **Статус:**

Режим: **{mode.upper() if mode else "ВЫКЛ"}**
⏱️ {settings["duration"]} сек
⏲️ {settings["interval"]} сек'''
        msg = await event.respond(status_text)
        await event.delete()
        await register_command_message(chat_id, msg.id)
        return True
    
    if message_text.lower().startswith('.anim mode '):
        parts = message_text.split(maxsplit=2)
        if len(parts) < 3:
            msg = await event.respond('❌ `.anim mode <тип>`')
            await event.delete()
            await register_command_message(chat_id, msg.id)
            return True
            
        mode = parts[2].lower()
        if mode == 'off':
            set_animation_mode(chat_id, None)
            msg = await event.respond('❌ ВЫКЛ')
        elif mode in ['rainbow', 'caps']:
            set_animation_mode(chat_id, mode)
            msg = await event.respond(f'✅ **{mode.upper()}**')
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
    try:
        chat_id, message_id, sender_id = event.chat_id, event.message.id, event.sender_id
        
        if OWNER_ID and sender_id == OWNER_ID:
            return
        
        # Удаляем сообщения заглушенных пользователей
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
        
        # Проверка на скоротечное медиа
        is_ttl_media = False
        if hasattr(event.message, 'media'):
            if hasattr(event.message.media, 'photo') and event.message.media.photo:
                if hasattr(event.message.media, 'ttl_seconds') and event.message.media.ttl_seconds:
                    is_ttl_media = True
                    print(f'⏱️ Скоротечное ФОТО! TTL: {event.message.media.ttl_seconds}с')
            elif hasattr(event.message.media, 'document') and event.message.media.document:
                if hasattr(event.message.media, 'ttl_seconds') and event.message.media.ttl_seconds:
                    is_ttl_media = True
                    print(f'⏱️ Скоротечное ВИДЕО! TTL: {event.message.media.ttl_seconds}с')
        
        config = load_saver_config()
        
        save_this_media = config.get('save_media', True)
        if is_ttl_media and config.get('save_ttl_media', False):
            save_this_media = True
            print(f'💾 Сохраняем скоротечное медиа')
        
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
                    caption_prefix = "⏱️ Скоротечное"
                
                if should_forward and media_path:
                    sender_name = message_data.get('sender_name', 'Неизвестно')
                    msg_text = message_data.get('text', '')
                    full_caption = f"{caption_prefix}\n👤 {sender_name}\n🗑️ {message_data.get('deleted_at', '')[:16]}"
                    if msg_text:
                        full_caption += f"\n📝 {msg_text[:100]}"
                    
                    print(f'📤 Пересылаем: {media_path}')
                    await forward_to_saved(media_path, full_caption)
                
                add_deleted_message(real_chat_id, message_data)
    except Exception as e:
        print(f'❌ Ошибка обработки удаленного: {e}')
        import traceback
        traceback.print_exc()

@client.on(events.NewMessage(incoming=True))
async def incoming_ai_handler(event):
    try:
        chat_id = event.chat_id
        is_private, is_group = event.is_private, event.is_group
        
        # Проверяем, должен ли ИИ отвечать
        if not should_ai_respond(chat_id, is_private, is_group):
            return
        
        # Игнорируем заглушенных
        sender_id = event.sender_id
        if is_user_muted(chat_id, sender_id):
            return
        
        # Игнорируем команды
        message_text = event.message.message or ''
        if is_command_message(message_text):
            return
        
        # Если нет текста и нет медиа - пропускаем
        if not message_text and not event.message.photo and not event.message.voice:
            return
        
        # Обрабатываем голосовое
        voice_path = None
        if event.message.voice:
            print('🎤 Получено голосовое')
            voice_path = await save_media_file(event.message)
        
        # Обрабатываем фото
        image_path = None
        if event.message.photo:
            print('🖼️ Получено фото')
            image_path = await save_media_file(event.message)
        
        # Сохраняем сообщение пользователя
        save_message(chat_id, 'user', message_text or '[медиа]')
        
        # Получаем историю
        history = get_chat_history(chat_id)
        
        # Получаем ответ ИИ
        response = await get_ai_response(history, include_voice=voice_path, include_image=image_path)
        content = response.get('content', 'не могу ответить...')
        
        if content and 'ошибка' not in content.lower():
            save_message(chat_id, 'assistant', content)
        
        # Отправляем ответ
        await event.respond(content)
        
    except RPCError as e:
        if 'TOPIC_CLOSED' in str(e) or 'CHAT_WRITE_FORBIDDEN' in str(e):
            print(f'⚠️ Чат закрыт: {chat_id}')
    except Exception as e:
        print(f'❌ Ошибка входящего: {e}')
        import traceback
        traceback.print_exc()

@client.on(events.NewMessage(outgoing=True))
async def outgoing_handler(event):
    try:
        chat_id = event.chat_id
        message_text = event.message.message or ''
        
        # Удаление последнего меню
        if message_text.lower() == '.del':
            await delete_previous_command(chat_id)
            await event.delete()
            return
        
        # Обработка команд
        if message_text.lower().startswith('.конфиг'):
            if await handle_ai_config_commands(event, message_text):
                return
        
        if message_text.lower().startswith('.ии'):
            if await handle_ai_chats_commands(event, message_text):
                return
        
        if message_text.lower().startswith('.замолчи') or message_text.lower().startswith('.говори'):
            if await handle_mute_commands(event, message_text):
                return
        
        if message_text.lower().startswith('.anim'):
            if await handle_animation_commands(event, message_text):
                return
        
        # Автоанимация
        settings = get_animation_settings(chat_id)
        if settings['mode'] and message_text.strip():
            if not message_text.startswith('.') and not is_command_message(message_text):
                print(f'🎬 Автоанимация {settings["mode"]}')
                await run_animation(event.message, message_text, settings['mode'], settings['duration'], settings['interval'])
                return
                
    except Exception as e:
        print(f'❌ Ошибка исходящего: {e}')
        import traceback
        traceback.print_exc()

# ============ ГЛАВНАЯ ФУНКЦИЯ ============
async def main():
    global OWNER_ID, db
    print('🚀 Запуск Telegram AI Userbot...')
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
        
        # Загружаем БД
        db = load_db()
        
        print(f'✅ Userbot запущен!')
        print(f'👤 Аккаунт: {me.username or me.first_name} (ID: {OWNER_ID})')
        print(f'🤖 AI: {MODEL_NAME} @ {ONLYSQ_API_URL}')
        print(f'\n🆕 НОВЫЕ ВОЗМОЖНОСТИ:')
        print('✅ ИИ отвечает как человек (с маленькой буквы)')
        print('🎤 Поддержка голосовых сообщений')
        print('🖼️ Поддержка изображений')
        print('⚙️ Настройка личности через JSON')
        print('🔇 Улучшенная заглушка (ID, @username, глобально)')
        print('⚡ Мгновенное сохранение удаленных')
        print('📤 Автопересылка медиа в избранное')
        print('⏱️ Сохранение скоротечных медиа')
        print('🔓 Без SSL verification')
        print('\n📝 ОСНОВНЫЕ КОМАНДЫ:')
        print('   .ии          - управление ИИ')
        print('   .конфиг      - настройка личности')
        print('   .замолчи     - заглушка')
        print('   .saver help  - сохранение')
        print('   .anim help   - анимации')
        print('   .del         - удалить меню')
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
    except Exception as e:
        print(f'\n❌ Критическая ошибка: {e}')
        sys.exit(1)

