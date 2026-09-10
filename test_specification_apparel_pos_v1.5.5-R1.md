# アパレルPOSシステム テスト仕様書

- **対象文書バージョン**: v1.5.5
- **テスト仕様書バージョン**: v1.5.5-R1
- **作成日**: 2026年9月
- **対象アーキテクチャ**: Next.js (TypeScript) + FastAPI (Python) + Azure Database for MySQL Flexible Server
- **目的**: v1.5.5設計仕様に対する機能・データ整合性・セキュリティ・業務シナリオの検証

---

## 1. テスト方針・V字モデル対応

設計書の各階層とテストレベルを対応づけ、要求・設計から実装・業務利用まで追跡可能な形で検証する。

| 開発工程 | テスト工程 | 主な検証対象・目的 | 主な手法 |
|---|---|---|---|
| 業務要求 / ユーザーシナリオ | ユーザーテスト（E2E / UAT） | レジ販売、返品・交換、在庫業務が店舗オペレーション通りに機能すること | 手動E2E / Playwright |
| システム要件 / アーキテクチャ設計 | 結合・機能テスト | BFF ↔ FastAPI ↔ MySQL、認証・認可、トランザクション、二重計算、排他制御 | pytest / API統合テスト |
| 詳細設計 / モジュール・テーブル定義 | 単体テスト | 計算、バリデーション、UI状態、権限判定、モデル整合性 | Jest / React Testing Library / pytest |
| DB物理設計 | DB整合性テスト | PK、FK、UNIQUE、CHECK、トランザクション整合性 | pytest / MySQL |

### 1.1 テスト観点

- 正常系：仕様通りに処理できること
- 境界値：最小・最大値および上限超過を検証すること
- 異常系：不正入力・権限不足・存在しないデータを拒否すること
- セキュリティ：認証・認可・Rate Limiting・本番API非公開を検証すること
- 整合性：Backend再計算、SKU/Product整合性、外部キー、在庫整合性を検証すること
- 排他制御：同一SKUの同時決済で在庫が負数にならないこと
- 業務継続性：通信切断・タイムアウト時に二重売上が発生しないこと

---

## 2. 単体テスト仕様

### 2.1 フロントエンド（Next.js / TypeScript）

Jest + React Testing Libraryを使用し、UI、入力制約、計算ロジック、認証状態を検証する。

| No. | 対象 | テストケース | 種別 | 入力 / 条件 | 期待結果 |
|---|---|---|---|---|---|
| FE-U01 | `calculateSubtotal` | 単一SKUの小計計算 | 正常 | 単価1,000円、数量2 | 小計2,000円（税抜） |
| FE-U02 | `calculateTax` / `calculateTotal` | 外税端数処理（切捨て） | 境界 | 税抜1,980円、税率10% | 税額198円、税込2,178円 |
| FE-U03 | `calculateTotal` | 値引きを含む合計計算 | 正常 | 商品値引等を設定 | 仕様の計算順序で正しい合計 |
| FE-U04 | `CheckoutItemRequest` | 数量下限・上限 | 境界 | 1、99 | バリデーション通過 |
| FE-U05 | `CheckoutItemRequest` | 数量範囲外 | 異常 | 0、100 | バリデーションエラー、送信抑止 |
| FE-U06 | `BarcodeScannerInput` | EAN-13形式 | 正常 | 13桁半角数字 | 受付可能 |
| FE-U07 | `BarcodeScannerInput` | EAN-13桁数不正 | 異常 | 12桁、14桁 | 入力エラー、API送信なし |
| FE-U08 | `BarcodeScannerInput` | 英字・記号混入 | 異常 | 英字混入 | 入力エラー、API送信なし |
| FE-U09 | `AuthContext` | Access Tokenの保持 | セキュリティ | ログイン成功 | localStorage等へ保存せずメモリ状態で保持 |
| FE-U10 | カート状態管理 | 購入リストSKU上限 | 境界 | 100SKU、101SKU | 100SKUまで登録、101SKU目は追加不可 |

