# app/logging_config.py: 應用程式日誌配置

import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    """
    配置應用程式的日誌系統。
    - 日誌將輸出到控制台和文件（僅限本地開發）。
    - 文件日誌將啟用輪換，防止文件過大。
    - 日誌級別可通過環境變數配置。
    - 在容器化環境中，建議主要輸出到 stdout/stderr。
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    # 確保日誌目錄存在（但在 Docker 中避免寫入檔案，除非使用 volume）
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "app.log")

    # 創建一個應用程式日誌器
    app_logger = logging.getLogger("warehouse_system_api")
    app_logger.setLevel(numeric_level)
    app_logger.propagate = False # 防止日誌事件被傳播到根日誌器

    # 清除現有的處理器，避免重複
    if app_logger.handlers:
        for handler in app_logger.handlers:
            app_logger.removeHandler(handler)

    # 格式器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )

    # 控制台處理器（主要輸出）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    app_logger.addHandler(console_handler)

    # 文件處理器 (帶有輪換功能，僅限本地開發)
    # 注意：在 Docker 容器中，建議避免寫入檔案或使用 volume 持久化
    if os.getenv("ENV") != "production":  # 假設有 ENV 變數，生產環境不寫檔案
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=10 * 1024 * 1024, # 10 MB
            backupCount=5 # 保留 5 個備份文件
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        app_logger.addHandler(file_handler)

    # 配置 SQLAlchemy 的日誌，可通過 SQL_ECHO 環境變數控制
    sql_echo = os.getenv("SQL_ECHO", "false").lower() == "true"
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.setLevel(logging.INFO if sql_echo else logging.WARNING) # SQL_ECHO true 時顯示 INFO
    sqlalchemy_logger.addHandler(console_handler) # 也輸出到控制台
    if os.getenv("ENV") != "production":
        sqlalchemy_logger.addHandler(file_handler) # 也輸出到文件
    sqlalchemy_logger.propagate = False
