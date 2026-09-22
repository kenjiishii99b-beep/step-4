# Apparel POS — プロジェクトコンテキスト

*2026-09-22時点*

店舗レジ業務（バーコード販売・返品交換・在庫・会員・マスター管理）を担うアパレル業向けPOSアプリ。

- GitHub: https://github.com/kenjiishii99b-beep/step-4
- 本番URL: https://ca-pos-frontend.whiteglacier-fe08d1c0.japaneast.azurecontainerapps.io
- リソースグループ: `rg-001-gen12`

---

## 1. 何のアプリか

アパレル小売店舗の店頭レジ業務を対象にしたPOS（Point of Sale）システム。バーコード（EAN-13）でSKUをスキャンして会計し、返品・交換、在庫（店舗/倉庫）、会員、値引き・税率マスターを扱う。担当者ID＋パスワードでログインし、STAFF／MANAGER／ADMINの3段階の権限で操作範囲が変わる。

設計上の一番の原則は**「フロントエンドの計算値・金額は一切信用しない」**こと。単価・値引き・税額は必ずバックエンドがDB最新マスターから再計算し、画面側の提示額と食い違えば422で中断・再確認させる。

---

## 2. アーキテクチャ（BFFパターン）

```
[ブラウザ] --HTTPS--> [Next.js: BFF]  --内部通信--> [FastAPI]  --SQLAlchemy--> [MySQL]
   UIのみ         /api/bff/** サーバー側      /api/v1/** 内部通信のみ        apparel_pos
```

ブラウザはFastAPIに直接アクセスしない。すべて同一オリジンの`/api/bff/**`を経由し、Next.jsのRoute Handlerがサーバー間で`/api/v1/**`へ転送する。FastAPIの物理URL（`BACKEND_INTERNAL_URL`）はBFFのサーバー側コードにしか存在せず、Azure上でも`ca-pos-backend`はInternal ingress（外部非公開）。

認証はJWT二重トークン方式：Access Token（15分・メモリ保持のみ、localStorage等へは一切保存しない）＋Refresh Token（8時間・BFFがHttpOnly/Secure/SameSite=Strict Cookieで終端）。Access Token期限切れ時はAPIクライアントが401を検知して自動的にRefreshし、リクエストを1回だけリトライする。

---

## 3. 技術スタック

| レイヤ | 技術 |
|---|---|
| フロントエンド | Next.js 14（App Router）+ TypeScript、Tailwind CSS、React Query |
| バックエンド | FastAPI（Python 3.12）、Pydantic v2、非同期I/O |
| ORM / マイグレーション | SQLAlchemy 2.0（async）+ Alembic、`asyncmy`ドライバ |
| DB | Azure Database for MySQL Flexible Server（本番）／MySQL 8.0コンテナ（ローカル） |
| 認証 | JWT（`python-jose`）+ Argon2ハッシュ（`passlib`） |
| コンテナ | Docker / docker compose（ローカル）、Azure Container Apps（本番） |
| テスト | pytest（バックエンド）、Jest + React Testing Library（フロントエンド単体）、Playwright（E2E） |

---

## 4. 業務ルール（要点）

| ルール | 内容 |
|---|---|
| 値引き優先順位 | SKU対象 > 商品ID対象 > 会員対象。最上位1件のみ適用（複数種別の多段適用はしない設計） |
| 消費税 | 外税方式、決済確定日時で有効な税率マスターを適用、1円未満切り捨て |
| 単価 | SKU単価があれば商品単価より優先。会計時点の単価をスナップショットとして明細に保存し、過去取引の金額は後から変わらない |
| 在庫 | 店舗・倉庫を分けて管理。マイナス在庫は許可しない（CHECK制約 + サーバー側検証）。同一SKU同時決済は`SELECT FOR UPDATE`で排他制御 |
| 数量上限 | 1SKUあたり99点まで。購入リストは100SKUまで（101件目は追加拒否） |
| 現金会計 | 預かり金額が確定合計未満なら422（`INSUFFICIENT_PAYMENT`）で在庫確定前にロールバック |
| 返品・交換 | 元取引が通常販売（SALE）のみ対象。同一明細の再返品・元数量を超える返品は拒否。交換は返品分の在庫を戻し、交換先の在庫を引当 |
| SKU一意性 | SKU ID・EAN-13バーコードに加え、`(商品ID, サイズ, カラー)`の組み合わせも一意（重複登録は409） |
| 論理削除 | マスター・取引履歴は物理削除しない。`is_active`フラグで無効化し、外部キーは`ON DELETE RESTRICT` |

---

## 5. 権限（RBAC）

