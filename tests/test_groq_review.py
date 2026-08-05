from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from src.agents.groq_review import GroqReviewAgent, GroqReviewError
from src.config import MODEL_NAME


class FakeCompletions:
    def __init__(self, document: dict):
        self.document = document
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=json.dumps(self.document))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    def __init__(self, document: dict):
        self.chat = SimpleNamespace(completions=FakeCompletions(document))


class FakeRepository:
    items_by_order = {"order-1": [{"seller_id": "seller-1"}]}
    payments_by_order = {"order-1": [{"payment_sequential": "1"}]}

    @staticmethod
    def require_order(order_id: str):
        return {"order_id": order_id, "order_status": "canceled"}


def sample_output() -> dict:
    return {
        "case_id": "EC_TEST",
        "case_assessment": {"primary_issue": "canceled_order_paid"},
        "affected_entities": {"order_ids": ["order-1"]},
        "delivery_analysis": {"delivery_variance_hours": None, "late_handoff_seller_ids": []},
        "payment_reconciliation": {
            "payment_total_brl": 100.0, "freight_total_brl": 10.0,
            "difference_brl": 0.0, "reconciled": True,
        },
        "root_cause_analysis": {
            "ranked_causes": [{"cause_code": "ORDER_CANCELED_AFTER_PAYMENT", "rank": 1}],
            "responsible_parties": [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
        },
        "financial_resolution": {"recommended_refund_brl": 100.0},
    }


class GroqBatchReviewTests(unittest.TestCase):
    def test_agreeing_batch_review_passes(self):
        response = {"reviews": [{
            "case_id": "EC_TEST", "agrees": True,
            "primary_issue": "canceled_order_paid", "cause_code": "ORDER_CANCELED_AFTER_PAYMENT",
            "responsible_party_ids": ["OLIST_PLATFORM"], "recommended_refund_brl": 100.0,
        }]}
        client = FakeClient(response)
        agent = GroqReviewAgent(client=client)
        reviews = agent.review_batch([sample_output()], FakeRepository())
        self.assertEqual(reviews[0]["case_id"], "EC_TEST")
        call = client.chat.completions.calls[0]
        self.assertEqual(call["model"], MODEL_NAME)
        self.assertEqual(call["response_format"], {"type": "json_object"})

    def test_conflicting_batch_review_fails_closed(self):
        response = {"reviews": [{
            "case_id": "EC_TEST", "agrees": False,
            "primary_issue": "valid_split_payment", "cause_code": "MULTIPLE_PAYMENTS_RECONCILED",
            "responsible_party_ids": [], "recommended_refund_brl": 0.0,
        }]}
        agent = GroqReviewAgent(client=FakeClient(response))
        with self.assertRaisesRegex(GroqReviewError, "policy conflict"):
            agent.review_batch([sample_output()], FakeRepository())


if __name__ == "__main__":
    unittest.main()

