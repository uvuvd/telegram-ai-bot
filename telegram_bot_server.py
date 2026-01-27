import asyncio
import json
import os
import tkinter as tk
from tkinter import simpledialog

import aiohttp
from telethon import TelegramClient, events
from telethon.errors import RPCError

# ============ КОНФИГУРАЦИЯ ============
# Telegram API (получить на https://my.telegram.org)
API_ID = 39678712
API_HASH = '3089ac53d532e75deb5dd641e4863d49'
PHONE = '+919036205120'

# OpenRouter API
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_API_KEY = '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'
MODEL_NAME = 'google/gemini-3-flash-preview'  # Исправлено название модели

# Команда активации
ACTIVATION_COMMAND = 'Ai Edem'

# Файлы базы данных
DB_FILE = 'messages.json'
ACTIVE_CHATS_FILE = 'active_chats.json'


# ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============
def get_code():
    """Получение кода подтверждения от пользователя"""
    root = tk.Tk()
    root.withdraw()
    code = simpledialog.askstring("Telegram", "Введи код из Telegram:")
    root.destroy()
    return code


def get_password():
    """Получение пароля 2FA от пользователя"""
    root = tk.Tk()
    root.withdraw()
    password = simpledialog.askstring("Telegram", "Введи пароль 2FA:", show='*')
    root.destroy()
    return password


# Инициализация Telegram клиента
client = TelegramClient('session', API_ID, API_HASH)


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


# Загрузка базы данных
db = load_db()


# ============ РАБОТА С AI API ============
async def get_ai_response(messages):
    """
    Получение ответа от AI API
    messages - список сообщений в формате [{'role': 'user/assistant', 'content': 'текст'}]
    """
    try:
        timeout = aiohttp.ClientTimeout(total=120)  # Увеличен таймаут

        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                'model': MODEL_NAME,
                'messages': messages,
                'temperature': 0.7,
                'max_tokens': 2048  # Увеличено количество токенов
            }

            headers = {
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/telegram-bot',
                'X-Title': 'Telegram AI Bot'
            }

            print(f'🔄 Отправка запроса к API...')
            async with session.post(OPENROUTER_API_URL, json=payload, headers=headers) as resp:
                response_text = await resp.text()
                print(f'📥 Ответ API (статус {resp.status}): {response_text[:200]}...')

                if resp.status == 200:
                    result = json.loads(response_text)
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    if content:
                        return content.strip()
                    return 'Не понял ваш вопрос'
                else:
                    print(f'❌ API ошибка {resp.status}: {response_text}')
                    return f'Ошибка API ({resp.status}). Попробуйте позже.'

    except asyncio.TimeoutError:
        print('⏱️ API таймаут')
        return 'Извините, слишком долго обрабатываю запрос'
    except json.JSONDecodeError as e:
        print(f'❌ Ошибка парсинга JSON: {e}')
        return 'Ошибка обработки ответа от API'
    except Exception as e:
        print(f'❌ Ошибка API: {type(e).__name__}: {e}')
        return 'Не смог сформировать ответ'


# ============ РАБОТА С МЕДИАФАЙЛАМИ ============
async def transcribe_voice(voice_data):
    """Обработка голосовых сообщений (заглушка)"""
    return '[получено голосовое сообщение]'


async def analyze_photo(photo_data):
    """Обработка изображений (заглушка)"""
    return '[получено изображение]'


# ============ РАБОТА С ИСТОРИЕЙ ЧАТА ============
def get_chat_history(chat_id, limit=10):  # Уменьшен лимит для экономии токенов
    """Получение истории сообщений чата"""
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []

    # Фильтруем сообщения с ошибками API из истории
    filtered_history = [
        msg for msg in db[chat_key]
        if not (msg.get('role') == 'assistant' and
                ('Ошибка API' in msg.get('content', '') or
                 'Произошла ошибка при обращении к API' in msg.get('content', '')))
    ]

    return filtered_history[-limit:]


def save_message(chat_id, role, content):
    """Сохранение сообщения в историю"""
    chat_key = str(chat_id)
    if chat_key not in db:
        db[chat_key] = []

    # Не сохраняем ошибки API в историю
    if role == 'assistant' and ('Ошибка API' in content or 'Произошла ошибка при обращении к API' in content):
        return

    db[chat_key].append({
        'role': role,
        'content': content
    })

    # Ограничение истории 100 сообщениями
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


