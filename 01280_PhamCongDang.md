# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                         |
| --------------- | ------------------------------------------------ |
| Họ và tên       | Phạm Công Đăng                                   |
| MSSV            | 2A202601280                                      |
| Khóa/Lớp        | K4                                               |
| Vai trò chính   | Thiết kế kiến trúc multi-agent và pipeline xử lý |
| Ngày hoàn thành | 2026-08-05                                       |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | --------------- | ---------- |
| Data layer | `data_loader.py` (`OlistData`, `get_data`) | 9 CSV trong `data/` | Object cache trong RAM + các hàm tra cứu theo `order_id` | Hoàn thành |
| Customer Agent | `agents/customer_agent.py` (`run`) | `order_id`, row order | `customer_context`, cờ `repeat_customer` | Hoàn thành |
| Order & Product Agent | `agents/order_product_agent.py` (`run`) | `order_id` | item/seller/product/category, cờ `multi_item_order`, `multi_seller_order`, `multiple_categories` | Hoàn thành |
| Payment Agent | `agents/payment_agent.py` (`run`) | `order_id`, tổng tiền hàng + phí ship, cờ `has_items` | `payment_reconciliation`, cờ `split_payment` | Hoàn thành |
| Delivery Agent | `agents/delivery_agent.py` (`run`) | `order_id`, row order, `items_df` | `delivery_analysis` | Hoàn thành |
| Policy Agent (rule engine) | `policy_engine.py` (`determine_primary_issue`, `build_actions`, `build_root_cause_and_financial`) | Evidence bundle từ 4 agent | `case_assessment`, `root_cause_analysis`, `financial_resolution`, `resolution_actions` | Hoàn thành |
| Verifier Agent | `verifier.py` (`verify`, `auto_trim`) | JSON nháp + tập ID hợp lệ | JSON đã kiểm tra hoặc danh sách lỗi | Hoàn thành |
| Orchestration | `coordinator.py`, `main.py` | 50 file `input/EC_*.json` | 50 file `output/EC_*.json`, `logging/trace.jsonl` | Hoàn thành |
| LLM client | `llm_client.py` | `customer_request.message` + digest evidence | Đoạn diễn giải tiếng Việt ghi vào `trace.jsonl` | Hoàn thành |
| Tài liệu | `architecture.md`, `logging/metadata.json` | — | Sơ đồ agent, quyền truy cập, luồng handoff, khai báo model/runtime | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Viết script validator đối chiếu output với README | Khâu QA trước khi nộp | Script kiểm 11 nhóm ràng buộc (schema, giới hạn mảng, định dạng evidence, làm tròn, thứ tự mảng, tính nhất quán refund↔status); phát hiện được các sai lệch mà mắt thường bỏ qua |
| Xử lý môi trường chạy trên Windows | Khâu vận hành | Ghim `pandas<3` (bản đã kiểm chứng thật), dùng `uv` quản lý venv, xử lý lỗi Cloudflare 1010 và rate limit 429 khi gọi API |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | --------------------------- | ---------------- | ------------- |
| Xây pipeline 7 agent xử lý 50 case | `coordinator.py`, `agents/` | 50 file `output/EC_*.json` | `uv run main.py --workers 2` → in `Xong: 50/50 case OK` |
| Áp `EC_POLICY_V2` bằng rule engine | `policy_engine.py` | `primary_issue`, `secondary_issues`, refund, actions | Đối chiếu phân bố `primary_issue` với thống kê thủ công trên CSV |
| Kiểm tra schema trước khi ghi file | `verifier.py` | Không ghi file cho case sai schema | Validator độc lập báo 0 lỗi trên 50 file |
| Gọi LLM ≤10B và ghi trace | `llm_client.py`, `logging/trace.jsonl` | 50 dòng trace, mỗi dòng ghi rõ model, latency, trạng thái | Đọc `trace.jsonl`, kiểm trường `llm_call.model` và `llm_call.ok` |

Một output cụ thể mà phần việc của tôi tạo ra và giúp xác minh:

