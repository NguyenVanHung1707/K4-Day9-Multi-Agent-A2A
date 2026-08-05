# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung          |
| --------------- | ----------------- |
| Họ và tên       | Nhữ Văn Hùng      |
| MSSV            | 01372             |
| Khóa/Lớp        | K4                |
| Vai trò chính   | Developer         |
| Ngày hoàn thành | 2026-08-05        |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable          | File/hàm phụ trách                              | Input nhận vào                          | Output bàn giao                        | Trạng thái |
| --------------------------- | ------------------------------------------------ | --------------------------------------- | -------------------------------------- | ---------- |
| Data Engine                 | `src/data_engine.py` — `DatasetRepository`       | 9 file CSV Olist trong `data/`          | Case snapshot (order, items, payments) | Hoàn thành |
| Policy Engine               | `src/policy_engine.py` — `PolicyResolver`        | Findings từ các specialist              | Decision (primary issue, refund, actions) | Hoàn thành |
| Multi-Agent Orchestration   | `src/agents.py` — `DisputeOrchestrator`          | Input JSON từ `input/EC_*.json`         | Output JSON trong `output/EC_*.json`   | Hoàn thành |
| Output Verifier             | `src/verifier.py` — `OutputGuard`                | Output JSON đã assembly                 | Validated output hoặc raise ValueError | Hoàn thành |
| Main Pipeline               | `main.py`                                        | 50 input JSON + CSV data                | `output.zip`, `trace.jsonl`, `metadata.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                              | Thành viên/module được hỗ trợ | Kết quả                                              |
| -------------------------------------- | ----------------------------- | ---------------------------------------------------- |
| Viết `architecture.md`                 | Toàn nhóm                     | Sơ đồ agent, vai trò, quyền truy cập và luồng handoff |
| Viết `src/check_output.py`            | Submission validation          | Script kiểm tra đủ 50 file JSON trước khi nén zip    |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                              | File/hàm/artifact liên quan         | Kết quả bàn giao                         | Cách xác minh                    |
| --------------------------------------------------- | ------------------------------------ | ---------------------------------------- | -------------------------------- |
| Xây dựng read-only repository đọc 9 CSV Olist       | `src/data_engine.py`                 | `DatasetRepository` index theo order_id  | `python main.py` — load 50 case |
| Triển khai 6 specialist agents với handoff tuần tự   | `src/agents.py`                      | 50 output JSON hợp lệ                   | `python src/check_output.py`     |
| Áp dụng bảng ưu tiên EC_POLICY_V2 xác định          | `src/policy_engine.py`               | Decision chính xác cho 50 case           | So sánh output với rubric        |
| Kiểm tra schema, array limits, policy consistency    | `src/verifier.py`                    | `OutputGuard.validate()` pass 50/50      | `python src/check_output.py`     |
| Tạo submission archive                              | `main.py` — `create_submission_zip`  | `output.zip` chứa đúng 50 JSON          | Giải nén và đếm file             |

Output cụ thể: File `output.zip` chứa 50 JSON từ `EC_001.json` đến `EC_050.json`, mỗi file tuân thủ đầy đủ schema trong Mục 6 của đề bài. Trace chạy thật được ghi vào `trace.jsonl` với 7 bước cho mỗi case (350 dòng tổng cộng).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần xử lý 50 khiếu nại giao hàng trễ của khách hàng trên dữ liệu Olist. Với mỗi case, hệ thống phải đối chiếu nhiều nguồn dữ liệu CSV (orders, items, payments, customers, products), xác định vấn đề chính theo bảng ưu tiên EC_POLICY_V2, tính toán chính xác các chỉ số giao vận và đối soát thanh toán, rồi đưa ra quyết định hoàn tiền và hành động xử lý.

### Cách triển khai

1. **DatasetRepository** (`src/data_engine.py`): Index toàn bộ CSV vào dictionary theo `order_id`. Khi nhận `claimed_order_id`, trả về snapshot bất biến gồm order row, danh sách items (sắp xếp theo `order_item_id`), danh sách payments (sắp xếp theo `payment_sequential`), `customer_unique_id` và danh sách `related_order_ids`. Tất cả phép tính tiền dùng `Decimal` với `ROUND_HALF_UP` để tránh sai số dấu phẩy động.

2. **Specialist agents** (`src/agents.py`): Mỗi specialist nhận đúng input cần thiết và trả về fact thuộc một domain duy nhất:
   - `CustomerSpecialist`: trích xuất `customer_unique_id` và `related_order_ids`.
   - `ProductSpecialist`: trích xuất `product_ids`, `category_names`, `seller_ids` từ items.
   - `DeliverySpecialist`: tính `delivery_variance_hours` và `handoff_variance_hours` cho từng seller, xác định `late_handoff` bằng so sánh trực tiếp datetime (không dựa vào số giờ đã làm tròn). Tính toán giờ dùng `Decimal` chia cho `3600` rồi làm tròn `ROUND_HALF_UP`.
   - `PaymentSpecialist`: đối soát `payment_total` với `item_total + freight_total`, xác định `reconciled` khi `|difference| <= 0.10 BRL`.
   - `ResolutionSpecialist`: áp dụng bảng ưu tiên EC_POLICY_V2 qua `PolicyResolver.decide()`.
   - `OutputSpecialist`: assembly JSON schema và gọi `OutputGuard.validate()`.

3. **PolicyResolver** (`src/policy_engine.py`): Áp dụng chính xác thứ tự ưu tiên: `canceled_order_paid` → `unavailable_order_paid` → `late_delivery_seller` → `late_delivery_logistics` → `valid_split_payment` → `unsupported_late_claim`. Actions bổ sung được thêm theo đúng thứ tự nghiệp vụ trong đề bài.

4. **DisputeOrchestrator** (`src/agents.py`): Điều phối tuần tự 6 specialist, mỗi specialist sau nhận findings từ specialist trước mà không đọc lại hoặc sửa output của specialist trước. Ghi trace cho mỗi bước handoff.

### Input, output và contract

| Thành phần              | Mô tả                                                                 |
| ----------------------- | --------------------------------------------------------------------- |
| Input                   | 50 file JSON trong `input/` với `case_id`, `claimed_order_id`, `policy_version` |
| Output                  | 50 file JSON trong `output/` theo schema Mục 6; `trace.jsonl`; `metadata.json` |
| Module phụ thuộc        | `src/config.py` (model name, parameter size)                          |
| Module sử dụng output   | `main.py` đọc output để validate và nén zip                          |
| Điều kiện lỗi cần xử lý | Order không tồn tại trong CSV → raise `ValueError`; timestamp rỗng → trả `None` |

### Cách xác minh

```bash
python main.py
python src/check_output.py
```

- **Kết quả mong đợi:** 50 file JSON hợp lệ, `Validated 50/50 output files.`, `output.zip` được tạo thành công.
- **Kết quả thực tế:** Đạt đúng như mong đợi — 50/50 file pass validation, archive tạo thành công.
- **Artifact/log:** `output.zip`, `logging/trace.jsonl`, `logging/metadata.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần chọn giữa việc dùng LLM để sinh quyết định chính sách hay dùng quy tắc xác định (deterministic rules) dựa trên bảng ưu tiên EC_POLICY_V2.
- **Các phương án đã cân nhắc:**
  1. Dùng LLM (llama-3.1-8b-instant) để phân tích dữ liệu và sinh quyết định qua prompt.
  2. Dùng quy tắc xác định từ bảng ưu tiên, LLM chỉ khai báo trong metadata.
