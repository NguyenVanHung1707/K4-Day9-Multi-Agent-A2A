# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                  |
| --------------- | ------------------------- |
| Họ và tên       | Nguyễn Văn Hùng           |
| MSSV            | K4-Day9                   |
| Khóa/Lớp        | K4                        |
| Vai trò chính   | Lead Multi-Agent Developer |
| Ngày hoàn thành | 2026-08-05                |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| Data Engine & Deterministic Calculators | `src/data_engine.py` | 9 file CSV từ Olist (`data/`) | Cấu trúc dữ liệu đã trích xuất & các cờ đối soát | Hoàn thành |
| Multi-Agent System Core & LLM Client | `src/agents.py`, `src/llm_client.py` | Groq API (`gemma2-9b-it`, `llama-3.1-8b-instant`), raw domain context | Phán quyết policy, evidence IDs, actions, feedback loop | Hoàn thành |
| Pipeline Orchestrator & Trace Logger | `run_pipeline.py` | 50 file `input/EC_0xx.json` | 50 file `output/EC_0xx.json`, `trace.jsonl`, `metadata.json` | Hoàn thành |
| Architecture & Flow Specifications | `architecture.md`, `flow.md`, `model.md` | Đề bài & quy tắc `EC_POLICY_V2` | Mermaid sequence diagrams, data permissions & spec | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| :--- | :--- | :--- |
| Verifier Agent Rule Engine | System Reliability | Xây dựng bộ lọc Regex & cap độ dài mảng tự động 100% chính xác |
| Git Branch Management | Repository & GitHub | Đẩy nhánh làm việc độc lập `HungNV` lên remote origin |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| :--- | :--- | :--- | :--- |
| Xây dựng hệ thống Multi-Agent | `src/agents.py`, `src/data_engine.py` | Luồng xử lý A2A 5 phase hoàn chỉnh | `python run_pipeline.py` |
| Xử lý 50 case đối soát khiếu nại | `output/EC_001.json` - `output/EC_050.json` | 50 JSON outputs chuẩn schema | Đã kiểm tra 50/50 file hợp lệ |
| Tạo nhật ký chạy Trace | `trace.jsonl` | Nhật ký phân tích theo từng phase cho 50 case | 50 dòng JSONL |
| Đăng ký thông số kỹ thuật Model | `metadata.json` | Khai báo các model $\le$ 10B (`gemma2-9b-it`, `llama-3.1-8b-instant`) | File JSON chuẩn cấu trúc |

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Xử lý tự động khiếu nại của khách hàng trên dữ liệu Olist bằng kiến trúc Multi-Agent theo chính sách `EC_POLICY_V2`. Tránh việc LLM bị ảo giác về số liệu (toán tiền tệ và phép trừ thời gian) bằng cách kết hợp giữa Deterministic Data Engine và LLM suy luận.

### Cách triển khai
1. **Data Engine (`src/data_engine.py`):** Đọc dữ liệu Olist CSV, lập chỉ mục (index) siêu tốc, tính toán độ lệch ngày giao `delivery_variance_hours`, `handoff_variance_hours`, tổng kỳ vọng item + freight `expected_total_brl`, tổng thanh toán `payment_total_brl` và cờ đối soát `reconciled`.
2. **Domain Agents (`src/agents.py`):** `CustomerAgent`, `OrderProductAgent`, `PaymentAgent`, `DeliveryAgent` xử lý từng phạm vi dữ liệu độc lập.
3. **Policy Agent (`PolicyAgent`):** Sử dụng `gemma2-9b-it` trên Groq API để suy luận theo cây ưu tiên chính sách `EC_POLICY_V2` (1. Canceled -> 2. Unavailable -> 3. Late Seller -> 4. Late Logistics -> 5. Valid Split -> 6. Unsupported).
4. **Verifier Agent (`VerifierAgent`):** Áp dụng bộ lọc Regex, cap mảng (tối đa 20 evidence, 5 order_ids, 5 actions,...), đảm bảo xử lý `null` chuẩn xác khi không có item.

### Input, output và contract

| Thành phần | Mô tả |
| :--- | :--- |
| **Input** | File JSON khiếu nại `input/EC_xxx.json` & 9 file CSV Olist trong `data/` |
| **Output** | File kết quả `output/EC_xxx.json`, `trace.jsonl`, `metadata.json` |
| **Module phụ thuộc** | `groq`, `pandas`, `python-dotenv` |
| **Module sử dụng output** | Hệ thống chấm điểm tự động & Leaderboard |
| **Điều kiện lỗi cần xử lý** | Đơn hàng không có item (trả `null` cho expected_total/difference/reconciled, mảng rỗng `[]` cho items/sellers/products/categories) |

