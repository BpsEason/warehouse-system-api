# alembic/env.py：Alembic 資料庫遷移環境設定

from logging.config import fileConfig
import os
from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context

from sqlmodel import SQLModel

# 載入 .env 檔案中的環境變數
load_dotenv()

# ===========================================================================
# IMPORTANT: 從環境變數獲取資料庫 URL
# 這將覆蓋 alembic.ini 中 sqlalchemy.url 的設定，
# 使得在 Docker Compose 環境中可以輕鬆連接到 'db' 服務。
# ===========================================================================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import app.models  # noqa: F401
target_metadata = SQLModel.metadata

def run_migrations_offline():
    context.configure(url=DATABASE_URL, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
