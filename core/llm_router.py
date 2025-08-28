import os, requests

def llm_complete(prompt: str) -> str:
    base = os.getenv("MODEL_ROUTER_URL", "").rstrip("/")
    if not base:
        return "MODEL_ROUTER_URL not set – skipping."
    url = base + "/chat/completions"
    model = os.getenv("MODEL_NAME", "gpt-llmstudio-ensemble")
    headers = {}
    if os.getenv("LLM_API_KEY"):
        headers["Authorization"] = f"Bearer {os.getenv('LLM_API_KEY')}"
    payload = {
        "model": model,
        "messages": [
            {"role":"system","content":"You are a trading assistant."},
            {"role":"user","content": prompt},
        ],
        "temperature": 0.2,
    }
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
