# コードマップ — 各ファイルの主な役割

Next.js（BFF）+ FastAPI + MySQL構成のアパレルPOSアプリ。バックエンド・フロントエンド合わせた全ファイルの役割を層ごとにまとめた一覧。

```
[ブラウザ] --HTTPS--> [Next.js: BFF]  --内部通信--> [FastAPI]  --SQLAlchemy--> [MySQL]
   UIのみ        /api/bff/** サーバー側      /api/v1/** 内部通信のみ        apparel_pos
```

---

## リポジトリ直下のドキュメント

| ファイル | 役割 |
|---|---|
| `CLAUDE.md` / `AGENTS.md` | プロジェクト概要・設計方針・コマンド集（Claude Code向け/Codex向け、同内容） |
| `PROJECT_CONTEXT.md` | アプリ全体のコンテキスト（業務ルール・権限・稼働環境・テスト状況・残課題） |
| `CODEGEN_CONTEXT.md` | コード生成用の技術リファレンス（レイヤーパターン・全スキーマ・全エンドポイント・設定値） |
| `CODE_EXPLAINED.md` | 主要ロジック（認証・会計・返品按分・カート管理・RBAC）の動きをコード引用付きで解説 |
| `CODE_MAP.md` | 本ファイル。全ファイルの役割一覧 |
| `CODE_REVIEW.md` | コードレビュー結果（重複SKU脆弱性の指摘と対応記録） |
| `OPERATIONS_MANUAL.md` | 店舗スタッフ向け操作マニュアル |
| `BACKEND_UNIT_TEST_RESULTS.md` / `FRONTEND_UNIT_TEST_RESULTS.md` | pytest・Jestの実行結果記録 |
| `Apparel_POS_Design_Specification_v1.5.5.md` | 詳細設計仕様書（UML・DDL・BFF対応表の一次情報） |
| `Apparel_POS_Requirements_v2.md` / `Apparel_POS_System_Specification.md` | 要件定義書・要件仕様書(SRS) |
| `test_specification_apparel_pos_v1.5.5-R1.md` | テスト仕様書・結果記録 |

---

## Backend（`backend/`）

### Core（`app/core/`, `app/main.py`, `app/api/deps.py`）

| ファイル | 役割 |
|---|---|
| `app/main.py` | FastAPIエントリポイント。ルーター登録、CORS設定、本番では`/docs`・`/redoc`・`/openapi.json`を無効化 |
| `app/core/config.py` | pydantic-settingsによる環境変数設定（DATABASE_URL、SECRET_KEY、トークン有効期限、ログイン試行回数上限など） |
| `app/core/database.py` | SQLAlchemy非同期エンジン・セッション生成。Azure MySQL向けTLS（SSLContext）設定、`get_db()`依存性注入 |
| `app/core/security.py` | Argon2パスワードハッシュ化・検証、JWTアクセス/リフレッシュトークンの発行・検証 |
| `app/core/rate_limit.py` | ログイン試行のレート制限（staff_id単位・IP単位を別しきい値で管理、インメモリ実装） |
| `app/api/deps.py` | `CurrentStaff`・`DbSession`依存性、`require_roles()`によるRBAC権限チェック |

### Models（`app/models/`、SQLAlchemy）

| ファイル | 役割 |
|---|---|
| `base.py` | `Base`宣言基底、`CreatedAtMixin`/`TimestampMixin`共通カラム、MySQL共通テーブル引数 |
| `enums.py` | Role・支払方法・取引種別・値引対象種別・値引種別・在庫移動種別の列挙型 |
| `staff.py` | `Staff`：担当者ID、パスワードハッシュ、ロール、有効フラグ |
| `member.py` | `Member`：会員情報、保有ポイント |
| `product.py` | `Product`・`Sku`（product_id+size_code+color_codeの複合UNIQUE制約含む）・`PriceHistory`・`DiscountMaster` |
| `master.py` | `SizeMaster`・`ColorMaster`・`TaxRate`（有効期間つきマスター） |
| `inventory.py` | `InventoryHistory`：入荷・移動・販売による在庫増減の履歴 |
| `transaction.py` | `Transaction`・`SalesItem`：会計・返品・交換の取引本体と明細（単価・値引・税のスナップショットを保持） |

### Schemas（`app/schemas/`、Pydantic）

| ファイル | 役割 |
|---|---|
| `auth.py` | ログイン・トークンリフレッシュのリクエスト/レスポンス |
| `staff.py` | スタッフ登録・更新・一覧のリクエスト/レスポンス |
| `product.py` | 商品・SKU登録/更新/検索のリクエスト/レスポンス（`SkuLookupResponse`はバーコード・手入力両方の検索結果形状） |
| `member.py` | 会員登録・更新・照会のリクエスト/レスポンス |
| `masters.py` | 値引き・税率マスターの登録・更新スキーマ |
| `pos.py` | 会計（checkout）・返品交換（refund-exchange）のリクエスト/レスポンス。`items`/`return_items`/`exchange_items`内の`sku_id`重複を拒否するバリデーションあり |
| `inventory.py` | 在庫照会・入荷登録・在庫移動のリクエスト/レスポンス、店舗/倉庫ロケーション種別 |
| `transaction.py` | 取引照会レスポンス（明細含む） |

