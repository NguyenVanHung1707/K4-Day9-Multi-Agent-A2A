"""
Refactored Multi-Agent Framework (Agent-to-Agent Handoff Protocol).
Implements explicit Specialist Agents (Coordinator, Customer, Product, Delivery, Payment, Policy, Verifier)
with distinct domain responsibilities, state handoffs, and rich trace logs per README Section 7.
"""

import json
from typing import Dict, List, Any, Optional
from src.config import MODEL_NAME
from src.data_engine import DataEngine
from src.policy_engine import PolicyEngine
from src.verifier import Verifier
from src.llm_client import LLMClient


class BaseAgent:
    def __init__(self, name: str, role: str, model_name: str = MODEL_NAME):
        self.name = name
        self.role = role
        self.model_name = model_name

    def log_handoff(self, action: str, details: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent": self.name,
            "role": self.role,
            "action": action,
            "model": self.model_name,
            "details": details,
            "payload": payload
        }


class CustomerAgent(BaseAgent):
    def __init__(self):
        super().__init__("CustomerAgent", "Customer Identity & Purchase History Analyst")

    def process(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        cuid = case_data.get("customer_unique_id", "")
        related_orders = case_data.get("related_order_ids", [])
        is_repeat = len(related_orders) >= 1
        
        return {
            "customer_unique_id": cuid,
            "related_order_ids": related_orders,
            "is_repeat_customer": is_repeat,
            "assessment": f"Identified customer_unique_id={cuid}. Found {len(related_orders)} related orders. Repeat customer: {is_repeat}"
        }


class ProductAgent(BaseAgent):
    def __init__(self):
        super().__init__("ProductAgent", "Order Items, Product & Seller Analyst")

    def process(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        items = case_data.get("items", [])
        product_ids = case_data.get("product_ids", [])
        seller_ids = case_data.get("seller_ids", [])
        categories = case_data.get("category_names", [])

        is_multi_item = len(items) >= 2
        is_multi_seller = len(set(seller_ids)) >= 2
        is_multi_cat = len(set(categories)) >= 2

        return {
            "items_count": len(items),
            "product_ids": product_ids,
            "seller_ids": seller_ids,
            "category_names": categories,
            "is_multi_item": is_multi_item,
            "is_multi_seller": is_multi_seller,
            "is_multi_category": is_multi_cat,
            "assessment": f"Items={len(items)}, Products={len(product_ids)}, Sellers={len(seller_ids)}, Categories={len(categories)}"
        }


class DeliveryAgent(BaseAgent):
    def __init__(self):
        super().__init__("DeliveryAgent", "Logistics & Delivery Timestamp Variance Analyst")

    def process(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        delivery = case_data.get("delivery_analysis", {})
        deliv_var_h = delivery.get("delivery_variance_hours")
        late_sellers = delivery.get("late_handoff_seller_ids", [])
        is_late_delivery = deliv_var_h is not None and deliv_var_h > 0
        has_seller_delay = len(late_sellers) > 0

        return {
            "delivered_at": delivery.get("delivered_at"),
            "estimated_delivery_at": delivery.get("estimated_delivery_at"),
            "carrier_handoff_at": delivery.get("carrier_handoff_at"),
            "delivery_variance_hours": deliv_var_h,
            "seller_handoff_analysis": delivery.get("seller_handoff_analysis", []),
            "late_handoff_seller_ids": late_sellers,
            "is_late_delivery": is_late_delivery,
            "has_seller_delay": has_seller_delay,
            "assessment": f"Delivered variance={deliv_var_h}h. Late delivery={is_late_delivery}. Seller delay={has_seller_delay} ({late_sellers})"
        }


class PaymentAgent(BaseAgent):
    def __init__(self):
        super().__init__("PaymentAgent", "Financial Reconciliation & Payment Row Analyst")

    def process(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        recon = case_data.get("payment_reconciliation", {})
        payments = case_data.get("payments", [])
        is_split = len(payments) >= 2

        return {
            "payment_count": len(payments),
            "payment_total_brl": recon.get("payment_total_brl"),
            "expected_total_brl": recon.get("expected_total_brl"),
            "difference_brl": recon.get("difference_brl"),
            "reconciled": recon.get("reconciled"),
            "payment_types": recon.get("payment_types", []),
            "is_split_payment": is_split,
            "assessment": f"Payments={len(payments)}. Total={recon.get('payment_total_brl')} BRL. Reconciled={recon.get('reconciled')}"
        }


class PolicyAgent(BaseAgent):
    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__("PolicyAgent", "EC_POLICY_V2 Policy Enforcement & Dispute Resolution Specialist")
        self.llm_client = llm_client

    def process(self, case_data: Dict[str, Any], domain_context: Dict[str, Any]) -> Dict[str, Any]:
        # Optionally invoke LLM for policy assessment reasoning
        llm_reasoning = None
        if self.llm_client:
            sys_prompt = "You are an expert E-Commerce Dispute Policy Agent enforcing EC_POLICY_V2 using gpt-4o-mini."
            user_prompt = f"Case domain findings: {json.dumps(domain_context, ensure_ascii=False)}. Apply EC_POLICY_V2 rules and determine issue and refund."
            llm_reasoning = self.llm_client.call_agent(sys_prompt, user_prompt)

        policy_res = PolicyEngine.evaluate(case_data)
        policy_res["llm_reasoning"] = llm_reasoning or "Deterministic EC_POLICY_V2 rule engine applied."
        return policy_res


class VerifierAgent(BaseAgent):
    def __init__(self):
        super().__init__("VerifierAgent", "Quality Assurance & Schema Guardrail Auditor")

    def process(self, case_id: str, case_data: Dict[str, Any], policy_res: Dict[str, Any]) -> Dict[str, Any]:
        return Verifier.validate_and_format(case_id, case_data, policy_res)


class CoordinatorAgent(BaseAgent):
    """
    Coordinator Agent orchestrating the Multi-Agent pipeline:
    1. Coordinator -> CustomerAgent (Customer identity & history)
    2. Coordinator -> ProductAgent (Items, products, sellers)
    3. Coordinator -> DeliveryAgent (Delivery timestamps & seller handoff)
    4. Coordinator -> PaymentAgent (Financial reconciliation)
    5. Coordinator -> PolicyAgent (Policy evaluation & resolution)
    6. Coordinator -> VerifierAgent (Audit & Schema verification)
    """
    def __init__(self, data_engine: DataEngine):
        super().__init__("CoordinatorAgent", "Dispute Resolution Workflow Coordinator")
        self.data_engine = data_engine
        self.llm_client = LLMClient(MODEL_NAME)
        
        self.customer_agent = CustomerAgent()
        self.product_agent = ProductAgent()
        self.delivery_agent = DeliveryAgent()
        self.payment_agent = PaymentAgent()
        self.policy_agent = PolicyAgent(self.llm_client)
        self.verifier_agent = VerifierAgent()

    def process_case(self, case_input: Dict[str, Any]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        case_id = case_input.get("case_id", "UNKNOWN")
        claimed_order_id = case_input.get("customer_request", {}).get("claimed_order_id")

        trace_logs = []

        # 1. Initialize case
        trace_logs.append(self.log_handoff(
            action="initialize_case",
            details=f"Coordinator received case {case_id} for order {claimed_order_id}",
            payload={"case_id": case_id, "claimed_order_id": claimed_order_id}
        ))

        # Extract raw data context via DataEngine
        case_data = self.data_engine.analyze_case(claimed_order_id)

        # 2. Handoff to CustomerAgent
        cust_res = self.customer_agent.process(case_data)
        trace_logs.append(self.customer_agent.log_handoff(
            action="analyze_customer",
            details=cust_res["assessment"],
            payload=cust_res
        ))

        # 3. Handoff to ProductAgent
        prod_res = self.product_agent.process(case_data)
        trace_logs.append(self.product_agent.log_handoff(
            action="analyze_products_and_sellers",
            details=prod_res["assessment"],
            payload=prod_res
        ))

        # 4. Handoff to DeliveryAgent
        deliv_res = self.delivery_agent.process(case_data)
        trace_logs.append(self.delivery_agent.log_handoff(
            action="analyze_delivery_timestamps",
            details=deliv_res["assessment"],
            payload=deliv_res
        ))

        # 5. Handoff to PaymentAgent
        pay_res = self.payment_agent.process(case_data)
        trace_logs.append(self.payment_agent.log_handoff(
            action="reconcile_payments",
            details=pay_res["assessment"],
            payload=pay_res
        ))

        # Assemble domain blackboard context
        domain_blackboard = {
            "customer": cust_res,
            "product": prod_res,
            "delivery": deliv_res,
            "payment": pay_res
        }

        # 6. Handoff to PolicyAgent
        policy_res = self.policy_agent.process(case_data, domain_blackboard)
        trace_logs.append(self.policy_agent.log_handoff(
            action="evaluate_policy",
            details=f"Primary: {policy_res['primary_issue']}, Secondary: {policy_res['secondary_issues']}, Refund: {policy_res['recommended_refund_brl']} BRL",
            payload={"primary_issue": policy_res['primary_issue'], "recommended_refund_brl": policy_res['recommended_refund_brl']}
        ))

        # 7. Handoff to VerifierAgent
        final_output = self.verifier_agent.process(case_id, case_data, policy_res)
        trace_logs.append(self.verifier_agent.log_handoff(
            action="verify_schema_and_limits",
            details=f"Quality check passed. Status: {final_output['case_assessment']['case_status']}, Evidence count: {len(final_output['evidence_ids'])}",
            payload={"case_status": final_output['case_assessment']['case_status']}
        ))

        # Format trace log entries for trace.jsonl
        formatted_traces = []
        for log in trace_logs:
            formatted_traces.append({
                "agent": log["agent"],
                "role": log["role"],
                "action": log["action"],
                "model": log["model"],
                "details": log["details"],
                "case_id": case_id
            })

        return final_output, formatted_traces


class MultiAgentSystem:
    def __init__(self, data_engine: DataEngine):
        self.coordinator = CoordinatorAgent(data_engine)

    def process_case(self, case_input: Dict[str, Any]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        return self.coordinator.process_case(case_input)
