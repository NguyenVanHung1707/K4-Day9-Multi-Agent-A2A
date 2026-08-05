Lựa chọn cực kỳ sắc bén! Sử dụng **Groq** cho hệ thống Multi-Agent này là một nước đi chiến lược. Với bài toán chia làm 6-7 Agents giao tiếp liên tục, độ trễ (latency) của API là yếu tố sống còn. Groq sử dụng chip LPU (Language Processing Unit) cho tốc độ có thể lên tới 800 - 1000 tokens/giây, giúp toàn bộ quy trình phân tích một đơn hàng (`EC_0xx.json`) hoàn thành chỉ trong vài giây.

Dưới đây là sơ đồ chiến thuật sử dụng các model $\le$ 10B có sẵn trên Groq cho từng Agent và cách thiết lập code.

### 1. Phân bổ Model Groq cho các Agent

Groq hiện cung cấp 2 dòng model mã nguồn mở dưới 10 tỷ tham số rất mạnh mẽ. Ta sẽ phân bổ như sau:

* **Policy Agent (Bộ não - Quyết định):** Dùng `gemma2-9b-it`
* *Lý do:* Khả năng suy luận (reasoning) và đọc hiểu luật của Gemma 2 9B là vô đối trong phân khúc dưới 10B. Nó sẽ theo dõi sát sao cây quyết định ưu tiên từ 1-6 của chính sách `EC_POLICY_V2` mà không bị lộn xộn.

* **Coordinator, Customer, Order & Product, Payment, Delivery Agent:** Dùng `llama-3.1-8b-instant`
* *Lý do:* Llama 3.1 8B xuất sắc trong việc xuất dữ liệu dạng JSON (JSON mode) và gọi hàm (Tool Calling). Các Agent này chủ yếu làm nhiệm vụ trích xuất dữ liệu từ Context/CSV, tính toán ngày tháng và trả về JSON để Coordinator ghép lại.

* **Verifier Agent:** Code Python thuần túy + `llama-3.1-8b-instant`
* *Lý do:* Python đảm nhiệm việc đếm số lượng mảng (giới hạn 5 order IDs, 20 evidence IDs, v.v.) và check Regex cho chuỗi. Nếu sai, quăng lỗi đó cho Llama-3.1-8B sửa lại file JSON.

---

### 2. Hướng dẫn Tích hợp Code với Groq API

Thư viện của Groq sử dụng cú pháp gần như giống hệt thư viện của OpenAI. Bạn có thể cài đặt bằng lệnh: `pip install groq`

Dưới đây là đoạn code mẫu minh họa cách Coordinator gọi **Policy Agent** để sinh ra JSON Output.

```python
import os
import json
from groq import Groq

# Khởi tạo Client (Lấy API Key miễn phí từ console.groq.com)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def call_policy_agent(global_context_data):
    """
    Hàm mô phỏng Policy Agent nhận dữ liệu tổng hợp từ 4 Domain Agents 
    và đưa ra quyết định cuối cùng dựa trên EC_POLICY_V2.
    """
    
    system_prompt = """Bạn là Policy Agent - một Thẩm phán tại Olist. 
Nhiệm vụ của bạn là áp dụng chính sách EC_POLICY_V2 để đưa ra quyết định xử lý khiếu nại.
Trọng tâm: Xác định primary_issue, secondary_issues, responsible_parties, recommended_refund_brl và resolution_actions.
Bắt buộc phải trả về CHỈ MỘT cục JSON đúng định dạng schema yêu cầu."""

    # global_context_data là chuỗi JSON chứa kết quả phân tích từ Payment, Delivery, Customer, Product Agents
    user_prompt = f"Dữ liệu điều tra (Context Data):\n{json.dumps(global_context_data)}\n\nHãy ra phán quyết:"

    response = client.chat.completions.create(
        model="gemma2-9b-it", # Dùng Gemma 2 9B cho suy luận
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"}, # Ép Groq trả về chuẩn JSON
        temperature=0.1 # Giữ temperature thấp để LLM không bị ảo giác, đảm bảo tính deterministic
    )
    
    return json.loads(response.choices[0].message.content)

# Giả lập dữ liệu handoff từ các Agent trước
mock_context_from_agents = {
    "order_status": "delivered",
    "delivery_analysis": {
        "is_late_delivery_seller": True,
        "handoff_variance_hours": 48.5
    },
    "payment_analysis": {
        "expected_total_brl": 150.0,
        "payment_total_brl": 150.0,
        "reconciled": True
    },
    "freight_total": 20.0
}

# Chạy thử 
draft_resolution = call_policy_agent(mock_context_from_agents)
print(json.dumps(draft_resolution, indent=2))
```

---

### 3. Lưu ý sống còn khi làm Toán với LLM 8B

Vì bạn bị giới hạn dùng model $\le$ 10B, LLM có thể làm toán cộng/trừ cơ bản nhưng **rất tệ trong việc trừ ngày tháng** (ví dụ tính `variance_hours` giữa hai chuỗi ISO-8601).

**Mẹo xử lý (Bắt buộc để không bị fail test):**
Đừng để `llama-3.1-8b-instant` tự ngồi đếm số giờ chênh lệch. Hãy cấp cho Delivery Agent và Payment Agent một **công cụ (Tool / Function)** bằng code Python.

1. Agent đọc văn bản tìm ra mốc thời gian: `2018-05-10T10:00:00Z` và `2018-05-12T15:00:00Z`.
2. Agent truyền 2 biến này vào hàm Python `calculate_variance_hours(t1, t2)`.
3. Hàm Python chạy ra kết quả `53.00` và trả ngược lại cho Agent.
4. Agent chốt kết quả và chuyển (Handoff) cho Policy Agent.
