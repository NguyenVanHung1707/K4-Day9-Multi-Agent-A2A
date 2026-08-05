"""
Schema Validator: Validate output against schema constraints
"""

from typing import List, Dict, Any
from src.models.case_model import CaseOutput
from src.utils.config import (
    MAX_ORDER_IDS, MAX_ITEM_IDS, MAX_SELLER_IDS,
    MAX_PAYMENT_IDS, MAX_RELATED_ORDER_IDS, MAX_PRODUCT_IDS,
    MAX_CATEGORY_NAMES, MAX_ROOT_CAUSES, MAX_RESPONSIBLE_PARTIES,
    MAX_EVIDENCE_IDS, MAX_ACTIONS, DECIMAL_PLACES
)


class SchemaValidator:
    """Validator for output schema compliance"""
    
    def validate(self, output: CaseOutput) -> tuple[bool, List[str]]:
        """
        Validate output against schema constraints
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Check array limits
        if len(output.affected_entities.order_ids) > MAX_ORDER_IDS:
            errors.append(f"Too many order_ids: {len(output.affected_entities.order_ids)} > {MAX_ORDER_IDS}")
        
        if len(output.affected_entities.item_ids) > MAX_ITEM_IDS:
            errors.append(f"Too many item_ids: {len(output.affected_entities.item_ids)} > {MAX_ITEM_IDS}")
        
        if len(output.affected_entities.seller_ids) > MAX_SELLER_IDS:
            errors.append(f"Too many seller_ids: {len(output.affected_entities.seller_ids)} > {MAX_SELLER_IDS}")
        
        if len(output.affected_entities.payment_ids) > MAX_PAYMENT_IDS:
            errors.append(f"Too many payment_ids: {len(output.affected_entities.payment_ids)} > {MAX_PAYMENT_IDS}")
        
        if len(output.customer_context.related_order_ids) > MAX_RELATED_ORDER_IDS:
            errors.append(f"Too many related_order_ids: {len(output.customer_context.related_order_ids)} > {MAX_RELATED_ORDER_IDS}")
        
        if len(output.product_context.product_ids) > MAX_PRODUCT_IDS:
            errors.append(f"Too many product_ids: {len(output.product_context.product_ids)} > {MAX_PRODUCT_IDS}")
        
        if len(output.product_context.category_names) > MAX_CATEGORY_NAMES:
            errors.append(f"Too many category_names: {len(output.product_context.category_names)} > {MAX_CATEGORY_NAMES}")
        
        if len(output.root_cause_analysis.ranked_causes) > MAX_ROOT_CAUSES:
            errors.append(f"Too many ranked_causes: {len(output.root_cause_analysis.ranked_causes)} > {MAX_ROOT_CAUSES}")
        
        if len(output.root_cause_analysis.responsible_parties) > MAX_RESPONSIBLE_PARTIES:
            errors.append(f"Too many responsible_parties: {len(output.root_cause_analysis.responsible_parties)} > {MAX_RESPONSIBLE_PARTIES}")
        
        if len(output.evidence_ids) > MAX_EVIDENCE_IDS:
            errors.append(f"Too many evidence_ids: {len(output.evidence_ids)} > {MAX_EVIDENCE_IDS}")
        
        if len(output.resolution_actions) > MAX_ACTIONS:
            errors.append(f"Too many resolution_actions: {len(output.resolution_actions)} > {MAX_ACTIONS}")
        
        # Check confidence range
        if not (0 <= output.case_assessment.confidence <= 1):
            errors.append(f"Confidence out of range: {output.case_assessment.confidence}")
        
        # Check case_status
        if output.case_assessment.case_status not in ["action_required", "no_action"]:
            errors.append(f"Invalid case_status: {output.case_assessment.case_status}")
        
        # Check decimal places for monetary values
        refund = output.financial_resolution.recommended_refund_brl
        if refund is not None:
            decimal_str = str(refund).split('.')
            if len(decimal_str) > 1 and len(decimal_str[1]) > DECIMAL_PLACES:
                errors.append(f"Refund has too many decimal places: {refund}")
        
        return (len(errors) == 0, errors)


if __name__ == "__main__":
    # Test validator with mock data
    from src.models.case_model import (
        CaseOutput, CaseAssessment, AffectedEntities,
        CustomerContext, ProductContext, DeliveryAnalysis,
        PaymentReconciliation, RootCauseAnalysis, FinancialResolution
    )
    
    output = CaseOutput(
        case_id="EC_001",
        case_assessment=CaseAssessment(
            primary_issue="late_delivery_seller",
            secondary_issues=["multi_item_order"],
            case_status="action_required",
            confidence=0.92
        ),
        affected_entities=AffectedEntities(
            order_ids=["order1"],
            item_ids=["item1"],
            seller_ids=["seller1"],
            payment_ids=["payment1"]
        ),
        customer_context=CustomerContext(
            customer_unique_id="cust1",
            related_order_ids=[]
        ),
        product_context=ProductContext(
            product_ids=["prod1"],
            category_names=["furniture"]
        ),
        delivery_analysis=DeliveryAnalysis(
            delivered_at="2018-01-01 10:00:00",
            estimated_delivery_at="2018-01-01 09:00:00",
            carrier_handoff_at="2017-12-31 10:00:00",
            delivery_variance_hours=1.0,
            seller_handoff_analysis=[],
            late_handoff_seller_ids=[]
        ),
        payment_reconciliation=PaymentReconciliation(
            currency="BRL",
            item_total_brl=100.0,
            freight_total_brl=10.0,
            expected_total_brl=110.0,
            payment_total_brl=110.0,
            difference_brl=0.0,
            reconciled=True,
            payment_types=["credit_card"]
        ),
        root_cause_analysis=RootCauseAnalysis(
            ranked_causes=[],
            responsible_parties=[]
        ),
        evidence_ids=["order:order1"],
        financial_resolution=FinancialResolution(
            currency="BRL",
            recommended_refund_brl=10.0
        ),
        resolution_actions=["refund_freight"]
    )
    
    validator = SchemaValidator()
    is_valid, errors = validator.validate(output)
    
    print(f"Validation: {'✅ PASS' if is_valid else '❌ FAIL'}")
    if errors:
        for error in errors:
            print(f"  - {error}")
