# アパレル POSシステム 要件仕様書（System Requirements Specification）

- **文書番号**：SRS-POS-202609-001
- **版数**：v1.0
- **作成日**：2026年9月
- **ステータス**：承認済 / 開発移行可

---

## 目次
1. [システム概要およびシステムアーキテクチャ仕様](#1-システム概要およびシステムアーキテクチャ仕様)
2. [データモデリングおよびデータベース設計（DDL含む）](#2-データモデリングおよびデータベース設計ddl含む)
3. [画面仕様およびUIコンポーネント要件](#3-画面仕様およびuiコンポーネント要件)
4. [業務ロジックおよびアルゴリズム仕様](#4-業務ロジックおよびアルゴリズム仕様)
5. [RESTful API仕様書](#5-restful-api仕様書)
6. [非機能要件およびインフラ・セキュリティ仕様](#6-非機能要件およびインフラセキュリティ仕様)
7. [ロール・権限マトリクス](#7-ロール権限マトリクス)

---

## 1. システム概要およびシステムアーキテクチャ仕様

### 1.1 システムの目的・スコープ
本システムは、アパレル店舗におけるレジ販売業務、在庫管理（店舗・倉庫・店舗間移動）、会員連携、値引き適用、返品・交換業務を一貫して担うマルチデバイス対応のWeb型POS（Point of Sale）システムである。

### 1.2 アーキテクチャ構成
```
[ クライアント環境 ]
ノートPC / タブレット / スマートフォン (Webブラウザ: Chrome, Safari, Edge)
  │ (HTTPS / WSS)
  ▼
[ プレゼンテーション層: Next.js 14+ (App Router) ]
  ├── UIコンポーネント / POS販売画面 / 管理画面
  ├── HTML5 Camera Stream (html5-qrcode / WebRTC)
  └── クライアント側状態管理 (Zustand / TanStack Query)
  │ (RESTful API / JSON)
  ▼
[ アプリケーション層: FastAPI (Python 3.11+) ]
  ├── 認証・認可ミドルウェア (JWT / Session)
  ├── 業務ロジックサービス (POS, 在庫, 値引きエンジン, 税計算, 返品交換)
  ├── O/Rマッパー (SQLAlchemy 2.0 / Alembic)
  └── DBコネクションプール (QueuePool: 常時接続維持)
  │ (MySQL Native Protocol / SSL)
  ▼
[ データ層: Azure Database for MySQL Flexible Server ]
  ├── ストレージエンジン: InnoDB (ACID準拠)
  ├── 文字セット: utf8mb4 (Collation: utf8mb4_unicode_ci)
  └── トランザクション分離レベル: READ COMMITTED
```

### 1.3 前提制約
1. **常時接続プール**: コールドスタートによる遅延を防止するため、FastAPI起動時に最小コネクション数を確保し、リクエストごとのDB再接続を行わない。
2. **完全Web完結**: 専用アプリのインストールは不要。ブラウザ標準のMediaDevices APIを用いて内蔵カメラを直接制御する。
3. **オフライン非対応**: リアルタイムな在庫整合性および売上スナップショット永続化のため、オンライン通信（HTTPS）を前提とする。

---

## 2. データモデリングおよびデータベース設計（DDL含む）

### 2.1 ER関係および依存関係
- `products` (1) ──── (N) `skus`
- `sizes` (1) ──── (N) `skus`
- `colors` (1) ──── (N) `skus`
- `skus` (1) ──── (1) `ean13` (一意キー)
- `transactions` (1) ──── (N) `transaction_items`
- `skus` (1) ──── (N) `inventory_histories`

### 2.2 DDL定義 (MySQL 8.0 Flexible Server)

```sql
-- 1. スタッフ管理テーブル
CREATE TABLE `staffs` (
  `staff_id` VARCHAR(32) NOT NULL,
  `staff_name` VARCHAR(64) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role` ENUM('general', 'manager', 'admin') NOT NULL DEFAULT 'general',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`staff_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. サイズ体系マスター
CREATE TABLE `size_systems` (
  `size_system_id` VARCHAR(32) NOT NULL,
  `system_name` VARCHAR(64) NOT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`size_system_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. サイズマスター
CREATE TABLE `sizes` (
  `size_system_id` VARCHAR(32) NOT NULL,
  `size_code` VARCHAR(16) NOT NULL,
  `size_name` VARCHAR(32) NOT NULL,
  `display_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`size_system_id`, `size_code`),
  CONSTRAINT `fk_sizes_system` FOREIGN KEY (`size_system_id`) REFERENCES `size_systems` (`size_system_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. カラー体系マスター
CREATE TABLE `color_systems` (
  `color_system_id` VARCHAR(32) NOT NULL,
  `system_name` VARCHAR(64) NOT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`color_system_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. カラーマスター
CREATE TABLE `colors` (
  `color_system_id` VARCHAR(32) NOT NULL,
  `color_code` VARCHAR(16) NOT NULL,
  `color_name` VARCHAR(32) NOT NULL,
  `display_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`color_system_id`, `color_code`),
  CONSTRAINT `fk_colors_system` FOREIGN KEY (`color_system_id`) REFERENCES `color_systems` (`color_system_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. 商品マスター
CREATE TABLE `products` (
  `product_id` VARCHAR(32) NOT NULL COMMENT '型番',
  `product_name` VARCHAR(128) NOT NULL,
  `category` VARCHAR(64) NOT NULL,
  `base_price` DECIMAL(10, 0) NOT NULL COMMENT '商品ID単価(税抜)',
  `image_url` VARCHAR(512) NULL,
  `size_system_id` VARCHAR(32) NOT NULL,
  `color_system_id` VARCHAR(32) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`product_id`),
  CONSTRAINT `fk_products_size_sys` FOREIGN KEY (`size_system_id`) REFERENCES `size_systems` (`size_system_id`),
  CONSTRAINT `fk_products_color_sys` FOREIGN KEY (`color_system_id`) REFERENCES `color_systems` (`color_system_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. SKUテーブル
CREATE TABLE `skus` (
  `sku_id` VARCHAR(64) NOT NULL COMMENT '商品ID-サイズコード-カラーコード',
  `product_id` VARCHAR(32) NOT NULL,
  `ean13` VARCHAR(13) NOT NULL COMMENT 'JANコード13桁(一意)',
  `size_system_id` VARCHAR(32) NOT NULL,
  `size_code` VARCHAR(16) NOT NULL,
  `color_system_id` VARCHAR(32) NOT NULL,
  `color_code` VARCHAR(16) NOT NULL,
  `store_stock` INT NOT NULL DEFAULT 0 COMMENT '店舗在庫数',
  `warehouse_stock` INT NOT NULL DEFAULT 0 COMMENT '倉庫在庫数',
  `location` VARCHAR(64) NULL COMMENT '棚番',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`sku_id`),
  UNIQUE KEY `uq_skus_ean13` (`ean13`),
  UNIQUE KEY `uq_skus_prod_size_color` (`product_id`, `size_code`, `color_code`),
  CONSTRAINT `fk_skus_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`),
  CONSTRAINT `fk_skus_size` FOREIGN KEY (`size_system_id`, `size_code`) REFERENCES `sizes` (`size_system_id`, `size_code`),
  CONSTRAINT `fk_skus_color` FOREIGN KEY (`color_system_id`, `color_code`) REFERENCES `colors` (`color_system_id`, `color_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. 単価マスター（個別単価・履歴）
CREATE TABLE `price_histories` (
  `price_id` BIGINT AUTO_INCREMENT NOT NULL,
  `product_id` VARCHAR(32) NULL,
  `sku_id` VARCHAR(64) NULL,
  `price` DECIMAL(10, 0) NOT NULL COMMENT '税抜単価',
  `start_datetime` DATETIME NOT NULL,
  `end_datetime` DATETIME NOT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`price_id`),
  INDEX `idx_price_lookup` (`sku_id`, `product_id`, `start_datetime`, `end_datetime`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. 値引きマスター
CREATE TABLE `discounts` (
  `discount_id` VARCHAR(32) NOT NULL,
  `target_type` ENUM('sku', 'product', 'member') NOT NULL,
  `target_id` VARCHAR(64) NULL COMMENT 'sku_id または product_id (member時はNULL)',
  `discount_type` ENUM('percentage', 'fixed_amount') NOT NULL,
  `discount_value` DECIMAL(10, 2) NOT NULL COMMENT '20.00(%) または 200(円)',
  `priority` INT NOT NULL DEFAULT 0,
  `start_datetime` DATETIME NOT NULL,
  `end_datetime` DATETIME NOT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`discount_id`),
  INDEX `idx_discounts_active` (`target_type`, `target_id`, `start_datetime`, `end_datetime`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. 税率マスター
CREATE TABLE `tax_rates` (
  `tax_rate_id` VARCHAR(32) NOT NULL,
  `tax_rate` DECIMAL(5, 4) NOT NULL COMMENT '0.1000 = 10%',
  `start_datetime` DATETIME NOT NULL,
  `end_datetime` DATETIME NOT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`tax_rate_id`),
  INDEX `idx_tax_lookup` (`start_datetime`, `end_datetime`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 11. 会員テーブル
CREATE TABLE `members` (
  `member_id` VARCHAR(32) NOT NULL,
  `name` VARCHAR(64) NOT NULL,
  `phone` VARCHAR(20) NOT NULL,
  `address` VARCHAR(255) NOT NULL,
  `gender` ENUM('male', 'female', 'other', 'unspecified') NOT NULL,
  `age` INT NOT NULL,
  `points` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`member_id`),
  INDEX `idx_members_phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 12. 取引テーブル (売上親ヘッダー)
CREATE TABLE `transactions` (
  `transaction_id` VARCHAR(64) NOT NULL COMMENT 'UUID または 採番ID',
  `member_id` VARCHAR(32) NULL,
  `staff_id` VARCHAR(32) NOT NULL,
  `payment_method` ENUM('cash', 'credit_card', 'qr_code', 'electronic_money') NOT NULL,
  `subtotal_excl_tax` DECIMAL(12, 0) NOT NULL COMMENT '値引き前税抜小計',
  `discount_total` DECIMAL(12, 0) NOT NULL COMMENT '値引き総額',
  `tax_rate` DECIMAL(5, 4) NOT NULL COMMENT '適用消費税率',
  `tax_amount` DECIMAL(12, 0) NOT NULL COMMENT '消費税額(端数切捨て)',
  `total_incl_tax` DECIMAL(12, 0) NOT NULL COMMENT '最終請求税込金額',
  `transaction_type` ENUM('sale', 'return', 'exchange') NOT NULL DEFAULT 'sale',
  `original_transaction_id` VARCHAR(64) NULL COMMENT '返品/交換時の元取引ID',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`transaction_id`),
  INDEX `idx_tx_created` (`created_at`),
  INDEX `idx_tx_member` (`member_id`),
  CONSTRAINT `fk_tx_staff` FOREIGN KEY (`staff_id`) REFERENCES `staffs` (`staff_id`),
  CONSTRAINT `fk_tx_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`member_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 13. 売上明細テーブル (取引明細)
CREATE TABLE `transaction_items` (
  `item_id` BIGINT AUTO_INCREMENT NOT NULL,
  `transaction_id` VARCHAR(64) NOT NULL,
  `sku_id` VARCHAR(64) NOT NULL,
  `product_id` VARCHAR(32) NOT NULL,
  `quantity` INT NOT NULL COMMENT '販売時は正数、返品・交換返金時は負数',
  `unit_price` DECIMAL(10, 0) NOT NULL COMMENT '購入確定時点の税抜単価',
  `discount_amount` DECIMAL(10, 0) NOT NULL DEFAULT 0 COMMENT '適用値引き額(1点あたり)',
  `applied_tax_rate` DECIMAL(5, 4) NOT NULL COMMENT '購入時点の適用税率',
  `tax_amount` DECIMAL(10, 0) NOT NULL COMMENT '明細税額',
  `subtotal_incl_tax` DECIMAL(12, 0) NOT NULL COMMENT '明細小計(税込)',
  `original_item_id` BIGINT NULL COMMENT '返品交換時の元売上明細ID',
  PRIMARY KEY (`item_id`),
  INDEX `idx_ti_tx` (`transaction_id`),
  CONSTRAINT `fk_ti_tx` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`transaction_id`),
  CONSTRAINT `fk_ti_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus` (`sku_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 14. 在庫変動履歴テーブル
CREATE TABLE `inventory_histories` (
  `history_id` BIGINT AUTO_INCREMENT NOT NULL,
  `sku_id` VARCHAR(64) NOT NULL,
  `location_type` ENUM('store', 'warehouse') NOT NULL,
  `change_quantity` INT NOT NULL COMMENT '正負で増減を記録',
  `change_type` ENUM('sale', 'return', 'inbound', 'transfer_out', 'transfer_in', 'adjustment') NOT NULL,
  `transaction_id` VARCHAR(64) NULL,
  `staff_id` VARCHAR(32) NOT NULL,
  `note` VARCHAR(255) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`history_id`),
  INDEX `idx_inv_sku` (`sku_id`),
  INDEX `idx_inv_tx` (`transaction_id`),
  CONSTRAINT `fk_inv_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus` (`sku_id`),
  CONSTRAINT `fk_inv_staff` FOREIGN KEY (`staff_id`) REFERENCES `staffs` (`staff_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## 3. 画面仕様およびUIコンポーネント要件

### 3.1 販売画面（メインPOS画面）
- **URL**: `/pos`
- **認証**: 必須（セッション/JWT）

```
+--------------------------------------------------------------------------------------------------------+
| [TechPOS] 店舗: 本店 | 担当: 石井 賢治 (一般)                              [会員読取] [ 100021 ] (山田 花子 様) |
+---------------------------------------------------+----------------------------------------------------+
| 【バーコードスキャン / 商品手入力】               | 【購入リスト】 (合計点数: 3点)                     |
| +-----------------------------------------------+ | +------------------------------------------------+ |
| | [ カメラ映像ストリーム (常時稼働)          ]   | | | [x] 1. リネン混ノーカラージャケット             | |
| | [ バーコードを枠内に合わせてください       ]   | | |     SKU: JK-001-M-NVY (M / NAVY)                 | |
| +-----------------------------------------------+ | |     単価: ¥12,000 | 数量: [ - | 1 | + ]            | |
| [ EAN-13手入力: 4901234567890 ] [ 登録 ]         | |     値引: 会員特別10% (-¥1,200) | 小計: ¥10,800     | |
| [ SKU手入力: JK-001-M-NVY    ] [ 登録 ]         | | +------------------------------------------------+ |
|                                                   | | | [ ] 2. クルーネックTシャツ                     | |
| 【直近スキャン商品プレビュー】                    | | |     SKU: TS-102-L-WHT (L / WHITE)                | |
| +-----------------------------------------------+ | |     単価: ¥2,500  | 数量: [ - | 2 | + ]            | |
| | [画像] クルーネックTシャツ (WHITE / L)        | | |     小計: ¥5,000                                 | |
| | SKU: TS-102-L-WHT | 定価: ¥2,500 (在庫: 15)   | | +------------------------------------------------+ |
| | >> 「1件追加されました (数量: 2)」            | | [ 選択行を削除 ] [ リスト全クリア ]              |
| +-----------------------------------------------+ +----------------------------------------------------+
|                                                   | 【金額サマリー】                                   |
|                                                   |  税抜小計:                            ¥17,000      |
|                                                   |  値引き合計:                          -¥1,200      |
|                                                   |  税抜合計:                            ¥15,800      |
|                                                   |  消費税 (10%):                         ¥1,580      |
|                                                   |  ------------------------------------------------- |
|                                                   |  税込合計金額:                        ¥17,380      |
|                                                   |  [ 決済へ進む (現金 / クレジット / QR) ]          |
+---------------------------------------------------+----------------------------------------------------+
```

#### 各機能・コンポーネント挙動
1. **カメラ読取部**:
   - `navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })` で背面カメラを優先起動。
   - `requestAnimationFrame` または `html5-qrcode` で 100ms〜200ms ごとにフレーム解析。
   - 読み取り成功時、短音ビープ（Web Audio API）と緑色枠フラッシュを発火し、即座にカート登録APIまたはローカルストア更新を実行。カメラは切断せず連続待機。
2. **購入リスト管理**:
   - 行クリックにより対象行を選択（青色ハイライト表示）。
   - 数量変更は「+」「-」ボタンおよび数値直接入力。1〜99の範囲外入力はバリデーションエラー（0は削除ダイアログ表示へ誘導）。
   - 数量変更または行追加・削除時、即時に税・値引きエンジンが再計算を実行。

### 3.2 ログイン画面 (`/login`)
- 担当者ID、パスワードの入力フォーム。
- 不正入力時は「担当者IDまたはパスワードが正しくありません」と表示。
- ログイン完了後、ロール情報をJWTに含めてCookieに保存し `/pos` へ遷移。

### 3.3 返品・交換画面 (`/returns`)
- 元取引ID（レシート番号）または取引日時・会員IDから過去取引を検索。
- 元取引明細一覧を表示し、返品対象商品を選択。
- 返品現物のバーコードをスキャンして照合（一致：返品返金 / 不一致：別SKUへの交換差額決済）。
- 元取引時点の単価・値引き額・税率を自動適用。

---

## 4. 業務ロジックおよびアルゴリズム仕様

### 4.1 EAN-13（JANコード）チェックデジット計算仕様
13桁のEAN-13コードは、先頭12桁からモジュラス10 ウェイト3・1 アルゴリズムによって算出し、一致を検証する。

$$	ext{CheckDigit} = \left(10 - \left( \sum_{i=1}^{6} d_{2i-1} 	imes 1 + \sum_{i=1}^{6} d_{2i} 	imes 3 ight) mod 10 ight) mod 10$$

### 4.2 単価特定ロジック
商品登録時、以下の優先度で適用単価（税抜）を決定する。
1. **SKU単価判定**: `price_histories` において `sku_id = target_sku_id` かつ `NOW() BETWEEN start_datetime AND end_datetime` で有効な最新レコード。
2. **商品ID単価判定**: SKU単価が存在しない場合、`products.base_price` または `price_histories` の商品ID指定レコード。

### 4.3 値引き優先順位および計算ロジック
1つのSKUに対して複数の割引が重複適用されないよう、厳格な優先順位を適用する。

1. **優先順位判定**:
   $$	ext{① SKU値引き} > 	ext{② 商品ID値引き} > 	ext{③ 会員値引き}$$
   ※同一カテゴリ内で複数該当する場合、`priority` 数値が最大のレコードを1件のみ適用。
2. **割引計算式**:
   - 割引率の場合: $	ext{割引額} = \lfloor 	ext{単価} 	imes rac{	ext{discount\_value}}{100} floor$
   - 定額引の場合: $	ext{割引額} = \min(	ext{単価}, 	ext{discount\_value})$
   - 値引き後単価: $	ext{値引き後単価} = 	ext{単価} - 	ext{割引額}$
3. **明細小計および税計算**:
   - 明細税抜小計: $	ext{item\_subtotal\_excl} = (	ext{単価} - 	ext{割引額}) 	imes 	ext{数量}$
   - 合計税抜金額: $	ext{total\_excl} = \sum 	ext{item\_subtotal\_excl}$
   - 消費税計算（外税・端数切り捨て）:
     $$	ext{tax\_amount} = \lfloor 	ext{total\_excl} 	imes 	ext{tax\_rate} floor$$
   - 税込合計金額:
     $$	ext{total\_incl} = 	ext{total\_excl} + 	ext{tax\_amount}$$

### 4.4 決済・購入確定トランザクション仕様
決済ボタン押下時、DBは分離レベル `READ COMMITTED` にて一連の処理を単一トランザクション内で実行する。

```
[BEGIN TRANSACTION]
  1. 会員存在チェック (会員ID指定時)
  2. 税率確定 (決済実行日時を基準に有効な税率を1件取得)
  3. 各SKUの店舗在庫排他ロック (SELECT ... FOR UPDATE)
     - 在庫数チェック (在庫不足でも販売を許可するかは要件に従い、履歴にはマイナス数を記録)
     - `skus.store_stock = store_stock - quantity`
  4. `transactions` レコード挿入 (売上サマリー永続化)
  5. `transaction_items` レコード一括挿入 (購入時単価・値引き額・適用税率を固定保存)
  6. `inventory_histories` レコード挿入 (変動種別: 'sale', 変動数: -quantity)
[COMMIT]
```

---

## 5. RESTful API仕様書

### 5.1 認証系
- **`POST /api/v1/auth/login`**
  - **Request**: `{ "staff_id": "ST-001", "password": "SecurePassword123!" }`
  - **Response (200 OK)**:
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
      "token_type": "bearer",
      "staff": {
        "staff_id": "ST-001",
        "staff_name": "石井 賢治",
        "role": "general"
      }
    }
    ```

### 5.2 商品・SKU系
- **`GET /api/v1/skus/barcode/{ean13}`**
  - バーコードからSKU情報・商品マスター・最新単価を取得する。
  - **Response (200 OK)**:
    ```json
    {
      "sku_id": "JK-001-M-NVY",
      "ean13": "4901234567890",
      "product_id": "JK-001",
      "product_name": "リネン混ノーカラージャケット",
      "category": "Jacket",
      "image_url": "/images/jk-001.jpg",
      "size": { "code": "M", "name": "M (Medium)" },
      "color": { "code": "NVY", "name": "NAVY" },
      "unit_price": 12000,
      "store_stock": 5
    }
    ```
  - **Response (404 Not Found)**:
    ```json
    { "detail": "指定されたバーコードの商品が登録されていません。" }
    ```

### 5.3 会員系
- **`GET /api/v1/members/{member_id}`**
  - **Response (200 OK)**:
    ```json
    {
      "member_id": "100021",
      "name": "山田 花子",
      "phone": "090-1234-5678",
      "gender": "female",
      "age": 34,
      "points": 450
    }
    ```

### 5.4 取引・販売確定系
- **`POST /api/v1/transactions/checkout`**
  - **Request**:
    ```json
    {
      "member_id": "100021",
      "payment_method": "credit_card",
      "items": [
        { "sku_id": "JK-001-M-NVY", "quantity": 1 },
        { "sku_id": "TS-102-L-WHT", "quantity": 2 }
      ]
    }
    ```
  - **Response (201 Created)**:
    ```json
    {
      "transaction_id": "TX-20260902-882194",
      "subtotal_excl_tax": 17000,
      "discount_total": 1200,
      "tax_rate": 0.10,
      "tax_amount": 1580,
      "total_incl_tax": 17380,
      "created_at": "2026-09-02T17:40:00Z"
    }
    ```

---

## 6. 非機能要件およびインフラ・セキュリティ仕様

### 6.1 パフォーマンス要件
- **バーコード読取〜レスポンス**: サーバーAPI応答時間は 200ms 以内（EAN-13検索クエリは主キーまたは一意インデックススキャンにより 5ms 未満）。
- **コネクションプーリング**:
  - FastAPI の SQLAlchemy 設定で `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600` を設定。
  - Azure Database for MySQL Flexible Server の常時接続を維持し、コールドスタートによる遅延を防止。

### 6.2 セキュリティ要件
1. **通信暗号化**: 常時 HTTPS（TLS 1.3 推奨、TLS 1.2 必須）。
2. **パスワード管理**: `bcrypt` (コストファクタ 12) によるハッシュ化保存。平文保存は厳禁。
3. **権限分離**: JWT ペイロード内の `role` に基づき、エンドポイントごとの認可（RBAC）を実施。
4. **個人情報保護**: 会員情報は暗号化通信でのみ送受信し、アクセスログに個人名・電話番号・住所を出力しない。

---

## 7. ロール・権限マトリクス

| 機能モジュール | API エンドポイント / 画面 | 一般 (general) | 店長 (manager) | システム管理者 (admin) |
| :--- | :--- | :---: | :---: | :---: |
| **レジ販売** | `/pos`, `POST /transactions/checkout` | ◯ | ◯ | ◯ |
| **返品・交換** | `/returns`, `POST /transactions/returns` | ◯ | ◯ | ◯ |
| **在庫照会** | `/inventory`, `GET /inventory` | ◯ | ◯ | ◯ |
| **入荷登録** | `POST /inventory/inbound` | ◯ | ◯ | ◯ |
| **店舗間移動** | `POST /inventory/transfer` | ✕ | ◯ | ◯ |
| **会員検索** | `GET /members/{id}` | ◯ | ◯ | ◯ |
| **会員管理(編集)**| `POST /members`, `PUT /members/{id}` | ✕ | ◯ | ◯ |
| **商品マスター更新**| `/admin/products`, `POST /products` | ✕ | ◯ | ◯ |
| **値引き設定** | `/admin/discounts` | ✕ | ◯ | ◯ |
| **税率マスター** | `/admin/tax-rates` | ✕ | ✕ | ◯ |
| **スタッフ管理** | `/admin/staffs` | ✕ | ✕ | ◯ |
