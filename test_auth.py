import hmac
import hashlib
import json
import requests
from urllib.parse import urlencode

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


def generate_fake_tg_data(user_id: int, first_name: str, username: str) -> str:
    """Генерирует валидную строку initData, как если бы её прислал Telegram"""
    user_data = {
        "id": user_id,
        "first_name": first_name,
        "username": username,
        "language_code": "ru"
    }

    params = {
        "auth_date": "1716666666",
        "query_id": "AAHXXXXX",
        "user": json.dumps(user_data)
    }

    # Сортируем и создаем строку для хэша
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    params["hash"] = computed_hash
    return urlencode(params)


# --- ИМИТАЦИЯ ИГРЫ ---
URL = "http://127.0.0.1:8000/api/auth"

print("1. Вход Босса (Иван)...")
boss_data = generate_fake_tg_data(11111, "Иван", "ivan_boss")
res1 = requests.post(URL, headers={"x-telegram-init-data": boss_data})
print("Ответ сервера:", res1.json())

print("\n2. Вход Реферала (Петр) по ссылке Ивана...")
worker_data = generate_fake_tg_data(22222, "Петр", "petr_worker")
# Передаем в query-параметрах referrer_id=11111 (ID Ивана)
res2 = requests.post(f"{URL}?referrer_id=11111", headers={"x-telegram-init-data": worker_data})
print("Ответ сервера:", res2.json())