from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, conint
from decimal import Decimal

from app.models import MovementType

class LocationQuantity(BaseModel):
    location: str
    quantity: int

class ProductBase(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    sku: str = Field(min_length=3, max_length=50)
    price: Decimal = Field(gt=0, description="商品價格必須大於0")

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    sku: Optional[str] = Field(None, min_length=3, max_length=50)
    price: Optional[Decimal] = Field(None, gt=0, description="商品價格必須大於0")

class ProductRead(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class WarehouseItemBase(BaseModel):
    product_id: int
    quantity: conint(ge=0) = Field(description="庫存數量必須大於或等於0")
    location: str = Field(min_length=2, max_length=100)
    safety_stock: conint(ge=0) = Field(default=5, description="安全庫存量必須大於或等於0")

class WarehouseItemCreate(WarehouseItemBase):
    pass

class WarehouseItemUpdate(BaseModel):
    quantity: Optional[conint(ge=0)] = Field(None, description="庫存數量必須大於或等於0")
    location: Optional[str] = Field(None, min_length=2, max_length=100)
    safety_stock: Optional[conint(ge=0)] = Field(None, description="安全庫存量必須大於或等於0")

class WarehouseItemRead(WarehouseItemBase):
    id: int
    created_at: datetime
    updated_at: datetime
    product: ProductRead

    class Config:
        from_attributes = True

class MovementBase(BaseModel):
    product_id: int
    warehouse_item_id: Optional[int] = Field(None, description="可選，若有特定庫存項目的移動則填寫")
    movement_type: MovementType
    quantity: conint(gt=0) = Field(description="移動數量必須大於0")
    remarks: Optional[str] = Field(None, max_length=500)

class MovementCreate(MovementBase):
    pass

class MovementRead(MovementBase):
    id: int
    movement_date: datetime
    product: ProductRead
    warehouse_item: Optional[WarehouseItemRead] = None

    class Config:
        from_attributes = True

class StockInRequest(BaseModel):
    product_id: int
    quantity: conint(gt=0) = Field(description="入庫數量必須大於0")
    location: str = Field(min_length=2, max_length=100, description="入庫存放位置")
    remarks: Optional[str] = Field(None, max_length=500)

class StockOutRequest(BaseModel):
    product_id: int
    quantity: conint(gt=0) = Field(description="出庫數量必須大於0")
    location: Optional[str] = Field(None, min_length=2, max_length=100, description="可選，若從特定位置出庫")
    remarks: Optional[str] = Field(None, max_length=500)

class LowStockAlert(BaseModel):
    product_id: int
    product_name: str
    sku: str
    current_stock: int = Field(description="當前庫存總量")
    safety_stock: int = Field(description="安全庫存閾值")
    location_details: List[LocationQuantity] = Field(
        description="各存放位置的庫存細節"
    )

    class Config:
        from_attributes = True

class InventoryQueryRead(BaseModel):
    product_id: int
    product_name: str
    sku: str
    total_quantity: int
    locations: List[LocationQuantity]

    class Config:
        from_attributes = True
