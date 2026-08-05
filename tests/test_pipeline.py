from __future__ import annotations

import json
import unittest
from copy import deepcopy
from decimal import Decimal

from src.agents.policy import PolicyAgent
from src.agents.verifier import VerificationError, VerifierAgent
from src.config import DATA_DIR, INPUT_DIR, OUTPUT_DIR, TRACE_PATH
from src.main import run_pipeline
from src.repository import DataRepository
from src.utils import money, stable_unique, variance_hours


class UtilityTests(unittest.TestCase):
    def test_stable_unique_preserves_order(self):
        self.assertEqual(stable_unique(["b", "a", "b", "c"]), ["b", "a", "c"])

    def test_money_rounding(self):
        self.assertEqual(money(Decimal("1.235")), 1.24)

    def test_variance_hours(self):
        self.assertEqual(variance_hours("2018-01-02 01:30:00", "2018-01-01 00:00:00"), 25.5)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.agent = PolicyAgent()
        self.customer = {"repeat_customer": False}
        self.order = {"order": {"order_id": "o1", "order_status": "delivered"}, "item_count": 1,
                      "seller_count": 1, "category_count": 1, "freight_total_brl": 12.5}
        self.payment = {"payment_total_brl": 100.0, "payment_count": 1, "reconciled": True}

    def test_canceled_has_priority(self):
        self.order["order"]["order_status"] = "canceled"
        self.payment["payment_count"] = 2
        result = self.agent.run(self.order, self.customer, self.payment,
                                {"delivery_variance_hours": 50.0, "late_handoff_seller_ids": ["s1"]})
        self.assertEqual(result["primary_issue"], "canceled_order_paid")
        self.assertEqual(result["recommended_refund_brl"], 100.0)

    def test_late_seller_refunds_freight(self):
        result = self.agent.run(self.order, self.customer, self.payment,
                                {"delivery_variance_hours": 3.0, "late_handoff_seller_ids": ["s1"]})
        self.assertEqual(result["primary_issue"], "late_delivery_seller")
        self.assertEqual(result["recommended_refund_brl"], 12.5)

    def test_unmatched_case_is_rejected(self):
        self.payment["reconciled"] = False
        with self.assertRaisesRegex(ValueError, "refusing to invent"):
            self.agent.run(self.order, self.customer, self.payment,
                           {"delivery_variance_hours": -1.0, "late_handoff_seller_ids": []})


class EndToEndTests(unittest.TestCase):
    def test_all_published_inputs_generate_verified_json(self):
        inputs = sorted(INPUT_DIR.glob("EC_*.json"))
        if not inputs:
            self.skipTest("Competition inputs have not been published")
        count = run_pipeline(DATA_DIR, INPUT_DIR, OUTPUT_DIR, TRACE_PATH)
        self.assertEqual(count, len(inputs))
        outputs = sorted(OUTPUT_DIR.glob("EC_*.json"))
        self.assertEqual(len(outputs), len(inputs))
        for path in outputs:
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["case_id"], path.stem)

    def test_verifier_rejects_action_or_evidence_tampering(self):
        run_pipeline(DATA_DIR, INPUT_DIR, OUTPUT_DIR, TRACE_PATH)
        case = json.loads((INPUT_DIR / "EC_002.json").read_text(encoding="utf-8"))
        document = json.loads((OUTPUT_DIR / "EC_002.json").read_text(encoding="utf-8"))
        verifier = VerifierAgent(DataRepository(DATA_DIR))

        bad_actions = deepcopy(document)
        bad_actions["resolution_actions"] = list(reversed(bad_actions["resolution_actions"]))
        with self.assertRaisesRegex(VerificationError, "resolution_actions"):
            verifier.verify(case, bad_actions)

        bad_evidence = deepcopy(document)
        bad_evidence["evidence_ids"].pop()
        with self.assertRaisesRegex(VerificationError, "evidence_ids"):
            verifier.verify(case, bad_evidence)


if __name__ == "__main__":
    unittest.main()
