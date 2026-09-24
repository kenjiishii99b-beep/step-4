# バックエンド単体・結合テスト結果

| 項目 | 内容 |
|---|---|
| 実施日 | 2026-09-24 |
| 実施者 | Claude Code |
| テストフレームワーク | pytest 8.4 + pytest-asyncio（ASGI経由の非同期テストクライアント） |
| 実行環境 | Docker（Python 3.12）+ **ローカルMySQL 8.0**（`mysql:3306`） |
| 実行コマンド | `docker compose -f docker-compose.yml run --rm -T --no-deps backend pytest -v` |
| 対象 | `backend/tests/*.py` |

> **実行環境の注意**: ローカルbackendは通常`docker-compose.override.yml`でAzureの共有DB（`gen12-mysql-pos`）を向いている。テストはDBにテスト用データ（`AUTOTEST-*`）を作成・更新するため、**Azure DBに書き込まないよう`-f docker-compose.yml`でoverrideを外し、ローカルMySQLに対して実行**した。

## 結果サマリ

| 項目 | 件数 |
|---|---|
| 合格 | **107** |
| 失敗 | 0 |
| エラー | 0 |
| スキップ | 0 |
| 実行時間 | 11.84秒 |

`107 passed in 11.84s`

## ファイル別

| テストファイル | 件数 | 主な検証対象 |
|---|---|---|
| `test_admin_staff.py` | 15 | スタッフ管理API（ADMIN限定、自己ロックアウト防止、一覧のフィルタ/ページング） |
| `test_auth.py` | 10 | ログイン、リフレッシュ、ロックアウト、`require_roles` |
| `test_health.py` | 1 | 死活監視 |
| `test_inventory.py` | 12 | 在庫照会・入荷・店舗⇔倉庫移動（権限、在庫不足） |
| `test_master_validity.py` | 6 | 値引き・税率の有効期間境界 |
| `test_masters.py` | 9 | 値引き・税率マスター登録と権限 |
| `test_members.py` | 7 | 会員照会・登録・更新と権限 |
| `test_pos_checkout.py` | 18 | 会計（金額改ざん検知、預かり不足、値引き優先順位、上限） |
| `test_pos_refund_exchange.py` | 11 | 返品・交換（二重返品防止、対象外取引、差額精算） |
| `test_products.py` | 15 | 商品/SKU登録・更新、バーコード/手入力検索、重複検証 |
| `test_transactions.py` | 3 | 取引照会 |
| **合計** | **107** | |

## テストケース詳細

### `test_admin_staff.py`（15）
- test_admin_can_create_new_staff
- test_create_without_password_is_rejected
- test_admin_can_change_existing_staff_role
- test_admin_can_deactivate_other_staff
- test_admin_cannot_demote_self
- test_admin_cannot_deactivate_self
- test_manager_cannot_access_admin_endpoint
- test_requires_authentication
- test_password_too_short_is_rejected
- test_admin_can_list_staff_filtered_by_role_and_active
- test_admin_can_list_inactive_staff
- test_staff_list_respects_limit
- test_staff_list_offset_beyond_total_returns_empty
- test_manager_cannot_list_staff
- test_list_staff_requires_authentication

### `test_auth.py`（10）
- test_login_success
- test_login_wrong_password_is_generic
- test_login_unknown_staff_matches_wrong_password_message
- test_login_inactive_staff_rejected
- test_refresh_issues_new_access_token
- test_refresh_rejects_access_token
- test_refresh_rejects_garbage_token
- test_login_locks_out_after_max_failures
- test_require_roles_allows_matching_role
- test_require_roles_rejects_other_role

### `test_health.py`（1）
- test_health

### `test_inventory.py`（12）
- test_get_inventory_status
- test_get_inventory_status_unknown_sku_returns_404
- test_inventory_status_requires_authentication
- test_staff_can_receive_stock_to_store
- test_staff_can_receive_stock_to_warehouse
- test_receipt_defaults_to_store_location
- test_receipt_unknown_sku_returns_404
- test_manager_can_transfer_from_warehouse_to_store
- test_transfer_more_than_available_returns_409
- test_transfer_same_location_is_rejected_by_schema
- test_staff_cannot_transfer_stock
- test_transfer_unknown_sku_returns_404

