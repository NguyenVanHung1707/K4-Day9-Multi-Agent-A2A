import json
import glob
from src.data_engine import DataEngine

de = DataEngine()
input_files = sorted(glob.glob("input/EC_*.json"))

for fpath in input_files:
    case = json.load(open(fpath, encoding="utf-8"))
    cid = case["case_id"]
    oid = case["customer_request"]["claimed_order_id"]
    cdata = de.analyze_case(oid)
    order = cdata["order"]
    recon = cdata["payment_reconciliation"]
    deliv = cdata["delivery_analysis"]
    items = cdata["items"]
    payments = cdata["payments"]
    
    print(f"{cid} | Order: {oid[:8]} | Status: {order.get('order_status')} | Items: {len(items)} | Pay: {len(payments)} | Rec: {recon.get('reconciled')} | Diff: {recon.get('difference_brl')} | DelivVar: {deliv.get('delivery_variance_hours')} | LateSellers: {deliv.get('late_handoff_seller_ids')}")
