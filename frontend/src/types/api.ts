import { Role } from "./auth";

export type PaymentMethod = "CASH" | "CREDIT_CARD" | "QR_CODE" | "IC";
export type TransactionType = "SALE" | "RETURN" | "EXCHANGE";
export type StockLocation = "STORE" | "WAREHOUSE";
export type DiscountTargetType = "SKU" | "PRODUCT" | "MEMBER";
export type DiscountType = "RATE" | "AMOUNT";

// --- POS 会計 ---
export interface CheckoutItem {
  sku_id: string;
  quantity: number;
}

export interface CheckoutRequest {
  items: CheckoutItem[];
  client_total: number;
  payment_method: PaymentMethod;
  member_id?: string | null;
  amount_tendered?: number | null;
}

export interface CheckoutResponse {
  transaction_id: string;
  subtotal_ex_tax: number;
  discount_total: number;
  tax_amount: number;
  total_inc_tax: number;
  change: number;
}

// --- 返品・交換 ---
export interface RefundExchangeRequest {
  parent_transaction_id: string;
  tx_type: "RETURN" | "EXCHANGE";
  return_items: CheckoutItem[];
  exchange_items: CheckoutItem[];
  client_total: number;
  payment_method: PaymentMethod;
  amount_tendered?: number | null;
}

export interface RefundExchangeResponse {
  transaction_id: string;
  parent_transaction_id: string;
  tx_type: TransactionType;
  subtotal_ex_tax: number;
  discount_total: number;
  tax_amount: number;
  total_inc_tax: number;
  change: number;
}

// --- 商品 / SKU ---
export interface SkuLookup {
  sku_id: string;
  barcode_ean13: string;
  product_id: string;
  product_name: string;
  reference_price: number;
  size_code: string;
  color_code: string;
  store_stock: number;
  is_active: boolean;
}

export interface SkuInput {
  sku_id: string;
  barcode_ean13: string;
  size_system_id: string;
  size_code: string;
  color_system_id: string;
  color_code: string;
  store_stock?: number;
  warehouse_stock?: number;
  location?: string | null;
}

export interface SkuResponse {
  sku_id: string;
  barcode_ean13: string;
  size_system_id: string;
  size_code: string;
  color_system_id: string;
  color_code: string;
  store_stock: number;
  warehouse_stock: number;
  location: string | null;
  is_active: boolean;
}

export interface ProductCreateRequest {
  product_id: string;
  product_name: string;
  category: string;
  default_price: number;
  image_url?: string | null;
  size_system_id?: string | null;
  color_system_id?: string | null;
  skus?: SkuInput[];
}

export interface ProductUpdateRequest {
  product_name: string;
  category: string;
  default_price: number;
  image_url?: string | null;
  size_system_id?: string | null;
  color_system_id?: string | null;
  is_active: boolean;
  skus?: SkuInput[];
}

export interface ProductResponse {
  product_id: string;
  product_name: string;
  category: string;
  default_price: number;
  image_url: string | null;
  size_system_id: string | null;
  color_system_id: string | null;
  is_active: boolean;
  skus: SkuResponse[];
}

// --- 在庫 ---
export interface InventoryStatus {
  sku_id: string;
  store_stock: number;
  warehouse_stock: number;
}

export interface InventoryReceiptRequest {
  sku_id: string;
  location: StockLocation;
  quantity: number;
}

export interface InventoryTransferRequest {
  sku_id: string;
  from_location: StockLocation;
  to_location: StockLocation;
  quantity: number;
}

// --- 会員 ---
export interface Member {
  member_id: string;
  member_name: string;
  phone_number: string | null;
  address: string | null;
  gender: string | null;
  age: number | null;
  point_balance: number;
}

export interface MemberUpsertRequest {
  member_name: string;
  phone_number?: string | null;
  address?: string | null;
  gender?: string | null;
  age?: number | null;
  point_balance?: number | null;
}

// --- スタッフ管理 ---
export interface Staff {
  staff_id: string;
  staff_name: string;
  role: Role;
  is_active: boolean;
}

export interface StaffUpsertRequest {
  staff_id: string;
  staff_name: string;
  role: Role;
  is_active: boolean;
  password?: string;
}

export interface StaffListResponse {
  items: Staff[];
  total: number;
}

// --- 値引き・税率マスター ---
export interface DiscountUpsertRequest {
  discount_id: string;
  target_type: DiscountTargetType;
  product_id?: string | null;
  sku_id?: string | null;
  discount_type: DiscountType;
  discount_value: string;
  valid_from: string;
  valid_to?: string | null;
  priority: number;
  is_active: boolean;
}

export interface DiscountResponse extends DiscountUpsertRequest {
  product_id: string | null;
  sku_id: string | null;
  valid_to: string | null;
}

export interface TaxRateUpsertRequest {
  tax_rate_id: string;
  tax_rate: string;
  valid_from: string;
  valid_to?: string | null;
  is_active: boolean;
}

export interface TaxRateResponse extends TaxRateUpsertRequest {
  valid_to: string | null;
}

// --- API エラー形状（バックエンドの HTTPException detail） ---
export interface ApiErrorDetail {
  error: string;
  message?: string;
  [key: string]: unknown;
}
