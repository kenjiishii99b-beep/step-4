# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

アパレル業向け POS（販売時点情報管理）アプリケーション。店舗での商品販売（バーコードスキャン）、在庫（SKU/サイズ・カラー展開）管理、会計・決済、返品交換、会員管理、店長・管理者向けのマスター管理/売上集計を対象とする。

モノレポ構成で、フロントエンドとバックエンドを `frontend/` と `backend/` に分離する。

**詳細設計の一次情報は [`Apparel_POS_Design_Specification_v1.5.md`](./Apparel_POS_Design_Specification_v1.5.md) を参照すること。** UML（ユースケース/アクティビティ/シーケンス/クラス図）、DB の DDL、BFF↔Backend のエンドポイント対応表、セキュリティ要件の詳細はすべてそこにある。本 CLAUDE.md はその要点と実装時の運用ルールのみをまとめる。

## Tech stack

| レイヤ | 技術 | 補足 |
|---|---|---|
| フロントエンド | Next.js 14 (App Router) + TypeScript | **BFF (Backend For Frontend) を兼ねる。** React Query でサーバー状態管理、Tailwind CSS でスタイリング |
| バックエンド | FastAPI (Python 3.12) | 非同期 I/O、Pydantic v2 でスキーマ検証。BFF からの内部通信のみを受け付ける想定 |
| ORM / マイグレーション | SQLAlchemy 2.0 (async) + Alembic | `asyncmy` ドライバで MySQL に接続 |
| DB（本番） | Azure Database for MySQL - Flexible Server | MySQL 8.0 互換 |
| DB（ローカル） | Docker の MySQL 8.0 コンテナ | `docker-compose.yml` で起動、本番スキーマ差異が出ないよう同一メジャーバージョンを使用 |
| 認証 | JWT 二重トークン方式 | Access Token（15分, メモリ保持）+ Refresh Token（8時間, BFF が HttpOnly/Secure/SameSite=Strict Cookie で終端）。`python-jose` + `passlib[argon2]` |
| 認可 | RBAC（STAFF < MANAGER < ADMIN） | FastAPI の `Depends()` で権限チェック |
| コンテナ | Docker / docker-compose | ローカル開発は compose で frontend / backend / mysql を一括起動 |

## アーキテクチャ（BFF パターン）

```
[ブラウザ] --HTTPS--> [Next.js: BFF]  --内部通信--> [FastAPI]  --SQLAlchemy--> [MySQL]
```

- **ブラウザは FastAPI に直接アクセスしない。** すべてのAPI呼び出しはブラウザから見て同一オリジンの `/api/bff/**`（Next.js の Route Handler）を経由し、そこから FastAPI の `/api/v1/**` へサーバー間でフォワードする。
- FastAPI の物理URL（`BACKEND_INTERNAL_URL`）は `frontend/src/app/api/bff/**` のようなサーバー側コードにしか存在しない。`NEXT_PUBLIC_` で始まる環境変数としてクライアントに露出させない。
- フロントエンドのコンポーネント/フックからは `frontend/src/lib/api-client.ts`（`baseURL: "/api/bff"`）経由でのみ API を呼ぶ。
- Refresh Token の HttpOnly Cookie 変換・付与など認証まわりの終端処理は BFF (`api/bff/**`) 側の責務。

## Repository structure

