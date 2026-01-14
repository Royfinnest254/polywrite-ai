
import jwt
import datetime
from src.config import get_settings

def generate_test_token():
    settings = get_settings()
    
    # Payload matching what's expected by get_current_user
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001", # Test User ID
        "email": "tester@example.com",
        "role": "authenticated",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token

if __name__ == "__main__":
    print(generate_test_token())
