"""
Policy Engine: Apply EC_POLICY_V2 rules (deterministic, no LLM)
"""

from typing import Dict, Any, List, Optional
from src.data_processing.db_helper import DatabaseHelper
from src.utils.config import (
    MAX_ROOT_CAUSES, MAX_RESPONSIBLE_PARTIES, 
    MAX_EVIDENCE_IDS, MAX_ACTIONS, DECIMAL_PLACES
)


class PolicyEngine:
    """Deterministic policy engine for EC_POLICY_V2"""
    
    def __init__(self, db_path: str = "olist.db"):
        self.db_path = db_path
    
    def apply_policy(
        self,
        order_id: str,
        order_data: Dict,
        customer_data: Dict,
        payment_data: Dict,
        delivery_data: Dict
    ) -> Dict[str, Any]:
        """
        Apply EC_POLICY_V2 rules
        
        Returns:
            Dict with case_assessment, root_cause_analysis, evidence_ids,
            financial_resolution, resolution_actions
        """
        # Get order status
        with DatabaseHelper(self.db_path) as db:
            order = db.get_order(order_id)
            if not order:
                return self._empty_result()
            
            order_status = order.get('order_status', '').lower()
        
        # Extract data
        payment_recon = payment_data['payment_reconciliation']
        delivery_analysis = delivery_data['delivery_analysis']
        items_raw = order_data.get('items_raw', [])
        payments_raw = payment_data.get('payments_raw', [])
        
        # Apply rules in priority order
        policy_result = None
        
        # Priority 1: canceled_order_paid
        if order_status == 'canceled' and payment_recon['payment_total_brl'] > 0:
            policy_result = {
                "primary_issue": "canceled_order_paid",
                "root_cause": "ORDER_CANCELED_AFTER_PAYMENT",
                "responsible_parties": [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
                "refund_brl": payment_recon['payment_total_brl'],
                "primary_action": "issue_full_refund"
            }
        
        # Priority 2: unavailable_order_paid
        elif order_status == 'unavailable' and payment_recon['payment_total_brl'] > 0:
            policy_result = {
                "primary_issue": "unavailable_order_paid",
                "root_cause": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
                "responsible_parties": [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
                "refund_brl": payment_recon['payment_total_brl'],
                "primary_action": "issue_full_refund"
            }
        
        # Priority 3: late_delivery_seller
        elif (delivery_analysis['delivery_variance_hours'] is not None and
              delivery_analysis['delivery_variance_hours'] > 0 and
              len(delivery_analysis['late_handoff_seller_ids']) > 0):
            policy_result = {
                "primary_issue": "late_delivery_seller",
                "root_cause": "SELLER_HANDOFF_AFTER_LIMIT",
                "responsible_parties": [
                    {"party_type": "seller", "party_id": sid}
                    for sid in delivery_analysis['late_handoff_seller_ids']
                ],
                "refund_brl": payment_recon['freight_total_brl'] or 0.0,
                "primary_action": "refund_freight"
            }
        
        # Priority 4: late_delivery_logistics
        elif (delivery_analysis['delivery_variance_hours'] is not None and
              delivery_analysis['delivery_variance_hours'] > 0 and
              len(delivery_analysis['late_handoff_seller_ids']) == 0):
            policy_result = {
                "primary_issue": "late_delivery_logistics",
                "root_cause": "CARRIER_DELIVERED_AFTER_ESTIMATE",
                "responsible_parties": [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}],
                "refund_brl": payment_recon['freight_total_brl'] or 0.0,
                "primary_action": "refund_freight"
            }
        
        # Priority 5: valid_split_payment
        elif (len(payments_raw) >= 2 and payment_recon['reconciled'] == True):
            policy_result = {
                "primary_issue": "valid_split_payment",
                "root_cause": "MULTIPLE_PAYMENTS_RECONCILED",
                "responsible_parties": [],
                "refund_brl": 0.0,
                "primary_action": "explain_valid_split_payment"
            }
        
        # Priority 6: unsupported_late_claim
        elif ((delivery_analysis['delivery_variance_hours'] is None or
               delivery_analysis['delivery_variance_hours'] <= 0) and
              payment_recon['reconciled'] == True):
            policy_result = {
                "primary_issue": "unsupported_late_claim",
                "root_cause": "DELIVERY_WITHIN_ESTIMATE",
                "responsible_parties": [],
                "refund_brl": 0.0,
                "primary_action": "reject_late_refund"
            }
        
        # No match
        else:
            policy_result = {
                "primary_issue": None,
                "root_cause": "NO_POLICY_MATCH",
                "responsible_parties": [],
                "refund_brl": 0.0,
                "primary_action": "manual_review"
            }
        
        # Detect secondary issues
        secondary_issues = self._detect_secondary_issues(
            items_raw, payments_raw, customer_data, order_data
        )
        
        # Build actions
        actions = self._build_actions(
            policy_result['primary_action'],
            policy_result['primary_issue'],
            delivery_analysis,
            len(order_data['affected_entities']['seller_ids']) > 1,
            len(payments_raw) > 1,
            policy_result['refund_brl'] > 0
        )
        
        # Build evidence IDs
        evidence_ids = self._build_evidence_ids(
            order_id,
            items_raw,
            payments_raw,
            policy_result['responsible_parties'],
            policy_result['root_cause']
        )
        
        # Determine case status
        case_status = "action_required" if policy_result['refund_brl'] > 0 else "no_action"
        
        return {
            "case_assessment": {
                "primary_issue": policy_result['primary_issue'],
                "secondary_issues": secondary_issues,
                "case_status": case_status,
                "confidence": 0.92  # High confidence for deterministic rules
            },
            "root_cause_analysis": {
                "ranked_causes": [
                    {"cause_code": policy_result['root_cause'], "rank": 1}
                ][:MAX_ROOT_CAUSES],
                "responsible_parties": policy_result['responsible_parties'][:MAX_RESPONSIBLE_PARTIES]
            },
            "evidence_ids": evidence_ids[:MAX_EVIDENCE_IDS],
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": round(policy_result['refund_brl'], DECIMAL_PLACES)
            },
            "resolution_actions": actions[:MAX_ACTIONS]
        }
    
    def _detect_secondary_issues(
        self,
        items_raw: List[Dict],
        payments_raw: List[Dict],
        customer_data: Dict,
        order_data: Dict
    ) -> List[str]:
        """Detect secondary issues in order"""
        secondary = []
        
        # 1. multi_item_order
        if len(items_raw) >= 2:
            secondary.append("multi_item_order")
        
        # 2. multi_seller_order
        if len(order_data['affected_entities']['seller_ids']) >= 2:
            secondary.append("multi_seller_order")
        
        # 3. split_payment
        if len(payments_raw) >= 2:
            secondary.append("split_payment")
        
        # 4. repeat_customer
        if len(customer_data.get('related_order_ids', [])) > 0:
            secondary.append("repeat_customer")
        
        # 5. multiple_categories
        if len(order_data['product_context']['category_names']) >= 2:
            secondary.append("multiple_categories")
        
        return secondary
    
    def _build_actions(
        self,
        primary_action: str,
        primary_issue: Optional[str],
        delivery_analysis: Dict,
        is_multi_seller: bool,
        is_split_payment: bool,
        needs_refund: bool
    ) -> List[str]:
        """Build resolution actions"""
        actions = [primary_action]
        
        # Add conditional actions
        if len(delivery_analysis['late_handoff_seller_ids']) > 0:
            actions.append("review_seller_handoff")
        elif (delivery_analysis['delivery_variance_hours'] is not None and
              delivery_analysis['delivery_variance_hours'] > 0):
            actions.append("review_carrier_delay")
        
        if needs_refund:
            actions.append("verify_refund_completion")
        
        if is_multi_seller:
            actions.append("coordinate_multi_seller_case")
        
        if is_split_payment and primary_issue != "valid_split_payment":
            actions.append("verify_payment_allocation")
        
        return actions
    
    def _build_evidence_ids(
        self,
        order_id: str,
        items_raw: List[Dict],
        payments_raw: List[Dict],
        responsible_parties: List[Dict],
        root_cause: str
    ) -> List[str]:
        """Build evidence IDs"""
        evidence = []
        
        # Always include order
        evidence.append(f"order:{order_id}")
        
        # Add items
        for item in items_raw[:5]:
            evidence.append(f"item:{order_id}:{item['order_item_id']}")
        
        # Add payments
        for payment in payments_raw[:5]:
            evidence.append(f"payment:{order_id}:{payment['payment_sequential']}")
        
        # Add responsible sellers
        for party in responsible_parties:
            if party['party_type'] == 'seller':
                evidence.append(f"seller:{party['party_id']}")
        
        # Add policy
        evidence.append(f"policy:{root_cause}")
        
        return evidence
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result when order not found"""
        return {
            "case_assessment": {
                "primary_issue": None,
                "secondary_issues": [],
                "case_status": "no_action",
                "confidence": 0.0
            },
            "root_cause_analysis": {
                "ranked_causes": [],
                "responsible_parties": []
            },
            "evidence_ids": [],
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": 0.0
            },
            "resolution_actions": []
        }