Script validator đối chiếu 50 file output với README phát hiện hai sai lệch mà đọc mắt không thấy: `item_total_brl` và `freight_total_brl` bị để `null` cho 6 case không có item row (README chỉ yêu cầu `null` cho `expected_total_brl`, `difference_brl`, `reconciled` — hai trường kia là tổng trên tập rỗng nên phải là `0.0`), và `estimated_delivery_at` bị `null` ở 14 case dù CSV có dữ liệu thật. Sau khi sửa, validator báo 0 lỗi; điểm chấm mục Giao vận tăng từ 67.60 lên 79.56, mục Ngữ cảnh khách hàng/sản phẩm tăng từ 68.49 lên 80.23.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Mỗi khiếu nại chỉ cung cấp `claimed_order_id`. Hệ thống phải tự đối chiếu 9 bảng CSV để dựng lại toàn bộ bối cảnh đơn hàng (khách, item, seller, sản phẩm, thanh toán, các mốc giao vận), rồi áp `EC_POLICY_V2` để kết luận vấn đề chính, bên chịu trách nhiệm, khoản hoàn và hành động xử lý — với ràng buộc mỗi agent chỉ được dùng model ≤10B tham số.

### Cách triển khai

Kiến trúc là **case-level parallel fan-out + DAG trong từng case**:

- 50 case độc lập nhau nên chạy song song qua `ThreadPoolExecutor`.
- Trong một case, Customer Agent và Order & Product Agent chạy trước; Payment Agent và Delivery Agent phụ thuộc dữ liệu item/seller nên chạy sau. Cách này tránh việc mỗi agent tự join lại CSV, vốn dễ gây lệch số liệu giữa các agent do trùng logic.
- Các agent handoff bằng dict có cấu trúc cố định, kèm `evidence_ids` dựng ngay tại nguồn, không dùng văn bản tự do — nhờ vậy Policy Agent chỉ gom lại chứ không tự bịa ID.
- Policy Agent áp bảng policy theo đúng thứ tự ưu tiên 6 hàng dưới dạng chuỗi if-elif.
- Verifier Agent chạy vòng kiểm tra — tự sửa: phát hiện mảng vượt giới hạn thì tự cắt rồi kiểm lại; lỗi không tự sửa được an toàn thì đánh dấu case `FAILED` trong trace và **không ghi output sai**, tránh nhận 0 điểm vì một trường lẽ ra sửa được.

Quyết định quan trọng: **Policy Agent và Verifier Agent là code Python thuần, không dùng LLM**. LLM (Llama 3.1 8B) chỉ đọc `customer_request.message` và sinh đoạn diễn giải tiếng Việt ghi vào `trace.jsonl`, không tham gia vào bất kỳ con số nào trong `output/*.json`.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ----- |
| Input | `input/EC_xxx.json` gồm `case_id`, `customer_request.claimed_order_id`, `investigation_scope`, `policy_version` |
| Output | `output/EC_xxx.json` theo schema mục 6 README (11 khối bắt buộc); `logging/trace.jsonl` 1 dòng/case |
| Module phụ thuộc | `data_loader.py` — mọi agent đọc dữ liệu qua đây |
| Module sử dụng output | `policy_engine.py` dùng evidence bundle; `verifier.py` dùng JSON nháp; `main.py` ghi file |
| Điều kiện lỗi cần xử lý | `order_id` không có trong `orders.csv`; order không có item row (6 case — phải `null` đúng 3 trường và để mảng rỗng); `order_delivered_customer_date` hoặc `order_delivered_carrier_date` rỗng; LLM bị rate limit hoặc mất mạng (không được làm sập pipeline) |

### Cách xác minh

```bash
uv run main.py --workers 2
uv run python -c "import json;t=[json.loads(l) for l in open('logging/trace.jsonl',encoding='utf-8')];print(len(t),'dong trace')"
```

