# Multi-Agent E-commerce Dispute Resolution Architecture

## 1. Mục tiêu

Hệ thống xử lý từng `EC_*.json` bằng dữ liệu kiểm chứng được trong Olist CSV. Không agent nào được tạo ID, timestamp, payment hoặc sự kiện không có trong nguồn. Case không khớp `EC_POLICY_V2` bị dừng thay vì sinh kết quả suy đoán.

## 2. Sơ đồ agent và handoff

```text
Input JSON
   |
   v
Coordinator Agent
   |-- Customer Agent --------> CustomerResult
   |-- Order & Product Agent -> OrderProductResult
   |                              |
   |                              +--> Payment Agent --> PaymentResult
   |                              +--> Delivery Agent -> DeliveryResult
   |
   +-- all structured results --> Policy Agent --> PolicyResult
                                              |
                                              v
                         Coordinator composes draft output
                                              |
                                              v
                                     Verifier Agent
                                      |         |
                                    reject    verified JSON
```

## 3. Vai trò và quyền truy cập

| Agent | Trách nhiệm | Dữ liệu được đọc | Handoff |
|---|---|---|---|
| Coordinator | Điều phối, ghép output, ghi trace | Input và kết quả agent | Draft output |
| Customer | Identity và lịch sử mua hàng | orders, customers | unique customer, related orders |
| Order & Product | Order, item, seller, product, category | orders, items, products, sellers | entities và totals |
| Payment | Tổng hợp và đối soát payment | payments và handoff Order | totals, difference, reconciled |
| Delivery | Delivery/seller handoff variance | handoff Order | timestamps và late sellers |
| Policy | Áp dụng thứ tự `EC_POLICY_V2` | Chỉ structured handoff | issue, cause, party, refund, actions |
| Verifier | Hard gate trước khi ghi | Draft và repository read-only | verified output hoặc lỗi |

`DataRepository` load CSV một lần và cung cấp index read-only. Policy Agent không tự truy vấn CSV nên ranh giới handoff rõ ràng.

## 4. Contract và tính xác định

- Dedupe giữ thứ tự nguồn, không dùng thứ tự ngẫu nhiên của set.
- Tiền được tính bằng `Decimal`, làm tròn hai chữ số.
- Timestamp so sánh trực tiếp theo giá trị CSV, không đổi timezone.
- Order không có item có `expected_total_brl`, `difference_brl`, `reconciled` bằng `null`.
- Policy chạy đúng thứ tự ưu tiên trong README.
- Evidence thuộc đúng namespace và được đối chiếu ngược với repository.
- Output chỉ được ghi sau khi Verifier pass; file tạm được replace atomically.

## 5. Trace và lỗi

`trace.jsonl` được truncate ở đầu mỗi lượt chạy. Mỗi case ghi các event `case_started`, `handoff`, `verification_passed`, `case_completed`; lỗi ghi `case_failed`. Trace chỉ chứa summary cần audit, không chứa secret. Nếu bất kỳ case nào không khớp policy hoặc evidence sai, lệnh chạy trả exit code 1 và nêu rõ case lỗi.

## 6. Model và bảo mật

Pipeline dùng agent xác định, không dùng LLM (`parameter_size = 0`, đáp ứng giới hạn ≤10B). Không cần API key. Nếu mở rộng bằng provider, secret phải nằm trong `.env` và không được ghi vào trace hoặc commit.

## 7. Cách chạy

```powershell
python -m src.main
python -m unittest discover -s tests -v
```
