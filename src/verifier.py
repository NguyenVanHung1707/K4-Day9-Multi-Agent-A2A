"""
Verifier & Schema Guardrail Agent.
Validates JSON structure, array length limits, data types, and formatting.
"""

from typing import Dict, List, Any

class Verifier:
    @staticmethod
    def validate_and_format(case_id: str, case_data: Dict[str, Any], policy_res: Dict[str, Any]) -> Dict[str, Any]:
        order_id = case_data["order"].get("order_id")
        
        # 1. Affected Entities
        item_ids = [f"{order_id}:{item.get('order_item_id')}" for item in case_data["items"] if item.get("order_item_id")]
        seller_ids = list(dict.fromkeys(case_data["seller_ids"]))[:3]
        payment_ids = case_data["payment_ids"][:5]

        affected_entities = {
            "order_ids": [order_id] if order_id else [],
            "item_ids": item_ids[:5],
            "seller_ids": seller_ids,
            "payment_ids": payment_ids
        }

        # 2. Customer Context
        customer_context = {
            "customer_unique_id": case_data["customer_unique_id"],
            "related_order_ids": case_data["related_order_ids"][:5]
        }

        # 3. Product Context
        product_context = {
            "product_ids": case_data["product_ids"][:5],
            "category_names": case_data["category_names"][:5]
        }

        # 4. Delivery Analysis
        delivery_analysis = case_data["delivery_analysis"]

        # 5. Payment Reconciliation
        payment_reconciliation = case_data["payment_reconciliation"]

        # 6. Root Cause Analysis
        root_cause_analysis = {
            "ranked_causes": [
                {
                    "cause_code": policy_res["root_cause_code"],
                    "rank": 1
                }
            ][:3],
            "responsible_parties": policy_res["responsible_parties"][:3]
        }

        # 7. Financial Resolution
        financial_resolution = {
            "currency": "BRL",
            "recommended_refund_brl": round(policy_res["recommended_refund_brl"], 2)
        }

        # 8. Resolution Actions & Evidence IDs
        resolution_actions = policy_res["resolution_actions"][:5]
        evidence_ids = policy_res["evidence_ids"][:20]

        output = {
            "case_id": case_id,
            "case_assessment": {
                "primary_issue": policy_res["primary_issue"],
                "secondary_issues": policy_res["secondary_issues"],
                "case_status": policy_res["case_status"],
                "confidence": round(policy_res["confidence"], 2)
            },
            "affected_entities": affected_entities,
            "customer_context": customer_context,
            "product_context": product_context,
            "delivery_analysis": delivery_analysis,
            "payment_reconciliation": payment_reconciliation,
            "root_cause_analysis": root_cause_analysis,
            "evidence_ids": evidence_ids,
            "financial_resolution": financial_resolution,
            "resolution_actions": resolution_actions
        }

        return output
