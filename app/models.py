# app/models.py: 定義資料庫模型，使用 SQLModel 進行 ORM 映射
# 這個檔案包含了倉儲系統的核心資料模型，包括產品、庫存項目和出入庫記錄。
# 所有模型都繼承自 SQLModel，並設定了表格名稱、欄位約束和關係。

from datetime import datetime
from typing import Optional, List
from enum import Enum
from decimal import Decimal

from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Numeric

class MovementType(str, Enum):
    """出入庫類型枚舉：IN 表示入庫，OUT 表示出庫。"""
    IN = "IN"
    OUT = "OUT"

class Product(SQLModel, table=True):
    """產品模型：代表倉儲中的商品資訊。"""
    __tablename__ = "product"  # 資料庫表格名稱

    id: Optional[int] = Field(default=None, primary_key=True)  # 產品 ID，主鍵，自動生成
    name: str = Field(index=True, max_length=100)  # 產品名稱，支援索引，最大長度 100
    description: Optional[str] = Field(None, max_length=500)  # 產品描述，可選，最大長度 500
    sku: str = Field(unique=True, index=True, max_length=50)  # SKU 編碼，唯一且支援索引，最大長度 50
    price: Decimal = Field(sa_column=Numeric(precision=10, scale=2), gt=0)  # 產品價格，使用 Decimal 確保精度，大於 0

    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)  # 建立時間，預設為當前 UTC 時間，不可為空
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)  # 更新時間，預設為當前 UTC 時間，不可為空

    warehouse_items: List["WarehouseItem"] = Relationship(
        back_populates="product",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )  # 關聯的庫存項目：一對多關係，刪除產品時級聯刪除相關庫存項目

    movements: List["Movement"] = Relationship(
        back_populates="product",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )  # 關聯的出入庫記錄：一對多關係，刪除產品時級聯刪除相關記錄

class WarehouseItem(SQLModel, table=True):
    """庫存項目模型：代表產品在特定位置的庫存資訊。"""
    __tablename__ = "warehouse_item"  # 資料庫表格名稱

    id: Optional[int] = Field(default=None, primary_key=True)  # 庫存項目 ID，主鍵，自動生成
    product_id: int = Field(foreign_key="product.id", index=True)  # 產品 ID，外鍵，支援索引
    quantity: int = Field(ge=0)  # 庫存數量，大於或等於 0
    location: str = Field(index=True, max_length=100)  # 存放位置，支援索引，最大長度 100
    safety_stock: int = Field(default=5, ge=0)  # 安全庫存量，預設 5，大於或等於 0

    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)  # 建立時間，預設為當前 UTC 時間，不可為空
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)  # 更新時間，預設為當前 UTC 時間，不可為空

    product: Product = Relationship(back_populates="warehouse_items")  # 關聯的產品：多對一關係

    movements: List["Movement"] = Relationship(
        back_populates="warehouse_item",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )  # 關聯的出入庫記錄：一對多關係，刪除庫存項目時級聯刪除相關記錄

class Movement(SQLModel, table=True):
    """出入庫記錄模型：記錄產品的出入庫操作歷史。"""
    __tablename__ = "movement"  # 資料庫表格名稱

    id: Optional[int] = Field(default=None, primary_key=True)  # 記錄 ID，主鍵，自動生成
    product_id: int = Field(foreign_key="product.id", index=True)  # 產品 ID，外鍵，支援索引
    warehouse_item_id: int = Field(foreign_key="warehouse_item.id", index=True, nullable=True)  # 庫存項目 ID，外鍵，可選，支援索引
    movement_type: MovementType = Field(index=True)  # 出入庫類型，支援索引
    quantity: int = Field(gt=0)  # 操作數量，大於 0
    movement_date: datetime = Field(default_factory=datetime.utcnow, nullable=False)  # 操作日期，預設為當前 UTC 時間，不可為空
    remarks: Optional[str] = Field(None, max_length=500)  # 備註，可選，最大長度 500

    product: Product = Relationship(back_populates="movements")  # 關聯的產品：多對一關係

    warehouse_item: Optional[WarehouseItem] = Relationship(back_populates="movements")  # 關聯的庫存項目：多對一關係，可選