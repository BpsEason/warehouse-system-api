import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_session
from app.models import Product, WarehouseItem, Movement, MovementType

@pytest.fixture(name="session")
def session_fixture():
    """測試用的資料庫 session fixture，使用 in-memory SQLite，避免影響真實資料庫。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    """測試用的 FastAPI 客戶端 fixture，覆寫 session 依賴以使用測試資料庫。"""
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_create_product(client: TestClient):
    """測試創建產品端點：驗證是否能成功新增產品，並檢查回傳資料和 HTTP 狀態碼。"""
    response = client.post(
        "/api/v1/products/",
        json={"name": "測試產品", "sku": "TEST123", "price": 10.0, "description": "這是測試描述"},
    )
    data = response.json()
    assert response.status_code == 201
    assert data["name"] == "測試產品"
    assert data["sku"] == "TEST123"
    assert data["price"] == 10.0
    assert "id" in data  # 確保有生成 ID

def test_get_product(client: TestClient, session: Session):
    """測試獲取單一產品端點：先新增產品，然後查詢，驗證資料正確。"""
    # 先新增一個產品
    product = Product(name="測試產品2", sku="TEST456", price=20.0)
    session.add(product)
    session.commit()
    session.refresh(product)

    response = client.get(f"/api/v1/products/{product.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "測試產品2"
    assert data["sku"] == "TEST456"

def test_get_product_not_found(client: TestClient):
    """測試獲取不存在產品：驗證回傳 404 錯誤。"""
    response = client.get("/api/v1/products/9999")
    assert response.status_code == 404
    assert "商品不存在" in response.json()["detail"]  # 假設自定義錯誤訊息是中文

def test_update_product(client: TestClient, session: Session):
    """測試更新產品端點：修改名稱和價格，驗證更新成功。"""
    # 先新增一個產品
    product = Product(name="舊產品", sku="OLD123", price=15.0)
    session.add(product)
    session.commit()
    session.refresh(product)

    response = client.patch(
        f"/api/v1/products/{product.id}",
        json={"name": "新產品", "price": 25.0},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "新產品"
    assert data["price"] == 25.0

def test_stock_in(client: TestClient, session: Session):
    """測試入庫端點：新增庫存項目，驗證數量增加和 Movement 記錄。"""
    # 先新增一個產品
    product = Product(name="庫存產品", sku="STOCK123", price=30.0)
    session.add(product)
    session.commit()
    session.refresh(product)

    response = client.post(
        "/api/v1/warehouse-items/",
        json={"product_id": product.id, "quantity": 100, "location": "A1", "remarks": "首次入庫"},
    )
    data = response.json()
    assert response.status_code == 201
    assert data["quantity"] == 100
    assert data["location"] == "A1"

    # 檢查 Movement 記錄
    movement = session.exec(select(Movement).where(Movement.product_id == product.id)).first()
    assert movement.movement_type == MovementType.IN
    assert movement.quantity == 100

def test_stock_out_insufficient(client: TestClient, session: Session):
    """測試出庫端點（庫存不足情境）：驗證回傳 400 錯誤。"""
    # 先新增產品和少量庫存
    product = Product(name="出庫產品", sku="OUT123", price=40.0)
    session.add(product)
    session.commit()
    session.refresh(product)

    warehouse_item = WarehouseItem(product_id=product.id, quantity=50, location="B2")
    session.add(warehouse_item)
    session.commit()

    response = client.post(
        "/api/v1/warehouse-items/stock-out",
        json={"product_id": product.id, "quantity": 100, "remarks": "出庫測試"},
    )
    assert response.status_code == 400
    assert "庫存不足" in response.json()["detail"]  # 假設自定義錯誤訊息

# 可以繼續添加更多測試，如 delete_product、get_low_stock_alerts 等