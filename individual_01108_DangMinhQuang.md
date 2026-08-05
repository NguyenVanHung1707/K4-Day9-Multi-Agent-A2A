# Member Role Report — Day 9: Multi-Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                                 |
| --------------- | -------------------------------------------------------- |
| Họ và tên       | Đặng Minh Quang                                          |
| MSSV            | 2A202601108                                              |
| Khóa/Lớp        | K4                                                       |
| Vai trò chính   | Multi-agent orchestration, policy engine và verification |
| Ngày hoàn thành | 2026-08-05                                               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable           | File/hàm phụ trách                                                                                         | Input nhận vào               | Output bàn giao                                                            | Trạng thái                                                 |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Data access layer            | `src/repository.py`, `DataRepository`                                                                      | 9 CSV Olist                  | Các index read-only theo order, customer, item, payment, product và seller | Hoàn thành                                                 |
| Multi-agent orchestration    | `src/coordinator.py`, `src/agents/*`                                                                       | Một case `EC_*.json`         | Structured handoff giữa Customer, Order/Product, Payment và Delivery Agent | Hoàn thành                                                 |
| Policy và output composition | `src/agents/policy.py`, `Coordinator._compose`                                                             | Các structured handoff       | Primary/secondary issues, root cause, refund, actions và evidence          | Hoàn thành                                                 |
| Verification và audit        | `src/agents/verifier.py`, `src/tracing.py`                                                                 | Draft output và repository   | Output đã kiểm tra hoặc lỗi fail-closed; `trace.jsonl`                     | Hoàn thành                                                 |
| Groq LLM review              | `src/agents/groq_review.py`, `src/agents/groq_policy_review.py`, `src/agents/groq_strict_policy_review.py` | 50 candidate đã qua verifier | Review JSON theo chunk bằng `llama-3.1-8b-instant`                         | Đã tích hợp; lượt API cuối cần xác nhận trace đủ 50 review |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                      | Module được hỗ trợ                         | Kết quả                                                                    |
| ------------------------------ | ------------------------------------------ | -------------------------------------------------------------------------- |
| Viết unit và integration test  | Policy, verifier, Groq reviewer            | 10 test chạy thành công                                                    |
| Chuẩn hóa submission ZIP       | `output/`                                  | ZIP có đúng `output/EC_001.json` đến `output/EC_050.json`                  |
| Tài liệu kiến trúc và metadata | `architecture.md`, `metadata.json`         | Ghi rõ model, parameter size, runtime, quyền truy cập và handoff           |
| Bảo vệ secret                  | `.gitignore`, `.env.example`, `src/env.py` | `GROQ_API_KEY` chỉ đọc từ `.env`; không ghi key vào source, trace hoặc ZIP |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan                   | Kết quả bàn giao                                       | Cách xác minh                                    |
| --------------------- | --------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------ |
| Xử lý 50 case Olist   | `src/main.py`, `output/`                      | 50 JSON đúng tên case                                  | Đếm `output/EC_*.json`                           |
| Đối soát payment      | `src/agents/payment.py`                       | Tổng item, freight, payment, difference và reconciled  | Unit test và đối chiếu CSV                       |
| Phân tích delivery    | `src/agents/delivery.py`                      | Delivery variance và seller handoff variance           | Kiểm tra timestamp nguồn                         |
| Áp dụng EC_POLICY_V2  | `src/agents/policy.py`                        | Đủ sáu primary issue theo đúng priority                | `tests/test_pipeline.py`                         |
| Chống evidence giả    | `src/repository.py`, `src/agents/verifier.py` | Evidence sai hoặc không tồn tại bị từ chối             | Test tampering verifier                          |
| Tích hợp model 8B     | `src/config.py`, Groq review agents           | `MODEL_NAME="llama-3.1-8b-instant"`, parameter size 8B | `metadata.json` và trace sau lượt LLM thành công |

Một artifact cụ thể là `output/EC_001.json`. File chứa assessment, affected entities, customer/product context, delivery analysis, payment reconciliation, root cause, evidence, refund và actions. Các giá trị được dựng từ CSV; model không có quyền sửa dữ kiện hoặc số tiền.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Một khiếu nại không thể kết luận chỉ từ message của khách. Pipeline phải join nhiều bảng Olist, phân biệt trách nhiệm seller/logistics/platform, tính đúng tiền hoàn và chỉ nộp evidence tồn tại. Đồng thời bài yêu cầu có nhiều agent, handoff và trace thay vì dồn toàn bộ logic vào một prompt.

### Cách triển khai

`DataRepository` load CSV một lần và tạo index theo khóa. Coordinator nhận `claimed_order_id`, sau đó gọi các domain agent:

1. Customer Agent tìm `customer_unique_id` và tối đa năm related order.
2. Order & Product Agent lấy item, seller, product, category, item total và freight total.
3. Payment Agent cộng từng `payment_value`, tính expected total, difference và reconciled với sai số 0.10 BRL.
4. Delivery Agent tính delivery variance và handoff variance theo `shipping_limit_date` sớm nhất của từng seller.
5. Policy Agent áp dụng sáu luật theo first-match priority và sinh refund/actions.
6. Verifier đối chiếu evidence, entity ID, giới hạn mảng, status/refund và schema.
7. Groq Review Agent audit các candidate theo chunk nhỏ để tuân thủ quota; nếu thiếu case hoặc mâu thuẫn, pipeline fail-closed và không ghi output mới.

