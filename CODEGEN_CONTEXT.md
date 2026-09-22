# Apparel POS — コード生成用コンテキスト

このリポジトリに新しいコードを追加・修正する際に、既存の実装パターンから逸脱しないための詳細リファレンス。プロジェクト概要・業務ルール・稼働状況は `PROJECT_CONTEXT.md` を参照。本ファイルは「どう書くか」に特化する。

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

1. **`models/`**: 新テーブルが要るならモデルを追加し、`alembic revision --autogenerate` でマイグレーション生成（後述）
2. **`schemas/`**: `XxxRequest` / `XxxResponse` を Pydantic `BaseModel` で定義
3. **`crud/`**: DBアクセス関数を追加。関数名は `get_xxx_by_yyy` / `create_xxx` / `get_xxx_for_update`（行ロックが要る場合）のパターンに合わせる
4. **`services/`**: 業務ロジック本体。エラーは専用の例外クラス（下記パターン）で表現する
5. **`api/v1/endpoints/`**: `try/except` でservicesの例外をHTTPExceptionに変換
6. **`api/v1/router.py`**: 新しい`APIRouter`を`include_router`する
7. テストを`backend/tests/`に追加（後述のフィクスチャ規約に従う）

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

`detail`は必ず `{"error": "SNAKE_CASE_CODE", ...関連フィールド}` の形（文字列直書きにしない）。フロントの `getErrorMessage()` は `detail.message` → `detail.error` の順で拾うため、`message`が無いと生のエラーコード文字列がそのままUIに出る（既知の仕様、意図的にユーザー向け文言へ丁寧化していない箇所が残っている）。

### 権限チェック

```python
_require_manager_or_admin = require_roles([RoleEnum.MANAGER, RoleEnum.ADMIN])

@router.put("/xxx/{id}", response_model=XxxResponse)
async def update_xxx(
    id: str, payload: XxxRequest, db: DbSession,
    _current_staff: Annotated[Staff, Depends(_require_manager_or_admin)],
) -> XxxResponse: ...
```

閲覧系（GET）は基本的に `CurrentStaff`（全ロール可）。書き込み系は業務の重要度に応じて `require_roles([...])` を付ける（`app/api/deps.py`）。ロール階層は `STAFF < MANAGER < ADMIN`（`app/models/enums.py::RoleEnum`）。

### 非同期SQLAlchemyの既知の落とし穴

- **`await db.rollback()` の直後にORM属性へアクセスしない。** greenlet外での暗黙lazy-loadが `MissingGreenlet` になる。rollback前に必要な値をローカル変数へ退避してから呼ぶこと。
- **flush直後、そのセッション内で同じ行を再クエリしない。** identity mapが古いまま返ることがある。必要な値はflush前にPython側の変数として保持する。
- 行ロックが必要な処理（会計、在庫更新）は `crud/*.py` に `get_xxx_for_update()`（`.with_for_update()`付き）を用意し、servicesはそれを使う。

---

## 2. データモデル完全リファレンス

`server_default` があるカラムは新規作成時に省略可能。`Mapped[X | None]` はNULL許容。

### `staff`（`app/models/staff.py`）
| カラム | 型 | 備考 |
|---|---|---|
| `staff_id` | `String(32)` PK | |
| `staff_name` | `String(64)` | |
| `password_hash` | `String(255)` | Argon2（`app.core.security.hash_password`） |
| `role` | `Enum(RoleEnum)` | default `STAFF` |
| `is_active` | `Boolean` | default `1` |
| `created_at`/`updated_at` | `TimestampMixin` | |

### `members`
| カラム | 型 | 備考 |
|---|---|---|
| `member_id` | `String(32)` PK | |
| `member_name` | `String(128)` | |
| `phone_number` | `String(32)?` | |
| `address` | `String(255)?` | |
| `gender` | `String(16)?` | |
| `age` | `Integer?` | |
| `point_balance` | `Integer` | default `0` |

### `products`
| カラム | 型 | 備考 |
|---|---|---|
| `product_id` | `String(32)` PK | |
| `product_name` | `String(128)` | |
| `category` | `String(64)` | |
| `default_price` | `Integer` | |
| `image_url` | `String(512)?` | |
| `size_system_id` / `color_system_id` | `String(32)?` | 商品全体で使うサイズ/カラー体系（任意） |
| `is_active` | `Boolean` | default `1` |

### `skus`
| カラム | 型 | 備考 |
|---|---|---|
| `sku_id` | `String(64)` PK | |
| `product_id` | `String(32)` FK→products, RESTRICT | |
| `barcode_ean13` | `String(13)` **UNIQUE** | |
| `size_system_id`+`size_code` | 複合FK→size_masters, RESTRICT | |
| `color_system_id`+`color_code` | 複合FK→color_masters, RESTRICT | |
| `store_stock` / `warehouse_stock` | `Integer` | default `0`、`store_stock >= 0` CHECK制約 |
| `location` | `String(32)?` | |
| `is_active` | `Boolean` | default `1` |
| **制約** | `UniqueConstraint(product_id, size_code, color_code)` 名前 `uq_sku_product_size_color` | 2026-09-20追加。違反時は`DuplicateSkuVariantError`→409 |

