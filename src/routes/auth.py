"""
Auth Routes
Endpoints for authentication and profile management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from supabase import Client

from ..middleware.auth import get_current_user, get_supabase_anon_client, get_supabase_client
from ..models.schemas import UserContext, Profile
from ..services.profile import ProfileService


router = APIRouter(prefix="/auth", tags=["Authentication"])


class SignUpRequest(BaseModel):
    """Request to sign up a new user."""
    email: EmailStr
    password: str


class SignInRequest(BaseModel):
    """Request to sign in."""
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Response after successful authentication."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


@router.post("/signup", response_model=AuthResponse)
async def signup(
    request: SignUpRequest,
    supabase: Client = Depends(get_supabase_anon_client)
):
    """
    Sign up a new user.
    
    This creates:
    1. A Supabase auth user
    2. A profile (via database trigger)
    3. A rate limit entry (via database trigger)
    """
    
    try:
        result = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password
        })
        
        if not result.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user"
            )
        
        return AuthResponse(
            access_token=result.session.access_token if result.session else "",
            user_id=result.user.id,
            email=result.user.email
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/signin", response_model=AuthResponse)
async def signin(
    request: SignInRequest,
    supabase: Client = Depends(get_supabase_anon_client)
):
    """
    Sign in an existing user.
    
    Returns an access token for use in subsequent requests.
    """
    
    try:
        result = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        if not result.user or not result.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        return AuthResponse(
            access_token=result.session.access_token,
            user_id=result.user.id,
            email=result.user.email
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/me", response_model=Profile)
async def get_current_profile(
    user: UserContext = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Get the current user's profile.
    
    Requires authentication.
    """
    profile_service = ProfileService(supabase)
    
    profile = await profile_service.get_profile(user.user_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    return profile


@router.get("/usage")
async def get_usage(
    user: UserContext = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Get the current user's rate limit usage.
    
    Requires authentication.
    """
    from ..services.rate_limiter import RateLimiter
    
    rate_limiter = RateLimiter(supabase)
    
    return await rate_limiter.get_usage(user)
