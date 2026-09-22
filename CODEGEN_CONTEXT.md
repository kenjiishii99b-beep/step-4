# Apparel POS — コード生成用コンテキスト

このリポジトリに新しいコードを追加・修正する際に、既存の実装パターンから逸脱しないための詳細リファレンス。プロジェクト概要・業務ルール・稼働状況は `PROJECT_CONTEXT.md` を参照。本ファイルは「どう書くか」＋「今ある型・エンドポイントの正確な形」を、他のファイルを開かなくても新しいコードを書けるレベルで網羅する。

---

## 1. レイヤー構成と処理の流れ（バックエンド）

新機能を追加するときは、必ずこの順で実装する。**エンドポイント関数の中に業務ロジックを書かない。**

```
api/v1/endpoints/*.py  … HTTPリクエスト/レスポンスの受け渡しと例外→HTTPステータス変換のみ
        ↓ 呼ぶ
services/*.py          … 業務ロジック（値引き計算、在庫引当、検証）。カスタム例外を投げる
        ↓ 呼ぶ
crud/*.py              … 素のSELECT/INSERT/UPDATE。業務ロジックを持たない
        ↓ 操作する
models/*.py            … SQLAlchemyモデル（DBスキーマそのもの）
```

`schemas/*.py`（Pydantic）はこの流れとは別軸で、エンドポイントの入出力形状のみを定義する。

### 新しいエンドポイントを追加する手順（テンプレート）

1. **`models/`**: 新テーブルが要るならモデルを追加し、`alembic revision --autogenerate` でマイグレーション生成（§6）
2. **`schemas/`**: `XxxRequest` / `XxxResponse` を Pydantic `BaseModel` で定義（§3のパターンに合わせる）
3. **`crud/`**: DBアクセス関数を追加。関数名は `get_xxx_by_yyy` / `create_xxx` / `get_xxx_for_update`（行ロックが要る場合）のパターンに合わせる
4. **`services/`**: 業務ロジック本体。エラーは専用の例外クラス（下記パターン）で表現する
5. **`api/v1/endpoints/`**: `try/except` でservicesの例外をHTTPExceptionに変換
6. **`api/v1/router.py`**: 新しい`APIRouter`を`include_router`する（`tags=["xxx"]`を付ける）
7. テストを`backend/tests/`に追加（§7のフィクスチャ規約に従う）
8. フロントで使うなら `frontend/src/types/api.ts` に対応する型を追加する（§8）

### エラーハンドリングパターン（必須で踏襲する）

servicesは**専用の例外クラス**を投げ、エンドポイントがHTTPExceptionへ変換する。生のSQLAlchemy例外やassertを直接HTTPに漏らさない。

```python
# services/xxx_service.py
class XxxNotFoundError(Exception):
    def __init__(self, xxx_id: str) -> None:
        self.xxx_id = xxx_id

async def get_xxx(db: AsyncSession, xxx_id: str) -> Xxx:
    obj = await get_xxx_by_id(db, xxx_id)
    if obj is None:
        raise XxxNotFoundError(xxx_id)
    return obj
```

```python
# api/v1/endpoints/xxx.py
@router.get("/xxx/{xxx_id}", response_model=XxxResponse)
async def get_xxx(xxx_id: str, db: DbSession, _current_staff: CurrentStaff) -> XxxResponse:
    try:
        obj = await xxx_service.get_xxx(db, xxx_id)
    except xxx_service.XxxNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "XXX_NOT_FOUND", "xxx_id": exc.xxx_id},
        ) from exc
    return _to_response(obj)
```

`detail`は必ず `{"error": "SNAKE_CASE_CODE", ...関連フィールド}` の形（文字列直書きにしない）。フロントの `getErrorMessage()`（`frontend/src/lib/errors.ts`）は次の優先順で拾う: `detail`が文字列ならそのまま／配列（Pydanticバリデーションエラー）なら`msg`を結合／オブジェクトなら`detail.message`→`detail.error`の順。**`message`フィールドを持たせない限り、生のエラーコード文字列がそのままUIに出る**（既存コードにも意図的にそうなっている箇所がある。ユーザー向け文言が必要なら`message`を追加する）。

### 権限チェック