```
teck4/
├── backend/            # FastAPI アプリケーション
│   ├── app/
│   │   ├── main.py          # FastAPI エントリポイント（本番は /docs, /redoc を無効化）
│   │   ├── core/             # 設定・DB接続・認証(JWT/パスワードハッシュ)などの横断的関心事
│   │   ├── api/v1/           # バージョニングされた REST エンドポイント（BFFからのみ呼ばれる）
│   │   ├── models/           # SQLAlchemy モデル（DB スキーマ）
│   │   ├── schemas/          # Pydantic スキーマ（リクエスト/レスポンス）
│   │   ├── crud/             # DB アクセスロジック
│   │   └── services/         # ドメインロジック（在庫計算、会計時のサーバー再計算など）
│   ├── alembic/               # DB マイグレーション
│   └── tests/
├── frontend/            # Next.js アプリケーション（App Router, `src/` 配下）
│   └── src/
│       ├── app/
│       │   ├── api/bff/[...path]/route.ts   # BFF: FastAPI へのリバースプロキシ
│       │   └── ...                            # ページ・レイアウト
│       ├── components/     # UI コンポーネント
│       ├── lib/             # api-client.ts など共通ロジック
│       ├── hooks/           # カスタム React フック
│       └── types/           # TypeScript 型定義
└── docker-compose.yml   # ローカル開発用（mysql / backend / frontend）
```

## 設計方針

- **ブラウザからバックエンドへの直接通信を禁止する。** 新しい API を追加する際は、必ず `backend/app/api/v1/**` と `frontend/src/app/api/bff/**` の対応するルートをセットで用意する（対応表は設計仕様書 5.1 節）。
- **フロントエンドの計算値・金額は一切信用しない。** 単価・値引き・税額は必ずバックエンド側で DB 最新マスターから再計算し、クライアント提示額と不一致なら `422 Unprocessable Entity` で中断する（改ざん・レースコンディション対策。設計仕様書 3.4 節）。
- **REST API はバージョニングする。** エンドポイントは `/api/v1/...` 配下に追加し、将来の破壊的変更は `v2` を新設して対応する。
- **レイヤ分離を徹底する。** `api/` はリクエスト/レスポンスの受け渡しのみを担当し、DB アクセスは `crud/`、ドメインロジック（在庫引当、割引計算、レジ締めなど）は `services/` に置く。エンドポイント関数の中に業務ロジックを書かない。
- **認可は RBAC で行う。** `require_roles([...])` のような依存性注入でエンドポイント単位に権限を強制する（一般スタッフ/店長/システム管理者、設計仕様書 3.1 節）。
- **マスターテーブル・取引履歴は物理削除しない。** `is_active` フラグによる論理無効化とし、外部キーは `ON DELETE RESTRICT` とする（過去取引のスナップショット整合性を優先。設計仕様書 4.1 節）。
- **スキーマ変更は必ず Alembic マイグレーションを伴う。** `app/models/` を直接編集した場合は `alembic revision --autogenerate` でマイグレーションを生成し、レビュー・コミットする。
- **ローカルの MySQL コンテナと Azure Flexible Server の差異を作らない。** ローカルも `mysql:8.0` を使用し、照合順序・タイムゾーンなど本番相当の設定を compose 側で揃える。
- **認証情報・接続文字列はコードに書かない。** `backend/.env` / `frontend/.env.local`（いずれも Git 管理外）に置き、`.env.example` を最新に保つ。

## Commands

### ローカル開発（Docker、推奨）

```bash
cp .env.example .env
docker compose up --build
```

- フロントエンド（ブラウザから使うのはここだけ）: http://localhost:3000
- バックエンド API: http://localhost:8000（ローカルでは動作確認用に Swagger UI `/docs` を有効化。本番では無効化される）
- MySQL: `localhost:3306`

### バックエンド（Docker を使わない場合）

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env

uvicorn app.main:app --reload          # 開発サーバー起動

ruff check app                          # Lint
black app                               # フォーマット

pytest                                  # 全テスト実行
pytest tests/test_health.py::test_health -v   # 単一テスト実行

alembic revision --autogenerate -m "message"   # マイグレーション生成
alembic upgrade head                            # マイグレーション適用
```

### フロントエンド

```bash
cd frontend
npm install
cp .env.example .env.local

npm run dev         # 開発サーバー起動（http://localhost:3000）
npm run lint         # ESLint
npm run typecheck    # tsc --noEmit
npm run build         # 本番ビルド
```