- **Kết quả mong đợi:** in `Xong: 50/50 case OK`; sinh đủ 50 file trong `output/` và 50 dòng trong `logging/trace.jsonl`.
- **Kết quả thực tế:** đúng như mong đợi — 50/50 case OK, 50 file output, 50 dòng trace. Ở lần chạy đầu, một số lượt gọi LLM trả về HTTP 429 do vượt hạn mức 6000 token/phút của Groq free tier; đã bổ sung cơ chế đọc thời gian chờ trong response rồi thử lại.
- **Artifact/log:** `output/EC_001.json` … `output/EC_050.json`, `logging/trace.jsonl`, `logging/metadata.json`. Không chứa secret — API key nằm trong `.env` và đã có trong `.gitignore`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Bảng `EC_POLICY_V2` ở mục 4 README là logic xác định (so sánh timestamp, cộng trừ tiền với sai số cho phép 0.10 BRL). Cần quyết định giao phần này cho LLM hay viết code.
- **Các phương án đã cân nhắc:** (a) đưa cả bảng policy vào prompt cho model 8B tự suy luận và trả JSON; (b) viết rule engine bằng Python triển khai đúng thứ tự 6 hàng, LLM không tham gia.
- **Phương án đã chọn:** (b).
- **Lý do:** model nhỏ dễ sai số học — chỉ lệch 0.01–0.10 BRL là đổi kết quả `reconciled`, kéo theo sai `primary_issue` rồi sai cả refund. LLM cũng không đảm bảo tái lập giữa các lần chạy, trong khi mỗi case bị chấm theo 7 thành phần có trọng số nên một sai lệch nhỏ lan ra nhiều mục. Rule engine đảm bảo đúng quy tắc, chạy lại cho kết quả giống hệt, và kiểm thử được độc lập.
- **Bằng chứng quyết định phù hợp:** phân bố `primary_issue` do rule engine sinh ra khớp tuyệt đối với thống kê tính tay trên CSV — 8 case `canceled_order_paid` đúng bằng 8 order `canceled`, 6 case `unavailable_order_paid` đúng bằng 6 order `unavailable`, 20 case `late_delivery_*` đúng bằng 20 order giao sau ngày dự kiến. Kiểm tra thêm độ ổn định của việc phân loại seller vs logistics: đổi cách lấy `shipping_limit_date` (sớm nhất ↔ muộn nhất) không làm đổi kết quả ở bất kỳ case nào trong 20 case, biên độ chênh lệch từ 17 đến 417 giờ. Ngoài ra, chạy có bật LLM và chạy `--no-llm` cho ra 50/50 file output giống hệt nhau, xác nhận LLM không chạm vào số liệu.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** không có exception nào; điểm chấm mục "Giao vận" chỉ đạt 67.60/100 trong khi các mục khác 75–90. Đọc output thì thấy 14 case có `"estimated_delivery_at": null` và `"seller_handoff_analysis": []`.
- **Lệnh hoặc bước tái hiện:** mở `output/EC_004.json`, `output/EC_012.json`, `output/EC_047.json` rồi đối chiếu với `data/olist_orders_dataset.csv` theo cùng `order_id`.
- **Nguyên nhân gốc:** tôi đã thêm một bước "tối ưu" trong Coordinator — nếu `order_status` là `canceled` hoặc `unavailable` thì bỏ qua Delivery Agent, dựa trên giả định các đơn này không có dữ liệu giao vận. Giả định sai: kiểm tra dữ liệu cho thấy **cả 14/14 case** đó đều có `order_estimated_delivery_date` thật trong CSV, `EC_047` còn có cả `order_delivered_carrier_date`, và 8 case `canceled` có item row nên bắt buộc phải có `seller_handoff_analysis`. README mục 4 chỉ cho phép để mảng rỗng khi order **không có item row**, không phải theo `order_status`.
- **Cách xử lý:** bỏ điều kiện rẽ nhánh, cho Delivery Agent luôn chạy với mọi `order_status`. Các trường không tính được vẫn trả `null` một cách tự nhiên vì hàm tính chênh lệch giờ đã xử lý giá trị rỗng sẵn.
- **Cách xác minh sau khi sửa:** thêm hai luật vào validator — `estimated_delivery_at` không được `null`, và `seller_handoff_analysis` rỗng khi và chỉ khi `item_ids` rỗng. Chạy lại: 0 lỗi trên 50 file. Điểm mục Giao vận tăng từ 67.60 lên 79.56.
- **Điều học được:** tối ưu dựa trên giả định thống kê ("gần như chắc chắn không có dữ liệu") mà không kiểm chứng từng trường bắt buộc của schema thì lợi bất cập hại — bước bỏ qua agent tiết kiệm được rất ít thời gian nhưng làm hỏng dữ liệu của 28% số case. Trước khi cắt bớt một nhánh xử lý, phải mở dữ liệu thật ra kiểm thay vì suy đoán.