- **Phương án đã chọn:** Quy tắc xác định (phương án 2).
- **Lý do:** Bảng ưu tiên trong đề bài định nghĩa rõ ràng từng điều kiện, responsible party, refund amount và action. Dùng LLM có rủi ro sinh ra kết quả không nhất quán giữa các lần chạy (hallucination, rounding khác nhau). Với deterministic rules, cùng input và cùng CSV luôn tạo cùng JSON, đảm bảo reproducibility 100%.
- **Bằng chứng quyết định phù hợp:** Chạy `main.py` nhiều lần cho kết quả byte-identical. Tất cả 50 case pass `OutputGuard.validate()` với schema và policy consistency.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Payments trong CSV không theo thứ tự `payment_sequential` tăng dần (ví dụ: sequence `[2, 1]` thay vì `[1, 2]`), dẫn đến `payment_ids` và `evidence_ids` trong output bị sai thứ tự so với expected.
- **Lệnh hoặc bước tái hiện:** Kiểm tra raw CSV cho order `23c312ca9f0242a48a95e5643bee2645` (EC_008): payment row sequence 2 xuất hiện trước sequence 1.
- **Nguyên nhân gốc:** `DatasetRepository._load()` đọc CSV tuần tự và append vào list theo thứ tự xuất hiện trong file. Khi CSV không đảm bảo thứ tự logic, output bị ảnh hưởng ở 9/50 case.
- **Cách xử lý:** Trong `DatasetRepository.load_order()`, thêm `items.sort(key=lambda x: int(x.get("order_item_id", 0)))` và `payments.sort(key=lambda x: int(x.get("payment_sequential", 0)))` trước khi trả về snapshot.
- **Cách xác minh sau khi sửa:**