### `price_histories`
`price_history_id`(PK) / `product_id`(FK) / `sku_id`(FK, NULL可=商品全体) / `price` / `valid_from` / `valid_to`(NULL=無期限) / `is_active`

### `discount_masters`
`discount_id`(PK) / `target_type`(`SKU`|`PRODUCT`|`MEMBER`) / `product_id`(FK, NULL可) / `sku_id`(FK, NULL可) / `discount_type`(`RATE`|`AMOUNT`) / `discount_value`(`Numeric(10,2)`) / `valid_from` / `valid_to` / `priority`(Integer、複数該当時は`_select_best_discount`で解決) / `is_active`

`target_type=MEMBER`の場合、`product_id`・`sku_id`ともに`NULL`（特定会員に紐付くのではなく「会員向け全体値引き」）。

### `size_masters` / `color_masters`
複合PK（`{size,color}_system_id` + `{size,color}_code`）、`{size,color}_name`、`display_order`（Integer, default 0）、`is_active`

### `tax_rates`
`tax_rate_id`(PK) / `tax_rate`(`Numeric(5,2)`) / `valid_from` / `valid_to`(NULL可) / `is_active`。有効判定は `crud/tax.py::get_active_tax_rate(db, now)`。

### `transactions`
`transaction_id`(PK) / `member_id`(FK, NULL可) / `staff_id`(FK) / `payment_method`(Enum) / `subtotal_ex_tax` / `discount_total`(default 0) / `tax_amount` / `total_inc_tax` / `tx_type`(`SALE`|`RETURN`|`EXCHANGE`, default `SALE`) / `parent_transaction_id`(自己参照FK、返品/交換の元取引)

### `sales_items`
`item_id`(PK, autoincrement) / `transaction_id`(FK) / `sku_id`(FK) / `product_id`(FK) / `quantity` / `unit_price_snapshot` / `discount_amount_snapshot`(default 0) / `tax_rate_snapshot`(`Numeric(5,2)`) / `tax_amount_snapshot` / `line_total_ex_tax` / `line_total_inc_tax`

返品明細は `quantity` が負数で記録される（`pos_service.refund_exchange`参照）。

### `inventory_histories`
`inventory_history_id`(PK, autoincrement, BigInteger) / `sku_id`(FK) / `location`(`STORE`|`WAREHOUSE`文字列) / `quantity_delta` / `movement_type`(`RECEIPT`|`SALE`|`RETURN`|`TRANSFER`|`ADJUSTMENT`) / `transaction_id`(FK, NULL可) / `staff_id`(FK)

### 共通Mixin（`app/models/base.py`）
- `CreatedAtMixin`: `created_at`（`CURRENT_TIMESTAMP`）
- `TimestampMixin(CreatedAtMixin)`: `updated_at`（`ON UPDATE CURRENT_TIMESTAMP`）も追加
- `MYSQL_TABLE_ARGS = {mysql_engine: InnoDB, mysql_charset: utf8mb4, mysql_collate: utf8mb4_bin}` を全テーブルの `__table_args__` に含める

### Enum一覧（`app/models/enums.py`、すべて`StrEnum`）
`RoleEnum`(STAFF/MANAGER/ADMIN) · `PaymentMethodEnum`(CASH/CREDIT_CARD/QR_CODE/IC) · `TransactionTypeEnum`(SALE/RETURN/EXCHANGE) · `DiscountTargetTypeEnum`(SKU/PRODUCT/MEMBER) · `DiscountTypeEnum`(RATE/AMOUNT) · `MovementTypeEnum`(RECEIPT/SALE/RETURN/TRANSFER/ADJUSTMENT)

---

## 3. マイグレーション運用

```bash
# モデル変更後、必ずこの順で
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

## 4. テストのフィクスチャ規約

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

## 5. フロントエンドの実装パターン

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

---

## 6. 環境・デプロイ運用の落とし穴

- **Docker Composeの新規ファイルはコンテナ再起動が要る場合がある。** 開発サーバーのファイル監視が新規ファイル追加を検知しないことがあるため、新しいAPIルート/ページを追加したら `docker compose restart frontend`（or backend）を試す
- **Azure Container Appsは`--image`を`:latest`のまま`update`しても再Pullされないことがある。** 必ず `--revision-suffix <一意な文字列>` を付けて新リビジョンを強制する
- **`az acr build`のログストリームがWindows端末でcp932エンコードエラーによりクラッシュすることがある。** これは表示上のバグでビルド自体は継続している。`az acr task list-runs --top 1 --query "[0].status"` で実際の結果を確認する
- **git管理下でのCRLF警告（`LF will be replaced by CRLF`）は無害。** Windows環境の`core.autocrlf`によるもので、コミット自体は成功する
- **Azure MySQLのパスワードに`&`, `@`等が含まれる場合、接続文字列に埋め込む前に`urllib.parse.quote_plus()`でURLエンコードする**（Cloud Shellでの手動接続時によく踏む）

---

## 7. コマンド早見表

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
