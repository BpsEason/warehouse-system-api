from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime
from app.models import Product, WarehouseItem, Movement, MovementType
from app.schemas import WarehouseItemRead, StockInRequest, StockOutRequest, LowStockAlert, InventoryQueryRead, LocationQuantity
from app.exceptions import ProductNotFoundException, InsufficientStockException

def stock_in(session: Session, item_request: StockInRequest) -> WarehouseItemRead:
    """
    處理商品的入庫操作。
    如果指定位置已有該商品的庫存，則更新其數量；否則，創建新的庫存項目。
    同時會記錄一筆入庫移動記錄。

    Args:
        session: 資料庫 Session 物件。
        item_request: 包含入庫商品ID、數量、位置和備註的請求資料。

    Returns:
        WarehouseItemRead: 更新或創建後的庫存項目。

    Raises:
        ProductNotFoundException: 如果商品ID不存在。
    """
    # 使用事務 (transaction) 確保操作的原子性：所有操作要嘛全部成功，要嘛全部失敗回滾。
    with session.begin():
        # 1. 檢查商品是否存在
        product = session.get(Product, item_request.product_id)
        if not product:
            # 如果商品不存在，則拋出商品未找到的例外
            raise ProductNotFoundException()

        # 2. 檢查指定位置是否已有該商品的庫存項目
        existing_item = session.exec(
            select(WarehouseItem).where(
                WarehouseItem.product_id == item_request.product_id,
                WarehouseItem.location == item_request.location
            )
        ).first()

        # 3. 處理庫存更新或創建
        if existing_item:
            # 如果存在現有庫存項目，則增加其數量
            existing_item.quantity += item_request.quantity
            existing_item.updated_at = datetime.utcnow() # 更新修改時間
            session.add(existing_item) # 將修改後的項目加入 session
            db_item = existing_item # 將現有項目設為操作結果
        else:
            # 如果沒有現有庫存項目，則創建一個新的
            item_dict = {
                'product_id': item_request.product_id,
                'quantity': item_request.quantity,
                'location': item_request.location,
            }
            db_item = WarehouseItem(**item_dict) # 建立新的 WarehouseItem 物件
            session.add(db_item) # 將新項目加入 session
            session.flush() # 立即將新項目寫入資料庫，以便獲取其 ID (如果 auto-increment)

        # 4. 記錄入庫移動
        movement = Movement(
            product_id=db_item.product_id,
            warehouse_item_id=db_item.id, # 關聯到剛剛更新或創建的庫存項目
            movement_type=MovementType.IN, # 移動類型為 "IN" (入庫)
            quantity=item_request.quantity,
            remarks=item_request.remarks,
        )
        session.add(movement) # 將移動記錄加入 session

    # 5. 刷新物件狀態並返回
    # 在事務提交後，刷新 db_item 以確保其關聯物件 (如 product) 能夠正確載入
    session.refresh(db_item)
    return db_item

