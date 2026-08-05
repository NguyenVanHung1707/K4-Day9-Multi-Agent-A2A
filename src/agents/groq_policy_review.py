from __future__ import annotations

import json

from src.agents.groq_review import GroqReviewAgent, GroqReviewError


class GroqPolicyReviewAgent(GroqReviewAgent):
    """Groq reviewer with the complete EC_POLICY_V2 contract in its system prompt."""

    def _request_chunk(self, facts: list[dict]) -> list[dict]:
        instructions = (
            "You are the independent Policy Review Agent for EC_POLICY_V2. Use only supplied JSON facts. "
            "Apply these rules in exact first-match order: "
            "1 canceled_order_paid if order_status=canceled and payment_total_brl>0; cause "
            "ORDER_CANCELED_AFTER_PAYMENT; responsible_party_ids=[OLIST_PLATFORM]; refund=payment_total_brl. "
            "2 unavailable_order_paid if order_status=unavailable and payment_total_brl>0; cause "
            "ORDER_UNAVAILABLE_AFTER_PAYMENT; responsible_party_ids=[OLIST_PLATFORM]; refund=payment_total_brl. "
            "3 late_delivery_seller if delivery_variance_hours>0 and late_handoff_seller_ids non-empty; cause "
            "SELLER_HANDOFF_AFTER_LIMIT; responsible_party_ids exactly late_handoff_seller_ids; refund=freight_total_brl. "
            "4 late_delivery_logistics if delivery_variance_hours>0 and late_handoff_seller_ids empty; cause "
            "CARRIER_DELIVERED_AFTER_ESTIMATE; responsible_party_ids=[LOGISTICS_PROVIDER]; refund=freight_total_brl. "
            "5 valid_split_payment if payment_count>=2 and reconciled=true; cause MULTIPLE_PAYMENTS_RECONCILED; "
            "responsible_party_ids=[]; refund=0. "
            "6 unsupported_late_claim if delivery_variance_hours<=0 and reconciled=true; cause "
            "DELIVERY_WITHIN_ESTIMATE; responsible_party_ids=[]; refund=0. "
            "Never invent IDs, money, timestamps, or events. Return compact JSON with a reviews array and "
            "exactly one review per case. Every review contains case_id, agrees, primary_issue, cause_code, "
            "responsible_party_ids, recommended_refund_brl. agrees is true only if candidate matches all rules."
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

