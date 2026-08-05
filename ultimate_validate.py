"""
Ultimate validation - Kiểm tra MỌI chi tiết có thể gây 0 điểm
"""

import json
from pathlib import Path

def ultimate_validate():
    """Kiểm tra mọi thứ có thể gây lỗi"""
    
    print("="*80)
    print("🔬 ULTIMATE VALIDATION - Tìm tất cả vấn đề có thể")
    print("="*80)
    
    issues = []
    warnings = []
    
    for i in range(1, 51):
        case_id = f"EC_{i:03d}"
        file_path = Path(f"output/{case_id}.json")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)
        
        # 1. Kiểm tra trailing comma
        if content.strip().endswith(',}') or content.strip().endswith(',]'):
            issues.append(f"{case_id}: Có trailing comma trong JSON")
        
        # 2. Kiểm tra whitespace/newline cuối file
        if not content.endswith('\n'):
            warnings.append(f"{case_id}: File không kết thúc bằng newline")
        
        # 3. Kiểm tra indent (phải là 2 spaces)
        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            if line.startswith('    '):  # 4 spaces
                pass  # OK
            elif line.startswith('  ') and not line.startswith('    '):  # 2 spaces but not 4
                if '"' in line:  # Có content
                    warnings.append(f"{case_id} line {line_num}: Indent 2 spaces thay vì 4")
                    break
        
        # 4. Kiểm tra payment_types thứ tự (PHẢI sorted alphabetically?)
        pr = data.get("payment_reconciliation", {})
        payment_types = pr.get("payment_types", [])
        if payment_types != sorted(payment_types):
            issues.append(f"{case_id}: payment_types không được sort: {payment_types}")
        
        # 5. Kiểm tra secondary_issues thứ tự (theo README)
        correct_order = ["multi_item_order", "multi_seller_order", "split_payment", 
                        "repeat_customer", "multiple_categories"]
        secondary = data.get("case_assessment", {}).get("secondary_issues", [])
        # Kiểm tra xem có giữ thứ tự không
        indices = [correct_order.index(s) for s in secondary if s in correct_order]
        if indices != sorted(indices):
            issues.append(f"{case_id}: secondary_issues không đúng thứ tự: {secondary}")
        
        # 6. Kiểm tra resolution_actions thứ tự
        actions = data.get("resolution_actions", [])
        primary = data.get("case_assessment", {}).get("primary_issue")
        
        # Action đầu tiên phải là main action tương ứng primary issue
        main_actions = {
            "canceled_order_paid": "issue_full_refund",
            "unavailable_order_paid": "issue_full_refund",
            "late_delivery_seller": "refund_freight",
            "late_delivery_logistics": "refund_freight",
            "valid_split_payment": "explain_valid_split_payment",
            "unsupported_late_claim": "reject_late_refund"
        }
        
        if actions and primary in main_actions:
            if actions[0] != main_actions[primary]:
                issues.append(f"{case_id}: First action phải là {main_actions[primary]}, nhận {actions[0]}")
        
        # 7. Kiểm tra seller_handoff_analysis phải sort theo seller_id
        da = data.get("delivery_analysis", {})
        sha = da.get("seller_handoff_analysis", [])
        if len(sha) > 1:
            seller_ids = [s.get("seller_id") for s in sha]
            if seller_ids != sorted(seller_ids):
                warnings.append(f"{case_id}: seller_handoff_analysis không sort theo seller_id")
        
        # 8. Kiểm tra số thập phân (phải 2 chữ số)
        for field in ["delivery_variance_hours", "handoff_variance_hours"]:
            if field == "delivery_variance_hours":
                val = da.get(field)
                if val is not None and isinstance(val, float):
                    decimal_part = str(val).split('.')
                    if len(decimal_part) > 1 and len(decimal_part[1]) > 2:
                        issues.append(f"{case_id}: {field} có >{decimal_part[1]} chữ số: {val}")
        
        # 9. Kiểm tra item_ids format (phải là order_id:sequential)
        item_ids = data.get("affected_entities", {}).get("item_ids", [])
        for item_id in item_ids:
            if ':' not in item_id:
                issues.append(f"{case_id}: item_id sai format (thiếu :): {item_id}")
            else:
                parts = item_id.split(':')
                if len(parts) != 2:
                    issues.append(f"{case_id}: item_id sai format: {item_id}")
        
        # 10. Kiểm tra payment_ids format
        payment_ids = data.get("affected_entities", {}).get("payment_ids", [])
        for payment_id in payment_ids:
            if ':' not in payment_id:
                issues.append(f"{case_id}: payment_id sai format (thiếu :): {payment_id}")
    
    print(f"\n📊 KẾT QUẢ:")
    print(f"   Tổng số case: 50")
    print(f"   Số lỗi nghiêm trọng: {len(issues)}")
    print(f"   Số cảnh báo: {len(warnings)}")
    
    if issues:
        print(f"\n❌ LỖI NGHIÊM TRỌNG (CÓ THỂ GÂY 0 ĐIỂM):")
        for issue in issues[:20]:  # Show first 20
            print(f"   - {issue}")
        if len(issues) > 20:
            print(f"   ... và {len(issues)-20} lỗi khác")
    
    if warnings:
        print(f"\n⚠️  CẢNH BÁO (có thể không ảnh hưởng):")
        for warning in warnings[:10]:
            print(f"   - {warning}")
        if len(warnings) > 10:
            print(f"   ... và {len(warnings)-10} cảnh báo khác")
    
    if not issues and not warnings:
        print(f"\n✅ HOÀN HẢO - KHÔNG CÓ VẤN ĐỀ NÀO!")
    
    print("="*80)

if __name__ == "__main__":
    ultimate_validate()
