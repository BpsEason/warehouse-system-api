# app/database.py：處理資料庫連線和 Session 管理

from sqlmodel import create_engine, Session, SQLModel
from dotenv import load_dotenv
import os
from typing import Generator

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("環境變數 'DATABASE_URL' 未設定。請檢查 .env 檔案或環境配置。")

SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"

engine = create_engine(DATABASE_URL, echo=SQL_ECHO)

def create_db_and_tables():
    import app.models # noqa: F401
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