```python
_require_manager_or_admin = require_roles([RoleEnum.MANAGER, RoleEnum.ADMIN])

@router.put("/xxx/{id}", response_model=XxxResponse)
async def update_xxx(
    id: str, payload: XxxRequest, db: DbSession,
    _current_staff: Annotated[Staff, Depends(_require_manager_or_admin)],
) -> XxxResponse: ...
```

`require_roles()`・`CurrentStaff`・`DbSession` はすべて `app/api/deps.py` からimportする：

```python
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentStaff = Annotated[Staff, Depends(get_current_active_staff)]  # 認証済みなら誰でも

def require_roles(allowed_roles: list[RoleEnum]):
    def role_checker(current_user: CurrentStaff) -> Staff:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="操作を行う権限がありません。")
        return current_user
    return role_checker
```

閲覧系（GET）は基本的に `CurrentStaff`（全ロール可）。書き込み系は業務の重要度に応じて `require_roles([...])` を付ける。ロール階層は `STAFF < MANAGER < ADMIN`。認証エンドポイント自体（`/auth/login`, `/auth/refresh`）と`/health`だけは`CurrentStaff`すら不要（未ログインでも叩ける）。

### 非同期SQLAlchemyの既知の落とし穴

- **`await db.rollback()` の直後にORM属性へアクセスしない。** greenlet外での暗黙lazy-loadが `MissingGreenlet` になる。rollback前に必要な値をローカル変数へ退避してから呼ぶこと。
- **flush直後、そのセッション内で同じ行を再クエリしない。** identity mapが古いまま返ることがある。必要な値はflush前にPython側の変数として保持する。
- 行ロックが必要な処理（会計、在庫更新）は `crud/*.py` に `get_xxx_for_update()`（`.with_for_update()`付き）を用意し、servicesはそれを使う。

---

## 2. データモデル完全リファレンス（SQLAlchemy, `app/models/`）

`server_default` があるカラムは新規作成時に省略可能。`Mapped[X | None]` はNULL許容。共通: `MYSQL_TABLE_ARGS = {mysql_engine: InnoDB, mysql_charset: utf8mb4, mysql_collate: utf8mb4_bin}`。`CreatedAtMixin`→`created_at`、`TimestampMixin(CreatedAtMixin)`→+`updated_at`。

### `staff`
| カラム | 型 | 備考 |
|---|---|---|
| `staff_id` | `String(32)` PK | |
| `staff_name` | `String(64)` | |
| `password_hash` | `String(255)` | Argon2（`app.core.security.hash_password`） |
| `role` | `Enum(RoleEnum)` | default `STAFF` |
| `is_active` | `Boolean` | default `1` |
| + `TimestampMixin` | | |

### `members`
`member_id`(`String(32)`PK) / `member_name`(`String(128)`) / `phone_number`(`String(32)?`) / `address`(`String(255)?`) / `gender`(`String(16)?`) / `age`(`Integer?`) / `point_balance`(`Integer`, default 0) / + `TimestampMixin`

### `products`
`product_id`(`String(32)`PK) / `product_name`(`String(128)`) / `category`(`String(64)`) / `default_price`(`Integer`) / `image_url`(`String(512)?`) / `size_system_id`・`color_system_id`(`String(32)?`, 商品全体の既定体系) / `is_active`(default 1) / + `TimestampMixin`

### `skus`
| カラム | 型 | 備考 |
|---|---|---|
| `sku_id` | `String(64)` PK | |
| `product_id` | `String(32)` FK→products, RESTRICT | |
| `barcode_ean13` | `String(13)` **UNIQUE** | |
| `size_system_id`+`size_code` | 複合FK→size_masters, RESTRICT | |
| `color_system_id`+`color_code` | 複合FK→color_masters, RESTRICT | |
| `store_stock` / `warehouse_stock` | `Integer`, default 0 | `store_stock >= 0` CHECK制約 |
| `location` | `String(32)?` | |
| `is_active` | `Boolean`, default 1 | |
| **制約** | `UniqueConstraint(product_id, size_code, color_code)` 名前`uq_sku_product_size_color` | 違反時`DuplicateSkuVariantError`→409 |
| + `CreatedAtMixin` | | |

### `price_histories`
`price_history_id`(`String(64)`PK) / `product_id`(FK) / `sku_id`(FK, NULL可=商品全体) / `price`(`Integer`) / `valid_from`(`DateTime`) / `valid_to`(`DateTime?`) / `is_active`