### CRUD（`app/crud/`、DBアクセス）

| ファイル | 役割 |
|---|---|
| `staff.py` | スタッフのID検索・作成・一覧・件数取得（ロール/有効フラグ絞り込み） |
| `product.py` | 商品のID検索・複数一括取得・作成 |
| `sku.py` | SKUのID/バーコード/商品+サイズ+カラー検索、会計用の行ロック取得（`with_for_update`） |
| `master_reference.py` | サイズ・カラーマスターの存在確認 |
| `discount.py` | 有効な値引き（SKU/商品/会員対象、期間内）の取得 |
| `tax.py` | 指定日時で有効な税率の取得 |
| `pricing.py` | 有効な単価履歴（PriceHistory）の取得 |
| `member.py` | 会員のID検索・作成 |
| `pos.py` | 会計確定時の取引・明細・在庫履歴のまとめての永続化 |
| `transaction.py` | 取引の検索・行ロック取得、元取引の明細集計、返品済み数量の集計 |

### Services（`app/services/`、業務ロジック）

| ファイル | 役割 |
|---|---|
| `auth_service.py` | ログイン認証、アカウントロック判定、アクセス/リフレッシュトークン発行・検証 |
| `staff_service.py` | スタッフの新規登録・更新（自己ロックアウト防止、新規時パスワード必須の検証含む） |
| `product_service.py` | 商品+SKU登録・更新、バーコード/手入力（商品ID+サイズ+カラー）でのSKU検索、重複検証 |
| `member_service.py` | 会員の照会・新規登録/更新 |
| `master_service.py` | 値引き・税率マスターの登録・更新と対象種別（SKU/商品/会員）のバリデーション |
| `inventory_service.py` | 在庫照会、入荷登録、店舗⇔倉庫の在庫移動（行ロック・在庫マイナス防止） |
| `pos_service.py` | 中核。会計時のサーバー側金額再計算・値引き優先順位判定・在庫引当・預かり金額検証、返品/交換の按分計算と在庫復元 |
| `transaction_service.py` | 取引詳細（明細つき）の取得 |

### API Endpoints（`app/api/v1/`、`/api/v1/**`）

| ファイル | 役割 |
|---|---|
| `router.py` | 全エンドポイントをまとめる`APIRouter`集約 |
| `endpoints/health.py` | `GET /health`（死活監視用、認証不要） |
| `endpoints/auth.py` | `POST /auth/login`・`/auth/refresh` |
| `endpoints/admin_staff.py` | `/admin/staff`の一覧・登録・更新（ADMIN限定） |
| `endpoints/products.py` | 商品の照会（全ロール）・登録/更新（MANAGER+ADMIN） |
| `endpoints/skus.py` | `/skus/barcode/{ean13}`・`/skus/lookup`（商品ID+サイズ+カラーの手入力フォールバック） |
| `endpoints/members.py` | 会員の照会（全ロール）・登録/更新（MANAGER+ADMIN） |
| `endpoints/masters.py` | 値引き・税率マスターの更新（値引きはMANAGER+ADMIN、税率はADMIN限定） |
| `endpoints/inventory.py` | 在庫照会・入荷登録（全ロール）・在庫移動（MANAGER+ADMIN限定） |
| `endpoints/pos.py` | `/pos/checkout`・`/pos/refund-exchange`。金額不一致・預かり不足・在庫不足・重複SKUなどの例外を422/409で応答 |
| `endpoints/transactions.py` | `/transactions/{id}`取引照会 |

### Migrations（`alembic/`）

| ファイル | 役割 |
|---|---|
| `env.py` | Alembic実行環境。`app.core.database`のengineを再利用しSSL設定を一致させる。URLエンコード済みパスワード（%を含む）を安全に渡すエスケープ処理あり |
| `282982afbef1_...py` | 初期スキーマ（全テーブル作成） |
| `936f0e6b6f53_...py` | products・skusに`is_active`列を追加 |
| `e50042f113f2_...py` | 参照マスター（サイズ体系STANDARD、カラー体系BASIC、デフォルト税率）の初期投入 |
| `708b74c1cb7c_...py` | skusに`(product_id, size_code, color_code)`複合UNIQUE制約を追加 |

### Scripts（`backend/`）

