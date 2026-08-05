# Multi-Agent Architecture for EC Dispute Resolution

> **Student:** Pham Tuan Anh  
> **Branch:** phamtuananh  
> **Framework:** LangGraph + SQLite + Deterministic Policy Engine

---

## 🏗️ Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    INPUT: EC_XXX.json                        │
│             { case_id, claimed_order_id }                    │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│               COORDINATOR (LangGraph Orchestrator)           │
│  - Parse input case                                          │
│  - Orchestrate parallel domain agents                        │
│  - Aggregate results into shared state                       │
└──────────────────────────┬───────────────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
       ▼                   ▼                   ▼
┌────────────┐      ┌────────────┐      ┌────────────┐
│  CUSTOMER  │      │   ORDER    │      │  PAYMENT   │
│   AGENT    │      │   AGENT    │      │   AGENT    │
└─────┬──────┘      └─────┬──────┘      └─────┬──────┘
      │                   │                   │
      │ customer_         │ affected_         │ payment_
      │ context           │ entities +        │ reconciliation
      │                   │ product_context   │
      └───────────────────┼───────────────────┘
                          │
                          ▼
                   ┌────────────┐
                   │  DELIVERY  │
                   │   AGENT    │
                   └─────┬──────┘
                         │ delivery_analysis
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│            SQL GENERATOR + SANDBOX (with Self-Correction)    │
│  - Generate SQL using Few-Shot examples                      │
│  - Execute in SQLite with error handling                     │
│  - Self-correction loop (max 3 retries)                      │
└──────────────────────────┬───────────────────────────────────┘
                           │ validated data
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              POLICY ENGINE (Deterministic Rules)             │
│  - Apply EC_POLICY_V2 (priority order 1-6)                   │
│  - Detect secondary issues (5 rules)                         │
│  - Calculate refund (Python, not LLM)                        │
│  - Generate evidence IDs + validate against DB               │
│  - Build resolution actions                                  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              VERIFIER & FORMATTER                            │
│  - Validate schema compliance                                │
│  - Check array limits (≤5 orders, ≤3 sellers)                │
│  - Verify evidence IDs exist in DB                           │
│  - Ensure 2 decimal places for numbers                       │
│  - Format final JSON output                                  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
                  OUTPUT: EC_XXX.json
             (10 sections with validated data)
```

---

## 🤖 Agent Roles & Responsibilities

| Agent | Role | Input | Output | Data Access |
|---|---|---|---|---|
| **Coordinator** | Orchestrator | Case JSON | Aggregated state | State management |
| **Customer Agent** | Customer lookup | order_id | `customer_context` | `customers`, `orders` |
| **Order Agent** | Order details | order_id | `affected_entities`, `product_context` | `orders`, `order_items`, `products`, `category_translation` |
| **Payment Agent** | Payment reconciliation | order_id | `payment_reconciliation`, `payment_ids` | `order_payments`, `order_items` |
| **Delivery Agent** | Delivery analysis | order_id | `delivery_analysis` | `orders`, `order_items` |
| **SQL Generator** | Query generation | Data request | SQL query | Few-Shot examples |
| **DB Sandbox** | Query execution | SQL query | DataFrame | SQLite database |
| **Policy Engine** | Rule application | Aggregated data | `case_assessment`, `root_cause_analysis`, `financial_resolution`, `resolution_actions`, `evidence_ids` | EC_POLICY_V2 rules |
| **Verifier** | Output validation | Full output | Validated JSON | Schema constraints |

---

## 🔄 Handoff Flow

```
1. Coordinator → Customer Agent
   Input: { order_id }
   Output: { customer_unique_id, related_order_ids }

2. Coordinator → Order Agent (parallel with Customer)
   Input: { order_id }
   Output: { order_ids, item_ids, seller_ids, product_ids, category_names }

3. Coordinator → Payment Agent (parallel)
   Input: { order_id }
   Output: { payment_reconciliation, payment_ids }

4. Coordinator → Delivery Agent (depends on Order Agent)
   Input: { order_id, items_data }
   Output: { delivery_analysis }

5. All Agents → SQL Generator (when needed)
   Input: { data_request, table_names }
   Output: { sql_query }
   ↓
   SQL Generator → DB Sandbox
   Input: { sql_query }
   Output: { dataframe } (or error → retry)

6. Coordinator → Policy Engine
   Input: { all_agent_outputs }
   Output: { primary_issue, secondary_issues, refund, actions, evidence }

7. Policy Engine → Verifier
   Input: { full_output }
   Output: { validated_json }