### `discount_masters`
`discount_id`(`String(64)`PK) / `target_type`(`Enum(DiscountTargetTypeEnum)`) / `product_id`(FK, NULL可) / `sku_id`(FK, NULL可) / `discount_type`(`Enum(DiscountTypeEnum)`) / `discount_value`(`Numeric(10,2)`) / `valid_from` / `valid_to`(NULL可) / `priority`(`Integer`) / `is_active`

`target_type=MEMBER`の場合、`product_id`・`sku_id`ともに`NULL`（特定会員に紐付くのではなく「会員向け全体値引き」）。複数該当時は`priority`昇順で`_select_best_discount()`が解決。

### `size_masters` / `color_masters`
複合PK（`{size,color}_system_id`+`{size,color}_code`）、`{size,color}_name`、`display_order`(`Integer`, default 0)、`is_active`

### `tax_rates`
`tax_rate_id`(`String(32)`PK) / `tax_rate`(`Numeric(5,2)`) / `valid_from` / `valid_to`(NULL可) / `is_active`。有効判定: `crud/tax.py::get_active_tax_rate(db, now)`。

### `transactions`
`transaction_id`(`String(64)`PK) / `member_id`(FK, NULL可) / `staff_id`(FK) / `payment_method`(`Enum(PaymentMethodEnum)`) / `subtotal_ex_tax`(`Integer`) / `discount_total`(`Integer`, default 0) / `tax_amount`(`Integer`) / `total_inc_tax`(`Integer`) / `tx_type`(`Enum(TransactionTypeEnum)`, default `SALE`) / `parent_transaction_id`(自己参照FK) / + `CreatedAtMixin`

### `sales_items`
`item_id`(`BigInteger`PK autoincrement) / `transaction_id`(FK) / `sku_id`(FK) / `product_id`(FK) / `quantity`(`Integer`, 返品明細は負数) / `unit_price_snapshot` / `discount_amount_snapshot`(default 0) / `tax_rate_snapshot`(`Numeric(5,2)`) / `tax_amount_snapshot` / `line_total_ex_tax` / `line_total_inc_tax`

### `inventory_histories`
`inventory_history_id`(`BigInteger`PK autoincrement) / `sku_id`(FK) / `location`(`String(32)`, `"STORE"`|`"WAREHOUSE"`) / `quantity_delta`(`Integer`) / `movement_type`(`Enum(MovementTypeEnum)`) / `transaction_id`(FK, NULL可) / `staff_id`(FK) / + `CreatedAtMixin`

### Enum一覧（`app/models/enums.py`、すべて`StrEnum`）
`RoleEnum`(STAFF/MANAGER/ADMIN) · `PaymentMethodEnum`(CASH/CREDIT_CARD/QR_CODE/IC) · `TransactionTypeEnum`(SALE/RETURN/EXCHANGE) · `DiscountTargetTypeEnum`(SKU/PRODUCT/MEMBER) · `DiscountTypeEnum`(RATE/AMOUNT) · `MovementTypeEnum`(RECEIPT/SALE/RETURN/TRANSFER/ADJUSTMENT)

---

## 3. Pydanticスキーマ完全リファレンス（`app/schemas/`）

以下はすべて実ファイルそのまま（省略なし）。新しいエンドポイントを作るときはこの粒度でバリデーションを書く。

### `auth.py`
```python
class LoginRequest(BaseModel):
    staff_id: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1)

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    staff_id: str
    staff_name: str
    role: RoleEnum

class RefreshRequest(BaseModel):
    refresh_token: str

class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    staff_id: str
    staff_name: str
    role: RoleEnum
```

### `staff.py`
```python
class StaffUpsertRequest(BaseModel):
    staff_id: str = Field(min_length=1, max_length=32)
    staff_name: str = Field(min_length=1, max_length=64)
    role: RoleEnum
    is_active: bool = True
    password: str | None = Field(default=None, min_length=8)  # 新規時必須、更新時省略で維持

class StaffResponse(BaseModel):
    staff_id: str
    staff_name: str
    role: RoleEnum
    is_active: bool

class StaffListResponse(BaseModel):
    items: list[StaffResponse]
    total: int
```

