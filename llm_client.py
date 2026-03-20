import os
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # "ollama" or "hf"
HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")


def chat(prompt: str, system: str = "You are a helpful assistant.", temperature: float = 0) -> str:
    """
    Unified LLM interface — routes to Ollama or HuggingFace based on LLM_PROVIDER env var.
    Returns raw string response.
    """
    if PROVIDER == "hf":
        from huggingface_hub import InferenceClient
        client = InferenceClient(model=HF_MODEL, token=HF_TOKEN)
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=temperature
        )
        return response.choices[0].message.content.strip()

    else:
        import ollama
        response = ollama.chat(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperature}
        )
        return response.message.content.strip()