```

---

## 🔍 Key Design Decisions

### **1. Why SQLite instead of CSV?**
- **Speed:** Indexed queries (~0.1s per case vs ~5s with CSV)
- **Accuracy:** No fan-out problem with JOINs
- **SQL Intelligence:** LLM better at SQL than Pandas code

### **2. Why Deterministic Policy Engine?**
- **Zero hallucination:** Business rules executed in Python, not LLM
- **100% reproducible:** Same input → same output
- **Debuggable:** Clear logic flow

### **3. Why Self-Correction Loop?**
- **Resilience:** Auto-fix SQL syntax errors
- **Learning:** Few-Shot examples improve over time
- **Efficiency:** No manual intervention needed

### **4. Why Parallel Domain Agents?**
- **Speed:** Customer, Order, Payment agents run simultaneously
- **Modularity:** Each agent has clear scope
- **Testability:** Each agent can be tested independently

### **5. Why Evidence Validation?**
- **No false positives:** Every evidence_id must exist in DB
- **Traceability:** Can verify all claims in output

---

## 📊 Data Flow

### **Input Processing:**
```python
case_input = {
    "case_id": "EC_001",
    "claimed_order_id": "9b75cdaf2d85857ef023980e15d01546"
}
```

### **Shared State (LangGraph):**
```python
class CaseState(TypedDict):
    case_id: str
    order_id: str
    
    # From domain agents
    customer_data: Dict
    order_data: Dict
    payment_data: Dict
    delivery_data: Dict
    
    # From policy engine
    policy_result: Dict
    
    # Final output
    output_json: Dict
```

### **Agent Communication:**
- Each agent updates shared state
- Next agent reads from state
- No direct agent-to-agent communication
- All communication via state transitions

---

## 🛠️ Technology Stack

| Component | Technology | Version/Config |
|---|---|---|
| **LLM** | Gemini 1.5 Flash | < 10B params |
| **Orchestration** | LangGraph | StateGraph |
| **Database** | SQLite | olist.db (144 MB) |
| **Data Processing** | Pandas | 2.0+ |
| **Schema Validation** | Pydantic | 2.0+ |
| **SQL Generation** | LangChain SQL Agent | Few-Shot prompting |
| **Logging** | Custom | trace.jsonl (LangSmith format) |

---

## 📦 File Structure

```
src/
├── agents/
│   ├── coordinator.py          # Main orchestrator (LangGraph)
│   ├── customer_agent.py       # Customer context
│   ├── order_agent.py          # Order & product
│   ├── payment_agent.py        # Payment reconciliation
│   ├── delivery_agent.py       # Delivery analysis
│   ├── sql_generator.py        # SQL generation with Few-Shot
│   └── policy_engine.py        # EC_POLICY_V2 rules (Python)
├── data_processing/
│   ├── csv_to_sqlite.py        # CSV → SQLite converter
│   └── db_helper.py            # Database query helpers
├── validators/
│   ├── schema_validator.py     # Output schema validation
│   └── evidence_validator.py   # Evidence ID verification
├── models/
│   ├── case_model.py           # Pydantic models
│   └── output_schema.py        # Output JSON schema
└── utils/
    ├── logger.py               # trace.jsonl logging
    └── config.py               # Configuration
```

---

## 🎯 Quality Assurance

### **Validation Layers:**
1. **SQL Validation:** Sandbox catches syntax errors → auto-retry
2. **Data Validation:** Check NULL, empty results
3. **Business Logic Validation:** Policy engine follows EC_POLICY_V2 exactly
4. **Schema Validation:** Check array limits, decimal places
5. **Evidence Validation:** Verify all IDs exist in DB

### **Error Handling:**
- SQL errors: Retry up to 3 times with error feedback
- Missing data: Return NULL/empty arrays (per spec)
- Schema violations: Log warning + fix before output
- Unmatched policy: Default to "no_action" status

---

## 📈 Expected Performance

| Metric | Target | Actual (after testing) |
|---|---|---|
| **Processing time per case** | ~10-15s | TBD |
| **Total time (50 cases)** | ~10 min | TBD |
| **Accuracy** | > 95% | TBD |
| **Schema compliance** | 100% | TBD |
| **Evidence validation** | 100% | TBD |

---

## 🔍 Trace & Logging

**trace.jsonl format:**
```json
{
  "timestamp": "2026-08-05T15:30:00Z",
  "case_id": "EC_001",
  "agent": "customer_agent",
  "action": "query_customer",
  "input": {"order_id": "9b75cdaf..."},
  "output": {"customer_unique_id": "861eff..."},
  "duration_ms": 120
}
```

**metadata.json:**
```json
{
  "model": "gemini-1.5-flash",
  "parameter_size": "< 10B",
  "framework": "LangGraph + SQLite",
  "runtime": "Python 3.11",
  "total_cases": 50,
  "total_duration_seconds": 600,
  "avg_case_duration_seconds": 12
}
```

---

## 🚀 Running the System

```bash
# 1. Setup environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Prepare database (already done)
python src/data_processing/csv_to_sqlite.py

# 3. Run all 50 cases
python main.py

# 4. Verify outputs
python verify_outputs.py

# 5. Generate submission zip
python prepare_submission.py
```

---

**Architecture designed by:** Pham Tuan Anh  
**Date:** 2026-08-05  
**Branch:** phamtuananh
