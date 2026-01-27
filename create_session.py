import asyncio
import os
import tkinter as tk
from tkinter import simpledialog

from telethon import TelegramClient

# ============ КОНФИГУРАЦИЯ ============
API_ID = 39678712
API_HASH = '3089ac53d532e75deb5dd641e4863d49'
PHONE = '+919036205120'

# Имя файла сессии для Railway
SESSION_NAME = 'railway_session'


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


async def create_new_session():
    """Создание новой сессии для Railway"""
    print('🔐 Создание новой Telegram сессии для Railway...')
    print(f'📱 Номер телефона: {PHONE}')
    
    # Создаем клиент с новым именем сессии
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    try:
        await client.connect()
        print('✅ Подключение к Telegram установлено')
        
        if not await client.is_user_authorized():
            print('📱 Требуется авторизация...')
            print('⏳ Отправка кода подтверждения...')
            await client.send_code_request(PHONE)
            
            code = get_code()
            
            try:
                await client.sign_in(PHONE, code)
                print('✅ Авторизация успешна!')
            except Exception as e:
                if '2FA' in str(e) or 'password' in str(e).lower():
                    print('⚠️ Требуется 2FA пароль')
                    password = get_password()
                    await client.sign_in(password=password)
                    print('✅ Авторизация с 2FA успешна!')
                else:
                    raise e
        
        # Проверяем успешность авторизации
        me = await client.get_me()
        print(f'\n✅ Сессия успешно создана!')
        print(f'👤 Аккаунт: {me.username or me.first_name}')
        print(f'📱 Телефон: {PHONE}')
        print(f'📁 Файл сессии: {SESSION_NAME}.session')
        print(f'\n⚠️ ВАЖНО: Загрузите файл "{SESSION_NAME}.session" в ваш GitHub репозиторий!')
        print(f'📋 Файл находится в текущей директории: {os.getcwd()}')
        
        await client.disconnect()
        
    except Exception as e:
        print(f'❌ Ошибка создания сессии: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    try:
        asyncio.run(create_new_session())
    except KeyboardInterrupt:
        print('\n👋 Создание сессии прервано пользователем')
    except Exception as e:
        print(f'\n❌ Критическая ошибка: {type(e).__name__}: {e}')
