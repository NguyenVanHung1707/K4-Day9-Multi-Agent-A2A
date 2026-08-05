import os
import time
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from groq import Groq, RateLimitError

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class LLMClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GROQ_API_KEY
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set in environment or .env file.")
        self.client = Groq(api_key=self.api_key)

    def chat_completion(
        self,
        messages: list,
        model: str = "llama-3.1-8b-instant",
        temperature: float = 0.1,
        json_object: bool = True,
        max_retries: int = 5
    ) -> str:
        """
        Executes a chat completion via Groq API with automatic rate-limit retry logic.
        """
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_object:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(**kwargs)
                # Polite delay to respect Groq 30 RPM limit
                time.sleep(2.1)
                return response.choices[0].message.content
            except RateLimitError as e:
                wait_time = 3.0 * (attempt + 1)
                print(f"[RateLimit 429] Waiting {wait_time}s before retry {attempt+1}/{max_retries}...")
                time.sleep(wait_time)
            except Exception as e:
                print(f"[Groq API Call Warning] {e}")
                time.sleep(2.0)
                if attempt == max_retries - 1:
                    raise e
        raise RuntimeError("Max retries exceeded for Groq API call.")

    def call_policy_agent_llm(self, prompt: str) -> str:
        """
        Policy Agent reasoning using llama-3.1-8b-instant.
        """
        messages = [
            {
                "role": "system",
                "content": "You are the Policy Agent for Olist E-commerce Dispute Resolution under EC_POLICY_V2. Output strict JSON."
            },
            {"role": "user", "content": prompt}
        ]
        return self.chat_completion(messages=messages, model="llama-3.1-8b-instant", temperature=0.1, json_object=True)

    def call_domain_agent_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Domain Agent JSON extraction/structuring using llama-3.1-8b-instant.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self.chat_completion(messages=messages, model="llama-3.1-8b-instant", temperature=0.1, json_object=True)
