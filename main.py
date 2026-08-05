"""
Main execution script for Multi-Agent E-Commerce Dispute Resolution (EC_POLICY_V2).
Processes all 50 cases, outputs JSON to output/, writes trace.jsonl and metadata.json.
"""

import os
import glob
import json
from src.config import MODEL_NAME, PARAMETER_SIZE, FRAMEWORK, RUNTIME
from src.data_engine import DataEngine
from src.agents import MultiAgentSystem

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(root_dir, "input")
    output_dir = os.path.join(root_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    print("Initializing Data Engine & Loading CSV datasets...")
    data_engine = DataEngine()
    agent_system = MultiAgentSystem(data_engine)

    input_files = sorted(glob.glob(os.path.join(input_dir, "EC_*.json")))
    print(f"Found {len(input_files)} input files in input/")

    all_traces = []

    for filepath in input_files:
        filename = os.path.basename(filepath)
        with open(filepath, encoding="utf-8") as f:
            case_input = json.load(f)

        case_id = case_input.get("case_id", filename.replace(".json", ""))
        output_data, traces = agent_system.process_case(case_input)

        # Save output JSON
        output_filepath = os.path.join(output_dir, filename)
        with open(output_filepath, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        for t in traces:
            t["case_id"] = case_id
            all_traces.append(t)

        print(f"Processed {case_id} -> output/{filename}")

    # Write trace.jsonl to logging/ directory and root
    logging_dir = os.path.join(root_dir, "logging")
    os.makedirs(logging_dir, exist_ok=True)

    trace_filepath = os.path.join(logging_dir, "trace.jsonl")
    root_trace_filepath = os.path.join(root_dir, "trace.jsonl")
    
    with open(trace_filepath, "w", encoding="utf-8") as f, open(root_trace_filepath, "w", encoding="utf-8") as f_root:
        for trace in all_traces:
            line = json.dumps(trace, ensure_ascii=False) + "\n"
            f.write(line)
            f_root.write(line)
    print(f"Saved execution traces to {trace_filepath} and {root_trace_filepath}")

    # Write metadata.json to logging/ directory and root
    metadata = {
        "model": MODEL_NAME,
        "parameter_size": PARAMETER_SIZE,
        "framework": FRAMEWORK,
        "runtime": RUNTIME
    }
    metadata_filepath = os.path.join(logging_dir, "metadata.json")
    root_metadata_filepath = os.path.join(root_dir, "metadata.json")

    with open(metadata_filepath, "w", encoding="utf-8") as f, open(root_metadata_filepath, "w", encoding="utf-8") as f_root:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
        json.dump(metadata, f_root, ensure_ascii=False, indent=2)
    print(f"Saved metadata to {metadata_filepath} and {root_metadata_filepath}")

if __name__ == "__main__":
    main()
