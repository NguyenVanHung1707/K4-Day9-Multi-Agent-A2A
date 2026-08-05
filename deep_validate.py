"""
Deep validation - Kiểm tra chi tiết schema so với README
"""

import json
from pathlib import Path

def deep_validate():
    """Kiểm tra chi tiết từng field"""
    
    print("="*80)
    print("🔬 DEEP VALIDATION - Chi tiết schema")
    print("="*80)
    
    errors = []
    
    for i in range(1, 51):
        case_id = f"EC_{i:03d}"
        file_path = Path(f"output/{case_id}.json")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Kiểm tra case_id
        if data.get("case_id") != case_id:
            errors.append(f"{case_id}: case_id không khớp tên file")
        
        # Kiểm tra case_assessment
        ca = data.get("case_assessment", {})
        valid_primary = ["canceled_order_paid", "unavailable_order_paid", 
                        "late_delivery_seller", "late_delivery_logistics",
                        "valid_split_payment", "unsupported_late_claim"]
        if ca.get("primary_issue") not in valid_primary:
            errors.append(f"{case_id}: primary_issue không hợp lệ: {ca.get('primary_issue')}")
        
        valid_secondary = ["multi_item_order", "multi_seller_order", 
                          "split_payment", "repeat_customer", "multiple_categories"]
        for sec in ca.get("secondary_issues", []):
            if sec not in valid_secondary:
                errors.append(f"{case_id}: secondary_issue không hợp lệ: {sec}")
        
        if ca.get("case_status") not in ["action_required", "no_action"]:
            errors.append(f"{case_id}: case_status không hợp lệ: {ca.get('case_status')}")
        
        conf = ca.get("confidence")
        if conf is None or not (0 <= conf <= 1):
            errors.append(f"{case_id}: confidence không hợp lệ: {conf}")
        
        # Kiểm tra evidence_ids format
        for evi in data.get("evidence_ids", []):
            if not any(evi.startswith(prefix) for prefix in ["order:", "item:", "payment:", "seller:", "policy:"]):
                errors.append(f"{case_id}: evidence_id sai format: {evi}")
        
        # Kiểm tra financial_resolution
        fr = data.get("financial_resolution", {})
        if fr.get("currency") != "BRL":
            errors.append(f"{case_id}: currency phải là BRL, nhận: {fr.get('currency')}")
        
        refund = fr.get("recommended_refund_brl")
        if refund is not None and not isinstance(refund, (int, float)):
            errors.append(f"{case_id}: recommended_refund_brl phải là số")
        
        # Kiểm tra case_status vs recommended_refund
        if ca.get("case_status") == "action_required" and refund == 0:
            errors.append(f"{case_id}: action_required nhưng refund = 0")
        if ca.get("case_status") == "no_action" and refund > 0:
            errors.append(f"{case_id}: no_action nhưng refund > 0")
        
        # Kiểm tra root_cause_analysis
        rca = data.get("root_cause_analysis", {})
        valid_causes = ["SELLER_HANDOFF_AFTER_LIMIT", "CARRIER_DELIVERED_AFTER_ESTIMATE",
                       "ORDER_CANCELED_AFTER_PAYMENT", "ORDER_UNAVAILABLE_AFTER_PAYMENT",
                       "MULTIPLE_PAYMENTS_RECONCILED", "DELIVERY_WITHIN_ESTIMATE"]
        for cause in rca.get("ranked_causes", []):
            if cause.get("cause_code") not in valid_causes:
                errors.append(f"{case_id}: cause_code không hợp lệ: {cause.get('cause_code')}")
        
        # Kiểm tra responsible_parties
        for party in rca.get("responsible_parties", []):
            if party.get("party_type") not in ["seller", "platform", "logistics_provider"]:
                errors.append(f"{case_id}: party_type không hợp lệ: {party.get('party_type')}")
        
        # Kiểm tra resolution_actions
        valid_actions = ["issue_full_refund", "refund_freight", "explain_valid_split_payment",
                        "reject_late_refund", "review_seller_handoff", "review_carrier_delay",
                        "verify_refund_completion", "coordinate_multi_seller_case",
                        "verify_payment_allocation"]
        for action in data.get("resolution_actions", []):
            if action not in valid_actions:
                errors.append(f"{case_id}: resolution_action không hợp lệ: {action}")
        
        # Kiểm tra payment_reconciliation
        pr = data.get("payment_reconciliation", {})
        if pr.get("currency") != "BRL":
            errors.append(f"{case_id}: payment currency phải là BRL")
        
        # Kiểm tra reconciled logic
        if pr.get("reconciled") is not None:
            diff = pr.get("difference_brl")
            if diff is not None:
                reconciled = abs(diff) <= 0.10
                if pr.get("reconciled") != reconciled:
                    errors.append(f"{case_id}: reconciled sai: diff={diff}, reconciled={pr.get('reconciled')}")
    
    print(f"\n📊 Kết quả:")
    print(f"   Tổng số case: 50")
    print(f"   Số lỗi tìm thấy: {len(errors)}")
    
    if errors:
        print(f"\n❌ CÁC LỖI PHÁT HIỆN:")
        for err in errors:
            print(f"   - {err}")
    else:
        print(f"\n✅ TẤT CẢ 50 CASE ĐỀU HỢP LỆ!")
    
    print("="*80)

if __name__ == "__main__":
    deep_validate()