Phần chưa xử lý xong:

- **Phạm vi bị ảnh hưởng:** điểm tổng đang là 79.85/100, cả 7 thành phần đều nằm trong khoảng hẹp 79.45–80.23.
- **Những gì đã loại trừ:** đã kiểm chứng độc lập và xác nhận đúng — `secondary_issues` (50/50 khớp khi tính lại từ CSV bằng script riêng, không tái dùng code của agent), phân loại `late_delivery_seller` vs `late_delivery_logistics`, thứ tự các mảng, định dạng timestamp, định dạng và tính tồn tại của evidence ID, giới hạn kích thước mảng, làm tròn 2 chữ số thập phân.
- **Bước tiếp theo:** hai chỗ README không quy định rõ đã được tách thành biến môi trường để thử nghiệm A/B: (1) `VARIANT_REFUND_COMPLETION` — điều kiện thêm `verify_refund_completion`; đoạn văn mục 4 hàm ý thêm cho mọi case `action_required`, nhưng ví dụ mẫu mục 6 lại không có action này dù case đang `action_required`. (2) `VARIANT_PAYMENT_TYPES` — `payment_types` là tập hợp các loại thanh toán hay danh sách theo từng payment row (ảnh hưởng 4 case). Kế hoạch là nộp thử từng biến thể và so điểm để chốt.

## 7. Hiểu biết về luồng end-to-end

> Ghi chú: 5 câu hỏi in sẵn trong mẫu (Crossref, vector index, freshness monitoring, corrupted/repaired) thuộc về một bài lab khác. Dưới đây tôi trả lời các câu tương ứng cho bài lab này.

**Câu trả lời:**

1. **Dữ liệu đi từ CSV đến output như thế nào?** `main.py` đọc 50 file `input/EC_*.json`, lấy `claimed_order_id` rồi giao cho Coordinator. `data_loader.py` nạp 9 CSV một lần vào RAM và chia sẻ cho mọi agent. Trong mỗi case, Customer Agent và Order & Product Agent tra dữ liệu trước; kết quả (danh sách item, seller, `shipping_limit_date`, tổng tiền hàng và phí ship) được handoff cho Payment Agent và Delivery Agent. Bốn agent này gộp thành một evidence bundle, Policy Agent áp `EC_POLICY_V2` lên bundle đó, Verifier Agent kiểm tra rồi mới ghi ra `output/EC_xxx.json`.

2. **Kết quả được đo bằng gì?** Không có ground truth công khai nên tôi dùng hai lớp kiểm chứng: (a) validator tự viết đối chiếu output với từng ràng buộc trong README; (b) tính lại độc lập bằng script pandas riêng, không tái sử dụng code của agent, rồi so từng con số. Điểm thật đến từ hệ thống chấm với 7 thành phần có trọng số.

3. **Verifier Agent khác validator ở điểm nào?** Verifier Agent nằm trong pipeline, chạy cho từng case trước khi ghi file, có quyền chặn không ghi hoặc tự cắt mảng vượt giới hạn. Validator là script chạy sau, kiểm toàn bộ 50 file như một khâu QA độc lập — nó bắt được những lỗi Verifier bỏ sót vì cả hai cùng dựa trên một cách hiểu sai, đúng như vụ `estimated_delivery_at` bị `null`.

4. **Vì sao phải chạy lại đủ 50 case sau mỗi lần sửa?** Vì các quy tắc trong `EC_POLICY_V2` liên kết với nhau: sửa cách tính `reconciled` có thể đổi `primary_issue`, kéo theo đổi root cause, refund và danh sách action. Chỉ kiểm vài case đại diện sẽ bỏ sót ảnh hưởng lan truyền, nên sau mỗi thay đổi tôi chạy lại toàn bộ 50 case rồi mới so điểm.

5. **Vì sao LLM không được tham gia tính toán?** Vì `output/*.json` là thứ bị chấm và phải tái lập được. Toàn bộ số liệu do code sinh ra, LLM chỉ sinh phần diễn giải ghi vào `trace.jsonl`. Điều này đã được kiểm chứng: chạy có bật LLM và chạy `--no-llm` cho ra 50/50 file output giống hệt nhau.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phạm Công Đăng
**Ngày xác nhận:** 2026-08-05