### `product.py`
```python
class SkuInput(BaseModel):
    sku_id: str = Field(min_length=1, max_length=64)
    barcode_ean13: str = Field(min_length=13, max_length=13)
    size_system_id: str = Field(min_length=1, max_length=32)
    size_code: str = Field(min_length=1, max_length=16)
    color_system_id: str = Field(min_length=1, max_length=32)
    color_code: str = Field(min_length=1, max_length=16)
    store_stock: int = Field(default=0, ge=0)
    warehouse_stock: int = Field(default=0, ge=0)
    location: str | None = Field(default=None, max_length=32)

class SkuResponse(BaseModel):
    sku_id: str
    barcode_ean13: str
    size_system_id: str
    size_code: str
    color_system_id: str
    color_code: str
    store_stock: int
    warehouse_stock: int
    location: str | None
    is_active: bool

class ProductCreateRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=32)
    product_name: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=64)
    default_price: int = Field(ge=0)
    image_url: str | None = Field(default=None, max_length=512)
    size_system_id: str | None = Field(default=None, max_length=32)
    color_system_id: str | None = Field(default=None, max_length=32)
    skus: list[SkuInput] = Field(default_factory=list, max_length=100)  # 登録と同時にSKUも作成

class ProductUpdateRequest(BaseModel):
    product_name: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=64)
    default_price: int = Field(ge=0)
    image_url: str | None = Field(default=None, max_length=512)
    size_system_id: str | None = Field(default=None, max_length=32)
    color_system_id: str | None = Field(default=None, max_length=32)
    is_active: bool = True
    skus: list[SkuInput] = Field(default_factory=list, max_length=100)  # 新規sku_idのみ追加登録される

class ProductResponse(BaseModel):
    product_id: str
    product_name: str
    category: str
    default_price: int
    image_url: str | None
    size_system_id: str | None
    color_system_id: str | None
    is_active: bool
    skus: list[SkuResponse]

class SkuLookupResponse(BaseModel):
    sku_id: str
    barcode_ean13: str
    product_id: str
    product_name: str
    reference_price: int  # 商品の定価。値引き・税込額は含まない概算表示専用
    size_code: str
    color_code: str
    store_stock: int
    is_active: bool
```
既存SKUの在庫数・バーコードは`ProductUpdateRequest`では上書きしない運用（在庫API `/inventory/receipt`, `/inventory/transfer` で履歴を残しながら変更する）。

### `member.py`
```python
class MemberUpsertRequest(BaseModel):
    member_name: str = Field(min_length=1, max_length=128)
    phone_number: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    gender: str | None = Field(default=None, max_length=16)
    age: int | None = Field(default=None, ge=0, le=150)
    point_balance: int | None = Field(default=None, ge=0)  # 新規時省略=0円、更新時省略=既存値維持

class MemberResponse(BaseModel):
    member_id: str
    member_name: str
    phone_number: str | None
    address: str | None
    gender: str | None
    age: int | None
    point_balance: int
```

### `masters.py`
```python
class DiscountUpsertRequest(BaseModel):
    discount_id: str = Field(min_length=1, max_length=64)
    target_type: DiscountTargetTypeEnum
    product_id: str | None = Field(default=None, max_length=32)
    sku_id: str | None = Field(default=None, max_length=64)
    discount_type: DiscountTypeEnum
    discount_value: Decimal = Field(ge=0)
    valid_from: datetime
    valid_to: datetime | None = None
    priority: int
    is_active: bool = True
    # model_validator(mode="after") _validate_target で以下を検証:
    #   SKU     → sku_idのみ必須、product_id不可
    #   PRODUCT → product_idのみ必須、sku_id不可
    #   MEMBER  → product_id・sku_idともに不可
    #   valid_to は valid_from より後
    #   discount_type=RATE の場合 discount_value <= 100

class DiscountResponse(BaseModel):
    discount_id: str
    target_type: DiscountTargetTypeEnum
    product_id: str | None
    sku_id: str | None
    discount_type: DiscountTypeEnum
    discount_value: Decimal
    valid_from: datetime
    valid_to: datetime | None
    priority: int
    is_active: bool

class TaxRateUpsertRequest(BaseModel):
    tax_rate_id: str = Field(min_length=1, max_length=32)
    tax_rate: Decimal = Field(ge=0, le=100)
    valid_from: datetime
    valid_to: datetime | None = None
    is_active: bool = True
    # valid_to > valid_from を検証

class TaxRateResponse(BaseModel):
    tax_rate_id: str
    tax_rate: Decimal
    valid_from: datetime
    valid_to: datetime | None
    is_active: bool
```

