from typing import Optional

class ProductNotFoundException(Exception):
    def __init__(self, detail: Optional[str] = "商品不存在"):
        self.detail = detail

class InsufficientStockException(Exception):
    def __init__(self, detail: Optional[str] = "庫存不足"):
        self.detail = detail
