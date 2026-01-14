"""
PHASE 1 & 3: Profile Service
Handles profile CRUD and role-based access control.
"""

from uuid import UUID
from typing import Optional
from supabase import Client

from ..models.schemas import Profile, UserContext


class ProfileService:
    """Service for managing user profiles."""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
    
    async def get_profile(self, user_id: UUID) -> Optional[Profile]:
        """
        Fetch a user's profile by ID.
        Returns None if profile doesn't exist.
        """
        result = self.supabase.table("profiles").select("*").eq("id", str(user_id)).single().execute()
        
        if result.data:
            return Profile(**result.data)
        return None
    
    async def ensure_profile_exists(self, user_id: UUID, email: str) -> Profile:
        """
        Ensure a profile exists for the user.
        Creates one if missing (defensive programming).
        
        PHASE 1 REQUIREMENT: Every authenticated user MUST have exactly one profile.
        """
        profile = await self.get_profile(user_id)
        
        if profile:
            return profile
        
        # Profile missing - create it
        # This should rarely happen due to the database trigger,
        # but we handle it defensively
        result = self.supabase.table("profiles").upsert({
            "id": str(user_id),
            "email": email,
            "role": "free"
        }).execute()
        
        # Also create rate limit entry
        self.supabase.table("rate_limits").upsert({
            "user_id": str(user_id)
        }).execute()
        
        return Profile(**result.data[0])
    
    async def get_user_context(self, user_id: UUID, email: str) -> UserContext:
        """
        Get full user context for request processing.
        Ensures profile exists and returns context.
        """
        profile = await self.ensure_profile_exists(user_id, email)
        
        return UserContext(
            user_id=profile.id,
            email=profile.email,
            role=profile.role
        )
    
    def require_role(self, user: UserContext, required_role: str) -> bool:
        """
        PHASE 3: Check if user has required role.
        
        Role hierarchy:
        - internal > free
        
        Returns True if user has sufficient privileges.
        Raises exception if not.
        """
        role_hierarchy = {
            "free": 0,
            "internal": 1
        }
        
        user_level = role_hierarchy.get(user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        if user_level < required_level:
            raise PermissionError(
                f"Role '{required_role}' required. You have '{user.role}'."
            )
        
        return True
    
    async def set_role(self, user_id: UUID, new_role: str) -> Profile:
        """
        Set a user's role. 
        This should only be called by admins/internal tooling.
        """
        if new_role not in ("free", "internal"):
            raise ValueError(f"Invalid role: {new_role}")
        
        result = self.supabase.table("profiles").update({
            "role": new_role
        }).eq("id", str(user_id)).execute()
        
        if not result.data:
            raise ValueError(f"User {user_id} not found")
        
        return Profile(**result.data[0])
