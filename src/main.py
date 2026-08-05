from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.config import DATA_DIR, INPUT_DIR, OUTPUT_DIR, TRACE_PATH
from src.coordinator import Coordinator
from src.repository import DataRepository
from src.tracing import TraceWriter


def run_pipeline(data_dir: Path, input_dir: Path, output_dir: Path, trace_path: Path) -> int:
    case_files = sorted(input_dir.glob("EC_*.json"))
    if not case_files:
        raise ValueError(f"No EC_*.json inputs found in {input_dir}")
    repository = DataRepository(data_dir)
    trace = TraceWriter(trace_path)
    trace.reset()
    coordinator = Coordinator(repository, trace)
    output_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for case_path in case_files:
        try:
            case = json.loads(case_path.read_text(encoding="utf-8"))
            result = coordinator.process(case)
            destination = output_dir / case_path.name
            temporary = destination.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(destination)
        except Exception as exc:
            failures.append(f"{case_path.name}: {exc}")
            trace.write(case_path.stem, "coordinator_agent", "case_failed", {"error": str(exc)})
    if failures:
        raise RuntimeError("Pipeline refused to fabricate failed cases:\n" + "\n".join(failures))
    return len(case_files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EC_POLICY_V2 over Olist dispute cases")
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    parser.add_argument("--input", type=Path, default=INPUT_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--trace", type=Path, default=TRACE_PATH)
    args = parser.parse_args()
    try:
        count = run_pipeline(args.data, args.input, args.output, args.trace)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Successfully generated and verified {count} case outputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