```bash
python main.py
python src/check_output.py
```

Kết quả: 50/50 file validated, `payment_ids` trong output đúng thứ tự tăng dần cho tất cả case.

- **Điều học được:** Không được giả định thứ tự dữ liệu trong CSV. Phải sort tường minh theo business key trước khi sử dụng.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ CSV đến output JSON như thế nào?**
   `DatasetRepository` đọc 5 file CSV (customers, orders, items, payments, products), index vào dictionary theo `order_id`. Khi `DisputeOrchestrator.process_case()` nhận một input JSON, nó trích `claimed_order_id`, gọi `repository.load_order()` để lấy snapshot bất biến, rồi chuyển qua 6 specialist agents theo thứ tự: Customer → Product → Delivery → Payment → Resolution → Output. Mỗi specialist trích xuất fact từ domain riêng, specialist sau nhận findings cần thiết từ trước đó. Cuối cùng `OutputSpecialist` assembly JSON và `OutputGuard` validate trước khi ghi file.

2. **Bảng ưu tiên EC_POLICY_V2 được áp dụng ra sao?**
   `PolicyResolver.decide()` kiểm tra theo đúng thứ tự: canceled → unavailable → late_delivery_seller → late_delivery_logistics → valid_split_payment → unsupported_late_claim. Mỗi điều kiện xác định `primary_issue`, `root_cause_code`, `responsible_parties`, `refund_brl` và `actions`. Secondary issues và actions bổ sung được tính riêng theo `PolicyResolver.secondary_issues()` và `PolicyResolver.enrich_actions()`.

3. **Quality checks được thực hiện ở đâu?**
   - `OutputGuard.validate()` kiểm tra schema, primary/secondary issue hợp lệ, confidence trong [0,1], case_status khớp refund, array limits (5 order, 5 item, 3 seller, 5 payment, 20 evidence, 5 actions).
   - `check_output.py` kiểm tra đủ 50 file, case_id khớp filename, và gọi lại `OutputGuard.validate()`.
   - `main.py` xóa output cũ trước mỗi run, chỉ tạo zip khi 50 file hợp lệ.

4. **Vì sao dùng Decimal thay vì float cho tính toán tiền và giờ?**
   Float có sai số biểu diễn (ví dụ `0.1 + 0.2 != 0.3`). Với tiền tệ BRL, sai số 0.01 có thể làm `reconciled` chuyển từ True sang False hoặc ngược lại. Dùng `Decimal` với `ROUND_HALF_UP` đảm bảo kết quả khớp chính xác với phép tính tay.

5. **Reproducibility được đảm bảo bằng gì?**
   Toàn bộ quyết định chính sách là deterministic (không có random, không có LLM inference). Model `llama-3.1-8b-instant` chỉ được khai báo trong `src/config.py` và `metadata.json` theo yêu cầu bài, không tham gia vào bất kỳ phép tính nào. Cùng CSV + cùng input luôn cho cùng output.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nhữ Văn Hùng
**Ngày xác nhận:** 2026-08-05
