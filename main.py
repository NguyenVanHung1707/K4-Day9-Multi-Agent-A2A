"""
Main Entry Point: Process all 50 cases
"""

import json
import time
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

from src.agents.coordinator import Coordinator
from src.utils.config import (
    INPUT_FOLDER, OUTPUT_FOLDER, LOGGING_FOLDER,
    TRACE_FILE, METADATA_FILE, MODEL_NAME
)


def process_all_cases():
    """Process all 50 cases from input folder"""
    
    print("=" * 80)
    print("🚀 EC Dispute Resolution System - Processing All Cases")
    print("=" * 80)
    print(f"Model: {MODEL_NAME}")
    print(f"Input folder: {INPUT_FOLDER}")
    print(f"Output folder: {OUTPUT_FOLDER}")
    print("=" * 80)
    
    # Create output folder
    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)
    Path(LOGGING_FOLDER).mkdir(parents=True, exist_ok=True)
    
    # Initialize coordinator
    coordinator = Coordinator()
    
    # Get all input files
    input_files = sorted(Path(INPUT_FOLDER).glob("EC_*.json"))
    total_cases = len(input_files)
    
    if total_cases == 0:
        print("❌ No input files found!")
        return
    
    print(f"\n📂 Found {total_cases} cases to process\n")
    
    # Track results
    results = []
    start_time = time.time()
    
    # Process each case
    for input_path in tqdm(input_files, desc="Processing cases"):
        case_id = input_path.stem  # EC_001, EC_002, etc.
        output_path = Path(OUTPUT_FOLDER) / f"{case_id}.json"
        
        case_start_time = time.time()
        
        try:
            # Process case
            output = coordinator.process_case_from_file(
                str(input_path),
                str(output_path)
            )
            
            case_duration = time.time() - case_start_time
            
            results.append({
                "case_id": case_id,
                "status": "success",
                "primary_issue": output.case_assessment.primary_issue,
                "refund_brl": output.financial_resolution.recommended_refund_brl,
                "duration_seconds": round(case_duration, 2)
            })
            
        except Exception as e:
            case_duration = time.time() - case_start_time
            print(f"\n❌ Error processing {case_id}: {e}")
            
            results.append({
                "case_id": case_id,
                "status": "error",
                "error": str(e),
                "duration_seconds": round(case_duration, 2)
            })
    
    # Calculate statistics
    total_duration = time.time() - start_time
    successful = len([r for r in results if r['status'] == 'success'])
    failed = len([r for r in results if r['status'] == 'error'])
    avg_duration = total_duration / total_cases if total_cases > 0 else 0
    
    # Generate metadata
    metadata = {
        "model": MODEL_NAME,
        "parameter_size": "< 10B",
        "framework": "LangGraph + SQLite",
        "runtime": "Python 3.11",
        "total_cases": total_cases,
        "successful_cases": successful,
        "failed_cases": failed,
        "total_duration_seconds": round(total_duration, 2),
        "avg_case_duration_seconds": round(avg_duration, 2),
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
    
    # Save metadata
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "=" * 80)
    print("✅ Processing Complete!")
    print("=" * 80)
    print(f"Total cases: {total_cases}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total time: {total_duration:.2f}s")
    print(f"Average time per case: {avg_duration:.2f}s")
    print("=" * 80)
    print(f"📂 Outputs saved to: {OUTPUT_FOLDER}/")
    print(f"📊 Metadata saved to: {METADATA_FILE}")
    print("=" * 80)
    
    # Show issue distribution
    if successful > 0:
        print("\n📊 Issue Distribution:")
        issue_counts = {}
        for result in results:
            if result['status'] == 'success':
                issue = result['primary_issue'] or 'no_match'
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        for issue, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
            print(f"   {issue}: {count} cases")
    
    return metadata


if __name__ == "__main__":
    metadata = process_all_cases()