### 2.2 バックエンド（FastAPI / Python）

pytestを使用し、認証、RBAC、値引き整合性、商品整合性を検証する。

| No. | 対象 | テストケース | 種別 | 入力 / 条件 | 期待結果 |
|---|---|---|---|---|---|
| BE-U01 | `verify_password` | 正しいPW照合 | 正常 | 正しいPW + ハッシュ | True |
| BE-U02 | `verify_password` | 誤ったPW照合 | 異常 | 誤ったPW | False |
| BE-U03 | `require_roles` | MANAGER許可 | 正常 | role=MANAGER、許可=[MANAGER,ADMIN] | 処理継続 |
| BE-U04 | `require_roles` | STAFF拒否 | 異常 | role=STAFF、許可=[MANAGER] | 403 Forbidden |
| BE-U05 | `validate_discount_master` | MEMBER対象値引 | 正常 | target_type=MEMBER、member_id設定、他NULL | 検証OK |
| BE-U06 | `validate_discount_master` | PRODUCT対象値引 | 正常 | product_idのみ設定 | 検証OK |
| BE-U07 | `validate_discount_master` | SKU対象値引 | 正常 | sku_idのみ設定 | 検証OK |
| BE-U08 | `validate_discount_master` | 対象ID排他違反 | 異常 | MEMBER + product_id設定 | バリデーションエラー |
| BE-U09 | `validate_discount_master` | 対象ID未設定 | 異常 | MEMBER + member_id=NULL | バリデーションエラー |
| BE-U10 | `validate_discount_master` | RATE値引計算 | 正常 | discount_type=RATE | 正しい値引額 |
| BE-U11 | `validate_discount_master` | AMOUNT値引計算 | 正常 | discount_type=AMOUNT | 正しい値引額 |
| BE-U12 | `validate_sales_item_product` | SKU/Product不一致 | 異常 | sales_items.product_id != skus.product_id | 登録拒否 |

---

## 3. 結合・機能テスト仕様

BFF ↔ FastAPI ↔ MySQL間の通信、認証、決済、値引き、在庫、DB整合性を検証する。

