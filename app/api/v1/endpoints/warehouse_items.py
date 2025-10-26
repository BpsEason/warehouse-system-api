# app/api/v1/endpoints/warehouse_items.py: 倉儲項目相關 API 端點定義
# 這個檔案定義了處理庫存項目的 FastAPI 路由，包括入庫、出庫、查詢等操作。
# 業務邏輯已抽象到 services/inventory_service.py 以提高可維護性。

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlmodel import Session, select, func
from datetime import datetime

from app.database import get_session
from app.services.inventory_service import stock_in, stock_out, get_low_stock_alerts, get_inventory_overview
from app.schemas import (
    WarehouseItemCreate, WarehouseItemRead, WarehouseItemUpdate,
    StockInRequest, StockOutRequest, LowStockAlert, InventoryQueryRead
)

router = APIRouter(tags=["Warehouse Items"], prefix="/warehouse-items")

@router.post("/", response_model=WarehouseItemRead, status_code=status.HTTP_201_CREATED)
async def create_warehouse_item(*, session: Session = Depends(get_session), item_request: StockInRequest):
    """入庫操作：根據請求新增或更新庫存項目，並記錄 Movement。"""
    return stock_in(session, item_request)

@router.post("/stock-out", response_model=WarehouseItemRead)
async def perform_stock_out(*, session: Session = Depends(get_session), stock_out_request: StockOutRequest):
    """出庫操作：根據請求扣減庫存，並記錄 Movement。如果未指定位置，會從多個位置分散扣減。"""
    return stock_out(session, stock_out_request)

@router.get("/", response_model=List[WarehouseItemRead])
async def get_all_warehouse_items(*, session: Session = Depends(get_session), offset: int = 0, limit: int = 100, product_id: Optional[int] = None, location: Optional[str] = None):
    """獲取所有庫存項目列表：支援分頁、產品 ID 和位置過濾。"""
    query = select(WarehouseItem).offset(offset).limit(limit)
    if product_id:
        query = query.where(WarehouseItem.product_id == product_id)
    if location:
        query = query.where(WarehouseItem.location.ilike(f"%{location}%"))

    items = session.exec(query).all()
    return items

@router.get("/{item_id}", response_model=WarehouseItemRead)
async def get_warehouse_item(*, session: Session = Depends(get_session), item_id: int):
    """獲取單一庫存項目：根據 ID 查詢，如果不存在則拋出 404 錯誤。"""
    item = session.get(WarehouseItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="庫存項目不存在")
    return item

@router.patch("/{item_id}", response_model=WarehouseItemRead)
async def update_warehouse_item(*, session: Session = Depends(get_session), item_id: int, item: WarehouseItemUpdate):
    """更新庫存項目：支援更新位置或安全庫存，但數量調整需透過入/出庫接口。如果不存在則拋出 404 錯誤。"""
    with session.begin():
        db_item = session.get(WarehouseItem, item_id)
        if not db_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="庫存項目不存在")

        if item.quantity is not None and item.quantity != db_item.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="請使用入庫或出庫接口調整數量。")

        item_data = item.model_dump(exclude_unset=True)
        for key, value in item_data.items():
            setattr(db_item, key, value)
        db_item.updated_at = datetime.utcnow()

        session.add(db_item)

    session.refresh(db_item)
    return db_item

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_warehouse_item(*, session: Session = Depends(get_session), item_id: int):
    """刪除庫存項目：根據 ID 刪除，如果不存在則拋出 404 錯誤。"""
    with session.begin():
        item = session.get(WarehouseItem, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="庫存項目不存在")

        session.delete(item)

@router.get("/inventory/overview", response_model=List[InventoryQueryRead])
async def get_inventory_overview(*, session: Session = Depends(get_session), offset: int = 0, limit: int = 100, product_name: Optional[str] = None, sku: Optional[str] = None):
    """獲取庫存概覽：按產品彙總總數量和位置細節，支援分頁和過濾。"""
    return get_inventory_overview(session, offset, limit, product_name, sku)

@router.get("/inventory/low-stock", response_model=List[LowStockAlert])
async def get_low_stock_alerts(*, session: Session = Depends(get_session)):
    """獲取低庫存警報：返回總庫存低於安全庫存的產品清單，包括位置細節。"""
    return get_low_stock_alerts(session)