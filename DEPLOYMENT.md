# デプロイ構成

このリポジトリは **2系統のAzure環境** にデプロイされている。それぞれ目的が異なるため、どちらを触っているか常に意識すること。

| | 用途 | ホスティング | URL |
|---|---|---|---|
| **A. 実験環境** | 個人のAzureサブスクリプションでの検証用 | Azure Container Apps | https://ca-pos-frontend.whiteglacier-fe08d1c0.japaneast.azurecontainerapps.io |
| **B. 授業提出用環境** | tech0 gen12コースの課題提出先（講師管理のリソースグループ） | Azure App Service（Linux） | https://app-tech0-gen12-15-fe.azurewebsites.net |

両環境とも **同一のデータベース**（`gen12-mysql-pos` / `apparel_pos`）を共有している。一方で投入したデータはもう一方にも反映される。

---

## B. 授業提出用環境（app-tech0-gen12-15-*）

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

## A. 実験環境（ca-pos-*, Container Apps）

- 技術的な詳細（CORS、Refresh TokenのHttpOnly Cookie終端、Azure Database for MySQLのTLS設定など）は `PROJECT_CONTEXT.md` と `CODEGEN_CONTEXT.md` を参照。
- `az acr build` でイメージをビルドし、`az containerapp update --revision-suffix <unique>` でリビジョンを切り替える運用。
- DB・ユーザーはBと共通（`gen12-mysql-pos` / `apparel_pos` / ユーザー `tech0`）。

---

*作成日: 2026-10-08。構成を変更した場合はこのファイルも更新すること。*
