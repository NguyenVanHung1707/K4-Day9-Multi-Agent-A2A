import os
import json
import time
import glob
import zipfile

from src.data_engine import DataEngine
from src.llm_client import LLMClient
from src.agents import CoordinatorAgent


def create_versioned_zip(output_dir: str, base_dir: str) -> str:
    """
    Creates a versioned zip archive (output.zip, output_v2.zip, output_v3.zip...) containing output/EC_001.json to output/EC_050.json.
    """
    version = 1
    zip_filename = "output.zip"
    while os.path.exists(os.path.join(base_dir, zip_filename)):
        version += 1
        zip_filename = f"output_v{version}.zip"

    zip_filepath = os.path.join(base_dir, zip_filename)
    json_files = sorted(glob.glob(os.path.join(output_dir, "*.json")))

    with zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
        for fpath in json_files:
            # Preserve output/ directory prefix inside zip archive
            arcname = f"output/{os.path.basename(fpath)}"
            zipf.write(fpath, arcname)

    return zip_filename


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    input_dir = os.path.join(base_dir, "input")
    output_dir = os.path.join(base_dir, "output")
    trace_path = os.path.join(base_dir, "trace.jsonl")
    metadata_path = os.path.join(base_dir, "metadata.json")

    os.makedirs(output_dir, exist_ok=True)

    print("Initializing DataEngine and LLMClient (Groq API)...")
    data_engine = DataEngine(data_dir=data_dir)
    llm_client = LLMClient()
    coordinator = CoordinatorAgent(data_engine=data_engine, llm_client=llm_client)

    all_traces = []
    start_time = time.time()

    print("Starting processing of 50 input cases with Groq LLM API...")
    for i in range(1, 51):
        case_file = f"EC_{i:03d}.json"
        case_path = os.path.join(input_dir, case_file)

        if not os.path.exists(case_path):
            print(f"Warning: {case_file} not found. Skipping.")
            continue

        with open(case_path, "r", encoding="utf-8") as f:
            case_input = json.load(f)

        case_id = case_input["case_id"]
        print(f"[{i:02d}/50] Processing {case_id} via Groq API...")

        output_data, trace_steps = coordinator.process_case(case_input)

        # Write output file
        out_file_path = os.path.join(output_dir, case_file)
        with open(out_file_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        # Record trace
        trace_record = {
            "case_id": case_id,
            "claimed_order_id": case_input["customer_request"]["claimed_order_id"],
            "primary_issue": output_data["case_assessment"]["primary_issue"],
            "case_status": output_data["case_assessment"]["case_status"],
            "recommended_refund_brl": output_data["financial_resolution"]["recommended_refund_brl"],
            "trace_steps": trace_steps
        }
        all_traces.append(trace_record)

    # Write trace.jsonl
    with open(trace_path, "w", encoding="utf-8") as f:
        for trace in all_traces:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    # Write metadata.json
    total_time = round(time.time() - start_time, 2)
    metadata_content = {
        "models": [
            {
                "agent_role": "Policy Agent (Reasoning & Decision)",
                "model_name": "llama-3.1-8b-instant",
                "parameter_size": "8B",
                "provider": "Groq"
            },
            {
                "agent_role": "Coordinator & Domain Agents (Structuring & Orchestration)",
                "model_name": "llama-3.1-8b-instant",
                "parameter_size": "8B",
                "provider": "Groq"
            }
        ],
        "framework": "Custom Python Multi-Agent Architecture (A2A)",
        "runtime": "Python 3.11",
        "max_parameter_limit": "<= 10B",
        "total_cases_processed": len(all_traces),
        "total_execution_time_seconds": total_time
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata_content, f, indent=2, ensure_ascii=False)

    # Automatically create versioned output zip
    zip_created = create_versioned_zip(output_dir, base_dir)

    print(f"Pipeline completed successfully in {total_time}s!")
    print(f"Outputs written to {output_dir}/")
    print(f"Versioned archive created: {zip_created}")
    print(f"Trace log written to {trace_path}")
    print(f"Metadata written to {metadata_path}")


if __name__ == "__main__":
    main()
