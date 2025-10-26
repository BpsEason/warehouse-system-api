# 倉儲物流系統教學專案

本檔案提供明確的上手指引、教學重點與工程師交接清單，讓開發者能在 30–60 分鐘內完成環境準備並立即開始實作或教學。專案技術棧：FastAPI、SQLModel (Pydantic v2)、Alembic、Poetry、Docker。

---

### 1. 目的與能學到的重點
- 快速建立可執行的倉儲 API，包含商品、庫存項目與出入庫 Movement 的完整流程。  
- 學會以 transaction 保證入庫/出庫原子性、使用 SELECT FOR UPDATE 在 Postgres 下防止競賣。  
- 操作 Alembic 的 autogenerate → 人工審核 → upgrade 工作流程，理解 schema 演化要點（enum、index、rename、backfill）。  
- 使用 Poetry 管理依賴、撰寫 pytest（單元與整合測試）並在 CI 中自動化 lint/test/migration-smoke。  
- 使用 Docker + docker-compose 本地模擬生產環境（可選 PostgreSQL），理解容器化與日誌設計（stdout 優先）。

---

### 2. 最短上手步驟（工程師 5–30 分鐘完成）
前提：安裝 Python 3.10+、Poetry、Docker（選用）、Git。

- 取得程式碼
  - git clone https://github.com/BpsEason/warehouse-system-api.git
  - cd warehouse-system-api

- 建立環境檔
  - cp .env.example .env
  - 編輯 .env：設定 DATABASE_URL（開發可留 sqlite:///./data/warehouse.db）、APP_SECRET_KEY（本地可用測試字串）

- 安裝依賴
  - pip install poetry
  - poetry install

- 建資料表（開發快速啟動）
  - 設定 .env 中 CREATE_TABLES_ON_STARTUP="true"
  - poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

- 或者使用 Alembic（推薦流程）
  - poetry run alembic revision --autogenerate -m "Initial"
  - 檢查 alembic/versions/*.py 並修正
  - poetry run alembic upgrade head
  - poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

- 測試 API（Swagger）
  - 開啟 http://localhost:8000/docs

- Docker（可選）
  - docker-compose build
  - docker-compose up -d
  - docker-compose exec web poetry run alembic upgrade head

---

### 3. 必讀概念（每位工程師上線前需理解）
- 模型責任：
  - **Product**：商品主資料（sku 唯一）。  
  - **WarehouseItem**：特定位址的商品庫存（quantity >= 0）。  
  - **Movement**：每次入/出庫的不可刪減稽核紀錄（每個被扣減的 warehouse_item 都要有一筆 Movement）。  
- 交易一致性：
  - 所有庫存變更在單一 transaction 完成（Session.begin()）。  
  - 在 Postgres 生產環境於扣庫查詢使用 SELECT ... FOR UPDATE 鎖定行以防競賣。  
- API 設計原則：
  - 端點只做驗證與授權，業務邏輯在 services 層實作以利單元測試。  
  - 禁止直接 PATCH quantity；數量改動必須透過 stock-in / stock-out。  
- 遷移實務：
  - autogenerate 僅輔助產出，遷移腳本必須人工審核（enum、index、欄位 rename、backfill）。  
- 日誌與 Secrets：
  - 生產日誌輸出到 stdout；不將 secrets 提交到 repo，使用 Secret Manager 或 CI 注入。

---

### 4. 快速檢查清單（Onboarding checklist）
- [ ] 本機能執行 poetry install 並啟動 uvicorn（或透過 Docker）。  
- [ ] Swagger /docs 可操作 create product、create warehouse-item、stock-in、stock-out。  
- [ ] Alembic autogenerate + upgrade head 在本地成功（並檢查 migration 檔內容）。  
- [ ] 測試：poetry run pytest 至少包含 CRUD 與 stock-in/out 測試。  
- [ ] .env.example 存在且 .env 已加入 .gitignore。  
- [ ] Dockerfile 與 docker-compose 已能在本地建置並啟動（含可選 db）。  
- [ ] 了解如何在 Postgres 啟用 SELECT FOR UPDATE 並在服務層使用 .with_for_update()。

---

### 5. 常用命令速查（可複製到團隊 README snippet）
- 安裝與啟動（開發）
  - pip install poetry
  - poetry install
  - poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
- Alembic
  - poetry run alembic revision --autogenerate -m "msg"
  - poetry run alembic upgrade head
- 測試與 lint
  - poetry run pytest -q
  - poetry run ruff check .
  - poetry run black .
- Docker
  - docker-compose build
  - docker-compose up -d
  - docker-compose exec web poetry run alembic upgrade head

---

### 6. 典型 onboarding 任務（前 2 小時）
1. 在本機啟動專案，完成一次從建立 Product → 建立 WarehouseItem → stock-in → stock-out 的完整流程，並截圖 Swagger 操作畫面（30–45 分）。  
2. 閱讀 services 層 stock_out 實作，說明在 multi-location 出庫時如何分割扣減並建立 Movement（15 分）。  
3. 以 Postgres 啟動 docker-compose，模擬兩個並行 client 執行相同出庫請求，確認是否產生負庫存；若出現負庫存，修改 service 加入 with_for_update 並重測（60 分）。  
4. 產生 Alembic migration 並提交 PR，PR 包含 migration 檔的簡短審核說明（30 分）。

---

### 7. 教學範例：必教示範片段（可直接在課堂 demo）
- 事務與 flush 示範（概念 + 5 行程式碼）：show session.begin()、session.flush() 後如何取得新 id。  
- SELECT FOR UPDATE 示範（Postgres）：展示 without lock vs with_for_update 的行為差異（實測兩個連線）。  
- Alembic autogenerate demo：產生 migration → 手動修正 enum/unique → upgrade → rollback。

---

### 8. 常見問題與快速排錯
- Alembic autogenerate 產生空 migration：檢查 alembic/env.py 是否 import app.models 並設定 target_metadata = SQLModel.metadata。  
- uvicorn import error main:app：確認 PYTHONPATH 與 uvicorn target（app.main:app vs main:app）一致。  
- psycopg2 編譯錯誤（Docker）：在 builder 階段安裝 libpq-dev 與 build-essential。  
- 測試在 SQLite 與 Postgres 行為差異：sqlite 沒有 row-level for update 行為，請在 Postgres 上驗證 SELECT FOR UPDATE。

---

### 9. 團隊建議與協作規範（快速同步）
- Pull Request 規範：
  - 一個 PR 僅處理一個功能或一個 migration。  
  - 若修改 schema，請同時提交 migration 檔並在 PR 描述說明關鍵變更與必要的 backfill。  
- Code Style：
  - 使用 ruff + black + isort，自動化 pre-commit 建議。  
- Review 重點：
  - Migration 是否會導致資料丟失；是否包含 enum/rename 的手動處理。  
  - Services 層是否有明確的事務邊界與錯誤處理。  
  - 日誌與 secret 是否有洩露風險。  
- 上線前檢核：
  - .env 不包含 secrets，部署使用 secrets manager；遷移在 staging 成功後再上 production。