def stock_out(session: Session, stock_out_request: StockOutRequest) -> WarehouseItemRead:
    """
    處理商品的彈性出庫操作。
    如果指定了出庫位置，則僅從該位置扣除庫存。
    如果未指定出庫位置，則從所有有庫存的位置中，按 ID 順序依序扣除，直到滿足出庫數量。
    同時會記錄一筆出庫移動記錄。

    Args:
        session: 資料庫 Session 物件。
        stock_out_request: 包含出庫商品ID、數量、可選位置和備註的請求資料。

    Returns:
        WarehouseItemRead: 更新後的庫存項目 (如果指定位置出庫，則返回該項目；否則返回第一個被修改的項目)。

    Raises:
        ProductNotFoundException: 如果商品ID不存在，或在指定位置無庫存記錄，或所有位置均無庫存。
        InsufficientStockException: 如果指定位置或總庫存不足以出庫。
    """
    # 使用事務 (transaction) 確保操作的原子性
    with session.begin():
        # 1. 檢查商品是否存在
        product = session.get(Product, stock_out_request.product_id)
        if not product:
            raise ProductNotFoundException()

        updated_items = [] # 用於存放所有被更新的庫存項目
        
        # 2. 判斷是否指定了具體出庫位置
        if stock_out_request.location:
            # 從指定位置出庫
            item_to_update = session.exec(
                select(WarehouseItem).where(
                    WarehouseItem.product_id == stock_out_request.product_id,
                    WarehouseItem.location == stock_out_request.location
                )
            ).first()

            if not item_to_update:
                raise ProductNotFoundException(detail=f"商品在位置 '{stock_out_request.location}' 無庫存記錄。")

            if item_to_update.quantity < stock_out_request.quantity:
                raise InsufficientStockException(detail=f"位置 '{stock_out_request.location}' 的庫存不足。")

            # 扣除庫存並更新時間
            item_to_update.quantity -= stock_out_request.quantity
            item_to_update.updated_at = datetime.utcnow()
            session.add(item_to_update)
            updated_items.append(item_to_update) # 記錄被更新的項目

            # 記錄出庫移動
            movement = Movement(
                product_id=stock_out_request.product_id,
                warehouse_item_id=item_to_update.id,
                movement_type=MovementType.OUT, # 移動類型為 "OUT" (出庫)
                quantity=stock_out_request.quantity,
                remarks=stock_out_request.remarks,
            )
            session.add(movement)
        else:
            # 從所有可用位置出庫 (未指定位置時)
            # 依 ID 排序，確保出庫順序的一致性 (例如：先進先出 FIFO 的簡化版，或從最老庫存開始扣除)
            available_items = session.exec(
                select(WarehouseItem).where(
                    WarehouseItem.product_id == stock_out_request.product_id,
                    WarehouseItem.quantity > 0 # 只考慮有庫存的項目
                ).order_by(WarehouseItem.id) # 依庫存項目 ID 升序排列
            ).all()

            if not available_items:
                raise ProductNotFoundException(detail="該商品所有位置均無庫存。")

            # 計算總可用庫存
            total_available = sum(item.quantity for item in available_items)
            if total_available < stock_out_request.quantity:
                raise InsufficientStockException(detail=f"總庫存不足。")

            remaining_to_deduct = stock_out_request.quantity # 剩餘待扣除的數量
            for item in available_items:
                if remaining_to_deduct == 0:
                    break # 如果已經扣除足夠數量，則停止
                
                # 計算本次從該位置扣除的數量 (取當前庫存和剩餘待扣除數量中較小者)
                deduct_amount = min(item.quantity, remaining_to_deduct)
                item.quantity -= deduct_amount
                item.updated_at = datetime.utcnow()
                session.add(item)
                updated_items.append(item) # 記錄被更新的項目
                remaining_to_deduct -= deduct_amount # 更新剩餘待扣除數量

                # 記錄本次移動的出庫記錄
                movement = Movement(
                    product_id=stock_out_request.product_id,
                    warehouse_item_id=item.id,
                    movement_type=MovementType.OUT,
                    quantity=deduct_amount,
                    remarks=stock_out_request.remarks,
                )
                session.add(movement)

        # 3. 返回結果
        # 如果有任何項目被更新，返回第一個被更新的項目；否則返回 None (理論上不會發生，因為前面有例外處理)
        db_item = updated_items[0] if updated_items else None

    # 4. 刷新物件狀態並返回
    if db_item:
        session.refresh(db_item)
    return db_item