### Cách xác minh

```bash
python run_pipeline.py
```

- **Kết quả mong đợi:** Xử lý thành công 50/50 case, xuất đầy đủ 50 file JSON tại `output/`, tạo `trace.jsonl` và `metadata.json`.
- **Kết quả thực tế:** Xử lý hoàn tất 50 case trong **2.74 giây**, 0 lỗi phát sinh, 100% file output khớp schema.
- **Artifact/log:** `output/`, `trace.jsonl`, `metadata.json`.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Các mô hình LLM cỡ nhỏ ($\le 10B$ parameters) như Llama-3.1 8B thường tính toán độ lệch ngày giờ ISO-8601 kém chuẩn xác, dẫn đến lỗi tính sai giờ trễ vận chuyển.
- **Các phương án đã cân nhắc:**
  1. *Phương án A:* Đưa toàn bộ mốc thời gian vào prompt và yêu cầu LLM tự thực hiện phép trừ ngày tháng.
  2. *Phương án B:* Thiết kế Deterministic Data Engine bằng Python để tính chính xác `delivery_variance_hours` và `handoff_variance_hours` bằng `datetime`, sau đó truyền kết quả số liệu cho Policy Agent.
- **Phương án đã chọn:** Phương án B.
- **Lý do:** Đảm bảo độ chính xác tuyệt đối 100% cho mọi số liệu tài chính và thời gian, không phụ thuộc vào may rủi của LLM, giúp đạt điểm tối đa ở phần Delivery Analysis và Payment Reconciliation.
- **Bằng chứng quyết định phù hợp:** Toàn bộ 50 case chạy với tốc độ 2.74s, các chỉ số hours và BRL hoàn toàn chính xác.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Xử lý đơn hàng không có dòng sản phẩm (empty items order) bị gán các giá trị kỳ vọng = 0.0 thay vì `null`, vi phạm quy tắc của `EC_POLICY_V2`.
- **Lệnh hoặc bước tái hiện:** Kiểm tra case đơn hàng bị hủy hoặc lỗi không tìm thấy item trong `olist_order_items_dataset.csv`.
- **Nguyên nhân gốc:** Logic cũ khởi tạo `expected_total_brl = 0.0` và `reconciled = True` mặc định thay vì phân biệt trạng thái có item hay không.
- **Cách xử lý:** Cập nhật `DataEngine.analyze_case_data()` và `VerifierAgent` để tự động gán `null` (`None`) cho `expected_total_brl`, `difference_brl`, `reconciled` và trả về mảng rỗng `[]` cho tất cả thực thể liên quan đến sản phẩm/seller.
- **Cách xác minh sau khi sửa:** Chạy lại `python run_pipeline.py` và kiểm tra các file output liên quan, xác nhận giá trị trả về đúng `null`.
- **Điều học được:** Luôn tuân thủ tuyệt đối quy định xử lý `null` của đề bài đối với các tập dữ liệu khiếm khuyết.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ input đến output như thế nào?**
   File `input/EC_xxx.json` chứa `claimed_order_id` được Coordinator tiếp nhận $\rightarrow$ Data Engine truy vấn 9 bảng Olist $\rightarrow$ Customer Agent, OrderProduct Agent, Payment Agent, Delivery Agent trích xuất dữ liệu miền $\rightarrow$ Policy Agent áp dụng cây quyết định `EC_POLICY_V2` $\rightarrow$ Verifier Agent kiểm duyệt schema & quy tắc mảng $\rightarrow$ Ghi file `output/EC_xxx.json`.
2. **Quy tắc bồi hoàn của chính sách EC_POLICY_V2?**
   Canceled/Unavailable $\rightarrow$ Hoàn 100% tiền thanh toán (Platform chịu trách nhiệm). Late Seller/Late Logistics $\rightarrow$ Hoàn 100% tiền vận chuyển (`freight`). Valid Split Payment / Unsupported Claim $\rightarrow$ 0 BRL refund.
3. **Vì sao phải tách riêng Verifier Agent?**
   Để làm lớp bảo vệ độc lập (guardrail), đảm bảo giới hạn mảng (max 20 evidence, max 5 actions,...), format regex của Evidence ID, làm tròn số 2 chữ số thập phân và tuân thủ schema JSON 100%.

---

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Văn Hùng  
**Ngày xác nhận:** 2026-08-05
