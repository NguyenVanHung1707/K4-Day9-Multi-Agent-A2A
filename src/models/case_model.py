"""
Pydantic Models for Case Input and Output
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ==================== Input Models ====================

class CustomerRequest(BaseModel):
    """Customer request details"""
    language: str
    message: str
    claimed_order_id: str


class InvestigationScope(BaseModel):
    """Investigation scope configuration"""
    include_customer_history: bool
    include_product_context: bool


class CaseInput(BaseModel):
    """Input case from JSON file"""
    case_id: str
    customer_request: CustomerRequest
    investigation_scope: InvestigationScope
    policy_version: str


# ==================== Output Models ====================

class CaseAssessment(BaseModel):
    """Case assessment result"""
    primary_issue: Optional[str]
    secondary_issues: List[str] = Field(default_factory=list)
    case_status: str  # "action_required" or "no_action"
    confidence: float = Field(ge=0, le=1)


class AffectedEntities(BaseModel):
    """Entities affected by the case"""
    order_ids: List[str] = Field(default_factory=list, max_length=5)
    item_ids: List[str] = Field(default_factory=list, max_length=5)
    seller_ids: List[str] = Field(default_factory=list, max_length=3)
    payment_ids: List[str] = Field(default_factory=list, max_length=5)


class CustomerContext(BaseModel):
    """Customer context information"""
    customer_unique_id: Optional[str]
    related_order_ids: List[str] = Field(default_factory=list, max_length=5)


class ProductContext(BaseModel):
    """Product context information"""
    product_ids: List[str] = Field(default_factory=list, max_length=5)
    category_names: List[str] = Field(default_factory=list, max_length=5)


class SellerHandoffAnalysis(BaseModel):
    """Analysis of seller handoff timing"""
    seller_id: str
    shipping_limit_at: Optional[str]
    handoff_variance_hours: Optional[float]
    late_handoff: bool


class DeliveryAnalysis(BaseModel):
    """Delivery timeline analysis"""
    delivered_at: Optional[str]
    estimated_delivery_at: Optional[str]
    carrier_handoff_at: Optional[str]
    delivery_variance_hours: Optional[float]
    seller_handoff_analysis: List[SellerHandoffAnalysis] = Field(default_factory=list)
    late_handoff_seller_ids: List[str] = Field(default_factory=list)


class PaymentReconciliation(BaseModel):
    """Payment reconciliation result"""
    currency: str = "BRL"
    item_total_brl: Optional[float]
    freight_total_brl: Optional[float]
    expected_total_brl: Optional[float]
    payment_total_brl: Optional[float]
    difference_brl: Optional[float]
    reconciled: Optional[bool]
    payment_types: List[str] = Field(default_factory=list)


class RankedCause(BaseModel):
    """Root cause with ranking"""
    cause_code: str
    rank: int


class ResponsibleParty(BaseModel):
    """Responsible party information"""
    party_type: str  # "seller", "platform", "logistics_provider"
    party_id: str


class RootCauseAnalysis(BaseModel):
    """Root cause analysis"""
    ranked_causes: List[RankedCause] = Field(default_factory=list, max_length=3)
    responsible_parties: List[ResponsibleParty] = Field(default_factory=list, max_length=3)


class FinancialResolution(BaseModel):
    """Financial resolution details"""
    currency: str = "BRL"
    recommended_refund_brl: float


class CaseOutput(BaseModel):
    """Complete case output"""
    case_id: str
    case_assessment: CaseAssessment
    affected_entities: AffectedEntities
    customer_context: CustomerContext
    product_context: ProductContext
    delivery_analysis: DeliveryAnalysis
    payment_reconciliation: PaymentReconciliation
    root_cause_analysis: RootCauseAnalysis
    evidence_ids: List[str] = Field(default_factory=list, max_length=20)
    financial_resolution: FinancialResolution
    resolution_actions: List[str] = Field(default_factory=list, max_length=5)


# ==================== State Models ====================

class CaseState(BaseModel):
    """Shared state for LangGraph"""
    # Input
    case_id: str
    order_id: str
    
    # Agent outputs
    customer_data: Optional[Dict[str, Any]] = None
    order_data: Optional[Dict[str, Any]] = None
    payment_data: Optional[Dict[str, Any]] = None
    delivery_data: Optional[Dict[str, Any]] = None
    
    # Policy result
    policy_result: Optional[Dict[str, Any]] = None
    
    # Final output
    output: Optional[CaseOutput] = None
    
    # Error tracking
    errors: List[str] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
