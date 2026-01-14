"""
PHASE 2: Authentication Middleware
Validates JWT tokens and extracts user context.

This middleware:
1. Rejects requests without a valid session
2. Extracts user ID from session
3. Attaches user + profile to request context
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from uuid import UUID
from supabase import create_client, Client

from ..config import get_settings
from ..models.schemas import UserContext
from ..services.profile import ProfileService


# HTTP Bearer token scheme
security = HTTPBearer()


def get_supabase_client() -> Client:
    """Get Supabase client with service role key."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key
    )


def get_supabase_anon_client() -> Client:
    """Get Supabase client with anon key (for user-scoped operations)."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    supabase: Client = Depends(get_supabase_client)
) -> UserContext:
    """
    Dependency that extracts and validates the current user from JWT.
    
    PHASE 2 REQUIREMENT:
    - Rejects requests without a valid session
    - Extracts user ID from session
    - Attaches user + profile to request context
    
    Raises HTTPException 401 if:
    - No token provided
    - Token is invalid
    - Token is expired
    """
    settings = get_settings()
    token = credentials.credentials
    
    try:
        # Validate token via Supabase API explicitly
        # This avoids needing the Supabase JWT secret locally
        user_response = supabase.auth.get_user(token)
        
        if not user_response or not user_response.user:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: user not found"
            )
            
        user_data = user_response.user
        
        # Extract info
        user_id = user_data.id
        email = user_data.email
        
        if not user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user information"
            )
        
        # Get or create profile
        profile_service = ProfileService(supabase)
        user_context = await profile_service.get_user_context(
            user_id=UUID(user_id),
            email=email
        )
        
        return user_context
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}"
        )


def require_auth(user: UserContext = Depends(get_current_user)) -> UserContext:
    """
    Simple alias for get_current_user.
    Use this to make route dependencies more readable.
    
    Example:
        @router.post("/rewrite")
        async def rewrite(user: UserContext = Depends(require_auth)):
            ...
    """
    return user


def require_role(required_role: str):
    """
    PHASE 3: Create a dependency that requires a specific role.
    
    Example:
        @router.get("/admin")
        async def admin_only(user: UserContext = Depends(require_role("internal"))):
            ...
    """
    async def role_checker(user: UserContext = Depends(get_current_user)) -> UserContext:
        role_hierarchy = {
            "free": 0,
            "internal": 1
        }
        
        user_level = role_hierarchy.get(user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required. You have '{user.role}'."
            )
        
        return user
    
    return role_checker
