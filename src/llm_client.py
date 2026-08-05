"""
LLM API Client module for OpenAI gpt-4o-mini.
Reads OPENAI_API_KEY from .env per competition rules.
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
        self._load_dotenv()
        self.api_key = (
            os.getenv("GROQ_API_KEY") or 
            os.getenv("LLM_API_KEY") or 
            os.getenv("OPENAI_API_KEY") or 
            ""
        )
        self.base_url = (
            os.getenv("LLM_BASE_URL") or 
            (
                "https://api.groq.com/openai/v1"
                if "llama" in model_name.lower()
                else "https://api.openai.com/v1"
            )
        )

    def _load_dotenv(self):
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip("'\"")

    def call_agent(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Sends an HTTP POST request to OpenAI API chat completions.
        """
        if not self.api_key:
            return None

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[LLMClient Warning] API call to {self.model_name} failed: {e}. Falling back to Policy Engine.")
            return None