STAFF < MANAGER < ADMIN の3段階。要件定義の権限マトリクスと実装が全項目一致していることを確認済み。

| 操作 | STAFF | MANAGER | ADMIN |
|---|---|---|---|
| 会計・返品交換・在庫照会・入荷・会員照会・商品照会 | ○ | ○ | ○ |
| 店舗⇔倉庫 在庫移動 | ✕ | ○ | ○ |
| 会員の新規登録・編集 | ✕ | ○ | ○ |
| 商品・SKUの新規登録・編集 | ✕ | ○ | ○ |
| 値引きマスターの登録・編集 | ✕ | ○ | ○ |
| 税率マスターの登録・編集 | ✕ | ✕ | ○ |
| スタッフ管理 | ✕ | ✕ | ○ |

---

## 6. データモデル（主要テーブル）

| テーブル | 役割 |
|---|---|
| `staff` | 担当者。ロール・パスワードハッシュ・有効フラグ |
| `products` / `skus` | 商品とSKU（サイズ・カラー展開）。SKUはバーコード・(商品+サイズ+カラー)ともに一意 |
| `price_histories` | 単価改定履歴。有効期間つき |
| `discount_masters` | 値引き（SKU/商品/会員対象、率 or 金額、有効期間） |
| `size_masters` / `color_masters` | サイズ体系・カラー体系マスター |
| `tax_rates` | 税率マスター（有効期間つき） |
| `members` | 会員情報・保有ポイント |
| `transactions` / `sales_items` | 取引本体と明細。販売・返品・交換すべてこの2テーブルに記録し、単価・値引・税をスナップショット保存 |
| `inventory_histories` | 入荷・移動・販売・返品による在庫増減履歴 |

---

## 7. 稼働環境

### ローカル（docker compose）
- 起動: `docker compose up --build`
- URL: http://localhost:3000
- API: http://localhost:8000/docs
- DB: `localhost:3306` / `apparel_pos`

### Azure本番（`rg-001-gen12`、共有リソースグループ）
- Frontend: `ca-pos-frontend`（外部公開）
- Backend: `ca-pos-backend`（Internal ingress、外部非公開）
- 環境: `cae-tvmvp`（他プロジェクトと共有）
- ACR: `acrtvmvp73bb.azurecr.io`（共有）
- DB: `gen12-mysql-pos` / `apparel_pos`（共有サーバー、`tech0`管理）
- スケール: `minReplicas=0`（コスト優先、コールドスタートは許容する判断済み）

### テスト用アカウント（ローカル・Azure本番の両方に存在）
| ロール | ID | パスワード |
|---|---|---|
| STAFF | `E2E-CASHIER` | `E2ePlaywright!23` |
| MANAGER | `E2E-MANAGER` | `E2ePlaywright!23` |
| ADMIN | `E2E-ADMIN` | `E2ePlaywright!23` |

---

## 8. テスト状況

| 種別 | 件数 |
|---|---|
| pytest（バックエンド） | 107 |
| Jest（フロントエンド単体） | 30 |
| Playwright（E2E・実ブラウザ） | 17 |

会計の金額改ざん検知・預かり不足・同時決済の排他制御、返品交換の二重防止・対象外取引拒否、値引き優先順位、権限マトリクス全項目、SKU一意性制約、購入リスト上限、削除確認ダイアログ、手入力フォールバック、セッション自動更新まで、要件仕様書の主要項目をpytest/Jest/Playwrightで裏付け済み。通信切断シナリオ（UT-10）のみ、環境未整備のため未実施。

---

## 9. 既知の残課題

**未対応:**
- Next.js 14.2.5の既知CVE（Critical/High）— アップグレード未実施。デプロイ後の破壊的変更リスクを見て保留中
- ログインレート制限がインメモリ実装 — Container Appsが複数レプリカにスケールアウトすると制限が分散し実効性が下がる。Redis等の共有ストアへの置き換えが必要
- ACRの認証がAdmin Credentials — Managed Identityへの切り替えが望ましい
- UI未実装: 商品詳細画面・在庫移動履歴画面・会員購入履歴表示、購入リストの商品画像・行選択強調

**決定済み:**
- Container Appsのコールドスタート — `minReplicas: 0`のまま運用継続と決定（スポンサープラン内でのコスト優先）

**対応済み:**
- SKU一意性・連続スキャン・手入力フォールバック・削除確認ダイアログ — 要件チェックで見つかった優先度の高い4項目は実装・テストとも完了
- DB移行・旧サーバー削除 — 専用だった`mysql-apparel-pos`から共有サーバー`gen12-mysql-pos`へ移行し、常時課金だった旧サーバーは削除済み
