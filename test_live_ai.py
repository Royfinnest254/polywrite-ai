
import httpx
import asyncio
import json
from generate_token import generate_test_token

async def test_live():
    # Read valid token from file
    with open("valid_token.txt", "r") as f:
        token = f.read().strip()
    url = "http://127.0.0.1:8000/api/rewrite"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "selected_text": "the ai is working i hope",
        "intent": "humanize"
    }
    
    # Increase timeout for AI models
    timeout = httpx.Timeout(30.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            print("Sending request...")
            response = await client.post(url, json=payload, headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("Response Body:")
                print(json.dumps(response.json(), indent=2))
            else:
                print("Error Body:")
                print(response.text)
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_live())