# ============ ОБРАБОТЧИК СООБЩЕНИЙ ============
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    """Основной обработчик входящих сообщений"""
    try:
        # Игнорируем собственные сообщения
        if event.out:
            return

        chat_id = event.chat_id
        message_text = event.message.message or ''

        print(f'📨 Получено сообщение в чате {chat_id}: {message_text[:50]}...')

        # ========== КОМАНДЫ УПРАВЛЕНИЯ ==========

        # Активация бота в чате
        if ACTIVATION_COMMAND.lower() in message_text.lower():
            activate_chat(chat_id)
            await event.respond(f'✅ Бот активирован! Теперь я буду отвечать на все сообщения в этом чате.\n\n'
                                f'Команды:\n'
                                f'• "Ai Stop" - деактивировать бота\n'
                                f'• "Ai Clear" - очистить историю чата')
            return

        # Деактивация бота
        if 'ai stop' in message_text.lower():
            deactivate_chat(chat_id)
            await event.respond('❌ Бот деактивирован. Напишите "Ai Edem" для повторной активации.')
            return

        # Очистка истории
        if 'ai clear' in message_text.lower():
            if is_chat_active(chat_id):
                clear_chat_history(chat_id)
                await event.respond('🗑️ История диалога очищена!')
            return

        # Проверка, активен ли бот в этом чате
        if not is_chat_active(chat_id):
            print(f'⏭️ Чат {chat_id} не активен, пропускаем')
            return

        # ========== ОБРАБОТКА МЕДИАФАЙЛОВ ==========

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

        # ========== ПОЛУЧЕНИЕ ОТВЕТА ОТ AI ==========

        save_message(chat_id, 'user', message_text)
        history = get_chat_history(chat_id)

        system_message = {
            'role': 'system',
            'content': 'Ты дружелюбный и полезный ассистент. Отвечай кратко и по существу. Общайся на том же языке, что и пользователь.'
        }

        messages_for_api = [system_message] + history

        print(f'🤖 Запрос к AI с {len(history)} сообщениями в истории')
        response = await get_ai_response(messages_for_api)

        if response and not response.startswith('Ошибка'):
            save_message(chat_id, 'assistant', response)

        # ========== ОТПРАВКА ОТВЕТА ==========

        try:
            await event.respond(response)
            print(f'✅ Отправлен ответ в чат {chat_id}: {response[:50]}...')

        except RPCError as e:
            if 'TOPIC_CLOSED' in str(e) or 'CHAT_WRITE_FORBIDDEN' in str(e):
                print(f'⚠️ Чат {chat_id} закрыт для записи')
                deactivate_chat(chat_id)
            else:
                print(f'❌ RPC ошибка: {e}')

        except Exception as e:
            print(f'❌ Ошибка отправки сообщения: {type(e).__name__}: {e}')

    except Exception as e:
        print(f'❌ Критическая ошибка обработки сообщения: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()


# ============ ГЛАВНАЯ ФУНКЦИЯ ============
async def main():
    """Запуск бота"""
    print('🚀 Запуск Telegram бота с AI...')
    print(f'📁 Рабочая директория: {os.getcwd()}')

    try:
        await client.connect()
        print('✅ Подключение к Telegram установлено')

        if not await client.is_user_authorized():
            print('📱 Требуется авторизация...')
            await client.send_code_request(PHONE)
            code = get_code()

            try:
                await client.sign_in(PHONE, code)
            except Exception as e:
                print(f'⚠️ Требуется 2FA: {e}')
                password = get_password()
                await client.sign_in(password=password)

        print('✅ Бот успешно запущен!')
        me = await client.get_me()
        print(f'👤 Аккаунт: {me.username or me.first_name}')
        print(f'🤖 Модель: {MODEL_NAME}')
        print(f'🔑 Команда активации: "{ACTIVATION_COMMAND}"')
        print('\n📝 Для активации бота в чате напишите: Ai Edem')
        print('⏹️ Для остановки нажмите Ctrl+C\n')
        print('🎧 Слушаю сообщения...\n')

        await client.run_until_disconnected()

    except Exception as e:
        print(f'❌ Ошибка запуска: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()


# ============ ЗАПУСК ПРОГРАММЫ ============
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n👋 Бот остановлен пользователем')
    except Exception as e:
        print(f'\n❌ Критическая ошибка: {type(e).__name__}: {e}')
        import traceback


        traceback.print_exc()


