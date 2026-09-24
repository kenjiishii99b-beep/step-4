# フロントエンド単体テスト結果

| 項目 | 内容 |
|---|---|
| 実施日 | 2026-09-24 |
| 実施者 | Claude Code |
| テストフレームワーク | Jest 30 + React Testing Library（`jest-environment-jsdom`） |
| 実行コマンド | `cd frontend && npx jest`（Docker Desktop停止中のためホスト側で直接実行） |
| 対象 | `frontend/src/lib/*.test.ts(x)`（`e2e/`配下のPlaywrightテストは`jest.config.js`の`testPathIgnorePatterns`で除外） |

## 結果サマリ

| スイート | テスト数 | 結果 |
|---|---|---|
| `auth-context.test.tsx` | 3 | 合格 |
| `cart.test.ts` | 6 | 合格 |
| `pos-calculations.test.ts` | 9 | 合格 |
| `validation.test.ts` | 12 | 合格 |
| **合計** | **30 / 30** | **全件合格** |

- Test Suites: 4 passed, 4 total
- Tests: 30 passed, 30 total
- 失敗・スキップ: 0件

## テストケース詳細

### `auth-context.test.tsx`（テスト仕様書 FE-U09）
| 結果 | テスト内容 |
|---|---|
| PASS | ログイン成功時、Access Tokenがメモリ上のセッション状態として保持される |
| PASS | ログイン成功時、localStorageへはAccess Tokenを保存しない |
| PASS | ログアウト時、メモリ上のセッション状態が破棄される |

### `cart.test.ts`（FE-U10、要件3.1）
| 結果 | テスト内容 |
|---|---|
| PASS | 既存SKUを追加すると数量が加算される |
| PASS | 既存SKUの数量加算は99でクランプされる |
| PASS | 新規SKUはリストに追加される |
| PASS | 99SKU登録済みの状態で新規SKUを追加すると100SKUになる |
| PASS | 100SKU登録済みの状態で新規SKU（101SKU目）を追加すると拒否される |
| PASS | 100SKU登録済みでも既存SKUの数量加算は拒否されない |

### `pos-calculations.test.ts`（FE-U01〜U03）
| 結果 | テスト内容 |
|---|---|
| PASS | `calculateSubtotal`: 単価1,000円・数量2の小計は2,000円 |
| PASS | `calculateSubtotal`: 複数行の小計は各行の単価×数量の合計 |
| PASS | `calculateSubtotal`: 空のカートの小計は0円 |
| PASS | `calculateTax`: 税抜1,980円・税率10%の税額は198円（1円未満切捨て） |
| PASS | `calculateTax`: 端数が出ない場合はそのまま計算される |
| PASS | `calculateTax`: 税抜0円の税額は0円 |
| PASS | `calculateTotal`: 税抜1,980円・税額198円の税込合計は2,178円 |
| PASS | `calculateTotal`: 値引きを差し引いた上で税額を加算した合計になる |
| PASS | `calculateTotal`: 値引きが0円の場合は税抜小計+税額と一致する |

### `validation.test.ts`（FE-U04〜U08）
| 結果 | テスト内容 |
|---|---|
| PASS | `isQuantityValid`: 数量1（下限）はバリデーション通過する |
| PASS | `isQuantityValid`: 数量99（上限）はバリデーション通過する |
| PASS | `isQuantityValid`: 数量0は範囲外のためバリデーションエラーになる |
| PASS | `isQuantityValid`: 数量100は範囲外のためバリデーションエラーになる |
| PASS | `isQuantityValid`: 負の数量はバリデーションエラーになる |
| PASS | `isQuantityValid`: 整数でない数量はバリデーションエラーになる |
| PASS | `isValidEan13Format`: 半角数字13桁は受付可能 |
| PASS | `isValidEan13Format`: 490123456789（12桁）は入力エラーになる |
| PASS | `isValidEan13Format`: 49012345678945（14桁）は入力エラーになる |
| PASS | `isValidEan13Format`: 490123456789A（英字混入）は入力エラーになる |
| PASS | `isValidEan13Format`: 4901234-67894（記号混入）は入力エラーになる |
| PASS | `isValidEan13Format`: 空文字は入力エラーになる |

## 備考

- フロントエンドの計算ロジック（`pos-calculations.ts`）はプレビュー表示専用。会計確定額は常にサーバー側（`pos_service.py`）で再計算されるため、金額の正当性はバックエンドのpytest・Playwright E2Eでも別途検証している。
- コンポーネント（`pos/page.tsx`等）のUI挙動は本スイートの対象外。Playwright（E2E、17件）でカバーしている。
- 関連テスト: バックエンド pytest 107件、Playwright E2E 17件（それぞれ Docker Desktop 起動が必要）。
