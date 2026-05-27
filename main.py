from fastapi import FastAPI, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional

import models
from database import engine, get_db
from auth import verify_telegram_data

import time

# Автоматически создаем таблицы в БД (game.db) при старте сервера, если их еще нет
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Slavery Game API")

# Настройка CORS (разрешаем фронтенду делать запросы к нашему API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене замени на конкретный URL фронтенда
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/auth")
def authenticate_user(
        x_telegram_init_data: str = Header(...),
        referrer_id: Optional[int] = Query(None),  # Принимаем ID пригласившего из ссылки t.me/bot?start=ref_ID
        db: Session = Depends(get_db)
):
    """
    Эндпоинт авторизации и регистрации.
    1. Проверяет подлинность строки initData от Telegram.
    2. Если пользователя нет в БД — регистрирует его.
    3. Если пользователь новый и пришел по рефералке — устраивает его в компанию к боссу.
    """

    # 1. Валидация данных Telegram (защита от подделки ID и балансов)
    tg_user = verify_telegram_data(x_telegram_init_data)
    tg_id = tg_user.get("id")

    # 2. Ищем игрока в базе данных
    user = db.query(models.User).filter(models.User.id == tg_id).first()
    is_new_user = False

    # 3. Если игрока нет в базе — это его первый заход, регистрируем новичка
    if not user:
        is_new_user = True
        user = models.User(
            id=tg_id,
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            balance=100,  # Стартовый капитал в монетах
            works_in_company_id=None
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[Регистрация] Новый игрок: {user.first_name} (ID: {user.id})")

    # 4. РЕФЕРАЛЬНАЯ СИСТЕМА: Отрабатывает только ОДИН раз при первой регистрации
    if is_new_user and referrer_id and referrer_id != tg_id:
        # Ищем босса (того, кто пригласил) в БД
        boss = db.query(models.User).filter(models.User.id == referrer_id).first()

        if boss:
            # Если у босса еще нет своей компании, игра автоматически создает её
            if not boss.own_company:
                new_company = models.Company(
                    name=f"Корпорация {boss.first_name}",
                    owner_id=boss.id
                )
                db.add(new_company)
                db.commit()
                db.refresh(boss)  # Обновляем объект босса, чтобы связать с новой компанией

            # Отправляем новичка работать в компанию босса
            user.works_in_company_id = boss.own_company.id
            db.commit()
            db.refresh(user)
            print(f"[Рабство] Игрок {user.first_name} стал рефералом для {boss.first_name}")

    # 5. Формируем актуальный статус пользователя для отправки на фронтенд
    has_company = user.own_company is not None
    company_name = user.own_company.name if has_company else None

    # Определяем, кто наш босс на данный момент
    boss_name = "Свободный человек"
    if user.employer_company:
        boss_name = user.employer_company.owner.first_name

    return {
        "status": "success",
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "balance": user.balance,
            "has_company": has_company,
            "company_name": company_name,
            "boss": boss_name
        }
    }


@app.post("/api/company/collect")
def collect_income(
        x_telegram_init_data: str = Header(...),
        db: Session = Depends(get_db)
):
    """
    Сбор пассивного дохода со своих рабочих.
    """
    # 1. Авторизуем босса
    tg_user = verify_telegram_data(x_telegram_init_data)
    boss = db.query(models.User).filter(models.User.id == tg_user.get("id")).first()

    if not boss or not boss.own_company:
        return {"status": "error", "message": "У вас нет компании"}

    company = boss.own_company
    workers_count = len(company.workers)

    if workers_count == 0:
        return {"status": "error", "message": "У вас пока нет работников. Отправьте реф. ссылку друзьям!"}

    # 2. Считаем, сколько времени прошло с последнего сбора
    now = int(time.time())
    seconds_passed = now - company.last_collect

    if seconds_passed <= 0:
        return {"status": "error", "message": "Слишком рано для сбора прибыли"}

    # Формула: Работники * Время в сек * Доход в сек
    earned = workers_count * seconds_passed * company.income_per_worker

    # 3. Начисляем золото боссу и обновляем время сбора
    boss.balance += earned
    company.last_collect = now
    db.commit()

    return {
        "status": "success",
        "earned": earned,
        "new_balance": boss.balance
    }


@app.post("/api/worker/buyout")
def buyout_freedom(
        x_telegram_init_data: str = Header(...),
        db: Session = Depends(get_db)
):
    """
    Выкуп свободы. Работник платит фиксированную сумму (например, 500 монет),
    чтобы уйти от босса и открыть свою компанию.
    """
    COST_OF_FREEDOM = 500

    tg_user = verify_telegram_data(x_telegram_init_data)
    user = db.query(models.User).filter(models.User.id == tg_user.get("id")).first()

    if not user:
        return {"status": "error", "message": "Пользователь не найден"}

    if not user.works_in_company_id:
        return {"status": "error", "message": "Вы и так свободны"}

    if user.balance < COST_OF_FREEDOM:
        return {"status": "error", "message": f"Недостаточно средств. Нужно {COST_OF_FREEDOM} монет"}

    # Списываем деньги за свободу
    user.balance -= COST_OF_FREEDOM
    # Увольняем из компании текущего босса
    user.works_in_company_id = None

    # Сразу создаем ему личную компанию, теперь он сам босс!
    new_company = models.Company(
        name=f"Корпорация {user.first_name}",
        owner_id=user.id
    )
    db.add(new_company)
    db.commit()

    return {
        "status": "success",
        "message": "Вы выкупили свободу и основали свою компанию!",
        "new_balance": user.balance
    }

if __name__ == "__main__":
    import uvicorn

    # Запуск локального сервера на порту 8000 с автоперезагрузкой при изменении кода
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)