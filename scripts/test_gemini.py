import os
import requests

key = os.getenv("GROQ_API_KEY", "")
print(f"Key starts with: {key[:10]}...")

url = "https://api.groq.com/openai/v1/chat/completions"
response = requests.post(url,
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    json={
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": "Say hello in one sentence."}],
        "temperature": 0.1
    },
    timeout=30
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