### `inventory.py`
```python
class StockLocation(StrEnum):
    STORE = "STORE"
    WAREHOUSE = "WAREHOUSE"

class InventoryStatusResponse(BaseModel):
    sku_id: str
    store_stock: int
    warehouse_stock: int

class InventoryReceiptRequest(BaseModel):
    sku_id: str = Field(min_length=1, max_length=64)
    location: StockLocation = StockLocation.STORE
    quantity: int = Field(ge=1)

class InventoryTransferRequest(BaseModel):
    sku_id: str = Field(min_length=1, max_length=64)
    from_location: StockLocation
    to_location: StockLocation
    quantity: int = Field(ge=1)
    # model_validator: from_location != to_location
```

### `pos.py`
```python
class CheckoutItemRequest(BaseModel):
    sku_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=99)

class CheckoutRequest(BaseModel):
    items: list[CheckoutItemRequest] = Field(min_length=1, max_length=100)
    client_total: int = Field(ge=0)
    payment_method: PaymentMethodEnum
    member_id: str | None = Field(default=None, max_length=32)
    amount_tendered: int | None = Field(default=None, ge=0)

class CheckoutResponse(BaseModel):
    transaction_id: str
    subtotal_ex_tax: int
    discount_total: int
    tax_amount: int
    total_inc_tax: int
    change: int

class RefundExchangeItemRequest(BaseModel):
    sku_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=99)

class RefundExchangeRequest(BaseModel):
    parent_transaction_id: str = Field(min_length=1, max_length=64)
    tx_type: TransactionTypeEnum  # RETURN or EXCHANGE のみ（SALEは拒否）
    return_items: list[RefundExchangeItemRequest] = Field(min_length=1, max_length=100)
    exchange_items: list[RefundExchangeItemRequest] = Field(default_factory=list, max_length=100)
    client_total: int  # 符号付き差額。マイナス=返金、プラス=追加支払い
    payment_method: PaymentMethodEnum
    amount_tendered: int | None = Field(default=None, ge=0)
    # model_validator: RETURNならexchange_items空必須、EXCHANGEならexchange_items必須

class RefundExchangeResponse(BaseModel):
    transaction_id: str
    parent_transaction_id: str
    tx_type: TransactionTypeEnum
    subtotal_ex_tax: int
    discount_total: int
    tax_amount: int
    total_inc_tax: int
    change: int
```

### `transaction.py`
```python
class SalesItemResponse(BaseModel):
    sku_id: str
    product_id: str
    quantity: int
    unit_price_snapshot: int
    discount_amount_snapshot: int
    tax_rate_snapshot: Decimal
    tax_amount_snapshot: int
    line_total_ex_tax: int
    line_total_inc_tax: int

class TransactionResponse(BaseModel):
    transaction_id: str
    member_id: str | None
    staff_id: str
    payment_method: PaymentMethodEnum
    subtotal_ex_tax: int
    discount_total: int
    tax_amount: int
    total_inc_tax: int
    tx_type: TransactionTypeEnum
    parent_transaction_id: str | None
    created_at: datetime
    items: list[SalesItemResponse]
```

---

## 4. APIエンドポイント完全一覧

baseは全て `/api/v1`。認証は`Authorization: Bearer <access_token>`（`/auth/*`, `/health`を除く）。

