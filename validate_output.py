"""
Validate Output Format
Check if outputs match the required schema and constraints
"""

import json
from pathlib import Path
from typing import List, Tuple


def validate_single_output(file_path: Path) -> Tuple[bool, List[str]]:
    """Validate a single output JSON file"""
    errors = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return False, [f"Cannot read JSON: {e}"]
    
    # Check required top-level keys
    required_keys = [
        "case_id", "case_assessment", "affected_entities", 
        "customer_context", "product_context", "delivery_analysis",
        "payment_reconciliation", "root_cause_analysis", 
        "evidence_ids", "financial_resolution", "resolution_actions"
    ]
    
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing key: {key}")
    
    if errors:
        return False, errors
    
    # Validate case_assessment
    ca = data.get("case_assessment", {})
    if "primary_issue" not in ca:
        errors.append("Missing case_assessment.primary_issue")
    if "secondary_issues" not in ca or not isinstance(ca.get("secondary_issues"), list):
        errors.append("case_assessment.secondary_issues must be array")
    if "case_status" not in ca:
        errors.append("Missing case_assessment.case_status")
    elif ca["case_status"] not in ["action_required", "no_action"]:
        errors.append(f"Invalid case_status: {ca['case_status']}")
    if "confidence" not in ca:
        errors.append("Missing case_assessment.confidence")
    elif not (0 <= ca["confidence"] <= 1):
        errors.append(f"confidence out of range: {ca['confidence']}")
    
    # Validate affected_entities limits
    ae = data.get("affected_entities", {})
    if len(ae.get("order_ids", [])) > 5:
        errors.append(f"Too many order_ids: {len(ae['order_ids'])} > 5")
    if len(ae.get("item_ids", [])) > 5:
        errors.append(f"Too many item_ids: {len(ae['item_ids'])} > 5")
    if len(ae.get("seller_ids", [])) > 3:
        errors.append(f"Too many seller_ids: {len(ae['seller_ids'])} > 3")
    if len(ae.get("payment_ids", [])) > 5:
        errors.append(f"Too many payment_ids: {len(ae['payment_ids'])} > 5")
    
    # Validate customer_context
    cc = data.get("customer_context", {})
    if len(cc.get("related_order_ids", [])) > 5:
        errors.append(f"Too many related_order_ids: {len(cc['related_order_ids'])} > 5")
    
    # Validate product_context
    pc = data.get("product_context", {})
    if len(pc.get("product_ids", [])) > 5:
        errors.append(f"Too many product_ids: {len(pc['product_ids'])} > 5")
    if len(pc.get("category_names", [])) > 5:
        errors.append(f"Too many category_names: {len(pc['category_names'])} > 5")
    
    # Validate root_cause_analysis
    rca = data.get("root_cause_analysis", {})
    if len(rca.get("ranked_causes", [])) > 3:
        errors.append(f"Too many ranked_causes: {len(rca['ranked_causes'])} > 3")
    if len(rca.get("responsible_parties", [])) > 3:
        errors.append(f"Too many responsible_parties: {len(rca['responsible_parties'])} > 3")
    
    # Validate evidence_ids
    if len(data.get("evidence_ids", [])) > 20:
        errors.append(f"Too many evidence_ids: {len(data['evidence_ids'])} > 20")
    
    # Validate resolution_actions
    if len(data.get("resolution_actions", [])) > 5:
        errors.append(f"Too many resolution_actions: {len(data['resolution_actions'])} > 5")
    
    # Validate decimal places for monetary values
    fr = data.get("financial_resolution", {})
    if "recommended_refund_brl" in fr:
        refund = fr["recommended_refund_brl"]
        if refund is not None:
            decimal_str = str(refund).split('.')
            if len(decimal_str) > 1 and len(decimal_str[1]) > 2:
                errors.append(f"refund has >2 decimal places: {refund}")
    
    # Validate timestamps format (YYYY-MM-DD HH:MM:SS or null)
    da = data.get("delivery_analysis", {})
    timestamp_fields = ["delivered_at", "estimated_delivery_at", "carrier_handoff_at"]
    for field in timestamp_fields:
        value = da.get(field)
        if value is not None and value != "":
            # Basic format check
            if not isinstance(value, str) or len(value) != 19:
                errors.append(f"{field} invalid format: {value}")
    
    return len(errors) == 0, errors


def validate_all_outputs():
    """Validate all output files"""
    output_folder = Path("output")
    
    print("=" * 80)
    print("🔍 Validating Output Files")
    print("=" * 80)
    
    # Check if output folder exists
    if not output_folder.exists():
        print("❌ Output folder not found!")
        return
    
    # Get all JSON files
    json_files = sorted(output_folder.glob("EC_*.json"))
    
    if len(json_files) == 0:
        print("❌ No output files found!")
        return
    
    print(f"\n📂 Found {len(json_files)} output files\n")
    
    # Validate each file
    all_valid = True
    error_count = 0
    
    for json_file in json_files:
        is_valid, errors = validate_single_output(json_file)
        
        if is_valid:
            print(f"✅ {json_file.name}")
        else:
            all_valid = False
            error_count += len(errors)
            print(f"❌ {json_file.name}")
            for error in errors:
                print(f"   - {error}")
    
    # Summary
    print("\n" + "=" * 80)
    if all_valid:
        print("✅ All outputs are valid!")
    else:
        print(f"❌ Found {error_count} errors in outputs")
    print("=" * 80)
    
    # Check file count
    print(f"\n📊 File Count:")
    print(f"   Expected: 50 files (EC_001.json to EC_050.json)")
    print(f"   Actual: {len(json_files)} files")
    
    if len(json_files) == 50:
        print("   ✅ Correct number of files!")
    else:
        print(f"   ❌ Wrong number of files!")
    
    # Check sequence
    expected_ids = set(f"EC_{i:03d}" for i in range(1, 51))
    actual_ids = set(f.stem for f in json_files)
    missing = expected_ids - actual_ids
    extra = actual_ids - expected_ids
    
    if missing:
        print(f"\n❌ Missing files: {', '.join(sorted(missing))}")
    if extra:
        print(f"\n❌ Extra files: {', '.join(sorted(extra))}")
    
    if not missing and not extra and all_valid:
        print("\n🎉 All validations passed! Ready to submit.")
    else:
        print("\n⚠️ Please fix errors before submitting.")


if __name__ == "__main__":
    validate_all_outputs()
