# デプロイ構成

本番相当のAzure環境は以下の1系統のみ。

| | 用途 | ホスティング | URL |
|---|---|---|---|
| **授業提出用環境** | tech0 gen12コースの課題提出先（講師管理のリソースグループ） | Azure App Service（Linux） | https://app-tech0-gen12-15-fe.azurewebsites.net |

> 以前はAzure Container Apps（`ca-pos-frontend` / `ca-pos-backend`）による検証環境も並行稼働させていたが、2026-10-08にコスト整理のため削除し、この環境に一本化した。Container AppsのConsumptionプラン自体は`minReplicas: 0`でアイドル時課金なしだったが、運用環境を一本化する目的で削除している（詳細は本ファイル末尾の変更履歴を参照）。

## 授業提出用環境（app-tech0-gen12-15-*）

### リソース

- サブスクリプション: `Microsoft Azure スポンサー プラン`
- リソースグループ: `rg-001-gen12`（講師管理、タグ `managed-by: instructor`, `cohort: gen12`, `student-no: 15`）
- フロントエンド: `app-tech0-gen12-15-fe`（Linux, `NODE|24-lts`）
- バックエンド: `app-tech0-gen12-15-be`（Linux, `PYTHON|3.12`）
- DB: `gen12-mysql-pos`（Azure Database for MySQL Flexible Server、講師管理の共有サーバー）、データベース名 `apparel_pos`

### フロントエンド設定

- **出力モード**: `next.config.mjs` の `output: "standalone"` で `.next/standalone` に最小サーバーを生成し、それをそのままデプロイ（Oryxビルドは使わない。Node用ビルドをAzure側でやり直すと時間がかかるため）
- **起動コマンド**: `node server.js`
- **App Settings**:
  - `BACKEND_INTERNAL_URL` = `https://app-tech0-gen12-15-be.azurewebsites.net`
  - `SCM_DO_BUILD_DURING_DEPLOYMENT` = `false`（ビルド済み成果物をそのまま配置するため）

### バックエンド設定

- **ビルド**: ソース一式（`backend/`、`.venv`・`__pycache__`・`tests`等を除く）をzipデプロイし、Oryx（`SCM_DO_BUILD_DURING_DEPLOYMENT=true`）が `pip install -r requirements.txt` 相当のビルドを実行
- **起動コマンド**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **App Settings**:
  - `DATABASE_URL` = `mysql+asyncmy://tech0:<URLエンコード済みパスワード>@gen12-mysql-pos.mysql.database.azure.com:3306/apparel_pos`（値は本ファイルに書かない。ローカルの `docker-compose.override.yml`（gitignore対象）に同じ接続文字列がある）
  - `DATABASE_SSL` = `true`
  - `SECRET_KEY` = ランダム生成した値（JWT署名用）
  - `ENVIRONMENT` = `production`（`/docs`等を無効化）
  - `BACKEND_CORS_ORIGINS` = `["https://app-tech0-gen12-15-fe.azurewebsites.net"]`
  - `SCM_DO_BUILD_DURING_DEPLOYMENT` = `true`
  - `WEBSITES_PORT` = `8000`

### 再デプロイ手順

#### フロントエンド

```bash
cd frontend
npm run build                                   # .next/standalone を生成（next.config.mjs の output: "standalone" 前提）
cp -r .next/static .next/standalone/.next/
cp -r public .next/standalone/ 2>/dev/null || true

# zip化: Windows の PowerShell Compress-Archive はバックスラッシュ区切りの
# パスでzipを作るため、Linux側(Kudu)でのrsync展開が壊れる（"Invalid argument (22)"）。
# 必ずforward-slashでzipできるツール（例: node の archiver パッケージ）を使うこと。
#   npm install --no-save archiver
#   node -e "...ZipArchive で .next/standalone を deploy.zip に固める..."

az webapp deploy -g rg-001-gen12 -n app-tech0-gen12-15-fe --src-path deploy.zip --type zip
```

#### バックエンド

```bash
cd backend
# .venv, __pycache__, .pytest_cache, .ruff_cache, .mypy_cache, .git, tests, .env を除いて
# backend/ 一式を forward-slash パスでzip化（理由は上記と同じ）

az webapp deploy -g rg-001-gen12 -n app-tech0-gen12-15-be --src-path deploy-backend.zip --type zip
```

> `az webapp deploy` はビルド完了後も10分待って応答が無いと「失敗」と報告してくることがあるが、実際にはその後起動していることがある。判断に迷ったら `curl https://.../api/v1/health` や `az webapp log tail` で実態を確認すること。

### 既知のハマりどころ

| 症状 | 原因 | 対処 |
|---|---|---|
| デプロイ直後に `rsync: ... Invalid argument (22)` で失敗 | PowerShellの`Compress-Archive`がバックスラッシュ区切りのzipを作る | forward-slashでzipできるツール（archiver等）を使う |
| バックエンド起動時に `uvicorn: not found` (exit 127) | Oryxビルドの完了前にコンテナ起動が走った（タイミング） | 再試行すれば直ることが多い。ログで `Running oryx build...` が完走しているか確認 |
| バックエンド起動時に `ModuleNotFoundError: No module named 'greenlet'` | SQLAlchemy非同期エンジンの必須依存だが`sqlalchemy`本体だけでは入らない環境がある | `backend/requirements.txt` に `greenlet` を明示（対応済み、コミット`a9e648b`） |
| `DATABASE_URL`などパスワードを含む設定を `az webapp config appsettings set` で入れようとすると拒否される | Claude Codeの自動モード分類器が生のパスワードをコマンド引数に渡す操作をブロックする（Credential Leakage/Materialization） | ユーザー本人がAzure PortalまたはCloud Shellで設定する |

---

## 変更履歴

- **2026-10-08**: Azure Container Apps（`ca-pos-frontend` / `ca-pos-backend`）を削除し、App Service環境に一本化。共有の`cae-tvmvp`環境・ACR（`acrtvmvp73bb`）・`gen12-mysql-pos`は他アプリと共有のため削除せず存続。DBとそのデータはApp Service環境と共通のため影響なし。
- **2026-10-08**: App Service環境（`app-tech0-gen12-15-*`）を新規構築。

---

*構成を変更した場合はこのファイルも更新すること。*
