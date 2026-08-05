"""
Coordinator Agent — nhận 1 case, dispatch cho các agent theo DAG, Router theo
order_status (bo qua Delivery Agent cho canceled/unavailable), goi Policy
Agent, chay Verifier (co auto-trim + 1 lan fix), ghi trace.

Kien truc DAG (xem architecture.md):
  Customer Agent  ---\
  Order&Product   ----> Router(order_status) --> Payment/Delivery --> Policy --> Verifier
"""
from __future__ import annotations
import time
from data_loader import OlistData
from agents import customer_agent, order_product_agent, payment_agent, delivery_agent
import policy_engine
import verifier as verifier_mod
import llm_client

MAX_ORDER_IDS = 5
MAX_ITEM_IDS = 5
MAX_SELLER_IDS_AE = 3
MAX_PAYMENT_IDS = 5
MAX_EVIDENCE = 20


def _order_status_needs_delivery(order_status: str) -> bool:
    """Router: chi goi Delivery Agent khi order da delivered.
    canceled/unavailable gan nhu chac chan khong co delivered_customer_date
    (kiem chung tren toan dataset Olist: 6/1234)."""
    return order_status == "delivered"


def process_case(case: dict, data: OlistData, call_llm: bool = True) -> dict:
    """
    Chay toan bo pipeline cho 1 case. Tra ve:
      { "case_id", "status": "OK"|"FAILED", "output": {...}|None, "trace": {...} }
    """
    t0 = time.time()
    case_id = case["case_id"]
    order_id = case["customer_request"]["claimed_order_id"]
    customer_message = case["customer_request"].get("message", "")

    trace = {"case_id": case_id, "order_id": order_id, "agent_calls": [], "errors": [], "fixes": []}

    order_row = data.get_order(order_id)
    if order_row is None:
        trace["errors"].append(f"order_id khong ton tai trong orders.csv: {order_id}")
        trace["latency_ms"] = round((time.time() - t0) * 1000, 1)
        return {"case_id": case_id, "status": "FAILED", "output": None, "trace": trace}

    order_status = order_row.order_status

    # --- Fan-out: Customer Agent + Order&Product Agent ---
    t = time.time()
    cust = customer_agent.run(data, order_id, order_row)
    trace["agent_calls"].append({"agent": "customer_agent", "ms": round((time.time() - t) * 1000, 1)})

    t = time.time()
    op = order_product_agent.run(data, order_id)
    trace["agent_calls"].append({"agent": "order_product_agent", "ms": round((time.time() - t) * 1000, 1)})

    # --- Payment Agent (luon chay) ---
    t = time.time()
    pay = payment_agent.run(data, order_id, op["item_total_brl"], op["freight_total_brl"], op["has_items"])
    trace["agent_calls"].append({"agent": "payment_agent", "ms": round((time.time() - t) * 1000, 1)})

    # --- Router: Delivery Agent chi chay khi delivered ---
    needs_delivery = _order_status_needs_delivery(order_status)
    trace["router_decision"] = {"order_status": order_status, "delivery_agent_invoked": needs_delivery}
    t = time.time()
    if needs_delivery:
        deliv = delivery_agent.run(data, order_id, order_row, op["items_df"])
        trace["agent_calls"].append({"agent": "delivery_agent", "ms": round((time.time() - t) * 1000, 1)})
    else:
        deliv = delivery_agent.skipped_result()
        trace["agent_calls"].append({"agent": "delivery_agent", "ms": 0, "skipped": True,
                                      "reason": "order_status not delivered (Router optimization)"})

    # --- Policy Agent (rule engine) ---
    secondary_flags = {**cust["secondary_flags"], **op["secondary_flags"], **pay["secondary_flags"]}
    secondary_issues = policy_engine.build_secondary_issues(secondary_flags)

    primary_issue, root_cause_code = policy_engine.determine_primary_issue(
        order_status=order_status,
        payment_total=pay["payment_total_brl"],
        is_late=deliv["is_late"],
        late_handoff_seller_ids=deliv["late_handoff_seller_ids"],
        split_payment=secondary_flags.get("split_payment", False),
        reconciled=pay["payment_reconciliation"]["reconciled"],
    )
    is_fallback = (
        order_status == "delivered" and not deliv["is_late"]
        and not (secondary_flags.get("split_payment") and pay["payment_reconciliation"]["reconciled"])
        and not pay["payment_reconciliation"]["reconciled"]
    )

    case_assessment = policy_engine.build_case_assessment(primary_issue, secondary_issues, is_fallback)
    root_cause_analysis, financial_resolution = policy_engine.build_root_cause_and_financial(
        primary_issue, root_cause_code, pay["payment_total_brl"], op["freight_total_brl"],
        deliv["late_handoff_seller_ids"],
    )
    resolution_actions = policy_engine.build_actions(
        primary_issue, case_assessment["case_status"], secondary_issues,
    )
    trace["agent_calls"].append({"agent": "policy_agent", "primary_issue": primary_issue,
                                  "root_cause": root_cause_code, "is_fallback": is_fallback})

    # --- Affected entities / evidence ids ---
    responsible_seller_ids = [p["party_id"] for p in root_cause_analysis["responsible_parties"]
                               if p["party_type"] == "seller"]

    # item_ids/payment_ids da co dang "<order_id>:<n>", chi can them prefix loai evidence
    evidence_ids = [f"order:{order_id}"]
    evidence_ids += [f"item:{iid}" for iid in op["item_ids"]]
    evidence_ids += [f"payment:{pid}" for pid in pay["payment_ids"]]
    evidence_ids += [f"seller:{sid}" for sid in responsible_seller_ids]
    evidence_ids += [f"policy:{root_cause_code}"]
    evidence_ids = evidence_ids[:MAX_EVIDENCE]

    output = {
        "case_id": case_id,
        "case_assessment": case_assessment,
        "affected_entities": {
            "order_ids": [order_id][:MAX_ORDER_IDS],
            "item_ids": op["item_ids"][:MAX_ITEM_IDS],
            "seller_ids": op["seller_ids"][:MAX_SELLER_IDS_AE],
            "payment_ids": pay["payment_ids"][:MAX_PAYMENT_IDS],
        },
        "customer_context": cust["customer_context"],
        "product_context": {
            "product_ids": op["product_ids"],
            "category_names": op["category_names"],
        },
        "delivery_analysis": deliv["delivery_analysis"],
        "payment_reconciliation": pay["payment_reconciliation"],
        "root_cause_analysis": root_cause_analysis,
        "evidence_ids": evidence_ids,
        "financial_resolution": financial_resolution,
        "resolution_actions": resolution_actions,
    }

    # --- Verifier Agent (co auto-trim 1 lan = vong Evaluator-Optimizer) ---
    valid_order_ids = {order_id}
    valid_item_ids = {iid for iid in op["item_ids"]}
    valid_payment_ids = {pid for pid in pay["payment_ids"]}
    valid_seller_ids = set(op["seller_ids"]) | set(responsible_seller_ids)

    ok, errors = verifier_mod.verify(output, valid_order_ids, valid_item_ids, valid_payment_ids, valid_seller_ids)
    if not ok:
        fixes = verifier_mod.auto_trim(output)
        trace["fixes"] = fixes
        ok, errors = verifier_mod.verify(output, valid_order_ids, valid_item_ids, valid_payment_ids, valid_seller_ids)

    trace["agent_calls"].append({"agent": "verifier_agent", "ok": ok, "errors": errors})

    # --- LLM call (Gemma-2-9B-It qua Gemini API) — chi de sinh dien giai,
    # KHONG anh huong toi output.json (schema co dinh) ---
    if call_llm:
        evidence_digest = {
            "primary_issue": primary_issue,
            "case_status": case_assessment["case_status"],
            "refund_brl": financial_resolution["recommended_refund_brl"],
        }
        llm_result = llm_client.summarize_case(case_id, customer_message, evidence_digest)
        trace["llm_call"] = llm_result

    trace["latency_ms"] = round((time.time() - t0) * 1000, 1)

    if not ok:
        trace["errors"] = errors
        return {"case_id": case_id, "status": "FAILED", "output": output, "trace": trace}

    return {"case_id": case_id, "status": "OK", "output": output, "trace": trace}
