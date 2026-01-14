
import asyncio
from src.config import get_settings
from supabase import create_client

async def reset_limits():
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    
    # Reset all limits for simplicity in test env
    print("Resetting rate limits...")
    try:
        supabase.table("rate_limits").delete().neq("user_id", "00000000-0000-0000-0000-000000000000").execute()
        print("Limits cleared.")
    except Exception as e:
        print(f"Failed to clear limits: {e}")

if __name__ == "__main__":
    asyncio.run(reset_limits())
