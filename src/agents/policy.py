from __future__ import annotations


class PolicyAgent:
    name = "policy_agent"

    def run(self, order_result: dict, customer_result: dict, payment_result: dict, delivery_result: dict) -> dict:
        status = order_result["order"]["order_status"]
        payment_total = payment_result["payment_total_brl"]
        delivery_variance = delivery_result["delivery_variance_hours"]
        late_sellers = delivery_result["late_handoff_seller_ids"]

        if status == "canceled" and payment_total > 0:
            primary = "canceled_order_paid"
            cause = "ORDER_CANCELED_AFTER_PAYMENT"
            parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            refund = payment_total
            main_action = "issue_full_refund"
        elif status == "unavailable" and payment_total > 0:
            primary = "unavailable_order_paid"
            cause = "ORDER_UNAVAILABLE_AFTER_PAYMENT"
            parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            refund = payment_total
            main_action = "issue_full_refund"
        elif delivery_variance is not None and delivery_variance > 0 and late_sellers:
            primary = "late_delivery_seller"
            cause = "SELLER_HANDOFF_AFTER_LIMIT"
            parties = [{"party_type": "seller", "party_id": seller_id} for seller_id in late_sellers]
            refund = order_result["freight_total_brl"]
            main_action = "refund_freight"
        elif delivery_variance is not None and delivery_variance > 0 and not late_sellers:
            primary = "late_delivery_logistics"
            cause = "CARRIER_DELIVERED_AFTER_ESTIMATE"
            parties = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
            refund = order_result["freight_total_brl"]
            main_action = "refund_freight"
        elif payment_result["payment_count"] >= 2 and payment_result["reconciled"] is True:
            primary = "valid_split_payment"
            cause = "MULTIPLE_PAYMENTS_RECONCILED"
            parties = []
            refund = 0.0
            main_action = "explain_valid_split_payment"
        elif delivery_variance is not None and delivery_variance <= 0 and payment_result["reconciled"] is True:
            primary = "unsupported_late_claim"
            cause = "DELIVERY_WITHIN_ESTIMATE"
            parties = []
            refund = 0.0
            main_action = "reject_late_refund"
        else:
            order_id = order_result["order"]["order_id"]
            raise ValueError(
                f"Order {order_id} does not match any EC_POLICY_V2 primary issue; refusing to invent a result"
            )

        secondary = []
        if order_result["item_count"] >= 2:
            secondary.append("multi_item_order")
        if order_result["seller_count"] >= 2:
            secondary.append("multi_seller_order")
        if payment_result["payment_count"] >= 2:
            secondary.append("split_payment")
        if customer_result["repeat_customer"]:
            secondary.append("repeat_customer")
        if order_result["category_count"] >= 2:
            secondary.append("multiple_categories")

        actions = [main_action]
        if primary == "late_delivery_seller":
            actions.append("review_seller_handoff")
        elif primary == "late_delivery_logistics":
            actions.append("review_carrier_delay")
        if refund > 0:
            actions.append("verify_refund_completion")
        if "multi_seller_order" in secondary:
            actions.append("coordinate_multi_seller_case")
        if "split_payment" in secondary and primary != "valid_split_payment":
            actions.append("verify_payment_allocation")

        return {
            "primary_issue": primary,
            "secondary_issues": secondary,
            "case_status": "action_required" if refund > 0 else "no_action",
            "confidence": 1.0,
            "cause_code": cause,
            "responsible_parties": parties,
            "recommended_refund_brl": round(refund, 2),
            "resolution_actions": actions,
        }

