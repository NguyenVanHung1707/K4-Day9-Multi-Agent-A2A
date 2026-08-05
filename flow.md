# Workflow Chi Tiết Hệ Thống Multi-Agent (A2A) — Dispute Resolution Pipeline

Tài liệu này mô tả chi tiết luồng xử lý thực thi (Execution Workflow), giao thức giao tiếp giữa các Agents, và vị trí của các **Model LLM ($\le$ 10B)** trong kiến trúc Multi-Agent giải quyết khiếu nại thương mại điện tử Olist theo chính sách `EC_POLICY_V2`.

---

## 1. Sơ đồ Kiến trúc & Luồng Thực thi (Detailed Execution Workflow)

```mermaid
flowchart TD
    %% Styling & Theme Setup
    classDef inputStyle fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#01579b;
    classDef engineStyle fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100;
    classDef agentStyle fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20;
    classDef policyStyle fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;
    classDef verifierStyle fill:#ffebee,stroke:#d32f2f,stroke-width:2px,color:#b71c1c;
    classDef outputStyle fill:#ede7f6,stroke:#512da8,stroke-width:2px,color:#311b92;
    classDef modelBadge fill:#263238,stroke:#37474f,stroke-width:1px,color:#ffffff;

    %% Subgraph 1: Input & Data Preparation
    subgraph Phase1["PHASE 1: Khởi Tạo & Trích Xuất Dữ Liệu Chính Xác (Deterministic Data Engine)"]
        A["Input Case File: input/EC_xxx.json"] ::: inputStyle
        B["DataEngine: Nạp 9 CSV Olist trong data/"] ::: engineStyle
        C["Tính Toán Số Liệu Số Học Chuẩn Xác:
        - delivery_variance_hours
        - handoff_variance_hours
        - expected_total_brl & difference_brl
        - reconciled (abs diff <= 0.10)"] ::: engineStyle
    end

    %% Subgraph 2: Domain Agents
    subgraph Phase2["PHASE 2: Domain Analysis (Phân Phối Cho Các Chuyên Gia Tên Miền)"]
        D1["CustomerAgent
        (Phân tích lịch sử khách hàng)"] ::: agentStyle
        M1["Model: llama-3.1-8b-instant (Groq API - 8B)"] ::: modelBadge

        D2["OrderProductAgent
        (Trích xuất items, products, categories)"] ::: agentStyle
        M2["Model: llama-3.1-8b-instant (Groq API - 8B)"] ::: modelBadge

        D3["PaymentAgent
        (Đối soát thanh toán & Split Payment)"] ::: agentStyle
        M3["Model: llama-3.1-8b-instant (Groq API - 8B)"] ::: modelBadge

        D4["DeliveryAgent
        (Phân tích mốc thời gian & Trễ Seller/Vận chuyển)"] ::: agentStyle
        M4["Model: llama-3.1-8b-instant (Groq API - 8B)"] ::: modelBadge
    end

    %% Subgraph 3: Policy Agent Reasoning
    subgraph Phase3["PHASE 3: Policy Agent (Suy Luận Cây Ưu Tiên EC_POLICY_V2)"]
        P1["PolicyAgent: Đánh Giá Cây Ưu Tiên EC_POLICY_V2
        1. canceled_order_paid (Hoàn 100%)
        2. unavailable_order_paid (Hoàn 100%)
        3. late_delivery_seller (Hoàn Freight)
        4. late_delivery_logistics (Hoàn Freight)
        5. valid_split_payment (Giải thích, Hoàn 0)
        6. unsupported_late_claim (Bác bỏ, Hoàn 0)"] ::: policyStyle
        M5["Model: llama-3.1-8b-instant (Groq API - 8B <= 10B)"] ::: modelBadge
    end

    %% Subgraph 4: Verification & Guardrails
    subgraph Phase4["PHASE 4: Verifier Agent (Kiểm Tra Quy Tắc & Rào Chắn Dữ Liệu)"]
        V1["VerifierAgent: 
        - Kiểm tra 5 định dạng Regex Evidence ID
        - Xử lý null khi đơn không có Item
        - Giới hạn mảng (Max 20 evidence, 5 actions, 3 sellers)
        - Ép kiểu confidence trong range [0, 1]"] ::: verifierStyle
    end

    %% Subgraph 5: Output Generation
    subgraph Phase5["PHASE 5: Đóng Gói & Xuất Kết Quả Nộp Bài"]
        O1["Ghi file JSON kết quả: output_v3/EC_xxx.json"] ::: outputStyle
        O2["Ghi nhật ký vết chạy: trace_output_v3.jsonl"] ::: outputStyle
        O3["Ghi thông số kỹ thuật Model: metadata_output_v3.json"] ::: outputStyle
        O4["Đóng gói file nộp bài chuẩn Portal: output_v3.zip"] ::: outputStyle
    end

    %% Workflow Connections
    A --> B
    B --> C
    C --> D1 & D2 & D3 & D4
    
    D1 --- M1
    D2 --- M2
    D3 --- M3
    D4 --- M4

    D1 & D2 & D3 & D4 --> P1
    P1 --- M5

    P1 --> V1
    V1 --> O1 & O2 & O3 & O4
```