| ファイル | 役割 |
|---|---|
| `generate_demo_products.py` | アパレル商品50種×SKU展開のデモデータを生成・投入。EAN-13チェックデジットを正規計算 |
| `scripts/seed_e2e_fixtures.py` | Playwright E2Eテスト用の固定データ（STAFF/MANAGER/ADMIN各アカウント、テスト商品、会員、値引き、101件のバルクSKU）を冪等に投入 |

### Tests（`backend/tests/`、pytest・109件）

| ファイル | 役割 |
|---|---|
| `conftest.py` | ASGI経由の非同期テストクライアント`client`フィクスチャ |
| `test_health.py` | 死活監視エンドポイント |
| `test_auth.py` | ログイン成否、レート制限によるロックアウト |
| `test_admin_staff.py` | スタッフ管理API（権限、自己ロックアウト防止など） |
| `test_products.py` | 商品/SKU登録・更新、バーコード/手入力検索、重複検証（複合UNIQUE制約含む） |
| `test_members.py` | 会員照会・登録・更新の権限 |
| `test_masters.py` | 値引き・税率マスターの登録・更新・権限 |
| `test_master_validity.py` | 過去日時を指定した値引き・税率の有効期間境界テスト |
| `test_inventory.py` | 在庫照会・入荷・移動（マイナス防止、権限） |
| `test_pos_checkout.py` | 会計：金額改ざん検知、預かり金額不足、値引き優先順位、同時決済の排他制御、重複SKU拒否など |
| `test_pos_refund_exchange.py` | 返品・交換：二重返品防止、対象外取引、交換差額の預かり不足、同一リクエスト内の重複SKU拒否など |
| `test_transactions.py` | 取引照会API |

### 設定・デプロイ（`backend/`）

| ファイル | 役割 |
|---|---|
| `Dockerfile` | Python 3.12-slimベース、uvicorn起動 |
| `requirements.txt` / `requirements-dev.txt` | 本番依存（FastAPI, SQLAlchemy, asyncmy等）/開発依存（pytest, ruff, black） |
| `pyproject.toml` | ruff・pytest-asyncioなどのツール設定 |
| `alembic.ini` | Alembic設定ファイル（接続URLは実行時にenv.pyが上書き） |

---

## Frontend（`frontend/`）

### App Pages（`src/app/`、画面）

| ファイル | 役割 |
|---|---|
| `page.tsx` | ルート（/）、ログイン状態に応じて/pos等へリダイレクト |
| `layout.tsx` | ルートレイアウト、`Providers`でラップ |
| `providers.tsx` | React QueryとAuthProviderの初期化 |
| `login/page.tsx` | ログイン画面（担当者ID・パスワード） |
| `(protected)/layout.tsx` | 未ログイン時は/loginへリダイレクト。ログイン済みなら`AppShell`（ナビゲーション）を表示 |
| `(protected)/pos/page.tsx` | レジ会計画面：バーコード/カメラ/手入力でのSKU追加、購入リスト、会員照会、現金/カード会計、削除確認ダイアログ |
| `(protected)/pos/refund-exchange/page.tsx` | 返品・交換画面：元取引照会、返品数量指定、交換商品スキャン、差額精算 |
| `(protected)/inventory/page.tsx` | 在庫照会・入荷登録（全ロール）・店舗⇔倉庫移動（MANAGER/ADMINのみフォーム表示） |
| `(protected)/members/page.tsx` | 会員照会（全ロール）・編集/新規登録（MANAGER/ADMINのみ） |
| `(protected)/admin/products/page.tsx` | 商品・SKUの新規登録/更新フォーム（MANAGER/ADMIN限定、`RoleGate`で保護） |
| `(protected)/admin/staff/page.tsx` | スタッフ管理（ADMIN限定） |
| `(protected)/admin/masters/page.tsx` | 値引き・税率マスターの管理画面（税率はADMINのみ） |

### BFF Routes（`src/app/api/bff/`、サーバー側のみ）

| ファイル | 役割 |
|---|---|
| `[...path]/route.ts` | キャッチオール・リバースプロキシ。`/api/bff/*`を`/api/v1/*`へサーバー間転送 |
| `auth/login/route.ts` | ログインをFastAPIへ転送し、Refresh TokenをHttpOnly Cookieに変換して終端 |
| `auth/refresh/route.ts` | Cookie内のRefresh Tokenで新しいAccess Tokenを取得 |
| `auth/logout/route.ts` | Refresh Token Cookieの削除 |
| `auth/_lib/backend-url.ts` | FastAPI内部URLの組み立て（`BACKEND_INTERNAL_URL`環境変数、クライアント非公開） |
| `auth/_lib/refresh-cookie.ts` | Refresh Token Cookieのオプション定義（HttpOnly/Secure/SameSite=Strict/8時間）と削除処理 |

### Components（`src/components/`、UI部品）

