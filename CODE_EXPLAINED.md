# コード解説

このドキュメントは「何がどこにあるか」（`CODEGEN_CONTEXT.md`）ではなく、**主要なロジックが実際にどう動くか**を、コードを引用しながら順を追って説明する。初めてこのコードベースを読む人向け。

---

## 1. 認証の仕組み：なぜトークンが2種類あるのか

このアプリは「Access Token」と「Refresh Token」の二重トークン方式を使う。理由は単純なトレードオフのため：

- **Access Token**（15分で失効）: 毎リクエストに使うので、盗まれたときの被害を抑えるために短命にする
- **Refresh Token**（8時間）: 毎回ログインし直すのは使い勝手が悪いので、これでAccess Tokenを再発行する。ただし長命なのでHttpOnly Cookieに隠し、JavaScriptから読めないようにする

### ログイン時の流れ

`frontend/src/app/api/bff/auth/login/route.ts` がBFF側の窓口になる。ブラウザは直接FastAPIを叩かず、必ずこのBFFルートを経由する：

```
Browser --POST--> /api/bff/auth/login (Next.js)
                        │
                        ├─ FastAPI /api/v1/auth/login へ内部転送
                        │  （BACKEND_INTERNAL_URL、ブラウザは知らない）
                        │
                        ├─ 返ってきた refresh_token を HttpOnly Cookie に変換
                        │  （refreshCookieOptions: httpOnly, secure, sameSite=strict, path=/api/bff/auth, maxAge=8h）
                        │
                        └─ access_token だけをレスポンスボディでブラウザへ返す
```

ブラウザ側では、受け取った`access_token`を**メモリにしか保存しない**（`frontend/src/lib/token-store.ts`）：

```ts
let currentSession: StaffSession | null = null;
function setSession(next: StaffSession | null): void {
  currentSession = next;
  listeners.forEach((listener) => listener(next));
}
```

`localStorage`にも`sessionStorage`にも書かない。ブラウザをリロードすればこの変数は消える。その代わり、ページ読み込み時に毎回HttpOnly CookieからRefresh Tokenを使ってAccess Tokenを取り直す「サイレントログイン」を行う（`auth-context.tsx`の`AuthProvider`がマウント時に`refreshSession()`を呼ぶ）。

### Access Tokenが切れたときの自動リトライ

`frontend/src/lib/api-client.ts`のaxiosインターセプターが、401が返ってきたら自動的にRefreshして元のリクエストをもう一度送る：

```ts
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;  // 無限ループ防止（1回だけリトライ）
      const session = await refreshSession();
      if (session) {
        original.headers.Authorization = `Bearer ${session.access_token}`;
        return apiClient(original);  // 同じリクエストを再送
      }
    }
    return Promise.reject(error);
  }
);
```

`_retry`フラグがポイントで、これがないとRefreshにも失敗した場合に401→Refresh→401→Refresh…と無限に繰り返してしまう。Refreshにも失敗すれば（Refresh Token自体が切れている等）、`AuthProvider`の`session`が`null`になり、`(protected)/layout.tsx`が検知して`/login`へリダイレクトする。

---

## 2. BFFのリバースプロキシ：なぜ全部のAPIを手書きしないのか

`frontend/src/app/api/bff/[...path]/route.ts`が、`/api/bff/`以下の**あらゆるパス**を受け取り、対応する`/api/v1/`のパスへそのまま転送する（Next.jsの`[...path]`は「残り全部のパスセグメント」を1つの配列としてキャッチする機能）。これにより、バックエンドに新しいエンドポイントを追加しても、フロント側のBFFコードは触らなくてよい——`Authorization`ヘッダーをそのまま中継するだけで済むため。

例外は認証まわり（`auth/login`, `auth/refresh`, `auth/logout`）だけで、これらは専用のroute.tsを持つ。理由は、Refresh TokenをHttpOnly Cookieに変換する・削除するという**ブラウザには見せてはいけない処理**が必要だからだ（キャッチオールの単純転送では表現できない）。

---

## 3. 会計処理の内部ロジック（`pos_service.checkout`）

これがこのアプリの中核。実際の処理順序には理由がある。

