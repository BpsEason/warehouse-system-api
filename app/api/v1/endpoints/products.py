# app/api/v1/endpoints/products.py: 產品相關 API 端點定義
# 這個檔案定義了處理產品的 FastAPI 路由，包括 CRUD 操作。
# 使用自定義例外處理錯誤，以確保一致性。

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlmodel import Session, select
from datetime import datetime

from app.database import get_session
from app.models import Product
from app.schemas import ProductCreate, ProductRead, ProductUpdate
from app.exceptions import ProductNotFoundException

router = APIRouter(tags=["Products"], prefix="/products")

@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(*, session: Session = Depends(get_session), product: ProductCreate):
    """創建產品：檢查 SKU 唯一性，並將 SKU 轉為大寫儲存。"""
    with session.begin():
        existing_product = session.exec(select(Product).where(Product.sku == product.sku.upper())).first()
        if existing_product:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"SKU '{product.sku}' 已存在")

        product_dict = product.model_dump()
        product_dict['sku'] = product_dict['sku'].upper()
        db_product = Product(**product_dict)
        session.add(db_product)

    session.refresh(db_product)
    return db_product

@router.get("/", response_model=List[ProductRead])
async def get_all_products(*, session: Session = Depends(get_session), offset: int = 0, limit: int = 100, name: Optional[str] = None, sku: Optional[str] = None):
    """獲取所有產品列表：支援分頁、名稱和 SKU 過濾，SKU 查詢轉為大寫處理。"""
    query = select(Product)
    if name:
        query = query.where(Product.name.ilike(f"%{name}%"))
    if sku:
        query = query.where(Product.sku == sku.upper())
    products = session.exec(query.offset(offset).limit(limit)).all()
    return products

@router.get("/{product_id}", response_model=ProductRead)
async def get_product(*, session: Session = Depends(get_session), product_id: int):
    """獲取單一產品：根據 ID 查詢，如果不存在則拋出自定義 ProductNotFoundException。"""
    product = session.get(Product, product_id)
    if not product:
        raise ProductNotFoundException()
    return product

@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(*, session: Session = Depends(get_session), product_id: int, product: ProductUpdate):
    """更新產品：檢查新 SKU 的唯一性，並更新時間戳。如果不存在則拋出自定義例外。"""
    with session.begin():
        db_product = session.get(Product, product_id)
        if not db_product:
            raise ProductNotFoundException()

        if product.sku and product.sku.upper() != db_product.sku:
            existing_product_with_new_sku = session.exec(select(Product).where(Product.sku == product.sku.upper(), Product.id != product_id)).first()
            if existing_product_with_new_sku:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"新的 SKU '{product.sku}' 已被其他商品使用。")

        product_data = product.model_dump(exclude_unset=True)
        if 'sku' in product_data:
            product_data['sku'] = product_data['sku'].upper()
        for key, value in product_data.items():
            setattr(db_product, key, value)
        db_product.updated_at = datetime.utcnow()

        session.add(db_product)

    session.refresh(db_product)
    return db_product

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(*, session: Session = Depends(get_session), product_id: int):
    """刪除產品：根據 ID 刪除，如果不存在則拋出自定義例外。"""
    with session.begin():
        product = session.get(Product, product_id)
        if not product:
            raise ProductNotFoundException()

        session.delete(product)