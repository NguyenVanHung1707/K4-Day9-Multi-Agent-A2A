"""
Test with a single case (EC_001)
"""

import json
from pathlib import Path
from src.agents.coordinator import Coordinator


def test_single_case(case_id="EC_001"):
    """Test processing a single case"""
    
    print(f"🧪 Testing with {case_id}")
    print("=" * 80)
    
    # Initialize coordinator
    coordinator = Coordinator()
    
    # Process case
    input_path = f"input/{case_id}.json"
    output_path = f"output/{case_id}.json"
    
    if not Path(input_path).exists():
        print(f"❌ Input file not found: {input_path}")
        return
    
    try:
        output = coordinator.process_case_from_file(input_path, output_path)
        
        print("\n" + "=" * 80)
        print("✅ Test Successful!")
        print("=" * 80)
        print(f"\n📊 Results for {case_id}:")
        print(f"   Primary Issue: {output.case_assessment.primary_issue}")
        print(f"   Secondary Issues: {output.case_assessment.secondary_issues}")
        print(f"   Case Status: {output.case_assessment.case_status}")
        print(f"   Confidence: {output.case_assessment.confidence}")
        print(f"\n💰 Financial:")
        print(f"   Recommended Refund: {output.financial_resolution.recommended_refund_brl} BRL")
        print(f"\n🎬 Actions:")
        for action in output.resolution_actions:
            print(f"   - {action}")
        print(f"\n📋 Evidence IDs: {len(output.evidence_ids)} items")
        print(f"\n📄 Output saved to: {output_path}")
        
        # Pretty print full output
        print("\n" + "=" * 80)
        print("Full Output JSON:")
        print("=" * 80)
        with open(output_path, 'r', encoding='utf-8') as f:
            output_json = json.load(f)
        print(json.dumps(output_json, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"\n❌ Test Failed!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_single_case("EC_001")
