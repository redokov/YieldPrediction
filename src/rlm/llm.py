import os
import litellm
from dotenv import load_dotenv
from typing import Any, Dict

load_dotenv()

def get_llm_client():
    """Возвращает настроенный клиент LiteLLM для OpenRouter + Qwen"""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "sk-or-...":
        raise ValueError(
            "OPENROUTER_API_KEY не настроен. "
            "Пожалуйста, укажите ключ в .env или в переменных окружения."
        )
    
    litellm.api_key = api_key
    litellm.api_base = "https://openrouter.ai/api/v1"
    
    return litellm

def call_llm(
    prompt: str,
    system_prompt: str = "Ты полезный агрономический помощник.",
    model: str = None,
    temperature: float = 0.3,
    **kwargs
) -> str:
    """
    Вызов LLM через OpenRouter (модель Qwen3-70B или указанная)
    """
    client = get_llm_client()
    model_name = model or os.getenv("LITELLM_MODEL", "openrouter/qwen/qwen3-70b")
    
    response = client.completion(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        **kwargs
    )
    
    return response.choices[0].message.content.strip()