---

## 2. Phân Bổ Model LLM Kỹ Thuật (Model Allocation Matrix)

| Vị trí / Agent | Nhiệm vụ chính | Provider | Tên Model | Tham số | Giới hạn quy định |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Domain Agents** (`CustomerAgent`, `OrderProductAgent`, `PaymentAgent`, `DeliveryAgent`) | Trích xuất ngữ cảnh chuyên biệt, phân tích định danh khách hàng, đơn hàng, thanh toán và vận chuyển. | Groq API | `llama-3.1-8b-instant` | 8B | $\le$ 10B |
| **Policy Agent** (`PolicyAgent`) | Suy luận phán quyết theo cây ưu tiên chính sách `EC_POLICY_V2`, quyết định hoàn tiền, gán nguyên nhân gốc rễ và hành động. | Groq API | `llama-3.1-8b-instant` | 8B | $\le$ 10B |
| **Verifier Agent** (`VerifierAgent`) | Thực thi quy tắc Deterministic Python Rule Engine, lọc Regex Evidence ID, xử lý Null và gọt mảng theo giới hạn schema. | Deterministic Python Engine | N/A (Code Python) | N/A | Khống chế lỗi hallucination |

---

## 3. Chi Tiết Các Phase Trong Luồng Trao Đổi (A2A Handoffs)

### Phase 1: Deterministic Data Engine
- **Input:** File khiếu nại `input/EC_xxx.json` và 9 file CSV Olist trong `data/`.
- **Thực thi:** Đọc dữ liệu, tính toán chính xác số học toán tiền tệ (`expected_total_brl`, `difference_brl`, `reconciled`) và hiệu số thời gian (`delivery_variance_hours`, `handoff_variance_hours`).

### Phase 2: Domain Agents Processing (Groq LLM `llama-3.1-8b-instant`)
- Các Agent chuyên miền phân tích song song context, đảm bảo đóng gói dữ liệu đầu ra riêng biệt.

### Phase 3: Policy Agent Decision (Groq LLM `llama-3.1-8b-instant`)
- Thực thi cây suy luận 6 cấp:
  1. `canceled_order_paid`
  2. `unavailable_order_paid`
  3. `late_delivery_seller`
  4. `late_delivery_logistics`
  5. `valid_split_payment`
  6. `unsupported_late_claim`

### Phase 4: Verifier Agent Guardrails
- Thực thi rào chắn dữ liệu 100% bằng Python Rule Engine:
  - Match Regex 5 dạng Evidence ID (`order:`, `item:`, `payment:`, `seller:`, `policy:`).
  - Áp giới hạn độ dài mảng (Evidence $\le$ 20, Actions $\le$ 5, Sellers $\le$ 3, Orders $\le$ 5).
  - Ép giá trị `null` cho các đơn hàng không có sản phẩm.

### Phase 5: Pipeline Archiving & Zip Generation
- Ghi kết quả vào thư mục `output_v3/`, lưu nhật ký `trace_output_v3.jsonl`, `metadata_output_v3.json` và nén file **`output_v3.zip`** chuẩn định dạng portal (`output/EC_001.json` ... `output/EC_050.json`).