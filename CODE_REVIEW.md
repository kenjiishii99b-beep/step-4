# コードレビュー結果

| 項目 | 内容 |
|---|---|
| 実施日 | 2026-09-29 |
| 実施者 | Claude Code |
| 対象範囲 | バックエンド（`pos_service.py`を中心とした会計・返品交換ロジック、crud層）、フロントエンド（`pos/page.tsx`、`cart.ts`） |
| 前提 | 既存のセキュリティレビュー・要件チェック（`PROJECT_CONTEXT.md`「既知の残課題」）で挙がった項目は対象外。新規に見つかった正当性バグ・品質課題のみを対象とした |
| 検証方法 | 各指摘は実際のコードを直接読み、該当行を特定した上で再現シナリオを確認済み |

## サマリ

| 深刻度 | 件数 | 対応状況 |
|---|---|---|
| High | 2 | **2026-09-29 対応済み**（下記参照） |
| Medium | 1 | 未対応（軽微な丸め誤差のため保留） |
| Low | 0 | - |

**対応内容（指摘1・2）**: `backend/app/schemas/pos.py`の`CheckoutRequest`・`RefundExchangeRequest`に
`model_validator`を追加し、`items`/`return_items`/`exchange_items`それぞれの中で`sku_id`が
重複している場合は422で拒否するようにした。テストケースを追加し（`test_checkout_rejects_duplicate_sku_in_items`、
`test_return_rejects_duplicate_sku_in_same_request`）、既存分と合わせて109件全て合格を確認。

いずれもバックエンド。フロントエンド（`pos/page.tsx`、`cart.ts`）には新規の正当性バグは見つからなかった（`setCart`が一貫して関数更新形式を使っており、スキャン/手入力間の競合状態は発生しない）。ただし、以下の指摘はまさに「フロントエンドの計算値・金額は一切信用しない」設計方針が必要な理由そのもの——このアプリ自身のUIはこの不正なリクエストを作れないが、APIの入力検証がそれを独立して防いでいない。

---

## 指摘事項

### 1. [High] ✅対応済み | 会計時、同一SKUを複数行に分けたリクエストで在庫チェックを回避できる

**該当箇所**: `backend/app/services/pos_service.py:220-277`（`checkout`関数）

**問題**: `CheckoutRequest.items`（`backend/app/schemas/pos.py`）には`sku_id`の重複を禁止する制約がない。同じ`sku_id`を2行に分けて送信すると（例: 在庫100に対し数量60を2行）、245行目の在庫チェック `sku.store_stock < item.quantity` は両方の行で**同じインメモリのSkuオブジェクト**を参照する。しかし`store_stock`の減算は別ループ（326〜328行目付近）で後から行われるため、チェックの時点ではどちらの行も未減算の同じ値（100）に対して判定され、両方とも合格してしまう。

その後の減算ループで同じオブジェクトに対し`store_stock -= quantity`が2回実行され（100→40→-20）、DBの`store_stock >= 0` CHECK制約違反で未処理の`IntegrityError`（500エラー）になるか、タイミング次第では検証をすり抜けて在庫がマイナスのまま確定する可能性がある。

`refund_exchange`の`exchange_items`側は`stock_deltas`という累積辞書（456行目）でこの問題を回避しているが、`checkout`には同等の対策がない。

**再現条件**: `POST /pos/checkout`に`items: [{sku_id: "X", quantity: 60}, {sku_id: "X", quantity: 60}]`（在庫100）を送信する。

**修正案**: `checkout`の在庫チェック前に`request.items`を`sku_id`ごとに数量合算する。あるいは`CheckoutRequest`に`model_validator`を追加し、重複`sku_id`を含むリクエスト自体を拒否する。

### 2. [High] ✅対応済み | 返品時、同一SKUを複数行に分けることで二重返品防止チェックを回避できる

**該当箇所**: `backend/app/services/pos_service.py:379-384, 428-452`（`refund_exchange`関数）

**問題**: `RefundExchangeRequest.return_items`にも`sku_id`の重複禁止制約がない。382行目の`remaining = original_agg[sku].quantity - already_returned.get(sku, 0)`は、**このリクエスト内で他の行がすでに何個返品しようとしているか**を考慮せず、DBに保存済みの`already_returned`（過去の別取引分）のみを差し引いて毎回独立に計算する。

同一`sku_id`の行を2つ（それぞれ単独では正当な数量、例: 残数量2に対し2個ずつを2行）送ると、両方とも個別には検証を通過する。結果として実際の購入数量を超える金額が返金され、在庫も二重に復元される——`test_partial_return_then_exceeding_remaining_is_rejected`がカバーしているのは**別々の呼び出し**間の二重返品のみで、**同一リクエスト内**の重複行は検証されていない。

**再現条件**: SKU Xを2個購入した取引に対し、`POST /pos/refund-exchange`で`return_items: [{sku_id:"X", quantity:2}, {sku_id:"X", quantity:2}]`を送信する。

**修正案**: 指摘1と同様、`return_items`（および防御的に`exchange_items`も）を`sku_id`ごとに事前集約するか、スキーマの`model_validator`で重複`sku_id`を拒否する。

### 3. [Medium] 部分返品を複数回に分けると端数処理で少額が返金されずに残る

**該当箇所**: `backend/app/services/pos_service.py:211-214`（`_prorate_floor`）、`428-452`

**問題**: `_prorate_floor(total, numerator, denominator)`は常に**元取引の購入数量**を分母、**今回の返品数量**を分子として、その場でfloor計算する。過去に同じ取引から何個返品済みかという情報を按分計算に反映していない。

例: 3個購入・税抜小計100円の商品を1個ずつ3回に分けて返品すると、各回`floor(100×1/3)=33`円となり、合計99円しか返金されない（100円との差額1円が店舗に残る）。同様の誤差が`discount_total`・`tax_amount`の按分でも発生する。桁数の大きい取引・端数の出やすい金額ほど誤差が積み重なる。

**修正案**: 「すでに返品済みの分に対応する金額」を先に計算し、「元の合計 − 返品済み分」から今回の返品額を算出する（残数量ベースの按分）方式に変更する。または、既知の丸め誤差として仕様書に明記する。

---

## 備考

- 指摘1・2は、DB制約（`store_stock >= 0` CHECK、二重返品防止）が最終防波堤として機能する場面もあるが、想定していない500エラーや不整合なエラーレスポンスにつながりうるため、アプリケーション層での検証追加を推奨する。
- 既存の107件のpytestは、いずれも`items`/`return_items`内に重複`sku_id`を含むケースをテストしていない。修正時はテストケースも追加すること。
- フロントエンド（`pos/page.tsx`）はカート内で同一SKUを常に1行に集約する設計（`addOrIncrementCartLine`）のため、この画面経由では重複行を送信できない。今回の指摘はAPI契約そのものの防御漏れであり、別のクライアントや将来のUI変更に対する保険として対応を推奨する。
