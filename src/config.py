from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
INPUT_DIR = ROOT_DIR / "input"
OUTPUT_DIR = ROOT_DIR / "output"
TRACE_PATH = ROOT_DIR / "trace.jsonl"

POLICY_VERSION = "EC_POLICY_V2"
MODEL_NAME = "none-deterministic-policy-engine"
MODEL_PARAMETER_SIZE = 0

MAX_ITEMS = 5
MAX_SELLERS = 3
MAX_PAYMENTS = 5
MAX_RELATED_ORDERS = 5
MAX_PRODUCTS = 5
MAX_CATEGORIES = 5
MAX_EVIDENCE = 20
MAX_ACTIONS = 5

