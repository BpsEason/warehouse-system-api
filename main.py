# main.py：FastAPI 應用程式的主要入口檔案

from fastapi import FastAPI, Depends, HTTPException, status, Request
from dotenv import load_dotenv
import os
from typing import List
from datetime import datetime

# 載入 .env 檔案中的環境變數
load_dotenv()

# 匯入資料庫相關工具和模型
from app.database import create_db_and_tables, get_session
from app.models import Product, WarehouseItem, Movement, MovementType # 匯入所有模型
from app.schemas import (
    ProductCreate, ProductRead, ProductUpdate,
    WarehouseItemRead,
    MovementRead,
    StockInRequest, StockOutRequest,
    LowStockAlert, InventoryQueryRead
)
from sqlmodel import Session, select # 匯入 Session 和 select 進行資料庫操作

# 匯入並註冊 API 路由
from app.api.v1.endpoints import products, warehouse_items #, inventory # 暫時註解 inventory, 等待實作

# 匯入自定義例外
from app.exceptions import ProductNotFoundException, InsufficientStockException

# 初始化 FastAPI 應用程式實例
app = FastAPI(
    title="📦 倉儲物流系統 API",
    description="一個簡單的 FastAPI 應用程式，用於管理倉儲商品、庫存及出入庫記錄。",
    version="0.1.0",
)

# ===============================================
# 啟動事件 (Startup Event)
# 在應用程式啟動時執行，用於初始化資料庫等操作
# ===============================================
@app.on_event("startup")
def on_startup():
    """
    應用程式啟動時執行的事件處理器。
    根據環境變數 CREATE_TABLES_ON_STARTUP 決定是否在啟動時創建資料庫表格。
    注意：在生產環境中，此功能通常應關閉，並使用 Alembic 進行資料庫遷移管理。
    """
    print("🚀 應用程式啟動中...")
    if os.getenv("CREATE_TABLES_ON_STARTUP", "false").lower() == "true":
        create_db_and_tables() # 呼叫此函式以確保資料庫表格存在 (方便初期開發)
        print("✅ 資料庫表格檢查或初始化完成 (透過 CREATE_TABLES_ON_STARTUP)。")
    else:
        print("ℹ️ 未在啟動時自動創建資料庫表格 (CREATE_TABLES_ON_STARTUP 未設定或為 false)。請確保已執行 Alembic 遷移。")
    print("✨ 應用程式已成功啟動！")

# ===============================================
# 自定義例外處理器
# ===============================================
@app.exception_handler(ProductNotFoundException)
async def product_not_found_exception_handler(request: Request, exc: ProductNotFoundException):
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail)

@app.exception_handler(InsufficientStockException)
async def insufficient_stock_exception_handler(request: Request, exc: InsufficientStockException):
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail)

# ===============================================
# 根路由 (Root Route)
# 測試 API 是否正常運作的基本端點
# ===============================================
@app.get("/", tags=["🏠 Root"])
async def read_root():
    """
    應用程式的根路徑，提供歡迎訊息和 API 文件連結。
    """
    return {"message": "歡迎使用倉儲物流系統 API！", "docs_url": "/docs"}

# ===============================================
# 配置資訊路由 (Config Route)
# 展示如何從環境變數讀取資訊
# 注意：在生產環境中，建議限制此端點的訪問或移除敏感資訊
# ===============================================
@app.get("/config", tags=["⚙️ Configuration"])
async def get_config():
    """
    獲取應用程式的配置資訊，例如從環境變數讀取的值。
    注意：此端點僅用於開發除錯，請勿在生產環境暴露。
    """
    example_var = os.getenv("EXAMPLE_VAR", "Not Set")
    app_secret_key_status = "Set" if os.getenv("APP_SECRET_KEY") else "Not Set"
    create_tables_on_startup = os.getenv("CREATE_TABLES_ON_STARTUP", "Not Set")
    sql_echo = os.getenv("SQL_ECHO", "Not Set")

    return {
        "message": "應用程式配置資訊概覽",
        "env_example_var": example_var,
        "app_secret_key_status": app_secret_key_status,
        "create_tables_on_startup": create_tables_on_startup,
        "sql_echo": sql_echo
    }

# ===============================================
# 註冊 API 路由
# 將不同模組的 API 端點掛載到應用程式上
# ===============================================
app.include_router(products.router, prefix="/api/v1")
app.include_router(warehouse_items.router, prefix="/api/v1")
# app.include_router(inventory.router, prefix="/api/v1") # 未來如果有更多模組，可以在此處繼續 include
