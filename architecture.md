# Multi-Agent E-commerce Dispute Resolution Architecture

## 1. Mục tiêu

Hệ thống xử lý từng `EC_*.json` bằng dữ liệu kiểm chứng được trong Olist CSV. Không agent nào được tạo ID, timestamp, payment hoặc sự kiện không có trong nguồn. Case không khớp `EC_POLICY_V2`, evidence sai hoặc action không đúng thứ tự policy đều bị dừng thay vì sinh kết quả suy đoán.

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
                                       | pass       | conflict
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

`DataRepository` load CSV một lần và cung cấp index read-only. Các agent chỉ nhận phần dữ liệu và handoff cần thiết cho vai trò của mình.

## 4. Contract và chống hallucination

- Dedupe giữ thứ tự nguồn, không dùng thứ tự ngẫu nhiên của set.
- Tiền được tính bằng `Decimal`, làm tròn hai chữ số.
- Timestamp so sánh trực tiếp theo giá trị CSV, không đổi timezone.
- Order không có item có `expected_total_brl`, `difference_brl`, `reconciled` bằng `null`.
- Evidence được đối chiếu ngược với repository.
- Action được dựng lại độc lập từ primary issue, secondary issues và refund để kiểm tra cả nội dung lẫn thứ tự.
- File output được ghi atomically chỉ sau khi toàn bộ deterministic checks pass.

## 5. Trace và lỗi

`trace.jsonl` được truncate ở đầu mỗi lượt chạy. Trace ghi handoff và kết luận của từng agent cho đủ 50 case. Lỗi dữ liệu, evidence sai, action sai hoặc schema không hợp lệ làm pipeline trả exit code 1.

## 6. Model và bảo mật

- Provider: không có; pipeline không gọi dịch vụ AI bên ngoài.
- Model: `deterministic-rule-engine`.
- Parameter size: `0 parameters`, đáp ứng rõ ràng giới hạn ≤10B.
- Tất cả phép join, tính tiền, thời gian, policy và verification đều tái lập được từ dữ liệu nguồn.

## 7. Cách chạy

```powershell
python -m src.main
python -m unittest discover -s tests -v
```
