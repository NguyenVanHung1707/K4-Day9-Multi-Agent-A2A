"""
Configuration for EC Dispute Resolution System
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# SiliconFlow API Configuration
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
SILICONFLOW_BASE_URL = "https://api.siliconflow.com/v1"
MODEL_NAME = "Qwen/Qwen3.5-9B"

# Database Configuration
DB_PATH = "olist.db"
DATA_FOLDER = "data"

# Input/Output Configuration
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
LOGGING_FOLDER = "logging"

# Model Parameters
MODEL_TEMPERATURE = 0.1  # Low temperature for deterministic output
MODEL_MAX_TOKENS = 4096

# Agent Configuration
MAX_SQL_RETRIES = 3
SQL_TIMEOUT_SECONDS = 30

# Schema Constraints
MAX_ORDER_IDS = 5
MAX_ITEM_IDS = 5
MAX_SELLER_IDS = 3
MAX_PAYMENT_IDS = 5
MAX_RELATED_ORDER_IDS = 5
MAX_PRODUCT_IDS = 5
MAX_CATEGORY_NAMES = 5
MAX_ROOT_CAUSES = 3
MAX_RESPONSIBLE_PARTIES = 3
MAX_EVIDENCE_IDS = 20
MAX_ACTIONS = 5

# Policy Configuration
PAYMENT_RECONCILIATION_TOLERANCE = 0.10  # BRL
DECIMAL_PLACES = 2

# Logging
ENABLE_TRACE_LOGGING = True
TRACE_FILE = "logging/trace.jsonl"
METADATA_FILE = "logging/metadata.json"

# Validate configuration
if not SILICONFLOW_API_KEY:
    raise ValueError("SILICONFLOW_API_KEY not found in .env file")

print(f"✅ Configuration loaded:")
print(f"   Model: {MODEL_NAME}")
print(f"   Base URL: {SILICONFLOW_BASE_URL}")
print(f"   Database: {DB_PATH}")
