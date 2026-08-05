"""
Policy Engine for EC_POLICY_V2.
Implements the exact business rules, priority order, secondary issues sequence,
evidence building, financial resolution, and action sequences.
"""

from typing import Dict, List, Any

class PolicyEngine:
    @staticmethod
    def evaluate(case_data: Dict[str, Any]) -> Dict[str, Any]:
        order = case_data["order"]
        items = case_data["items"]
        payments = case_data["payments"]
        delivery = case_data["delivery_analysis"]
        payment_recon = case_data["payment_reconciliation"]

        order_id = order.get("order_id")
        order_status = order.get("order_status", "")
        
        delivery_var_h = delivery.get("delivery_variance_hours")
        late_sellers = delivery.get("late_handoff_seller_ids", [])
        reconciled = payment_recon.get("reconciled")
        payment_total_brl = payment_recon.get("payment_total_brl") or 0.0
        freight_total_brl = payment_recon.get("freight_total_brl") or 0.0

        primary_issue = None
        root_cause_code = None
        responsible_parties = []
        recommended_refund_brl = 0.0
        primary_action = None

        # 1. Evaluate Primary Issue (Priority Order from Section 4)
        if order_status == "canceled" and payment_total_brl > 0:
            primary_issue = "canceled_order_paid"
            root_cause_code = "ORDER_CANCELED_AFTER_PAYMENT"
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            recommended_refund_brl = payment_total_brl
            primary_action = "issue_full_refund"

        elif order_status == "unavailable" and payment_total_brl > 0:
            primary_issue = "unavailable_order_paid"
            root_cause_code = "ORDER_UNAVAILABLE_AFTER_PAYMENT"
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            recommended_refund_brl = payment_total_brl
            primary_action = "issue_full_refund"

        elif delivery_var_h is not None and delivery_var_h > 0 and len(late_sellers) > 0:
            primary_issue = "late_delivery_seller"
            root_cause_code = "SELLER_HANDOFF_AFTER_LIMIT"
            responsible_parties = [{"party_type": "seller", "party_id": sid} for sid in late_sellers]
            recommended_refund_brl = freight_total_brl
            primary_action = "refund_freight"

        elif delivery_var_h is not None and delivery_var_h > 0 and len(late_sellers) == 0:
            primary_issue = "late_delivery_logistics"
            root_cause_code = "CARRIER_DELIVERED_AFTER_ESTIMATE"
            responsible_parties = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
            recommended_refund_brl = freight_total_brl
            primary_action = "refund_freight"

        elif len(payments) >= 2 and reconciled is True:
            primary_issue = "valid_split_payment"
            root_cause_code = "MULTIPLE_PAYMENTS_RECONCILED"
            responsible_parties = []
            recommended_refund_brl = 0.0
            primary_action = "explain_valid_split_payment"

        elif (delivery_var_h is None or delivery_var_h <= 0) and reconciled is True:
            primary_issue = "unsupported_late_claim"
            root_cause_code = "DELIVERY_WITHIN_ESTIMATE"
            responsible_parties = []
            recommended_refund_brl = 0.0
            primary_action = "reject_late_refund"

        else:
            # Fallback default if edge case
            primary_issue = "unsupported_late_claim"
            root_cause_code = "DELIVERY_WITHIN_ESTIMATE"
            responsible_parties = []
            recommended_refund_brl = 0.0
            primary_action = "reject_late_refund"

        # 2. Evaluate Secondary Issues (Exact Sequence)
        secondary_issues = []
        if len(items) >= 2:
            secondary_issues.append("multi_item_order")
        
        unique_sellers = list(dict.fromkeys(case_data.get("seller_ids", [])))
        if len(unique_sellers) >= 2:
            secondary_issues.append("multi_seller_order")

        if len(payments) >= 2:
            secondary_issues.append("split_payment")

        if len(case_data.get("related_order_ids", [])) >= 1:
            secondary_issues.append("repeat_customer")

        unique_categories = list(dict.fromkeys(case_data.get("category_names", [])))
        if len(unique_categories) >= 2:
            secondary_issues.append("multiple_categories")

        # 3. Build Resolution Actions (Primary Action + Additional Actions in exact order)
        actions = [primary_action]

        # Action: review_seller_handoff or review_carrier_delay
        if primary_issue == "late_delivery_seller" or len(late_sellers) > 0:
            actions.append("review_seller_handoff")
        elif primary_issue == "late_delivery_logistics" or (delivery_var_h is not None and delivery_var_h > 0):
            actions.append("review_carrier_delay")

        # Action: verify_refund_completion
        if recommended_refund_brl > 0:
            actions.append("verify_refund_completion")

        # Action: coordinate_multi_seller_case
        if "multi_seller_order" in secondary_issues:
            actions.append("coordinate_multi_seller_case")

        # Action: verify_payment_allocation
        if "split_payment" in secondary_issues and primary_issue != "valid_split_payment":
            actions.append("verify_payment_allocation")

        # Remove duplicate actions preserving order
        resolution_actions = []
        for act in actions:
            if act not in resolution_actions:
                resolution_actions.append(act)

        # 4. Case Status & Confidence
        case_status = "action_required" if recommended_refund_brl > 0 else "no_action"
        confidence = 0.95

        # 5. Build Evidence IDs
        evidence_ids = []
        evidence_ids.append(f"order:{order_id}")
        
        for item in items:
            item_id = item.get("order_item_id")
            if item_id:
                evidence_ids.append(f"item:{order_id}:{item_id}")

        for p in payments:
            seq = p.get("payment_sequential")
            if seq:
                evidence_ids.append(f"payment:{order_id}:{seq}")

        for p_party in responsible_parties:
            if p_party.get("party_type") == "seller":
                sid = p_party.get("party_id")
                if sid:
                    ev_seller = f"seller:{sid}"
                    if ev_seller not in evidence_ids:
                        evidence_ids.append(ev_seller)

        evidence_ids.append(f"policy:{root_cause_code}")

        return {
            "primary_issue": primary_issue,
            "secondary_issues": secondary_issues,
            "case_status": case_status,
            "confidence": confidence,
            "root_cause_code": root_cause_code,
            "responsible_parties": responsible_parties,
            "recommended_refund_brl": recommended_refund_brl,
            "resolution_actions": resolution_actions,
            "evidence_ids": evidence_ids
        }