| No. | 対象機能 | テストケース | 種別 | テスト条件 | 期待結果 |
|---|---|---|---|---|---|
| IT-01 | Login | 連続認証失敗によるRate Limiting | 異常/境界 | 同一staff_idでPW誤りを5回、その後6回目 | 1～5回目401、6回目429 |
| IT-02 | Login | 正常ログイン | 正常 | 正しい認証情報 | 200、Access Token発行、Refresh TokenをCookie設定 |
| IT-03 | Refresh | Access Token再発行 | 正常 | Access Token期限切れ、Refresh Token有効 | BFF経由で新Access Token発行 |
| IT-04 | Refresh | Refresh Token期限切れ | 異常 | Refresh Token期限切れ | 401、再ログイン要求 |
| IT-05 | Barcode | EAN-13商品照会 | 正常 | 登録済EAN-13 | SKUを取得、0.5秒以内目標 |
| IT-06 | Barcode | 存在しないEAN-13 | 異常 | 未登録EAN-13 | 404等の仕様定義済エラー |
| IT-07 | Checkout | 正常トランザクション | 正常 | FE提示額とBE再計算額が一致 | 200、取引・明細・在庫・履歴をCOMMIT |
| IT-08 | Checkout | 金額改ざん検知 | 異常 | client_totalを1円改ざん | 422、ROLLBACK、在庫変化なし |
| IT-09 | Checkout | 同一SKU同時決済 | 境界 | 在庫1点、2台同時checkout | SELECT FOR UPDATEで片方成功、片方在庫不足 |
| IT-10 | Inventory | 在庫マイナス防止 | 異常/境界 | 在庫0、数量1で販売 | 拒否、DB更新なし |
| IT-11 | Inventory | 入荷登録 | 正常 | 入荷数量を登録 | 在庫が正しく増加、履歴RECEIPT |
| IT-12 | Discount | 値引き優先順位 | 正常 | SKU・商品・会員値引が重複 | SKU > 商品 > 会員の仕様順で適用 |
| IT-13 | Discount | 値引き有効期間 | 境界 | valid_from / valid_toの前後 | 有効期間内のみ適用 |
| IT-14 | Tax | 税率有効期間 | 境界 | 税率改定前後 | 該当時点の税率を適用 |
| IT-15 | Product | 商品登録・更新権限 | セキュリティ | STAFF / MANAGER / ADMIN | 許可ロールのみ処理可能 |
| IT-16 | Member | 会員照会 | 正常 | 有効なmember_id | 会員情報取得 |
| IT-17 | Member | 会員更新権限 | セキュリティ | STAFFが更新要求 | 403 |
| IT-18 | Inventory Transfer | 店舗間在庫移動権限 | セキュリティ | STAFFが実行 | 403 |
| IT-19 | Tax Master | 税率変更権限 | セキュリティ | MANAGERが実行 | 403 |
| IT-20 | Staff Admin | スタッフ管理権限 | セキュリティ | STAFF/MANAGERが実行 | 403 |
| IT-21 | Transaction | 取引照会 | 正常 | 有効transaction_id | 取引・レシート情報取得 |
| IT-22 | Reports | 売上集計 | 正常/権限 | MANAGER/ADMIN | 集計取得、一般STAFFは拒否 |
| IT-23 | Audit Log | 監査ログ照会 | セキュリティ | ADMIN以外がアクセス | 403 |
| IT-24 | DB | EAN-13重複登録 | 異常 | 同一barcode_ean13を登録 | UNIQUE制約で拒否 |
| IT-25 | DB | 外部キー整合性 | 異常 | 存在しないproduct_id等 | FK制約で拒否 |
| IT-26 | DB | SalesItem商品整合性 | 異常 | SKUとproduct_id不一致 | Backendで拒否 |
| IT-27 | Swagger | 本番API非公開 | セキュリティ | productionで/docs | 404 |
| IT-28 | ReDoc | 本番API非公開 | セキュリティ | productionで/redoc | 404 |
| IT-29 | OpenAPI | 本番スキーマ非公開 | セキュリティ | productionで/openapi.json | 404 |
| IT-30 | Checkout | 通信切断 | 異常 | 会計確定直後に通信切断 | 二重売上なし、再試行可能 |
| IT-31 | Checkout | DB処理途中の失敗 | 異常 | DB更新途中で例外 | transactions/sales_items/在庫/履歴をROLLBACK |
| IT-32 | Refund | 正常返品 | 正常 | 有効な元取引 + 対象SKU | 逆伝票作成、在庫+1 |
| IT-33 | Refund | 不正元取引 | 異常 | 存在しない/他店舗/対象外SKU | 処理拒否 |
| IT-34 | Refund | 二重返品防止 | 異常 | 同一明細を再度返品 | 処理拒否 |
| IT-35 | Exchange | 正常交換 | 正常 | 元SKU + 交換SKU | 元商品在庫増、新商品在庫減、逆伝票 |
| IT-36 | RBAC | 全ロール境界確認 | セキュリティ | STAFF/MANAGER/ADMINで主要管理API実行 | 設計書の許可ロール通り |

---

## 4. ユーザーテスト仕様（UAT / E2E）

レジ担当者および店舗管理者が実機端末で実施する。

