# KIẾN TRÚC HỆ THỐNG MULTI-AGENT - E-COMMERCE DISPUTE RESOLUTION (EC_POLICY_V2)

## 1. Tổng quan Kiến trúc (Architecture Overview)

Hệ thống được thiết kế theo mô hình **Multi-Agent phối hợp có kiểm chứng (Coordinated Specialist Agents with Deterministic Verification)**. Mỗi agent đảm nhận một nhiệm vụ chuyên biệt trong quy trình điều tra khiếu nại (Dispute Investigation Pipeline). 

Do yêu cầu cuộc thi quy định các LLM model phải **$\le$ 10B parameters** (ví dụ: OpenAI `gpt-4o-mini`, Qwen2.5-7B-Instruct, Llama-3.1-8B-Instruct), hệ thống áp dụng nguyên tắc **Hybrid Agent Architecture**:
- **Deterministic Data Tools Layer (Pandas/SQL Engine)**: Đảm nhận trích xuất dữ liệu thô, join bảng, và tính toán số học chính xác (thời gian, tiền tệ) để tránh lỗi ảo giác (hallucination) và sai sót tính toán của LLM < 10B.
- **LLM Reasoning & Policy Layer**: Đảm nhận suy luận logic theo quy tắc `EC_POLICY_V2`, phân loại nguyên nhân gốc rễ, xác định bên chịu trách nhiệm và lập luận đưa ra bằng chứng.
- **Deterministic Verifier Guardrail**: Kiểm định tính hợp lệ của JSON Schema, giới hạn mảng (array limits) và tính nhất quán dữ liệu trước khi hoàn tất output.

---

## 2. Sơ đồ luồng Multi-Agent (Agent Interaction & Handoff Flow)

```mermaid
graph TD
    Input[Input Case EC_xxx.json] --> Coordinator[1. Coordinator Agent]
    
    Coordinator -->|1. Query Case Data| DataEngine[(Deterministic Data Engine)]
    DataEngine -->|2. Structured Case Data| Coordinator
    
    subgraph Specialists Analysis (State Handoff)
        Coordinator -->|3a. Customer Profile| CustomerAgent[2. Customer Agent]
        Coordinator -->|3b. Items & Sellers| ProductAgent[3. Product Agent]
        Coordinator -->|3c. Timestamps| DeliveryAgent[4. Delivery Agent]
        Coordinator -->|3d. Financials| PaymentAgent[5. Payment Agent]
        
        CustomerAgent -->|4a. Customer Profile| Blackboard[(Shared Blackboard State)]
        ProductAgent -->|4b. Items & Sellers| Blackboard
        DeliveryAgent -->|4c. Delivery Variance| Blackboard
        PaymentAgent -->|4d. Reconciliation| Blackboard
    end

    Coordinator -->|5. Handoff Blackboard Context| PolicyAgent[6. Policy Agent]
    PolicyAgent -->|6. Resolution Proposal & Reasoning| Coordinator
    
    Coordinator -->|7. Audit Draft JSON| VerifierAgent[7. Verifier Agent]
    VerifierAgent -->|8. Validate limits & schema| FinalOutput{Final Decision}
    
    FinalOutput -->|Approved| Save[Output JSON & trace.jsonl]
    FinalOutput -->|Audit Failed| Fix[Auto-Fix / Log Error]
```

---

## 3. Danh sách các Agent & Vai trò chi tiết

### 1. Coordinator Agent (Agent Điều phối chính)
- **Vai trò**: Trưởng nhóm điều phối (Orchestrator).
- **Nhiệm vụ**:
  - Đọc file `input/EC_xxx.json`, trích xuất `claimed_order_id`, `investigation_scope`, `policy_version`.
  - Khởi tạo **Shared State (Blackboard)** cho case đang điều tra.
  - Phân công công việc cho các Specialist Agents và thu thập thông tin để chuyển giao (handoff) sang Policy Agent.

### 2. Customer & Order Agent (Agent Khách hàng & Đơn hàng)
- **Vai trò**: Chuyên gia lịch sử người dùng và thông tin tổng quan đơn hàng.
- **Nhiệm vụ**:
  - Xác định `customer_unique_id` tương ứng với `claimed_order_id`.
  - Tìm kiếm tất cả các `related_order_ids` của cùng khách hàng (`repeat_customer`).
  - Kiểm tra `order_status` (`canceled`, `unavailable`, `delivered`, v.v.).

### 3. Product & Item Agent (Agent Sản phẩm & Gian hàng)
- **Vai trò**: Chuyên gia về chi tiết mặt hàng và người bán.
- **Nhiệm vụ**:
  - Trích xuất danh sách `product_id`, `seller_id`, danh mục sản phẩm (`category_name`).
  - Xác định xem đơn hàng có thuộc loại `multi_item_order`, `multi_seller_order`, hoặc `multiple_categories` hay không.

### 4. Delivery Analysis Agent (Agent Phân tích Vận chuyển)
- **Vai trò**: Chuyên gia phân tích dòng thời gian giao nhận.
- **Nhiệm vụ**:
  - Tính toán `delivered_at`, `estimated_delivery_at`, `carrier_handoff_at`.
  - Tính `delivery_variance_hours` = `delivered_at` - `estimated_delivery_at` (làm tròn 2 chữ số thập phân).
  - Phân tích thời gian bàn giao của từng seller: `shipping_limit_at`, `handoff_variance_hours`, xác định `late_handoff` và danh sách `late_handoff_seller_ids`.

