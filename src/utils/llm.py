"""
LLM Wrapper for SiliconFlow API (Qwen3.5-9B)
"""

from langchain_openai import ChatOpenAI
from src.utils.config import (
    SILICONFLOW_API_KEY,
    SILICONFLOW_BASE_URL,
    MODEL_NAME,
    MODEL_TEMPERATURE,
    MODEL_MAX_TOKENS
)


def get_llm(temperature=None, max_tokens=None):
    """
    Get LLM instance configured for SiliconFlow API
    
    Args:
        temperature: Override default temperature
        max_tokens: Override default max_tokens
    
    Returns:
        ChatOpenAI instance configured for Qwen3.5-9B
    """
    return ChatOpenAI(
        model=MODEL_NAME,
        api_key=SILICONFLOW_API_KEY,
        base_url=SILICONFLOW_BASE_URL,
        temperature=temperature or MODEL_TEMPERATURE,
        max_tokens=max_tokens or MODEL_MAX_TOKENS,
    )


# Global LLM instance
llm = get_llm()


if __name__ == "__main__":
    # Test LLM connection
    print("Testing LLM connection...")
    test_llm = get_llm()
    response = test_llm.invoke("Hello! Please respond with 'OK' if you can read this.")
    print(f"✅ LLM Response: {response.content}")
