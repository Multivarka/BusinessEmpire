from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Указываем файл базы данных SQLite
DATABASE_URL = "sqlite:///./game.db"

# Создаем движок БД. Для SQLite нужен аргумент check_same_thread
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Создаем фабрику сессий для связи с БД
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс, от которого будут наследоваться наши таблицы
Base = declarative_base()

# Вспомогательная функция (Dependency) для получения сессии в FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()