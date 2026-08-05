"""
LLM API Client module for Qwen/Qwen2.5-7B-Instruct.
Supports OpenAI-compatible API providers (OpenRouter, Groq, vLLM, Ollama, Together AI, etc.).
Reads API Key from .env per rule 4.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from src.config import MODEL_NAME

class LLMClient:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        self.base_url = os.getenv("LLM_BASE_URL") or "https://api.groq.com/openai/v1"

    def call_qwen_agent(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Sends an HTTP POST request to OpenAI-compatible LLM endpoint.
        """
        if not self.api_key and "localhost" not in self.base_url:
            # If no API key provided, return None to trigger safe deterministic fallback
            return None

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 1000
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            # Log error and fallback silently to policy engine
            print(f"[LLMClient Warning] API call to {self.model_name} failed: {e}. Falling back to Policy Engine.")
            return None
