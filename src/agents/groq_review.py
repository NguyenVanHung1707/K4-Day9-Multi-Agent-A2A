from __future__ import annotations

import json
import os
import time
from typing import Any

from src.config import MODEL_NAME
from src.repository import DataRepository
from src.utils import stable_unique


class GroqReviewError(ValueError):
    pass


class GroqReviewAgent:
    """Rate-limit-aware Groq reviewer that cannot modify deterministic output facts."""

    name = "groq_review_agent"
    chunk_size = 10
    inter_chunk_delay_seconds = 31

    def __init__(self, api_key: str | None = None, client: Any | None = None):
        self.model_name = MODEL_NAME
        if client is not None:
            self.client = client
            return
        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise GroqReviewError("GROQ_API_KEY is missing; add it to .env before using --use-llm")
        try:
            from groq import Groq
        except ImportError as exc:
            raise GroqReviewError("groq is not installed; run: pip install -r requirements.txt") from exc
        self.client = Groq(api_key=key)

    def review_batch(self, outputs: list[dict], repository: DataRepository) -> list[dict]:
        all_reviews: list[dict] = []
        for offset in range(0, len(outputs), self.chunk_size):
            if offset:
                time.sleep(self.inter_chunk_delay_seconds)
            documents = outputs[offset:offset + self.chunk_size]
            facts = [self._build_case_facts(document, repository) for document in documents]
            all_reviews.extend(self._request_chunk(facts))
        self._verify_batch(all_reviews, outputs)
        return all_reviews

    def _request_chunk(self, facts: list[dict]) -> list[dict]:
        instructions = (
            "You are the independent Policy Review Agent for EC_POLICY_V2. Audit every case using only "
            "the supplied JSON facts. Never invent IDs, money, timestamps, or events. Primary priority is: "
            "canceled_order_paid; unavailable_order_paid; late_delivery_seller; late_delivery_logistics; "
            "valid_split_payment; unsupported_late_claim. Refund equals payment total for canceled/unavailable, "
            "freight total for late delivery, otherwise zero. Return one JSON object with a reviews array and "
            "exactly one review per case. Each review must contain case_id, agrees, primary_issue, cause_code, "
            "responsible_party_ids, and recommended_refund_brl. Set agrees=true only when every candidate field "
            "is correct. Output compact JSON only."
        )
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps(facts, ensure_ascii=False, separators=(",", ":"))},
            ],
            temperature=0,
            seed=42,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(response.choices[0].message.content)["reviews"]
        except (AttributeError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise GroqReviewError("Groq returned invalid batch JSON") from exc

    @staticmethod
    def _build_case_facts(document: dict, repository: DataRepository) -> dict:
        order_id = document["affected_entities"]["order_ids"][0]
        order = repository.require_order(order_id)
        items = repository.items_by_order.get(order_id, [])
        payments = repository.payments_by_order.get(order_id, [])
        root = document["root_cause_analysis"]
        return {
            "case_id": document["case_id"],
            "order_status": order["order_status"],
            "item_count": len(items),
            "seller_count": len(stable_unique(row["seller_id"] for row in items)),
            "payment_count": len(payments),
            "payment_total_brl": document["payment_reconciliation"]["payment_total_brl"],
            "freight_total_brl": document["payment_reconciliation"]["freight_total_brl"],
            "difference_brl": document["payment_reconciliation"]["difference_brl"],
            "reconciled": document["payment_reconciliation"]["reconciled"],
            "delivery_variance_hours": document["delivery_analysis"]["delivery_variance_hours"],
            "late_handoff_seller_ids": document["delivery_analysis"]["late_handoff_seller_ids"],
            "candidate": {
                "primary_issue": document["case_assessment"]["primary_issue"],
                "cause_code": root["ranked_causes"][0]["cause_code"],
                "responsible_party_ids": [p["party_id"] for p in root["responsible_parties"]],
                "recommended_refund_brl": document["financial_resolution"]["recommended_refund_brl"],
            },
        }

    @staticmethod
    def _verify_batch(reviews: list[dict], outputs: list[dict]) -> None:
        expected = {document["case_id"]: document for document in outputs}
        if len(reviews) != len(expected):
            raise GroqReviewError(f"Groq returned {len(reviews)} reviews for {len(expected)} cases")
        seen = set()
        errors = []
        for review in reviews:
            case_id = review.get("case_id")
            if case_id in seen or case_id not in expected:
                errors.append(f"unexpected/duplicate case_id {case_id}")
                continue
            seen.add(case_id)
            document = expected[case_id]
            candidate = {
                "primary_issue": document["case_assessment"]["primary_issue"],
                "cause_code": document["root_cause_analysis"]["ranked_causes"][0]["cause_code"],
                "responsible_party_ids": [p["party_id"] for p in document["root_cause_analysis"]["responsible_parties"]],
                "recommended_refund_brl": document["financial_resolution"]["recommended_refund_brl"],
            }
            disagreeing = not review.get("agrees")
            disagreeing |= review.get("primary_issue") != candidate["primary_issue"]
            disagreeing |= review.get("cause_code") != candidate["cause_code"]
            disagreeing |= review.get("responsible_party_ids") != candidate["responsible_party_ids"]
            try:
                disagreeing |= abs(float(review.get("recommended_refund_brl")) - candidate["recommended_refund_brl"]) > 0.01
            except (TypeError, ValueError):
                disagreeing = True
            if disagreeing:
                errors.append(f"policy conflict in {case_id}")
        if errors:
            raise GroqReviewError("; ".join(errors))