### 5. Payment Reconciliation Agent (Agent Đối soát Thanh toán)
- **Vai trò**: Chuyên gia đối soát tài chính và dòng tiền.
- **Nhiệm vụ**:
  - Tổng hợp tất cả các dòng thanh toán (`order_payments`): `payment_total_brl`, `payment_types`.
  - Tính `item_total_brl` và `freight_total_brl`.
  - Tính `expected_total_brl` = `item_total_brl` + `freight_total_brl`.
  - Tính `difference_brl` = `payment_total_brl` - `expected_total_brl`.
  - Đánh giá `reconciled` ($|\text{difference\_brl}| \le 0.10 \text{ BRL}$).
  - Xử lý đặc biệt với đơn hàng không có item row (`null` totals).

### 6. Policy & Resolution Agent (Agent Phân xử Quy định & Chính sách)
- **Vai trò**: Chuyên gia quyết định chính sách `EC_POLICY_V2` (Sử dụng LLM Reasoning).
- **Nhiệm vụ**:
  - Đánh giá cây quyết định ưu tiên để xác định **Primary Issue**:
    1. `canceled_order_paid`
    2. `unavailable_order_paid`
    3. `late_delivery_seller`
    4. `late_delivery_logistics`
    5. `valid_split_payment`
    6. `unsupported_late_claim`
  - Đánh giá và bổ sung danh sách **Secondary Issues** theo đúng thứ tự quy định.
  - Phân định bên chịu trách nhiệm (`responsible_parties`), mã nguyên nhân (`root_cause_analysis`), khoản hoàn tiền đề xuất (`financial_resolution`) và danh sách hành động xử lý (`resolution_actions`).
  - Tổng hợp danh sách `evidence_ids` hợp lệ theo đúng format (`order:`, `item:`, `payment:`, `seller:`, `policy:`).

### 7. Verifier & Audit Agent (Agent Kiểm định & Ghi vết)
- **Vai trò**: Trọng tài kiểm soát chất lượng & tuân thủ quy chuẩn (Deterministic Guardrail).
- **Nhiệm vụ**:
  - Kiểm tra độ tin cậy `confidence` $\in [0, 1]$.
  - Kiểm tra các giới hạn số lượng phần tử của mảng (Array Limits): $\le 5$ order IDs, $\le 5$ item IDs, $\le 3$ seller IDs, $\le 5$ payment IDs, $\le 5$ related order IDs, $\le 5$ product IDs, $\le 5$ category names, $\le 3$ root causes, $\le 3$ responsible parties, $\le 20$ evidence IDs, $\le 5$ actions.
  - Xác minh `case_status`: `action_required` (nếu refund > 0) hoặc `no_action`.
  - Ghi log hoạt động và luồng suy luận của các Agent vào file `trace.jsonl`.
  - Ghi file kết quả chuẩn JSON vào `output/EC_xxx.json`.

---

## 4. Giao thức Trao đổi & Quản lý Trạng thái (A2A Protocol & State Management)

Hệ thống sử dụng mô hình **Shared Blackboard Context** để quản lý trạng thái truyền giữa các Agent:

```json
{
  "case_id": "EC_001",
  "raw_input": { ... },
  "extracted_facts": {
    "customer": { ... },
    "order": { ... },
    "delivery": { ... },
    "payment": { ... }
  },
  "agent_assessments": {
    "policy_decision": { ... }
  },
  "verification_status": "APPROVED",
  "trace_logs": [ ... ]
}
```

---

## 5. Bảng Quyền hạn & Phân công Công cụ (Permissions & Tool Registry)

| Agent Name | Quyền truy cập Dữ liệu | Công cụ (Tools) | Loại Agent |
| :--- | :--- | :--- | :--- |
| **Coordinator Agent** | File Input (`input/`) | Input Parser, Workflow Orchestrator | Logic Flow |
| **Customer & Order Agent** | `orders.csv`, `customers.csv` | Customer Lookup Tool, Order Relational Tool | Python / Deterministic |
| **Product & Item Agent** | `order_items.csv`, `products.csv`, `sellers.csv` | Product Aggregator Tool, Category Mapping Tool | Python / Deterministic |
| **Delivery Agent** | `orders.csv`, `order_items.csv` | DateTime Variance Calculator Tool | Python / Deterministic |
| **Payment Agent** | `order_payments.csv`, `order_items.csv` | Payment Reconciler Tool | Python / Deterministic |
| **Policy Agent** | Output của 4 Domain Agents | Policy Rules Engine (`EC_POLICY_V2`), LLM Reasoning Tool | LLM ($\le$ 10B) |
| **Verifier Agent** | Toàn bộ State Context | JSON Schema Validator, Trace Logger | Python Guardrail |

---

## 6. Ma trận Tuân thủ Ràng buộc (Constraint Compliance Matrix)

1. **Giới hạn Model $\le$ 10B Parameters**: 
   - Sử dụng model mở hiệu năng cao (ví dụ: `Qwen/Qwen2.5-7B-Instruct` hoặc `meta-llama/Llama-3.1-8B-Instruct`).
   - Kết hợp với công cụ tính toán Python thuần túy cho số liệu định lượng, giúp model 7B/8B tập trung vào suy luận quy tắc chính xác 100%.
2. **Không ảo giác Evidence**:
   - Tất cả `evidence_ids` chỉ được sinh ra từ các ID có thực được trả về bởi các Data Agents.
3. **Đảm bảo Trace**:
   - Mọi lượt chuyển giao giữa các Agent đều được ghi lại dưới dạng JSON message trong file `trace.jsonl`.
