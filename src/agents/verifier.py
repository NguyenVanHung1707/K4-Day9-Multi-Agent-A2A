from __future__ import annotations

from src.config import (
    MAX_ACTIONS,
    MAX_CATEGORIES,
    MAX_EVIDENCE,
    MAX_ITEMS,
    MAX_PAYMENTS,
    MAX_PRODUCTS,
    MAX_RELATED_ORDERS,
    MAX_SELLERS,
)
from src.repository import DataRepository


class VerificationError(ValueError):
    pass


class VerifierAgent:
    name = "verifier_agent"

    def __init__(self, repository: DataRepository):
        self.repository = repository

    def verify(self, case: dict, output: dict) -> dict:
        errors: list[str] = []
        order_id = case["customer_request"]["claimed_order_id"]

        if output["case_id"] != case["case_id"]:
            errors.append("case_id does not match input")
        if output["affected_entities"]["order_ids"] != [order_id]:
            errors.append("affected order must be exactly claimed_order_id")
        if not 0 <= output["case_assessment"]["confidence"] <= 1:
            errors.append("confidence outside [0, 1]")
        refund = output["financial_resolution"]["recommended_refund_brl"]
        expected_status = "action_required" if refund > 0 else "no_action"
        if output["case_assessment"]["case_status"] != expected_status:
            errors.append("case_status disagrees with refund")

        limits = [
            ("item_ids", output["affected_entities"]["item_ids"], MAX_ITEMS),
            ("seller_ids", output["affected_entities"]["seller_ids"], MAX_SELLERS),
            ("payment_ids", output["affected_entities"]["payment_ids"], MAX_PAYMENTS),
            ("related_order_ids", output["customer_context"]["related_order_ids"], MAX_RELATED_ORDERS),
            ("product_ids", output["product_context"]["product_ids"], MAX_PRODUCTS),
            ("category_names", output["product_context"]["category_names"], MAX_CATEGORIES),
            ("evidence_ids", output["evidence_ids"], MAX_EVIDENCE),
            ("resolution_actions", output["resolution_actions"], MAX_ACTIONS),
        ]
        for name, values, maximum in limits:
            if len(values) > maximum:
                errors.append(f"{name} exceeds limit {maximum}")

        for evidence_id in output["evidence_ids"]:
            if not self.repository.evidence_exists(evidence_id):
                errors.append(f"false or malformed evidence: {evidence_id}")

        for item_id in output["affected_entities"]["item_ids"]:
            parts = item_id.split(":")
            if len(parts) != 2 or not self.repository.evidence_exists(f"item:{item_id}"):
                errors.append(f"invalid affected item: {item_id}")
        for payment_id in output["affected_entities"]["payment_ids"]:
            parts = payment_id.split(":")
            if len(parts) != 2 or not self.repository.evidence_exists(f"payment:{payment_id}"):
                errors.append(f"invalid affected payment: {payment_id}")
        for seller_id in output["affected_entities"]["seller_ids"]:
            if seller_id not in self.repository.sellers:
                errors.append(f"invalid affected seller: {seller_id}")
        for product_id in output["product_context"]["product_ids"]:
            if product_id not in self.repository.products:
                errors.append(f"invalid product: {product_id}")

        if not output["resolution_actions"]:
            errors.append("missing primary action")
        if len(output["root_cause_analysis"]["ranked_causes"]) > 3:
            errors.append("too many root causes")
        if len(output["root_cause_analysis"]["responsible_parties"]) > 3:
            errors.append("too many responsible parties")

        if errors:
            raise VerificationError("; ".join(errors))
        return output

