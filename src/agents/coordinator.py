"""
Coordinator: Orchestrate all agents to process a case
"""

import json
from typing import Dict, Any
from pathlib import Path

from src.models.case_model import CaseInput, CaseOutput
from src.agents.customer_agent import CustomerAgent
from src.agents.order_agent import OrderAgent
from src.agents.payment_agent import PaymentAgent
from src.agents.delivery_agent import DeliveryAgent
from src.agents.policy_engine import PolicyEngine
from src.validators.schema_validator import SchemaValidator


class Coordinator:
    """Main coordinator for case processing"""
    
    def __init__(self, db_path: str = "olist.db"):
        self.db_path = db_path
        
        # Initialize agents
        self.customer_agent = CustomerAgent(db_path)
        self.order_agent = OrderAgent(db_path)
        self.payment_agent = PaymentAgent(db_path)
        self.delivery_agent = DeliveryAgent(db_path)
        self.policy_engine = PolicyEngine(db_path)
        self.validator = SchemaValidator()
    
    def process_case(self, case_input: CaseInput) -> CaseOutput:
        """
        Process a single case through all agents
        
        Args:
            case_input: CaseInput from JSON file
            
        Returns:
            CaseOutput with all sections filled
        """
        order_id = case_input.customer_request.claimed_order_id
        
        print(f"\n🔍 Processing {case_input.case_id} (order: {order_id[:16]}...)")
        
        # Step 1: Customer Agent
        print("  → Customer Agent...")
        customer_data = self.customer_agent.investigate(order_id)
        
        # Step 2: Order Agent
        print("  → Order Agent...")
        order_data = self.order_agent.investigate(order_id)
        
        # Step 3: Payment Agent
        print("  → Payment Agent...")
        payment_data = self.payment_agent.investigate(
            order_id,
            order_data['items_raw']
        )
        
        # Step 4: Delivery Agent
        print("  → Delivery Agent...")
        delivery_data = self.delivery_agent.investigate(
            order_id,
            order_data['items_raw']
        )
        
        # Step 5: Policy Engine
        print("  → Policy Engine...")
        policy_result = self.policy_engine.apply_policy(
            order_id,
            order_data,
            customer_data,
            payment_data,
            delivery_data
        )
        
        # Step 6: Build output
        print("  → Building output...")
        output = self._build_output(
            case_input.case_id,
            customer_data,
            order_data,
            payment_data,
            delivery_data,
            policy_result
        )
        
        # Step 7: Validate
        print("  → Validating...")
        is_valid, errors = self.validator.validate(output)
        if not is_valid:
            print(f"  ⚠️ Validation errors:")
            for error in errors:
                print(f"     - {error}")
        
        print(f"  ✅ Complete: {policy_result['case_assessment']['primary_issue'] or 'no_match'}")
        
        return output
    
    def _build_output(
        self,
        case_id: str,
        customer_data: Dict,
        order_data: Dict,
        payment_data: Dict,
        delivery_data: Dict,
        policy_result: Dict
    ) -> CaseOutput:
        """Build final CaseOutput from all agent results"""
        
        # Merge payment_ids into affected_entities
        affected_entities = order_data['affected_entities'].copy()
        affected_entities['payment_ids'] = payment_data['payment_ids']
        
        # Import models
        from src.models.case_model import (
            CaseAssessment, AffectedEntities, CustomerContext,
            ProductContext, DeliveryAnalysis, PaymentReconciliation,
            RootCauseAnalysis, FinancialResolution,
            SellerHandoffAnalysis, RankedCause, ResponsibleParty
        )
        
        # Build output
        output = CaseOutput(
            case_id=case_id,
            case_assessment=CaseAssessment(**policy_result['case_assessment']),
            affected_entities=AffectedEntities(**affected_entities),
            customer_context=CustomerContext(**customer_data),
            product_context=ProductContext(**order_data['product_context']),
            delivery_analysis=DeliveryAnalysis(
                delivered_at=delivery_data['delivery_analysis']['delivered_at'],
                estimated_delivery_at=delivery_data['delivery_analysis']['estimated_delivery_at'],
                carrier_handoff_at=delivery_data['delivery_analysis']['carrier_handoff_at'],
                delivery_variance_hours=delivery_data['delivery_analysis']['delivery_variance_hours'],
                seller_handoff_analysis=[
                    SellerHandoffAnalysis(**item)
                    for item in delivery_data['delivery_analysis']['seller_handoff_analysis']
                ],
                late_handoff_seller_ids=delivery_data['delivery_analysis']['late_handoff_seller_ids']
            ),
            payment_reconciliation=PaymentReconciliation(**payment_data['payment_reconciliation']),
            root_cause_analysis=RootCauseAnalysis(
                ranked_causes=[
                    RankedCause(**item)
                    for item in policy_result['root_cause_analysis']['ranked_causes']
                ],
                responsible_parties=[
                    ResponsibleParty(**item)
                    for item in policy_result['root_cause_analysis']['responsible_parties']
                ]
            ),
            evidence_ids=policy_result['evidence_ids'],
            financial_resolution=FinancialResolution(**policy_result['financial_resolution']),
            resolution_actions=policy_result['resolution_actions']
        )
        
        return output
    
    def process_case_from_file(self, input_path: str, output_path: str):
        """
        Process a case from input JSON file and save to output JSON
        
        Args:
            input_path: Path to input JSON
            output_path: Path to output JSON
        """
        # Load input
        with open(input_path, 'r', encoding='utf-8') as f:
            case_dict = json.load(f)
        
        case_input = CaseInput(**case_dict)
        
        # Process
        output = self.process_case(case_input)
        
        # Save output with LF line endings (not CRLF)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(output.model_dump(), f, indent=2, ensure_ascii=False)
        
        return output


if __name__ == "__main__":
    # Test coordinator with EC_001
    coordinator = Coordinator()
    
    result = coordinator.process_case_from_file(
        "input/EC_001.json",
        "output/EC_001.json"
    )
    
    print(f"\n📊 Output saved to output/EC_001.json")
    print(f"   Primary issue: {result.case_assessment.primary_issue}")
    print(f"   Refund: {result.financial_resolution.recommended_refund_brl} BRL")