Tiền được tính bằng `Decimal`; dedupe giữ thứ tự nguồn; timestamp không chuyển timezone. Order không có item dùng `null` cho expected total, difference và reconciled theo README.

### Input, output và contract

| Thành phần              | Mô tả                                                                                                                         |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Input                   | `input/EC_001.json` đến `input/EC_050.json`, policy `EC_POLICY_V2`                                                            |
| Output                  | 50 JSON theo schema README và `trace.jsonl`                                                                                   |
| Module phụ thuộc        | Repository, domain agents, Policy Agent, Verifier Agent, Groq SDK                                                             |
| Module sử dụng output   | Website chấm điểm và quy trình audit của nhóm                                                                                 |
| Điều kiện lỗi cần xử lý | Order không tồn tại, null timestamp, không có item, evidence giả, policy không khớp, API quota, JSON thiếu case, LLM conflict |

### Cách xác minh

```powershell
python -m unittest discover -s tests -v
python -m src.main
python -m src.main --use-llm
```

- **Kết quả unit/integration test thực tế:** 10 test, trạng thái `OK`.
- **Kết quả deterministic thực tế:** sinh và xác minh đủ 50 output.
- **Kết quả Groq:** SDK và reviewer đã tích hợp; chỉ ghi hoàn thành sau khi `trace.jsonl` có đủ 50 event `groq_review_agent/review_agreed`.
- **Artifact/log:** `output/`, `output.zip`, `trace.jsonl`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** LLM có thể tính sai tiền, tạo evidence hoặc bỏ sót case; nếu để LLM sinh toàn bộ output thì khó tái lập.
- **Các phương án đã cân nhắc:** cho LLM xử lý end-to-end; chỉ dùng Python deterministic; hoặc dùng Python làm nguồn chân lý và LLM làm reviewer độc lập.
- **Phương án đã chọn:** structured multi-agent deterministic kết hợp Groq Llama 3.1 8B làm fail-closed reviewer.
- **Lý do:** phép join/tính tiền có tính xác định, còn LLM cung cấp một tầng review nhưng không thể làm sai lệch source facts. Model 8B đáp ứng giới hạn ≤10B.
- **Bằng chứng:** verifier tampering test pass; candidate chỉ được ghi sau khi kiểm tra schema/evidence và review completeness.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Groq trả HTTP 413 vì request 50 case yêu cầu khoảng 14.492 token trong khi tier hiện tại giới hạn 6.000 TPM. Các lần batch lớn hơn cũng có thể bỏ sót review.
- **Bước tái hiện:** chạy `python -m src.main --use-llm` với toàn bộ 50 case trong một request.
- **Nguyên nhân gốc:** batch quá lớn so với token-per-minute quota và khả năng giữ đủ phần tử của model 8B.
- **Cách xử lý:** chia thành các chunk tối đa tám case, đặt `max_tokens`, giãn cách request và kiểm tra completeness ngay sau từng chunk.
- **Cách xác minh sau khi sửa:** unit test mock pass; lượt chạy API chỉ được xem thành công khi trace có đúng 50 `review_agreed`.
- **Điều học được:** cần thiết kế orchestration theo quota thực tế và không được coi response JSON hợp lệ là đủ nếu số case bị thiếu.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi qua hệ thống thế nào?** Input cung cấp order ID; repository dùng nó để join orders với customers, items, payments, products và sellers. Mỗi domain agent trả một handoff nhỏ, sau đó Policy Agent và Verifier tổng hợp kết quả.
2. **Vì sao dùng `customer_unique_id`?** `customer_id` gắn với một order, còn `customer_unique_id` nhận diện cùng người mua qua nhiều order. Related orders chỉ thuộc customer context, không phải affected entities.
3. **Phân biệt seller delay và logistics delay thế nào?** Trước tiên kiểm tra giao cho khách có sau estimated date không. Nếu trễ và carrier nhận sau shipping limit của ít nhất một seller thì seller chịu trách nhiệm; nếu không seller nào bàn giao muộn thì logistics chịu trách nhiệm.
4. **Đối soát payment thế nào?** Expected total bằng tổng price cộng freight. Difference bằng tổng payment trừ expected total; reconciled khi trị tuyệt đối difference không quá 0.10 BRL. `payment_value` là giá trị mỗi payment row, không nhân với installment.
5. **Vì sao cần verifier và LLM review?** Verifier bảo đảm tính đúng theo CSV/schema; LLM review là tầng audit bổ sung. Nếu hai tầng mâu thuẫn thì pipeline dừng, không chọn kết quả thuận tiện hơn.

## 8. Cam kết của thành viên

Người nộp tự đánh dấu sau khi kiểm tra và điền thông tin cá nhân:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo thành viên khác.

**Họ và tên:** **Đặng Minh Quang**  
**Ngày xác nhận:** 2026-08-05