| No. | 業務シナリオ | テストケース | 種別 | 操作手順 / 入力 | 期待結果 |
|---|---|---|---|---|---|
| UT-01 | レジ販売 | 複数SKUスキャンと現金会計 | 正常 | 2SKUをカメラスキャン→会員読取→現金決済 | 商品一覧、会員割引、合計、お釣り、レシートが正しい |
| UT-02 | レジ販売 | SKU数量上限 | 境界 | 同一SKUを99点→+1 | 99点で上限、100点目不可 |
| UT-03 | レジ販売 | 購入リスト上限 | 境界 | 異なるSKUを100種類→101種類目追加 | 100SKUまで、101SKU目不可 |
| UT-04 | 返品 | レシート照合返品 | 正常 | 元取引ID→対象SKU→返品 | 逆伝票、parent_transaction_id設定、在庫+1 |
| UT-05 | 返品 | 不正取引ID | 異常 | 存在しない/他店舗/対象外SKU | エラー表示、処理中断 |
| UT-06 | 返品 | 二重返品 | 異常 | 同じ商品を再返品 | エラー、在庫二重復元なし |
| UT-07 | 交換 | 商品交換 | 正常 | 元商品を指定→交換商品を指定 | 元商品在庫+1、交換商品在庫-1 |
| UT-08 | 在庫移動 | 一般スタッフの権限境界 | 異常 | STAFFで店舗間在庫移動画面へ | 非表示または403 |
| UT-09 | 在庫移動 | 店長による在庫移動 | 正常 | MANAGERで在庫移動 | 移動元減、移動先増、履歴保存 |
| UT-10 | 通信障害 | 決済中ネットワーク切断 | 異常 | 会計確定直後に通信切断 | 二重売上なし、再試行可能 |
| UT-11 | 認証 | ログイン失敗・ロック | 異常 | PW誤りを連続送信 | 5回失敗後にロック状態 |
| UT-12 | 認証 | セッション更新 | 正常 | Access Token期限切れ後に操作 | Refreshにより継続、期限切れ後は再ログイン |
| UT-13 | 商品 | 商品検索・詳細表示 | 正常 | SKU/EAN-13で商品照会 | 正しい商品情報表示 |
| UT-14 | 会員 | 会員コード照会 | 正常 | 会員バーコード読取 | 会員情報・割引対象を正しく反映 |

---

## 5. DB整合性・トランザクション確認

### 5.1 決済成功時

以下が同一トランザクションで整合して保存されること。

1. `transactions` 登録
2. `sales_items` 登録
3. `skus.store_stock` 減算
4. `inventory_histories` にSALE履歴登録
5. COMMIT

### 5.2 決済失敗時

金額不一致・在庫不足・DB例外等の場合、

- `transactions` が作成されない
- `sales_items` が作成されない
- 在庫が変更されない
- `inventory_histories` が作成されない

ことを確認する。

### 5.3 データ整合性

- `sales_items.product_id == skus.product_id`
- `discount_masters.target_type` と対象IDが一致
- EAN-13が一意
- SKU在庫が負数にならない
- 外部キー制約に違反しない

---

## 6. セキュリティテスト

| No. | 項目 | 確認内容 | 合格条件 |
|---|---|---|---|
| SEC-01 | HTTPS | 本番通信 | HTTPSのみ |
| SEC-02 | JWT | Access Token署名検証 | 不正Token拒否 |
| SEC-03 | Refresh Token | Cookie属性 | HttpOnly / Secure / SameSite=Strict |
| SEC-04 | RBAC | ロール別APIアクセス | 許可ロールのみ200 |
| SEC-05 | Rate Limiting | 連続ログイン失敗 | 5回失敗後ロック、6回目429 |
| SEC-06 | API非公開 | docs/redoc/openapi | productionでは404 |
| SEC-07 | SQL Injection | 不正入力 | SQLとして実行されない |
| SEC-08 | 金額改ざん | client_total改ざん | 422 + ROLLBACK |
| SEC-09 | OSS | npm audit / pip-audit | High/Critical脆弱性を残して本番投入しない |
| SEC-10 | Cookie | Refresh Token保存場所 | localStorage等に保存しない |

---

## 7. 非機能テスト

### 7.1 性能

| No. | 対象 | 目標 |
|---|---|---|
| PERF-01 | EAN-13 SKU照会 | 0.5秒以内を目標 |
| PERF-02 | 通常Checkout API | 業務上許容できる応答時間 |
| PERF-03 | 同時Checkout | 在庫1点に対する同時要求で在庫負数なし |

### 7.2 可用性・障害

