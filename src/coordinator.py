from __future__ import annotations

from src.agents import CustomerAgent, DeliveryAgent, OrderProductAgent, PaymentAgent, PolicyAgent, VerifierAgent
from src.config import (
    MAX_ACTIONS, MAX_CATEGORIES, MAX_EVIDENCE, MAX_ITEMS, MAX_PAYMENTS,
    MAX_PRODUCTS, MAX_SELLERS, POLICY_VERSION,
)
from src.repository import DataRepository
from src.tracing import TraceWriter


class Coordinator:
    name = "coordinator_agent"

    def __init__(self, repository: DataRepository, trace: TraceWriter):
        self.repository = repository
        self.trace = trace
        self.customer_agent = CustomerAgent(repository)
        self.order_agent = OrderProductAgent(repository)
        self.payment_agent = PaymentAgent(repository)
        self.delivery_agent = DeliveryAgent()
        self.policy_agent = PolicyAgent()
        self.verifier_agent = VerifierAgent(repository)

    def process(self, case: dict) -> dict:
        case_id = case["case_id"]
        order_id = case["customer_request"]["claimed_order_id"]
        if case.get("policy_version") != POLICY_VERSION:
            raise ValueError(f"Unsupported policy version in {case_id}: {case.get('policy_version')}")
        self.trace.write(case_id, self.name, "case_started", {"order_id": order_id})
        scope = case.get("investigation_scope", {})
        customer = self.customer_agent.run(order_id, scope.get("include_customer_history", True))
        self.trace.write(case_id, self.customer_agent.name, "handoff", {
            "customer_unique_id": customer["customer_unique_id"],
            "related_order_count": len(customer["related_order_ids"]),
        })
        order = self.order_agent.run(order_id, scope.get("include_product_context", True))
        self.trace.write(case_id, self.order_agent.name, "handoff", {
            "item_count": order["item_count"], "seller_count": order["seller_count"]
        })
        payment = self.payment_agent.run(order_id, order)
        self.trace.write(case_id, self.payment_agent.name, "handoff", {
            "payment_count": payment["payment_count"], "reconciled": payment["reconciled"]
        })
        delivery = self.delivery_agent.run(order)
        self.trace.write(case_id, self.delivery_agent.name, "handoff", {
            "delivery_variance_hours": delivery["delivery_variance_hours"],
            "late_handoff_seller_count": len(delivery["late_handoff_seller_ids"]),
        })
        policy = self.policy_agent.run(order, customer, payment, delivery)
        self.trace.write(case_id, self.policy_agent.name, "handoff", {
            "primary_issue": policy["primary_issue"],
            "recommended_refund_brl": policy["recommended_refund_brl"],
        })
        output = self._compose(case_id, order_id, customer, order, payment, delivery, policy)
        verified = self.verifier_agent.verify(case, output)
        self.trace.write(case_id, self.verifier_agent.name, "verification_passed")
        self.trace.write(case_id, self.name, "case_completed")
        return verified

    def _compose(self, case_id: str, order_id: str, customer: dict, order: dict, payment: dict, delivery: dict, policy: dict) -> dict:
        responsible_seller_ids = [
            party["party_id"] for party in policy["responsible_parties"] if party["party_type"] == "seller"
        ][:MAX_SELLERS]
        evidence = [f"order:{order_id}"]
        evidence.extend(f'item:{order_id}:{row["order_item_id"]}' for row in order["items"][:MAX_ITEMS])
        evidence.extend(f'payment:{order_id}:{row["payment_sequential"]}' for row in payment["payments"][:MAX_PAYMENTS])
        evidence.extend(f"seller:{seller_id}" for seller_id in responsible_seller_ids)
        evidence.append(f'policy:{policy["cause_code"]}')
        return {
            "case_id": case_id,
            "case_assessment": {
                "primary_issue": policy["primary_issue"], "secondary_issues": policy["secondary_issues"],
                "case_status": policy["case_status"], "confidence": policy["confidence"],
            },
            "affected_entities": {
                "order_ids": [order_id], "item_ids": order["item_ids"][:MAX_ITEMS],
                "seller_ids": order["seller_ids"][:MAX_SELLERS], "payment_ids": payment["payment_ids"][:MAX_PAYMENTS],
            },
            "customer_context": {"customer_unique_id": customer["customer_unique_id"], "related_order_ids": customer["related_order_ids"]},
            "product_context": {"product_ids": order["product_ids"][:MAX_PRODUCTS], "category_names": order["category_names"][:MAX_CATEGORIES]},
            "delivery_analysis": delivery,
            "payment_reconciliation": {
                "currency": "BRL", "item_total_brl": order["item_total_brl"], "freight_total_brl": order["freight_total_brl"],
                "expected_total_brl": payment["expected_total_brl"], "payment_total_brl": payment["payment_total_brl"],
                "difference_brl": payment["difference_brl"], "reconciled": payment["reconciled"], "payment_types": payment["payment_types"],
            },
            "root_cause_analysis": {
                "ranked_causes": [{"cause_code": policy["cause_code"], "rank": 1}],
                "responsible_parties": policy["responsible_parties"][:MAX_SELLERS],
            },
            "evidence_ids": evidence[:MAX_EVIDENCE],
            "financial_resolution": {"currency": "BRL", "recommended_refund_brl": policy["recommended_refund_brl"]},
            "resolution_actions": policy["resolution_actions"][:MAX_ACTIONS],
        }