def get_inventory_overview(
    session: Session,
    offset: int = 0,
    limit: int = 100,
    product_name: Optional[str] = None,
    sku: Optional[str] = None
) -> List[InventoryQueryRead]:
    """
    獲取庫存概覽，匯總每個商品的總庫存和分位置庫存。

    Args:
        session: 資料庫 Session 物件。
        offset: 分頁查詢的偏移量。
        limit: 分頁查詢的限制數量。
        product_name: 可選的商品名稱篩選條件 (模糊匹配)。
        sku: 可選的商品 SKU 篩選條件 (精確匹配)。

    Returns:
        List[InventoryQueryRead]: 包含每個商品庫存概覽的列表。
    """
    # 1. 構建查詢：聯接 WarehouseItem 和 Product 表
    query = select(WarehouseItem, Product).join(Product)

    # 2. 應用篩選條件
    if product_name:
        query = query.where(Product.name.ilike(f"%{product_name}%")) # 模糊匹配商品名稱 (不區分大小寫)
    if sku:
        query = query.where(Product.sku == sku.upper()) # 精確匹配 SKU (轉換為大寫)

    # 3. 執行查詢獲取所有相關庫存項目及其商品資訊
    results = session.exec(query).all()

    # 4. 處理查詢結果，將數據按商品 ID 進行匯總
    inventory_map = {} # 用於暫存和匯總數據，key 為 product.id
    for item, product in results:
        if product.id not in inventory_map:
            # 如果是該商品第一次出現，則初始化其概覽資訊
            inventory_map[product.id] = {
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku,
                "total_quantity": 0, # 初始化總數量
                "locations": [] # 初始化分位置庫存列表
            }
        # 累加總數量
        inventory_map[product.id]["total_quantity"] += item.quantity
        # 記錄該商品在特定位置的庫存細節
        inventory_map[product.id]["locations"].append(LocationQuantity(location=item.location, quantity=item.quantity))

    # 5. 將匯總後的數據轉換為列表，並應用分頁
    overview_list = list(inventory_map.values())[offset : offset + limit]

    return overview_list

def get_low_stock_alerts(session: Session) -> List[LowStockAlert]:
    """
    獲取所有低於安全庫存閾值的商品警報。
    一個商品被視為低庫存，如果其所有位置的總庫存量低於其所有位置的安全庫存總和。

    Args:
        session: 資料庫 Session 物件。

    Returns:
        List[LowStockAlert]: 包含所有低庫存警報的列表。
    """
    # 1. 查詢總庫存量低於總安全庫存量的商品
    # 這裡聯接 Product 和 WarehouseItem 表，按 Product ID 分組，
    # 計算每個商品的總庫存量和總安全庫存量，
    # 然後篩選出總庫存量小於總安全庫存量的商品。
    query = select(
        Product.id,
        Product.name,
        Product.sku,
        func.sum(WarehouseItem.quantity).label("total_quantity"), # 計算總庫存量
        func.sum(WarehouseItem.safety_stock).label("total_safety_stock") # 計算總安全庫存量
    ).join(WarehouseItem).group_by(Product.id).having( # 按 Product ID 分組，然後應用 HAVING 條件
        func.sum(WarehouseItem.quantity) < func.sum(WarehouseItem.safety_stock)
    )

    low_stock_products = session.exec(query).all() # 執行查詢

    alerts = [] # 用於存放低庫存警報
    for product_id, product_name, sku, current_stock, safety_stock in low_stock_products:
        # 對於每個低庫存商品，進一步查詢其分位置庫存詳情
        location_items = session.exec(
            select(WarehouseItem.location, WarehouseItem.quantity).where(
                WarehouseItem.product_id == product_id
            )
        ).all()
        # 將查詢結果轉換為 LocationQuantity 對象列表
        location_details = [LocationQuantity(location=loc, quantity=qty) for loc, qty in location_items]

        # 創建 LowStockAlert 對象並加入警報列表
        alerts.append(LowStockAlert(
            product_id=product_id,
            product_name=product_name,
            sku=sku,
            current_stock=current_stock,
            safety_stock=safety_stock,
            location_details=location_details # 包含分位置庫存詳情
        ))
    return alerts # 返回低庫存警報列表