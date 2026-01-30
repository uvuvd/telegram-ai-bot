"""
Скрипт для создания новой сессии Telegram для Railway
Запускайте ЛОКАЛЬНО на вашем компьютере!
"""

import asyncio
import os
from telethon import TelegramClient

# Ваши данные из основного скрипта
API_ID = 39678712
API_HASH = '3089ac53d532e75deb5dd641e4863d49'
PHONE = '+919036205120'

# Имя сессии (то же что в main.py)
SESSION_NAME = 'railway_session'


async def create_new_session():
    """Создание новой сессии"""
    print('🔐 Создание новой Telegram сессии...')
    print(f'📱 Телефон: {PHONE}')
    print(f'📝 Файл сессии: {SESSION_NAME}.session')
    
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    await client.start(phone=PHONE)
    
    me = await client.get_me()
    print(f'\n✅ Авторизация успешна!')
    print(f'👤 Аккаунт: {me.username or me.first_name}')
    print(f'🆔 User ID: {me.id}')
    print(f'📞 Телефон: {me.phone}')
    
    print(f'\n✅ Сессия сохранена: {SESSION_NAME}.session')
    print(f'📤 Загрузите этот файл на Railway!')
    print(f'\n⚠️ ВАЖНО: Закройте все другие клиенты Telegram на этом аккаунте')
    print(f'⚠️ НЕ запускайте бота локально и на Railway одновременно!')
    
    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(create_new_session())
