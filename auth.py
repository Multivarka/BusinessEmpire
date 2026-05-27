import hmac
import hashlib
import json
from urllib.parse import parse_qsl
from fastapi import HTTPException, status
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


def verify_telegram_data(init_data: str) -> dict:
    """
    Проверяет строку initData от Telegram Web App.
    Возвращает словарь с данными пользователя, если проверка успешна.
    """
    try:
        # 1. Парсим строку параметров в словарь
        parsed_data = dict(parse_qsl(init_data))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid data format")

    if "hash" not in parsed_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing hash")

    received_hash = parsed_data.pop("hash")

    # 2. Сортируем оставшиеся параметры по алфавиту и соединяем через \n
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))

    # 3. Алгоритм валидации Telegram:
    # Шаг А: Создаем секретный ключ на основе токена бота
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    # Шаг Б: Считаем HMAC-SHA256 от нашей строки данных
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    # 4. Сравниваем хэши
    if computed_hash != received_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Data is not genuine")

    # 5. Если все ок, парсим поле 'user' (там лежит ID, имя и т.д.)
    user_data = json.loads(parsed_data.get("user", "{}"))
    return user_data