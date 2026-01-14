"""
COST & ABUSE CONTROL: Rate Limiter

Enforces per-user rate limits to protect against:
- Unbounded AI costs
- System abuse
- Unfair resource consumption

CORE PHILOSOPHY:
1. Hard limits > soft warnings
2. Gate BEFORE any AI-costly operation
3. Simple, deterministic, enforceable
4. Limits are per-user, not per-session
5. Governance > convenience

PIPELINE POSITION:
- Executes AFTER authentication
- Executes BEFORE AI proposal, embeddings, semantic validation
- If rejected here, AI NEVER runs

LIMITS (CONFIGURABLE VIA ENV):
- Per-minute: 5 (short-term burst protection)
- Per-day: 50 (long-term abuse protection)
"""

from uuid import UUID
from datetime import datetime, timedelta
from supabase import Client

from ..config import get_settings
from ..models.schemas import UserContext


# =============================================================================
# EXCEPTIONS
# =============================================================================

class RateLimitExceeded(Exception):
    """
    Raised when a user exceeds their rate limit.
    
    No grace period. No soft degradation.
    """
    
    def __init__(self, limit_type: str, retry_after_seconds: int = None):
        self.limit_type = limit_type  # "minute" or "day"
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded: {limit_type}")
    
    def get_user_message(self) -> str:
        """
        Return a clear, human-readable message.
        
        Does NOT leak internal counters or suggest bypasses.
        """
        if self.limit_type == "minute":
            return "Usage limit reached. Please wait a moment and try again."
        else:
            return "Daily usage limit reached. Please try again tomorrow."


# =============================================================================
# RATE LIMITER
# =============================================================================

class RateLimiter:
    """
    Per-user rate limiter with database storage.
    
    WHY DATABASE STORAGE:
    1. Persists across server restarts
    2. Works with multiple server instances
    3. Auditable - you can query usage patterns
    4. Consistent with "single source of truth"
    
    WHAT COUNTS AS A REQUEST:
    - Any operation that triggers an AI API call
    - Any operation that triggers embedding generation
    - UI interactions that do NOT call AI do NOT count
    
    RESET LOGIC:
    - Per-minute counters reset every 60 seconds
    - Per-day counters reset at UTC day boundary
    
    INTERNAL USERS:
    - Role "internal" bypasses all limits
    """
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.settings = get_settings()
    
    async def check_and_increment(self, user: UserContext) -> None:
        """
        Check if user is within rate limits and increment counters.
        
        MUST be called BEFORE any AI-costly operation.
        
        Raises:
            RateLimitExceeded: If limits are exceeded (reject immediately)
        """
        # Internal users bypass all limits
        if user.role == "internal":
            return
        
        # Fetch current rate limit state
        result = self.supabase.table("rate_limits").select("*").eq(
            "user_id", str(user.user_id)
        ).execute()
        
        if not result.data:
            # No rate limit record - create one
            self.supabase.table("rate_limits").insert({
                "user_id": str(user.user_id),
                "requests_today": 1,
                "requests_this_minute": 1,
                "last_minute_reset": datetime.utcnow().isoformat(),
                "last_day_reset": datetime.utcnow().date().isoformat()
            }).execute()
            return
        
        data = result.data[0]
        now = datetime.utcnow()
        
        # Parse timestamps (handle various formats)
        last_minute_reset = self._parse_timestamp(data["last_minute_reset"])
        last_day_reset = datetime.strptime(data["last_day_reset"], "%Y-%m-%d").date()
        
        requests_this_minute = data["requests_this_minute"]
        requests_today = data["requests_today"]
        
        # Check if we need to reset counters
        minute_reset_needed = (now - last_minute_reset) > timedelta(minutes=1)
        day_reset_needed = now.date() > last_day_reset
        
        if minute_reset_needed:
            requests_this_minute = 0
            last_minute_reset = now
        
        if day_reset_needed:
            requests_today = 0
            last_day_reset = now.date()
        
        # =====================================================================
        # HARD LIMIT ENFORCEMENT (NO GRACE PERIOD)
        # =====================================================================
        
        if requests_this_minute >= self.settings.rate_limit_requests_per_minute:
            seconds_until_reset = 60 - (now - last_minute_reset).seconds
            raise RateLimitExceeded("minute", retry_after_seconds=max(1, seconds_until_reset))
        
        if requests_today >= self.settings.rate_limit_requests_per_day:
            raise RateLimitExceeded("day", retry_after_seconds=None)
        
        # Increment counters (only if limits not exceeded)
        self.supabase.table("rate_limits").update({
            "requests_this_minute": requests_this_minute + 1,
            "requests_today": requests_today + 1,
            "last_minute_reset": last_minute_reset.isoformat(),
            "last_day_reset": last_day_reset.isoformat()
        }).eq("user_id", str(user.user_id)).execute()
    
    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse timestamp string handling various formats."""
        # Remove timezone suffixes for naive datetime
        ts = ts.replace("Z", "").replace("+00:00", "")
        if "." in ts:
            return datetime.fromisoformat(ts.split(".")[0])
        return datetime.fromisoformat(ts)
    
    async def get_usage(self, user: UserContext) -> dict:
        """
        Get current usage statistics for a user.
        
        For UI display only - does NOT influence limits.
        """
        result = self.supabase.table("rate_limits").select("*").eq(
            "user_id", str(user.user_id)
        ).execute()
        
        if not result.data:
            return {
                "requests_this_minute": 0,
                "requests_today": 0,
                "limit_per_minute": self.settings.rate_limit_requests_per_minute,
                "limit_per_day": self.settings.rate_limit_requests_per_day,
                "bypassed": user.role == "internal"
            }
        
        data = result.data[0]
        return {
            "requests_this_minute": data["requests_this_minute"],
            "requests_today": data["requests_today"],
            "limit_per_minute": self.settings.rate_limit_requests_per_minute,
            "limit_per_day": self.settings.rate_limit_requests_per_day,
            "bypassed": user.role == "internal"
        }


# =============================================================================
# FUTURE EXTENSIONS (NON-MVP, CLEARLY LABELED)
# =============================================================================
#
# 1. Tiered limits based on user roles/subscriptions
# 2. Quota pooling for organizations
# 3. Burst allowance with recovery
# 4. Admin override capabilities
# 5. Usage alerts via email/webhook
#
# These are explicitly NOT implemented in MVP.
# =============================================================================
