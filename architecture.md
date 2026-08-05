# Kiến trúc Multi-Agent — E-commerce Dispute Resolution

## 1. Tổng quan pattern

**Case-level Parallel Fan-Out + Intra-case DAG (Router + Evaluator-Optimizer).**

Không dùng Orchestrator-Worker "phẳng" (mọi agent chạy đủ, song song hoàn
toàn) vì dữ liệu 50 case thật cho thấy:

- `investigation_scope` giống hệt nhau ở cả 50/50 case → không có lợi ích rẽ
  nhánh theo cờ scope.
- 14/50 case (28%) là `order_status ∈ {canceled, unavailable}` và gần như
  chắc chắn không có `order_delivered_customer_date` (kiểm chứng trên toàn
  dataset Olist: chỉ 6/1234 order canceled/unavailable có ngày giao) → Delivery
  Agent có thể được **Router bỏ qua** cho các case này mà không mất thông tin.
- Payment/Delivery Agent phụ thuộc dữ liệu (item, seller, shipping_limit_date)
  do Order & Product Agent cung cấp → không thể song song hoàn toàn với Order
  Agent, phải là DAG có thứ tự.

## 2. Sơ đồ

```
                        50 case (input/EC_001..050)
                                  │
                    ┌─────────────┴─────────────┐
                    │   Case-level Fan-Out       │  ThreadPoolExecutor,
                    │   (worker pool, N=5)       │  50 case độc lập hoàn toàn
                    └─────────────┬─────────────┘
                                  │  mỗi case chạy DAG dưới đây:
                                  ▼
                            Coordinator
                          (đọc claimed_order_id,
                           tra order_status)
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                    │
      Customer Agent      Order & Product Agent        │  song song
      (customer_context,          │                    │
       repeat_customer)   (item/seller/product/         │
                           category, multi_item,        │
                           multi_seller,                │
                           multiple_categories)         │
              │                   │                    │
              └─────────┬─────────┘                    │
                        ▼                               │
                  Payment Agent                          │  luôn chạy
              (đối soát item+freight                     │  (cần output
               vs payment, split_payment)                │   Order Agent)
                        │                                │
                        ▼                                │
              Router (order_status)  ◄────────────────────┘
              ┌─────────┴─────────┐
   delivered  │                   │  canceled / unavailable
              ▼                   ▼
      Delivery Agent        Delivery Agent SKIPPED
   (delivery_variance,      (trả delivery_analysis
    seller handoff,          rỗng/null, tiết kiệm
    late_handoff_seller_ids) 1 lượt gọi cho 28% case)
              │                   │
              └─────────┬─────────┘
                        ▼
                  Policy Agent (rule engine thuần)
              áp EC_POLICY_V2 theo đúng thứ tự
              ưu tiên 6 hàng → primary/secondary
              issue, root cause, responsible party,
              refund, actions
                        ▼
                  Verifier Agent (rule engine thuần)
              check schema, giới hạn mảng, evidence
              id tồn tại trong CSV, rounding 2 chữ số
                        │
                 fail? ──┴── auto-trim mảng vượt giới hạn
                        │      rồi verify lại (Evaluator-
                        │      Optimizer 1 vòng, không LLM)
                 vẫn fail → ghi trace FAILED, KHÔNG ghi
                             output sai ra file
                        ▼
                 output/EC_xxx.json + trace.jsonl (append 1 dòng/case)
```

## 3. Vai trò, quyền truy cập, LLM hay không

| Agent | File | Đọc | Dùng LLM? | Output |
|---|---|---|---|---|
| Coordinator/Router | `coordinator.py`, `main.py` | không đọc CSV trực tiếp | Không (chỉ gọi LLM ở bước cuối để sinh diễn giải, xem mục 4) | dispatch, tổng hợp, ghi file |
| Customer Agent | `agents/customer_agent.py` | `customers`, `orders` | Không | `customer_context`, cờ `repeat_customer` |
| Order & Product Agent | `agents/order_product_agent.py` | `order_items`, `products`, `sellers`, `product_category_name_translation` | Không | item/seller/product/category, cờ `multi_item_order`/`multi_seller_order`/`multiple_categories` |
| Payment Agent | `agents/payment_agent.py` | `order_payments` + số liệu từ Order Agent | Không | `payment_reconciliation`, cờ `split_payment` |
| Delivery Agent | `agents/delivery_agent.py` | `orders` (timestamp) + seller list từ Order Agent | Không | `delivery_analysis` (hoặc rỗng nếu bị Router bỏ qua) |
| Policy Agent | `policy_engine.py` | không đọc CSV — chỉ evidence đã chuẩn hoá | **Không** (quyết định kỹ thuật, xem mục 5) | `case_assessment`, `root_cause_analysis`, `financial_resolution`, `resolution_actions` |
| Verifier Agent | `verifier.py` | JSON nháp + tập ID hợp lệ | Không | JSON final hoặc lỗi |
| LLM (Gemma-2-9B-It) | `llm_client.py`, gọi từ `coordinator.py` | `customer_request.message` + digest evidence đã tính | **Có** | đoạn diễn giải tiếng Việt log vào `trace.jsonl` — **không** đưa vào `output/*.json` vì schema output cố định |

