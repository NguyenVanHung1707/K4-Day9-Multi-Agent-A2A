# Multi-Agent E-commerce Dispute Resolution Architecture

## 1. Mục tiêu

Hệ thống xử lý 50 case bằng facts kiểm chứng được trong Olist CSV. ID, timestamp, tiền, evidence và policy được tính bằng Python xác định. LLM chỉ audit candidate; nếu LLM mâu thuẫn hoặc trả thiếu case, cả lượt chạy bị từ chối.

## 2. Luồng agent và handoff

```text
Input JSON
   |
   v
Coordinator
   |-- Customer Agent
   |-- Order & Product Agent
   |-- Payment Agent
   |-- Delivery Agent
   v
Policy Agent (EC_POLICY_V2)
   v
Verifier Agent
   v
50 verified candidates --one batch--> Groq Review Agent (Llama 3.1 8B)
                                            | agree / conflict
                                            v
                                      output / reject
```

## 3. Vai trò và quyền truy cập

| Agent | Trách nhiệm | Dữ liệu |
|---|---|---|
| Customer | Customer identity và lịch sử | orders, customers |
| Order & Product | Order, item, seller, product, category | orders, items, products, sellers |
| Payment | Tổng hợp và đối soát | payments + Order handoff |
| Delivery | Delivery và seller handoff variance | Order handoff |
| Policy | Issue, cause, responsibility, refund, actions | Structured handoffs |
| Verifier | Evidence, schema, ID, giới hạn | Draft + repository read-only |
| Groq Review | Audit 50 candidate trong một JSON request | Facts đã xác minh, không đọc CSV trực tiếp |

## 4. Chống hallucination

- Tiền dùng `Decimal`; timestamp không đổi timezone.
- Policy chạy đúng thứ tự `EC_POLICY_V2`.
- Evidence được đối chiếu ngược với CSV.
- Llama chạy temperature 0, seed cố định và JSON Object Mode.
- Batch phải trả đúng một review cho mỗi case.
- Primary issue, cause, responsible IDs và refund phải khớp hoàn toàn candidate xác định.
- Output chỉ được ghi sau khi deterministic checks và batch review đều pass.

## 5. Trace

Lượt chạy LLM thành công có 400 event phân tích và 50 event `groq_review_agent/review_agreed`. Trace không chứa API key. Lỗi API, JSON sai, thiếu case hoặc policy conflict làm lệnh trả exit code 1.

## 6. Model và bảo mật

- Provider: GroqCloud.
- Model: `llama-3.1-8b-instant`.
- Parameter size: 8B, đáp ứng giới hạn ≤10B.
- Secret: `GROQ_API_KEY` chỉ nằm trong `.env`, file bị Git ignore.
- Groq công bố model sẽ ngừng trên free/developer tier ngày 16/08/2026; cấu hình này cần được chạy trước thời điểm đó hoặc thay model khác ≤10B.

## 7. Cách chạy

```powershell
pip install -r requirements.txt
python -m src.main --use-llm
python -m unittest discover -s tests -v
```

`python -m src.main` là chế độ deterministic dành cho phát triển; trace audit chính thức phải được tạo với `--use-llm`.
