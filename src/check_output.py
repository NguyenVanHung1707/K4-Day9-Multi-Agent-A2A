"""
Verification script for output JSON compliance against Section 6 & 8 requirements.
"""

import os
import glob
import json

VALID_PRIMARY_ISSUES = {
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim"
}

VALID_SECONDARY_ISSUES = [
    "multi_item_order",
    "multi_seller_order",
    "split_payment",
    "repeat_customer",
    "multiple_categories"
]

def check_outputs():
    output_dir = "output"
    files = sorted(glob.glob(os.path.join(output_dir, "EC_*.json")))
    assert len(files) == 50, f"Expected 50 output files, found {len(files)}"

    for fpath in files:
        fname = os.path.basename(fpath)
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)

        # 1. Top-level keys
        required_keys = {
            "case_id", "case_assessment", "affected_entities", "customer_context",
            "product_context", "delivery_analysis", "payment_reconciliation",
            "root_cause_analysis", "evidence_ids", "financial_resolution", "resolution_actions"
        }
        missing = required_keys - set(data.keys())
        assert not missing, f"{fname} missing keys: {missing}"

        # 2. Case Assessment
        ca = data["case_assessment"]
        assert ca["primary_issue"] in VALID_PRIMARY_ISSUES, f"{fname} invalid primary_issue: {ca['primary_issue']}"
        assert ca["case_status"] in {"action_required", "no_action"}, f"{fname} invalid status: {ca['case_status']}"
        assert 0 <= ca["confidence"] <= 1, f"{fname} confidence out of range: {ca['confidence']}"

        # 3. Array limits (Section 6)
        ae = data["affected_entities"]
        assert len(ae["order_ids"]) <= 5, f"{fname} order_ids exceeds 5"
        assert len(ae["item_ids"]) <= 5, f"{fname} item_ids exceeds 5"
        assert len(ae["seller_ids"]) <= 3, f"{fname} seller_ids exceeds 3"
        assert len(ae["payment_ids"]) <= 5, f"{fname} payment_ids exceeds 5"

        cc = data["customer_context"]
        assert len(cc["related_order_ids"]) <= 5, f"{fname} related_order_ids exceeds 5"

        pc = data["product_context"]
        assert len(pc["product_ids"]) <= 5, f"{fname} product_ids exceeds 5"
        assert len(pc["category_names"]) <= 5, f"{fname} category_names exceeds 5"

        rca = data["root_cause_analysis"]
        assert len(rca["ranked_causes"]) <= 3, f"{fname} ranked_causes exceeds 3"
        assert len(rca["responsible_parties"]) <= 3, f"{fname} responsible_parties exceeds 3"

        assert len(data["evidence_ids"]) <= 20, f"{fname} evidence_ids exceeds 20"
        assert len(data["resolution_actions"]) <= 5, f"{fname} resolution_actions exceeds 5"

        # 4. Status consistency
        fr = data["financial_resolution"]
        if fr["recommended_refund_brl"] > 0:
            assert ca["case_status"] == "action_required", f"{fname} status should be action_required"
        else:
            assert ca["case_status"] == "no_action", f"{fname} status should be no_action"

    print("All 50 output files passed 100% verification check!")

if __name__ == "__main__":
    check_outputs()