- ネットワーク切断時に二重売上が発生しない
- DB例外時にトランザクションがROLLBACKされる
- タイムアウト後に再試行しても二重取引にならない

---

## 8. テスト環境・実施条件

### Frontend

- Next.js / TypeScript
- Jest
- React Testing Library
- Playwright

### Backend

- FastAPI / Python
- pytest
- テスト用DB
- SQLAlchemy

### Database

- Azure Database for MySQL Flexible Server相当のMySQL環境
- InnoDB
- 外部キー制約有効
- トランザクション検証可能なテストデータを準備

### 実機

- POS利用端末
- カメラによるEAN-13読み取り
- 実店舗を想定したネットワーク環境

---

## 9. 合否判定基準

### 合格

- 全必須テストケースがPASS
- Critical / High相当の未解決不具合がない
- 金額改ざん・在庫負数・権限逸脱・二重売上が発生しない
- DB整合性違反がない
- 本番Swagger / ReDoc / OpenAPIが公開されていない

### 不合格

以下のいずれかに該当する場合は本番投入不可とする。

- 金額計算が仕様と一致しない
- 在庫が負数になる
- 同一決済が二重登録される
- 権限外APIを実行できる
- 不正なRefresh Tokenを受け入れる
- 返品で在庫が二重復元される
- 主要テーブルの整合性が崩れる

---

## 10. テスト結果記録

| No. | テストID | 実施日 | 実施者 | 結果 | 不具合ID | 備考 |
|---|---|---|---|---|---|---|
| 1 | FE-U01 | | | 未実施 | | |
| 2 | FE-U02 | | | 未実施 | | |
| 3 | BE-U01 | | | 未実施 | | |
| 4 | IT-01 | | | 未実施 | | |
| 5 | IT-07 | | | 未実施 | | |
| 6 | IT-08 | | | 未実施 | | |
| 7 | IT-09 | | | 未実施 | | |
| 8 | UT-01 | | | 未実施 | | |
| 9 | UT-04 | | | 未実施 | | |
| 10 | UT-10 | | | 未実施 | | |

---

## 11. 設計仕様とのトレーサビリティ

| 設計項目 | 主なテスト |
|---|---|
| EAN-13 → SKU一意識別 | FE-U06～08 / IT-05～06 / IT-24 |
| SKU数量上限99 | FE-U04～05 / UT-02 |
| 購入リスト最大100SKU | FE-U10 / UT-03 |
| 値引き優先順位 | FE-U03 / IT-12 |
| DiscountMaster MEMBER | BE-U05 / BE-U08～09 |
| Discount RATE / AMOUNT | BE-U10～11 |
| 値引き有効期間 | IT-13 |
| 税率有効期間 | IT-14 |
| Backend金額再計算 | IT-07～08 |
| 在庫SELECT FOR UPDATE | IT-09 |
| 在庫CHECK | IT-10 |
| SalesItem Product整合性 | BE-U12 / IT-26 |
| 返品・交換 | IT-32～35 / UT-04～07 |
| JWT / RBAC | IT-01～04 / IT-15～20 / IT-36 |
| Refresh Token Cookie | IT-03～04 / SEC-03 / SEC-10 |
| Rate Limiting | IT-01 / SEC-05 |
| Swagger / ReDoc / OpenAPI非公開 | IT-27～29 / SEC-06 |
| トランザクション | IT-07～10 / IT-30～31 |
| 外部キー | IT-24～26 |
| OSS脆弱性管理 | SEC-09 |

---

## 12. レビュー完了判定

本テスト仕様書は、v1.5.5設計仕様に対して、

- 単体テスト
- 結合・機能テスト
- DB整合性テスト
- セキュリティテスト
- E2E / UAT
- 非機能テスト
- トレーサビリティ

を網羅する構成とする。

特に、**金額改ざん防止、在庫排他、RBAC、Refresh Token、値引き対象整合性、返品・交換、100SKU上限、DBトランザクション**を重点検証項目とする。

**提出・レビュー用としては、本版をv1.5.5-R1の基準版とする。**