```python
async def checkout(db, staff_id, request):
    # ① 対象SKUを行ロックしながら取得
    skus = await get_skus_for_update(db, sku_ids)
```

**なぜ最初に行ロックするか**：この後の計算中に、別のレジで同じSKUの在庫を先に押さえられてしまうと、両方とも「在庫あり」と誤判定してしまう（オーバーセル）。`SELECT ... FOR UPDATE`で行を占有し、他のトランザクションを待たせることで、在庫チェックと減算の間に割り込まれないようにする。

```python
    # ② 値引き・単価・税率をDBから取得（クライアントの提示額は一切使わない）
    price_histories = await get_active_price_histories(...)
    discounts = await get_active_discounts(...)
    tax_rate = await get_active_tax_rate(db, now)

    # ③ 各明細行の金額をサーバー側で計算
    for item in request.items:
        unit_price = _resolve_unit_price(sku, product, price_histories)
        discount = _resolve_discount(sku, product, discounts, request.member_id is not None)
        discount_amount = _compute_discount_amount(discount, unit_price, item.quantity)
        ...

    # ④ クライアントが提示した合計額と、サーバーが計算した合計額を突き合わせる
    if total_inc_tax != request.client_total:
        await db.rollback()
        raise PriceMismatchError(server_calculated_total=total_inc_tax)
```

**これがCLAUDE.mdの「フロントエンドの計算値は一切信用しない」の実装箇所**。フロントの`pos-calculations.ts`が計算する金額は、あくまで画面表示用のプレビューにすぎない。会計確定時は必ずここで再計算し、1円でもズレれば処理を止める。ズレる理由は改ざんだけでなく、「画面を開いている間に値引きが新しく設定された」といった正当なケースもあるため、フロント側はこの422を「確認して続行しますか？」という形でユーザーに見せる（`pos/page.tsx`の`pendingMismatchTotal`）。

```python
    # ⑤ 現金決済なら、確定額に対して預り金が足りているか検証
    if (
        request.payment_method == PaymentMethodEnum.CASH
        and request.amount_tendered is not None
        and request.amount_tendered < total_inc_tax
    ):
        await db.rollback()
        raise InsufficientPaymentError(required=total_inc_tax, tendered=request.amount_tendered)

    # ⑥ ここまで来て初めて、在庫減算・取引の永続化・コミット
    ...
    await persist_checkout(db, transaction, sales_items, inventory_histories)
    await db.commit()
```

**⑤が④より後、⑥より前にあることが重要**。これは過去に実際にあったバグの修正結果で、以前はこのチェックが`db.commit()`の**後**に置かれていて、預り金不足でも取引が確定してしまっていた（`change`が`max(0, ...)`でゼロにクランプされるだけで、エラーにはならなかった）。今は「金額の正当性チェックは全部、コミットより前に終わらせる」という原則になっている。

---

## 4. 値引き優先順位の解決（`_resolve_discount`）

```python
def _resolve_discount(sku, product, discounts, has_member):
    sku_matches = [d for d in discounts if d.target_type == SKU and d.sku_id == sku.sku_id]
    if sku_matches:
        return _select_best_discount(sku_matches)

    product_matches = [d for d in discounts if d.target_type == PRODUCT and d.product_id == product.product_id]
    if product_matches:
        return _select_best_discount(product_matches)

    if has_member:
        member_matches = [d for d in discounts if d.target_type == MEMBER]
        if member_matches:
            return _select_best_discount(member_matches)

    return None
```

早期returnの並びがそのまま優先順位（**SKU > 商品 > 会員**）になっている。`MEMBER`対象の値引きは「特定の会員ID」ではなく「`product_id`・`sku_id`ともにNULL」で表現される全体値引きで、`has_member`（会計に会員が紐付いているか）が真のときだけ候補になる——特定の会員の属性で絞り込むのではなく、「今この会計に会員が付いているかどうか」だけを見ている点に注意。

---

## 5. 返品・交換の按分計算

3点セットで買った商品を1点だけ返品する場合、値引き・税額をどう按分するか。`_prorate_floor`がこれを担う：

