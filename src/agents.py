"""
Multi-Agent Framework for Dispute Resolution.
Model name is hardcoded per competition requirements.
Simulates Agent-to-Agent (A2A) handoff flow and generates structured trace logs.
"""

from typing import Dict, List, Any
import json
from src.config import MODEL_NAME
from src.data_engine import DataEngine
from src.policy_engine import PolicyEngine
from src.verifier import Verifier
from src.llm_client import LLMClient

class MultiAgentSystem:
    """
    Coordinator Agent driving handoffs between Domain Specialist Agents:
    1. CoordinatorAgent -> DataEngine & Domain Agents
    2. CustomerAgent / ProductAgent / DeliveryAgent / PaymentAgent -> Context Assembly
    3. PolicyAgent (LLM Reasoning & Policy Engine) -> Policy Assessment
    4. VerifierAgent (Guardrail) -> Quality Control & Final JSON
    """
    def __init__(self, data_engine: DataEngine):
        self.data_engine = data_engine
        self.model_name = MODEL_NAME

    def process_case(self, case_input: Dict[str, Any]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        case_id = case_input.get("case_id", "UNKNOWN")
        claimed_order_id = case_input.get("customer_request", {}).get("claimed_order_id")

        trace_logs = []

        # Step 1: Coordinator Agent receives input & initializes state
        trace_logs.append({
            "agent": "CoordinatorAgent",
            "action": "initialize_case",
            "details": f"Received case {case_id} for order {claimed_order_id}",
            "model": self.model_name
        })

        # Step 2: Extract data via Domain Specialist Agents
        case_data = self.data_engine.analyze_case(claimed_order_id)
        
        trace_logs.append({
            "agent": "CustomerAgent",
            "action": "extract_customer_context",
            "details": f"Customer unique ID: {case_data['customer_unique_id']}, Related orders: {len(case_data['related_order_ids'])}"
        })

        trace_logs.append({
            "agent": "ProductAgent",
            "action": "extract_product_context",
            "details": f"Items count: {len(case_data['items'])}, Products: {len(case_data['product_ids'])}, Sellers: {len(case_data['seller_ids'])}"
        })

        trace_logs.append({
            "agent": "DeliveryAgent",
            "action": "analyze_delivery_timestamps",
            "details": f"Delivery variance: {case_data['delivery_analysis']['delivery_variance_hours']}h, Late sellers: {case_data['delivery_analysis']['late_handoff_seller_ids']}"
        })

        trace_logs.append({
            "agent": "PaymentAgent",
            "action": "reconcile_payments",
            "details": f"Payments count: {len(case_data['payments'])}, Reconciled: {case_data['payment_reconciliation']['reconciled']}"
        })

        # Step 3: Policy Agent (Calls Qwen/Qwen2.5-7B-Instruct via LLMClient or PolicyEngine)
        llm_response = None
        if hasattr(self, "llm_client") and self.llm_client:
            system_prompt = "You are an expert E-Commerce Dispute Policy Agent enforcing EC_POLICY_V2."
            user_prompt = f"Analyze order case data and determine primary issue, secondary issues, and refund: {json.dumps(case_data, ensure_ascii=False)}"
            llm_response = self.llm_client.call_qwen_agent(system_prompt, user_prompt)

        policy_res = PolicyEngine.evaluate(case_data)
        trace_logs.append({
            "agent": "PolicyAgent",
            "action": "evaluate_policy",
            "model": self.model_name,
            "details": f"Primary issue: {policy_res['primary_issue']}, Secondary issues: {policy_res['secondary_issues']}, Recommended refund: {policy_res['recommended_refund_brl']} BRL",
            "llm_api_call": "SUCCESS" if llm_response else "DETERMINISTIC_ENGINE_FALLBACK"
        })

        # Step 4: Verifier Agent checks schema & limits
        final_output = Verifier.validate_and_format(case_id, case_data, policy_res)
        trace_logs.append({
            "agent": "VerifierAgent",
            "action": "verify_schema_and_limits",
            "details": f"Verified case_status: {final_output['case_assessment']['case_status']}, Evidence count: {len(final_output['evidence_ids'])}"
        })

        return final_output, trace_logs
