from ollama import Client

from src.config import OLLAMA_LOCAL_HOST, LLM_MODEL

client = Client(
    host = OLLAMA_LOCAL_HOST
)

response = client.chat(
    model=LLM_MODEL,
    messages=[
        {"role": "user", "content": "What is the capital of France?"}
    ]
)

print(response['message']['content'])