| ファイル | 役割 |
|---|---|
| `AppShell.tsx` | ログイン後の共通ナビゲーション（会計/返品交換/在庫/会員/ログアウト） |
| `BarcodeScanner.tsx` | カメラでのEAN-13連続読取モーダル（@zxing/browser）。同一コードの連続検出を1.5秒デバウンス |
| `RoleGate.tsx` | 指定ロール以外には「権限がありません」を表示するラッパー |
| `ui.tsx` | Card・Button・TextInput・Select・Field・ErrorBanner・SuccessBannerなどの共通UI部品 |

### Lib（`src/lib/`、クライアントロジック。`*.test.ts`はJestユニットテスト・30件）

| ファイル | 役割 |
|---|---|
| `api-client.ts` | axiosインスタンス（baseURL: /api/bff）。Access Tokenの自動付与、401時の自動リフレッシュ&リトライ |
| `token-store.ts` | Access Tokenをメモリ上でのみ保持するpub/subストア（localStorage等へは一切保存しない） |
| `auth-context.tsx` | `AuthProvider`/`useAuth`。ログイン・ログアウト・マウント時のサイレント再認証 |
| `errors.ts` | バックエンドのHTTPException detail（文字列/オブジェクト/バリデーション配列）を表示用文字列へ正規化 |
| `pos-calculations.ts` | 小計・消費税・合計の計算（税額は1円未満切り捨て）。会計確定額は必ずサーバー側で再計算される前提のプレビュー専用 |
| `validation.ts` | 数量範囲（1〜99）・EAN-13形式（13桁数字）の検証 |
| `cart.ts` | 購入リストへのSKU追加ロジック（既存SKUは数量+1、新規は行追加、100SKU上限で拒否） |

### Types（`src/types/`、TypeScript）

| ファイル | 役割 |
|---|---|
| `api.ts` | バックエンドAPIの入出力型（SkuLookup、CheckoutRequest/Response、Member等） |
| `auth.ts` | Role列挙型、StaffSession型 |

### E2E Tests（`frontend/e2e/`、Playwright・17件）

| ファイル | 役割 |
|---|---|
| `fixtures.ts` | 共通ログインヘルパー、テスト用固定バーコード、MySQL直接確認・フィクスチャリセット関数 |
| `checkout.spec.ts` | 複数SKUスキャン→現金会計→レシート表示 |
| `cart-quantity-limit.spec.ts` | 同一SKU数量99上限 |
| `cart-sku-limit.spec.ts` | 購入リスト100SKU上限（101種類目は拒否） |
| `cart-remove-confirm.spec.ts` | 購入リスト削除の確認ダイアログ（キャンセル/確定） |
| `manual-sku-entry.spec.ts` | バーコード読取エラー時、商品ID+サイズ+カラーの手入力フォールバック |
| `refund.spec.ts` | 元取引照合→返品確定 |
| `refund-double-return.spec.ts` | 同一SKUの二重返品防止 |
| `refund-invalid-transaction.spec.ts` | 存在しない取引ID・対象外取引（通常販売以外）の照会エラー |
| `exchange.spec.ts` | 返品+交換、在庫の増減検証 |
| `inventory-transfer.spec.ts` | MANAGERロールでの店舗⇔倉庫在庫移動 |
| `inventory-staff-permission.spec.ts` | STAFFロールでは在庫移動フォームが非表示 |
| `member-lookup-discount.spec.ts` | 会員照会と会員向け値引きの会計反映 |
| `product-lookup.spec.ts` | EAN-13バーコードでの商品照会・表示内容の検証 |
| `login-lockout.spec.ts` | パスワード誤り5回連続でのアカウントロック |
| `session-refresh.spec.ts` | Access Token期限切れ時の自動リフレッシュ、失敗時のログイン画面遷移 |

### 設定・デプロイ（`frontend/`）

| ファイル | 役割 |
|---|---|
| `Dockerfile` | Node 20-alpineベース、本番は`next build`+`next start` |
| `next.config.mjs` | Next.js設定 |
| `tailwind.config.ts` / `postcss.config.mjs` | Tailwind CSS設定 |
| `jest.config.js` / `jest.setup.ts` | Jest設定（`e2e/`ディレクトリを除外し、Playwrightテストと混同しないようにしている） |
| `playwright.config.ts` | Playwright設定（baseURL: localhost:3000、Chromiumプロジェクト） |
| `e2e/tsconfig.json` | e2e/専用のTypeScript設定（本体のtsconfig/typecheckから分離） |
| `tsconfig.json` | アプリ本体のTypeScript設定 |
| `package.json` | 依存関係、dev/build/lint/typecheck/test/test:e2eスクリプト |

---

*Apparel POS · Next.js 14 + FastAPI + Azure Database for MySQL · pytest 109件 / Jest 30件 / Playwright 17件*
