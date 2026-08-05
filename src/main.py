from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.agents.groq_strict_policy_review import GroqStrictPolicyReviewAgent
from src.config import DATA_DIR, INPUT_DIR, OUTPUT_DIR, ROOT_DIR, TRACE_PATH
from src.coordinator import Coordinator
from src.env import load_env
from src.repository import DataRepository
from src.tracing import TraceWriter


def run_pipeline(
    data_dir: Path,
    input_dir: Path,
    output_dir: Path,
    trace_path: Path,
    use_llm: bool = False,
    review_client: Any | None = None,
) -> int:
    case_files = sorted(input_dir.glob("EC_*.json"))
    if not case_files:
        raise ValueError(f"No EC_*.json inputs found in {input_dir}")
    load_env(ROOT_DIR / ".env")
    repository = DataRepository(data_dir)
    trace = TraceWriter(trace_path)
    trace.reset()
    coordinator = Coordinator(repository, trace)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[tuple[Path, dict]] = []
    failures: list[str] = []
    for case_path in case_files:
        try:
            case = json.loads(case_path.read_text(encoding="utf-8"))
            generated.append((case_path, coordinator.process(case)))
        except Exception as exc:
            failures.append(f"{case_path.name}: {exc}")
            trace.write(case_path.stem, "coordinator_agent", "case_failed", {"error": str(exc)})
    if failures:
        raise RuntimeError("Pipeline refused to fabricate failed cases:\n" + "\n".join(failures))
    if use_llm:
        review_agent = GroqStrictPolicyReviewAgent(client=review_client)
        reviews = review_agent.review_batch([document for _, document in generated], repository)
        for review in reviews:
            trace.write(review["case_id"], review_agent.name, "review_agreed", {
                "model": review_agent.model_name,
                "primary_issue": review["primary_issue"],
                "cause_code": review["cause_code"],
            })
    for case_path, result in generated:
        destination = output_dir / case_path.name
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
    return len(case_files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EC_POLICY_V2 over Olist dispute cases")
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    parser.add_argument("--input", type=Path, default=INPUT_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--trace", type=Path, default=TRACE_PATH)
    parser.add_argument("--use-llm", action="store_true", help="Review policy results with Groq Llama 3.1 8B")
    args = parser.parse_args()
    try:
        count = run_pipeline(args.data, args.input, args.output, args.trace, use_llm=args.use_llm)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    mode = "Groq Llama-reviewed" if args.use_llm else "deterministic"
    print(f"Successfully generated and verified {count} case outputs ({mode} mode).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
