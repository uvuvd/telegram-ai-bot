"""
ИНСТРУКЦИЯ ДЛЯ СОЗДАНИЯ СЕССИИ НА ХОСТИНГЕ:

1. Загрузите ЭТОТ файл на Railway вместо основного бота
2. Временно измените команду запуска в Railway на:
   python create_session_on_hosting.py
3. Посмотрите логи Railway - там появится код авторизации
4. Введите код из Telegram в консоль Railway
5. После успешной авторизации скачайте файл railway_session.session
6. Верните обратно основной бот и запустите его
"""

import asyncio
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ.get('API_ID', '39678712'))
API_HASH = os.environ.get('API_HASH', '3089ac53d532e75deb5dd641e4863d49')
PHONE = os.environ.get('PHONE', '+919036205120')
SESSION_NAME = 'railway_session'

async def create_session():
    print('='*50)
    print('🔐 СОЗДАНИЕ TELEGRAM СЕССИИ НА ХОСТИНГЕ')
    print('='*50)
    print(f'\n📱 Телефон: {PHONE}')
    print(f'🆔 API_ID: {API_ID}')
    print(f'📝 Сессия: {SESSION_NAME}.session\n')
    
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    await client.start(phone=PHONE)
    
    me = await client.get_me()
    print('\n' + '='*50)
    print('✅ УСПЕШНАЯ АВТОРИЗАЦИЯ!')
    print('='*50)
    print(f'👤 Имя: {me.first_name}')
    print(f'📱 Телефон: {me.phone}')
    print(f'🆔 ID: {me.id}')
    print(f'📝 Username: @{me.username or "нет"}')
    print('='*50)
    print(f'\n✅ Сессия сохранена: {SESSION_NAME}.session')
    print('✅ Теперь можно запускать основной бот!')
    print('\nℹ️  Эта сессия привязана к IP хостинга.')
    print('⚠️  НЕ используйте её на других IP!')
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(create_session())