## 4. Vì sao chỉ 1 agent thật sự gọi LLM

Toàn bộ phần còn lại là join dữ liệu có cấu trúc và so sánh số/ngày — không
cần khả năng ngôn ngữ của LLM. Chỉ có phần đọc `customer_request.message`
(text tự do tiếng Việt) và diễn giải kết luận cho khách hàng mới thật sự cần
LLM. Gọi LLM ở đây không ảnh hưởng độ chính xác của `output/*.json` vì kết
quả LLM chỉ ghi vào `trace.jsonl`, không phải trường bắt buộc trong schema
mục 6 README.

Model dùng: **Gemma-2-9B-It** qua Gemini API (đúng ràng buộc mục 9.1: ≤10B
tham số). Client tự động fallback an toàn (không crash pipeline) nếu thiếu
mạng/API key — xem `llm_client.py`.

## 5. Quyết định kỹ thuật quan trọng: Policy & Verifier là rule engine, không phải LLM

- **Bối cảnh:** Bảng policy mục 4 README là logic if-elif xác định (so sánh
  timestamp, cộng trừ tiền với sai số cho phép 0.10 BRL).
- **Phương án cân nhắc:** (a) giao toàn bộ quyết định cho LLM 9B tự suy luận
  theo prompt chứa bảng policy; (b) code Python thuần triển khai đúng thứ tự
  6 hàng, LLM không tham gia.
- **Chọn (b).** Lý do: LLM 9B dễ sai số học (đối soát tiền sai 0.01-0.10 BRL
  đã đủ đổi kết quả `reconciled`), dễ sai thứ tự ưu tiên khi nhiều điều kiện
  cùng đúng, và không đảm bảo tái lập (reproducibility) giữa các lần chạy —
  trong khi mỗi case đều bị chấm điểm chính xác theo 7 thành phần có trọng số
  (mục 8 README). Rule engine đảm bảo đúng 100% quy tắc, tái lập được, và có
  thể unit-test độc lập.
- **Bằng chứng:** chạy dry-run trên đúng 50 case thật, đối chiếu phân phối
  `primary_issue` với thống kê thủ công trên CSV: 8 `canceled_order_paid` = 8
  order status canceled thật; 6 `unavailable_order_paid` = 6 order status
  unavailable thật; `late_delivery_seller` + `late_delivery_logistics` = 20 =
  đúng số order giao trễ thật; `unsupported_late_claim` + `valid_split_payment`
  = 16 = đúng số order giao đúng hạn. Không có case rơi vào nhánh fallback
  ngoài bảng policy gốc. 50/50 case pass Verifier.

## 6. Evaluator-Optimizer loop ở Verifier

Verifier không chỉ chấm PASS/FAIL một lần: nếu phát hiện mảng vượt giới hạn
(ví dụ `evidence_ids` > 20 do cộng dồn nhiều nguồn), tự động trim về đúng
giới hạn (`verifier.auto_trim`) rồi verify lại. Lỗi không tự sửa được an toàn
(thiếu order trong CSV, evidence sai định dạng) thì case được đánh dấu
`FAILED` trong `trace.jsonl` và **không ghi output sai** — tránh nhận `hard
gate = 0 điểm` vì một field sai nhỏ lẽ ra có thể tự sửa, đồng thời không tự
bịa dữ liệu để "cho đủ output".

## 7.1 Lỗi schema đã sửa