| メソッド | パス | 権限 | Request | Response | 主なエラー |
|---|---|---|---|---|---|
| GET | `/health` | 不要 | - | `{"status": "ok"}` | - |
| POST | `/auth/login` | 不要 | `LoginRequest` | `LoginResponse` | 401 (認証失敗), 429 (`AccountLockedError`、`Retry-After`ヘッダ) |
| POST | `/auth/refresh` | 不要 | `RefreshRequest` | `RefreshResponse` | 401 |
| GET | `/products/{product_id}` | 全ロール | - | `ProductResponse` | 404 `PRODUCT_NOT_FOUND` |
| POST | `/admin/products` | MANAGER+ | `ProductCreateRequest` | `ProductResponse` | 409 `PRODUCT_ALREADY_EXISTS`/`SKU_ALREADY_EXISTS`/`BARCODE_ALREADY_EXISTS`/`SKU_VARIANT_ALREADY_EXISTS`、404 `SIZE_MASTER_NOT_FOUND`/`COLOR_MASTER_NOT_FOUND` |
| PUT | `/admin/products/{product_id}` | MANAGER+ | `ProductUpdateRequest` | `ProductResponse` | 404 `PRODUCT_NOT_FOUND`、409/404同上 |
| GET | `/skus/barcode/{ean13}` | 全ロール | - | `SkuLookupResponse` | 404 `SKU_NOT_FOUND` |
| GET | `/skus/lookup?product_id=&size_code=&color_code=` | 全ロール | クエリパラメータ | `SkuLookupResponse` | 404 `SKU_NOT_FOUND`（手入力フォールバック用） |
| GET | `/members/{member_id}` | 全ロール | - | `MemberResponse` | 404 `MEMBER_NOT_FOUND` |
| PUT | `/members/{member_id}` | MANAGER+ | `MemberUpsertRequest` | `MemberResponse` | - |
| PUT | `/masters/discounts` | MANAGER+ | `DiscountUpsertRequest` | `DiscountResponse` | - |
| PUT | `/masters/tax-rates` | ADMIN | `TaxRateUpsertRequest` | `TaxRateResponse` | - |
| GET | `/inventory/{sku_id}` | 全ロール | - | `InventoryStatusResponse` | 404 |
| POST | `/inventory/receipt` | 全ロール | `InventoryReceiptRequest` | `InventoryStatusResponse` | 404 |
| POST | `/inventory/transfer` | MANAGER+ | `InventoryTransferRequest` | `InventoryStatusResponse` | 404, 409 (在庫不足) |
| POST | `/pos/checkout` | 全ロール | `CheckoutRequest` | `CheckoutResponse` | 404 `SKU_NOT_FOUND`/`MEMBER_NOT_FOUND`、409 `INSUFFICIENT_STOCK`、422 `PRICE_MISMATCH`/`INSUFFICIENT_PAYMENT`、500 `TAX_RATE_NOT_CONFIGURED` |
| POST | `/pos/refund-exchange` | 全ロール | `RefundExchangeRequest` | `RefundExchangeResponse` | 404 `PARENT_TRANSACTION_NOT_FOUND`/`SKU_NOT_FOUND`、409 `PARENT_TRANSACTION_NOT_ELIGIBLE`/`INSUFFICIENT_STOCK`、422 `RETURN_ITEM_NOT_IN_ORIGINAL_TRANSACTION`/`RETURN_QUANTITY_EXCEEDED`/`PRICE_MISMATCH`/`INSUFFICIENT_PAYMENT` |
| GET | `/transactions/{transaction_id}` | 全ロール | - | `TransactionResponse` | 404 |
| GET | `/admin/staff` | ADMIN | クエリ: `role?`, `is_active?` | `StaffListResponse` | - |
| POST | `/admin/staff` | ADMIN | `StaffUpsertRequest` | `StaffResponse` | 400 (新規時password省略), 409 (自己ロックアウト防止) |

「MANAGER+」= `require_roles([MANAGER, ADMIN])`。フロントのBFF経由パスは全て `/api/bff` を前置する（例: `/api/bff/pos/checkout`）。

---

## 5. 設定値・環境変数（`app/core/config.py`）

```python
class Settings(BaseSettings):
    PROJECT_NAME: str = "Apparel POS API"
    ENVIRONMENT: str = "local"                 # "production"でSwagger/ReDoc/OpenAPI無効化

    DATABASE_URL: str = "mysql+asyncmy://apparel_pos:apparel_pos_password@localhost:3306/apparel_pos"
    DATABASE_SSL: bool = False                  # Azure MySQLでは true 必須

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 480     # 8時間

    LOGIN_MAX_FAILURES: int = 5                 # staff_id単位のロック閾値
    LOGIN_MAX_FAILURES_PER_IP: int = 20         # IP単位のロック閾値（より緩い）
    LOGIN_LOCKOUT_MINUTES: int = 15

    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]
```
`.env`（`env_file=".env"`）または実際の環境変数から読み込む（`extra="ignore"`）。フロント側で対応する環境変数は `BACKEND_INTERNAL_URL`（BFFのみが参照、クライアント非公開）。

---

## 6. マイグレーション運用

```bash
docker compose exec backend alembic revision --autogenerate -m "説明"
# 生成されたファイルを backend/alembic/versions/ で目視レビュー（自動生成は誤検出することがある）
docker compose exec backend alembic upgrade head
docker compose exec backend pytest -q   # 既存データとの整合性を確認
```

