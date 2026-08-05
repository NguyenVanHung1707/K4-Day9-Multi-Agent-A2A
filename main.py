"""
Entry point — chay pipeline tren toan bo input/EC_*.json, case-level parallel
fan-out (ThreadPoolExecutor, IO-bound: pandas lookup nhe + goi LLM qua mang),
ghi output/EC_xxx.json va trace.jsonl (ghi de, khong append - dung yeu cau
README muc 8: "chi can luot chay moi nhat").

Chay: python main.py [--no-llm] [--workers N]
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from data_loader import get_data
import coordinator

BASE = Path(__file__).parent
INPUT_DIR = BASE / "input"
OUTPUT_DIR = BASE / "output"
TRACE_PATH = BASE / "trace.jsonl"


def load_cases() -> list[dict]:
    cases = []
    for f in sorted(INPUT_DIR.glob("EC_*.json")):
        cases.append(json.load(open(f, encoding="utf-8")))
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="Bo qua goi Gemini API (dry-run, dung khi khong co mang)")
    parser.add_argument("--workers", type=int, default=5, help="So case chay song song")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    data = get_data()
    cases = load_cases()
    if not cases:
        print(f"Khong tim thay input nao trong {INPUT_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"Chay {len(cases)} case, {args.workers} worker song song, LLM={'TAT' if args.no_llm else 'BAT'}")

    results = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(coordinator.process_case, c, data, not args.no_llm): c["case_id"] for c in cases}
        for fut in as_completed(futures):
            case_id = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"case_id": case_id, "status": "FAILED", "output": None,
                       "trace": {"case_id": case_id, "errors": [f"UNCAUGHT: {type(e).__name__}: {e}"]}}
            results.append(res)
            status_mark = "OK" if res["status"] == "OK" else "FAIL"
            print(f"  [{status_mark}] {case_id}")

    results.sort(key=lambda r: r["case_id"])

    ok_count = 0
    with open(TRACE_PATH, "w", encoding="utf-8") as trace_f:
        for res in results:
            if res["output"] is not None:
                out_path = OUTPUT_DIR / f"{res['case_id']}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(res["output"], f, ensure_ascii=False, indent=2)
                if res["status"] == "OK":
                    ok_count += 1
            trace_f.write(json.dumps(res["trace"], ensure_ascii=False) + "\n")

    elapsed = round(time.time() - t0, 2)
    print(f"\nXong: {ok_count}/{len(cases)} case OK, {elapsed}s. Output -> {OUTPUT_DIR}, trace -> {TRACE_PATH}")


if __name__ == "__main__":
    main()
