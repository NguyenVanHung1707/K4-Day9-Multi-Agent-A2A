# Multi-Agent E-commerce Dispute Resolution Architecture

## 1. Mục tiêu

Hệ thống xử lý từng `EC_*.json` bằng dữ liệu kiểm chứng được trong Olist CSV. Không agent nào được tạo ID, timestamp, payment hoặc sự kiện không có trong nguồn. Case không khớp `EC_POLICY_V2`, evidence sai, hoặc Gemini review mâu thuẫn với policy xác định đều bị dừng thay vì sinh kết quả suy đoán.

## 2. Sơ đồ agent và handoff

```text
50 Input JSON
      |
      v
Coordinator Agent (per case)
      |-- Customer Agent --------> CustomerResult
      |-- Order & Product Agent -> OrderProductResult
      |                              |
      |                              +--> Payment Agent --> PaymentResult
      |                              +--> Delivery Agent -> DeliveryResult
      |
      +-- structured results ------> Policy Agent --> deterministic candidate
                                               |
                                               v
                                        Verifier Agent
                                               |
                      50 verified candidates batched once
                                               |
                                               v
                                  Gemini Batch Review Agent
                                       | agree      | conflict
                                       v            v
                                  50 JSON files    reject run
```

## 3. Vai trò và quyền truy cập

| Agent | Trách nhiệm | Dữ liệu được đọc | Handoff |
|---|---|---|---|
| Coordinator | Điều phối, ghép output, ghi trace | Input và kết quả agent | Draft output |
| Customer | Identity và lịch sử mua hàng | orders, customers | unique customer, related orders |
| Order & Product | Order, item, seller, product, category | orders, items, products, sellers | entities và totals |
| Payment | Tổng hợp và đối soát payment | payments và handoff Order | totals, difference, reconciled |
| Delivery | Delivery/seller handoff variance | handoff Order | timestamps và late sellers |
| Policy | Áp dụng thứ tự `EC_POLICY_V2` | Structured handoff | candidate issue, cause, party, refund, actions |
| Verifier | Kiểm tra source IDs, schema và giới hạn | Draft và repository read-only | verified candidate hoặc lỗi |
| Gemini Batch Review | Đánh giá độc lập 50 candidate theo facts | Tóm tắt facts đã xác minh | 50 structured reviews hoặc conflict |

`DataRepository` load CSV một lần và cung cấp index read-only. Gemini không nhận API key trong prompt, không đọc CSV trực tiếp và không có quyền sửa handoff.

## 4. Contract và chống hallucination

- Dedupe giữ thứ tự nguồn, không dùng thứ tự ngẫu nhiên của set.
- Tiền được tính bằng `Decimal`, làm tròn hai chữ số.
- Timestamp so sánh trực tiếp theo giá trị CSV, không đổi timezone.
- Order không có item có `expected_total_brl`, `difference_brl`, `reconciled` bằng `null`.
- Gemini chạy temperature 0 và bắt buộc trả JSON theo schema.
- Batch phải có đúng một review cho mỗi case ID.
- Gemini phải đồng ý chính xác về primary issue, cause, responsible IDs và refund; khác biệt làm cả lượt chạy fail.
- Evidence được đối chiếu ngược với repository.
- File output được ghi atomically sau khi toàn bộ deterministic checks và Gemini batch review pass.

Batching 50 case vào một request giúp tuân thủ quota free tier 5 requests/phút nhưng vẫn giữ một review record riêng cho từng case.

## 5. Trace và lỗi

`trace.jsonl` được truncate ở đầu mỗi lượt chạy. Lượt chạy Gemini thành công có 400 event phân tích xác định và 50 event `gemini_review_agent/review_agreed`. Trace chỉ chứa model, case ID và kết luận audit; không chứa API key. Lỗi API, JSON sai schema, thiếu case hoặc kết luận mâu thuẫn làm pipeline trả exit code 1.

## 6. Model và bảo mật

- Provider: Google Gemini API.
- Model: `gemini-3.5-flash-lite`.
- `gemini-2.5-flash` ban đầu được cân nhắc nhưng API trả `404` vì không còn cấp cho user mới; pipeline chuyển sang model Flash ổn định khả dụng cho key.
- Parameter size: Google không công bố; khả năng đáp ứng giới hạn ≤10B không thể xác minh độc lập và được ghi rõ trong `metadata.json`.
- Secret: `GEMINI_API_KEY` chỉ nằm trong `.env`, file này bị Git ignore.

## 7. Cách chạy

```powershell
pip install -r requirements.txt
python -m src.main --use-gemini
python -m unittest discover -s tests -v
```

Chế độ `python -m src.main` không gọi API, chỉ dành cho phát triển. Trace dùng để nộp/audit phải được tạo bởi lệnh có `--use-gemini`.
