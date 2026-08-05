from __future__ import annotations

import time

from src.agents.groq_policy_review import GroqPolicyReviewAgent
from src.repository import DataRepository


class GroqStrictPolicyReviewAgent(GroqPolicyReviewAgent):
    """Use smaller chunks and validate every chunk before continuing."""

    chunk_size = 8

    def review_batch(self, outputs: list[dict], repository: DataRepository) -> list[dict]:
        all_reviews: list[dict] = []
        for offset in range(0, len(outputs), self.chunk_size):
            if offset:
                time.sleep(self.inter_chunk_delay_seconds)
            documents = outputs[offset:offset + self.chunk_size]
            facts = [self._build_case_facts(document, repository) for document in documents]
            reviews = self._request_chunk(facts)
            self._verify_batch(reviews, documents)
            all_reviews.extend(reviews)
        self._verify_batch(all_reviews, outputs)
        return all_reviews