**注意点:**
- `env.py` は `app.core.database` の `engine` を再利用する。DATABASE_SSL等の接続設定をここで重複定義しない
- `DATABASE_URL` にURLエンコード済みパスワード（`%40`等）が含まれる場合、`config.set_main_option()`に渡す前に `.replace("%", "%%")` でエスケープが必要（ConfigParserの補間構文と衝突するため。`env.py`で対応済み）
- 新しいUNIQUE/CHECK制約を追加する前に、既存データが違反していないか確認する（`SELECT ... GROUP BY ... HAVING COUNT(*) > 1`等）。違反があれば先にデータ側を是正してからマイグレーションを当てる

---

## 7. テストのフィクスチャ規約

### pytest（`backend/tests/`）
- 各テストファイルの先頭に **get-or-create ヘルパー**（`_ensure_xxx(db, ...)`）を書き、`module`スコープ`autouse=True`の1つのフィクスチャでまとめて呼ぶ
- IDは `AUTOTEST-<ファイル用途>-<役割>` 形式（例: `AUTOTEST-POS-STAFF`, `AUTOTEST-POS-SKU-MAIN`）。**新しいバーコードを使う前に、リポジトリ全体で重複していないか確認する**（`grep -rn "barcode_ean13.*['\"][0-9]\{13\}" backend/tests/`）
- 取引履歴は物理削除しない方針のため、fixtureは基本削除せず使い回す。数量・在庫などの可変フィールドだけテスト前にリセットする
- get-or-createの**更新パス（else節）で、作成時に渡した全フィールドを再代入し忘れない**こと（過去に`product_id`・`barcode_ean13`を更新パスで反映し忘れるバグを2回作っている。既存データと矛盾する新しい制約を追加する原因になる）
- 複合UNIQUE制約（`product_id, size_code, color_code`）に触れるフィクスチャを追加するときは、同じ商品を共有する別フィクスチャと組み合わせが衝突しないよう色/サイズを分ける

### Jest（`frontend/src/lib/*.test.ts`）
- 純粋関数のみを対象にする（`pos-calculations.ts`, `validation.ts`, `cart.ts`, `auth-context.tsx`）。DOM非依存のロジックは`.test.ts`、Reactコンポーネント/コンテキストは`.test.tsx`
- `jest.config.js`の`testPathIgnorePatterns`に`<rootDir>/e2e/`が必須（Playwrightの`*.spec.ts`をJestが誤って拾うため。実際にこの設定漏れで13スイートが壊れたことがある）

### Playwright（`frontend/e2e/`）
- 全テストが`fixtures.ts`の`login()`・`E2E_CASHIER`/`E2E_MANAGER`定数を共有する
- 固定フィクスチャ（商品・SKU・会員・値引き・STAFF/MANAGER/ADMINアカウント）は`backend/scripts/seed_e2e_fixtures.py`が投入する。**ローカル・Azure（gen12-mysql-pos）の両方に同じデータを入れているので、このスクリプトを編集したら両方に反映するのを忘れないこと**（過去に一度、ローカルだけ変更してコミットし忘れ、Azure側にE2E-ADMINが欠落した）
- 新しいテスト用バーコードは `29` プレフィックス + 正規のEAN-13チェックデジット計算で生成する（既存デモデータのプレフィックス`20`と衝突しない）。チェックデジット計算式は`seed_e2e_fixtures.py::_ean13_check_digit`と`e2e/fixtures.ts::ean13CheckDigit`に実装済み（両方とも同じロジックを維持すること）
- 100件近い連続操作を伴うテスト（例: `cart-sku-limit.spec.ts`）はReact再描画コストで遅くなるため、`test.setTimeout(60000)`で余裕を持たせる
- `getByText()`で一意に取れないボタン/ラベルが複数フォームに存在する場合（例:「SKU ID」「数量」が入荷登録フォームと在庫移動フォームの両方にある）、`page.locator("#specific-id")`で絞り込む

---

## 8. フロントエンドの実装パターン

### 新しいページを追加する
`frontend/src/app/(protected)/xxx/page.tsx`。ログイン必須ページは自動的に`(protected)/layout.tsx`が保護する。ロール制限が要るページは`RoleGate`でラップするか、`useAuth()`の`session.role`で分岐する（`members/page.tsx`のパターンを参照：閲覧は全ロール、編集フォームは`canEdit`条件で出し分け）。