Đối chiếu lại nguyên văn README mục 4 ("Với order không có item row,
`expected_total_brl`, `difference_brl` và `reconciled` phải là `null`; item,
seller, product, category và seller handoff để mảng rỗng") phát hiện code cũ
set nhầm cả `item_total_brl`/`freight_total_brl` thành `null` cho 6 case
0-item (`EC_012/031/033/034/035/043`, đều `unavailable`). Đây là tổng trên
tập rỗng nên đúng ra phải là `0.0` — README chỉ liệt kê đúng 3 trường phải
null. Đã sửa `order_product_agent.py` (thêm cờ `has_items` thay vì suy đoán
qua `None`) và `payment_agent.py` (dùng cờ này để null-hoá đúng 3 trường).
Đã chạy lại 50 case thật + validator tự động đối chiếu schema, 0 lỗi.

## 7.2 Lỗi logic action đã sửa (phát hiện qua đối chiếu trực tiếp với ví dụ mẫu README)

`EC_002` (order `eb09635680fadffb33358e40b05c9029`) trong dữ liệu thật trùng
khớp 100% với ví dụ minh hoạ chính thức ở README mục 6 (cùng
`delivered_at`, `estimated_delivery_at`, `carrier_handoff_at`,
`delivery_variance_hours=87.39`, `shipping_limit_at`,
`handoff_variance_hours=1.04`) — tức đây chính là case gốc được dùng viết ví
dụ. So khớp trực tiếp `resolution_actions` phát hiện lệch: ví dụ mẫu
(`case_status=action_required`, primary=`late_delivery_seller`) chỉ có
`["refund_freight", "review_seller_handoff", "verify_payment_allocation"]`
— KHÔNG có `verify_refund_completion`, dù case đang `action_required`.

Code cũ suy luận "thêm `verify_refund_completion` khi `case_status ==
action_required`" — sai theo bằng chứng trên. Quy tắc đúng suy ra từ ví dụ:
`verify_refund_completion` chỉ áp dụng cho case full-refund
(`canceled_order_paid`/`unavailable_order_paid`, action chính
`issue_full_refund`); case `late_delivery_seller`/`late_delivery_logistics`
đã có `review_seller_handoff`/`review_carrier_delay` làm bước theo dõi riêng,
không cần thêm `verify_refund_completion`.

Đã sửa `policy_engine.build_actions()`, chạy lại 50 case: `verify_refund_completion`
xuất hiện đúng 14/50 lần = đúng bằng tổng số case `canceled` (8) +
`unavailable` (6) — khớp tuyệt đối.

## 7.3 Hai lỗi làm mất điểm nặng đã sửa (sau khi có kết quả chấm 7.63)

Kết quả chấm lần đầu cho thấy 2 mục thấp bất thường: **Giao vận 6.76** và
**Ngữ cảnh KH/sản phẩm 6.85**. Truy nguyên:

**(a) Router bỏ qua Delivery Agent — sai nghiêm trọng.** Giả định ban đầu
("order canceled/unavailable không có dữ liệu giao vận") bị dữ liệu thật bác
bỏ: cả **14/14** case canceled/unavailable đều CÓ
`order_estimated_delivery_date` thực trong CSV; `EC_047` còn có cả
`order_delivered_carrier_date`; và 8 case canceled có item row nên bắt buộc
phải có `seller_handoff_analysis` (README mục 4 chỉ cho phép để mảng rỗng khi
order **không có item row**, không phải theo `order_status`). Bỏ qua agent
làm 28% số case xuất `null`/mảng rỗng sai. **Đã sửa: Delivery Agent luôn chạy
cho mọi `order_status`.** Đây là bài học: tối ưu dựa trên giả định thống kê
mà không kiểm chứng từng trường bắt buộc của schema thì lợi bất cập hại.

**(b) `category_names` dịch sang tiếng Anh — nhiều khả năng sai.** Code cũ
join `product_category_name_translation.csv` để đổi `beleza_saude` →
`health_beauty`. Nhưng README mục 2 liệt kê đầy đủ các khoá join cần dùng và
**không hề nhắc** tới file translation; cột gốc trong `products.csv` là
`product_category_name` (tiếng Bồ Đào Nha). **Đã sửa: lấy trực tiếp giá trị
gốc trong CSV**, không dịch. (`multiple_categories` không đổi vì ánh xạ 1:1.)

Đã kiểm chứng thêm: `related_order_ids` không phải nguyên nhân — toàn bộ 50
case có tối đa 2 related order và thứ tự theo `orders.csv` trùng khớp thứ tự
theo `order_purchase_timestamp`.

## 7. Giới hạn đã biết

- **Không chạy được LLM thật trong môi trường build này** (sandbox chặn
  domain `generativelanguage.googleapis.com` ở tầng proxy). Toàn bộ phần
  logic nghiệp vụ (chiếm phần lớn trọng số chấm điểm) đã được test đầy đủ ở
  chế độ `--no-llm`. Cần chạy `python main.py` trên máy có mạng thật để có
  `trace.jsonl` chứa `llm_call` thật sự.
- **1 nhánh fallback ngoài bảng policy gốc**: nếu một order `delivered`,
  giao đúng hạn, nhưng payment không khớp và không phải split payment (điều
  kiện không có trong bảng mục 4), hệ thống mặc định xử lý như
  `unsupported_late_claim` với `confidence=0.6` để đánh dấu đây là suy đoán,
  tránh tự tạo refund khi không có quy tắc rõ ràng. Trên 50 case thật, nhánh
  này **không bị kích hoạt** (0/50).