```python
def _prorate_floor(total, numerator, denominator):
    return int((Decimal(total) * numerator / Decimal(denominator)).to_integral_value(rounding=ROUND_FLOOR))

# 使用箇所
discount = -_prorate_floor(orig.discount_total, ret.quantity, orig.quantity)
tax = -_prorate_floor(orig.tax_total, ret.quantity, orig.quantity)
```

「元の値引き総額 × (返品数量 / 購入数量)」を切り捨てで計算し、マイナス符号を付けて返品明細として記録する（返品はプラスの取引の逆なので、金額・在庫増減ともに符号が反転する）。

`tx_type`が`RETURN`なら`exchange_items`は空、`EXCHANGE`なら空であってはならない——というのは`schemas/pos.py`の`model_validator`が事前に弾く。実際の処理では、返品明細の積み上げ（`stock_deltas[sku] += quantity`で在庫を戻す方向）と、交換明細の積み上げ（在庫を引き当てる方向）を同じ辞書で管理し、同じSKUが返品・交換両方に出てきても正しく相殺されるようにしている。

**2026年に見つかった注意点**: `return_items`や`exchange_items`の中に同じ`sku_id`を複数行入れると、1回のリクエスト内での重複チェックが機能しない場合があった（`CODE_REVIEW.md`参照）。現在は`RefundExchangeRequest`のスキーマ検証で、同一配列内の`sku_id`重複自体を拒否している。

---

## 6. フロントエンドのカート管理（`addOrIncrementCartLine`）

```ts
export function addOrIncrementCartLine<T extends CartLineLike>(cart: T[], newLine: T) {
  const existingIndex = cart.findIndex((line) => line.sku_id === newLine.sku_id);
  if (existingIndex >= 0) {
    const updated = [...cart];
    updated[existingIndex] = {
      ...updated[existingIndex],
      quantity: Math.min(MAX_QUANTITY, updated[existingIndex].quantity + newLine.quantity),
    };
    return { cart: updated, rejected: false };
  }
  if (cart.length >= MAX_CART_SKUS) {
    return { cart, rejected: true };  // 100SKU上限
  }
  return { cart: [...cart, newLine], rejected: false };
}
```

この関数が「同じSKUをスキャンしたら数量+1、新しいSKUなら行を追加、ただし100種類が上限」という購入リストのルールを一手に引き受けている。`pos/page.tsx`はバーコードスキャンでも手入力フォールバックでも、必ずこの関数を経由してカートを更新する——だからこそ、カートには**構造的に**同じSKUの行が重複して存在しえない（これが、会計APIの重複SKU入力チェックが「フロント経由では起こりえないが、API契約としては必要」と言える理由でもある）。

---

## 7. RBACの効き方：エンドポイント単位の依存性注入

```python
_require_manager_or_admin = require_roles([RoleEnum.MANAGER, RoleEnum.ADMIN])

@router.put("/members/{member_id}", response_model=MemberResponse)
async def upsert_member(
    member_id: str, payload: MemberUpsertRequest, db: DbSession,
    _current_staff: Annotated[Staff, Depends(_require_manager_or_admin)],
) -> MemberResponse:
```

`require_roles(...)`は関数を返す高階関数で、それ自体がFastAPIの`Depends()`に渡される。リクエストが来るたびに`get_current_active_staff`（JWTを検証してStaffを取得）→`role_checker`（許可ロールに含まれるか確認、含まれなければ403）の順で実行される。エンドポイント関数の中には権限チェックのコードが一切出てこない——これが「エンドポイント関数の中に業務ロジックを書かない」という設計方針の権限版で、権限はシグネチャ（関数の引数リスト）を見るだけで分かるようになっている。

フロントエンドの`RoleGate`コンポーネントはこれの**UI版**（見た目上隠すだけ）で、本当の防御はあくまでバックエンドのこの依存性注入。STAFFが直接APIを叩いても403で弾かれる。

---

## 関連ドキュメント

- ファイル単位で「何があるか」を知りたい → コードマップ（Artifact）
- 新しいコードを書くときの型・エンドポイント・パターン一覧 → `CODEGEN_CONTEXT.md`
- アプリ全体の状況（業務ルール・環境・テスト状況） → `PROJECT_CONTEXT.md`
- 実際の画面操作手順 → `OPERATIONS_MANUAL.md`