### API呼び出し
`apiClient`（`src/lib/api-client.ts`、baseURL: `/api/bff`）を必ず経由する。バックエンドの物理URLを直接使わない。

```ts
const response = await apiClient.get<SkuLookup>(`/skus/barcode/${encodeURIComponent(code)}`);
```

エラー表示は`getErrorMessage(err, "デフォルト文言")`で正規化する（`src/lib/errors.ts`）。

### 新しい純粋関数ロジックを追加する
`src/lib/xxx.ts` に関数を書き、`src/lib/xxx.test.ts` に同名でJestテストを書く（既存の`pos-calculations.ts`/`validation.ts`/`cart.ts`と同じ並び）。**金額計算はフロントで完結させない**——プレビュー表示専用であることをコメントで明記し、確定額は必ずサーバー応答を使う。

### 新しいBFFルートを追加する
`src/app/api/bff/xxx/route.ts`。既存の`auth/login`等を参考に、`backendAuthUrl()`相当のヘルパーで内部URLを組み立てる。認証系以外は基本的に`[...path]/route.ts`のキャッチオールが自動転送するので、Cookie変換など特殊処理が要る場合のみ専用routeを作る。

### 削除・破壊的操作には確認ダイアログを挟む
`window.confirm()`パターン（`pos/page.tsx::removeLine`参照）。

### フロントエンドの型定義（`frontend/src/types/`）

`api.ts`と`auth.ts`はバックエンドのPydanticスキーマ（§3）と1:1対応させる。新しいバックエンドスキーマを追加したら、必ずこちらにも追加する。

```ts
// auth.ts
export type Role = "STAFF" | "MANAGER" | "ADMIN";
export interface StaffSession {
  access_token: string; token_type: string;
  staff_id: string; staff_name: string; role: Role;
}

// api.ts（抜粋パターン）
export type PaymentMethod = "CASH" | "CREDIT_CARD" | "QR_CODE" | "IC";
export type TransactionType = "SALE" | "RETURN" | "EXCHANGE";
export type StockLocation = "STORE" | "WAREHOUSE";
export type DiscountTargetType = "SKU" | "PRODUCT" | "MEMBER";
export type DiscountType = "RATE" | "AMOUNT";

export interface ApiErrorDetail {
  error: string;
  message?: string;
  [key: string]: unknown;
}
```

`ApiErrorDetail`は全エラーレスポンスの`detail`形状（§1のエラーパターンと対応）。数値型のDecimalフィールド（`discount_value`, `tax_rate`）はJSON上は文字列で来るため、TypeScript側では`string`型で受ける（`DiscountUpsertRequest.discount_value: string`等）。金額（円）は全て`number`（整数）。

---

## 9. 環境・デプロイ運用の落とし穴

- **Docker Composeの新規ファイルはコンテナ再起動が要る場合がある。** 開発サーバーのファイル監視が新規ファイル追加を検知しないことがあるため、新しいAPIルート/ページを追加したら `docker compose restart frontend`（or backend）を試す
- **Azure Container Appsは`--image`を`:latest`のまま`update`しても再Pullされないことがある。** 必ず `--revision-suffix <一意な文字列>` を付けて新リビジョンを強制する
- **`az acr build`のログストリームがWindows端末でcp932エンコードエラーによりクラッシュすることがある。** これは表示上のバグでビルド自体は継続している。`az acr task list-runs --top 1 --query "[0].status"` で実際の結果を確認する
- **git管理下でのCRLF警告（`LF will be replaced by CRLF`）は無害。** Windows環境の`core.autocrlf`によるもので、コミット自体は成功する
- **Azure MySQLのパスワードに`&`, `@`等が含まれる場合、接続文字列に埋め込む前に`urllib.parse.quote_plus()`でURLエンコードする**（Cloud Shellでの手動接続時によく踏む）

---

## 10. コマンド早見表

```bash
# バックエンド
docker compose exec backend pytest -q                          # 全テスト
docker compose exec backend pytest tests/test_pos_checkout.py -q  # 単一ファイル
docker compose exec backend alembic upgrade head
docker compose exec backend ruff check app
docker compose exec backend python -m scripts.seed_e2e_fixtures

# フロントエンド
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run lint
docker compose exec frontend npm run test        # Jest
cd frontend && npx playwright test               # Playwright（ホスト側、Docker外で実行）
```