### `test_master_validity.py`（6）
- test_discount_not_active_before_valid_from
- test_discount_active_within_window
- test_discount_not_active_after_valid_to
- test_tax_rate_not_found_before_valid_from
- test_tax_rate_active_within_window
- test_tax_rate_not_active_after_valid_to

### `test_masters.py`（9）
- test_manager_can_upsert_sku_discount
- test_discount_target_type_mismatch_is_rejected
- test_discount_for_unknown_sku_returns_404
- test_discount_rate_over_100_is_rejected
- test_staff_cannot_manage_discounts
- test_admin_can_upsert_tax_rate
- test_manager_cannot_manage_tax_rates
- test_tax_rate_valid_to_before_valid_from_is_rejected
- test_masters_require_authentication

### `test_members.py`（7）
- test_manager_can_create_member
- test_staff_can_get_member
- test_get_unknown_member_returns_404
- test_update_preserves_point_balance_when_omitted
- test_staff_cannot_update_member
- test_get_member_requires_authentication
- test_update_member_requires_authentication

### `test_pos_checkout.py`（18）
- test_checkout_success
- test_checkout_tax_is_floored
- test_checkout_price_mismatch_returns_422
- test_checkout_insufficient_payment_returns_422
- test_checkout_exact_payment_gives_zero_change
- test_checkout_non_cash_ignores_amount_tendered
- test_checkout_insufficient_stock_returns_409
- test_checkout_unknown_sku_returns_404
- test_checkout_unknown_member_returns_404
- test_checkout_requires_authentication
- test_checkout_sku_discount_takes_priority_over_product_discount
- test_checkout_amount_discount_is_applied_per_unit
- test_checkout_amount_discount_does_not_exceed_line_subtotal
- test_checkout_discount_not_yet_valid_is_not_applied
- test_checkout_discount_within_valid_window_is_applied
- test_checkout_discount_after_valid_to_is_not_applied
- test_checkout_rejects_more_than_100_items
- test_checkout_rejects_quantity_over_99

### `test_pos_refund_exchange.py`（11）
- test_full_return_refunds_entire_amount
- test_partial_return_then_exceeding_remaining_is_rejected
- test_return_rejects_sku_not_in_original_transaction
- test_parent_transaction_not_found
- test_cannot_return_against_a_return
- test_exchange_for_pricier_item_charges_the_difference
- test_exchange_insufficient_payment_returns_422
- test_pure_return_ignores_amount_tendered
- test_refund_exchange_requires_authentication
- test_return_with_exchange_items_is_rejected_by_schema
- test_exchange_without_exchange_items_is_rejected_by_schema

### `test_products.py`（15）
- test_manager_can_create_product_with_skus
- test_create_product_duplicate_id_returns_409
- test_create_product_with_unknown_size_master_returns_404
- test_create_product_duplicate_barcode_returns_409
- test_create_product_duplicate_size_color_returns_409
- test_staff_cannot_create_product
- test_get_product_returns_full_detail
- test_get_unknown_product_returns_404
- test_manager_can_update_product_and_add_new_sku
- test_update_unknown_product_returns_404
- test_lookup_sku_by_barcode
- test_lookup_sku_by_product_size_color
- test_lookup_unknown_product_size_color_returns_404
- test_lookup_unknown_barcode_returns_404
- test_products_require_authentication

### `test_transactions.py`（3）
- test_get_transaction_returns_items
- test_get_unknown_transaction_returns_404
- test_get_transaction_requires_authentication

## 備考

- 通貨・在庫の整合性（金額改ざん検知、在庫マイナス防止、同時決済の排他制御）は本スイートに加え、Playwright E2E（17件）でも実ブラウザ操作で検証している。
- 同時決済の排他制御（`SELECT FOR UPDATE`）は自動化されたpytestケースがなく、curlによる並行リクエストの実地検証（テスト仕様書 IT-09）で確認している。
- 通信切断シナリオ（テスト仕様書 UT-10）は環境未整備のため未実施。
- フロントエンド単体テスト（Jest 30件）は `FRONTEND_UNIT_TEST_RESULTS.md` を参照。
