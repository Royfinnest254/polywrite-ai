"""
Pydantic models for request/response validation.
Used across all phases.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID


# ============================================================================
# PHASE 1: User & Profile Models
# ============================================================================

class Profile(BaseModel):
    """User profile from database."""
    id: UUID
    email: str
    role: Literal["free", "internal"]
    created_at: datetime


class UserContext(BaseModel):
    """User context attached to requests after auth."""
    user_id: UUID
    email: str
    role: Literal["free", "internal"]


# ============================================================================
# PHASE 5: Input Models (STRICT CONTRACT)
# ============================================================================

class RewriteRequest(BaseModel):
    """
    Request to rewrite/humanize/clarify text.
    
    PHASE 5 INPUT CONTRACT:
    - selected_text: required, 20-1800 characters
    - intent: required, one of: rewrite, humanize, clarify
    
    No additional fields allowed.
    No free-form instructions.
    No hidden context.
    """
    selected_text: str = Field(
        ..., 
        min_length=20, 
        max_length=1800,
        description="The user-selected text to modify (20-1800 characters)"
    )
    intent: Literal["rewrite", "humanize", "clarify"] = Field(
        ...,  # Required, no default
        description="What the user wants to do: rewrite, humanize, or clarify"
    )
    
    class Config:
        # Reject any extra fields
        extra = "forbid"



# ============================================================================
# PHASE 6: AI Proposal Models
# ============================================================================

class AIProposal(BaseModel):
    """Proposed text from AI with explanation."""
    proposed_text: str
    explanation_summary: str


# ============================================================================
# PHASE 7: Semantic Validation Models
# ============================================================================

class EntityPreservation(BaseModel):
    """Entity preservation status from validation."""
    preserved: bool
    missing: list[str] = []
    added: list[str] = []
    changed_numbers: list[dict] = []
    risk_level: Literal["none", "low", "high"] = "none"


class ClaimAnalysis(BaseModel):
    """Claim and citation analysis result."""
    claims_detected: int = 0
    uncited_claims: list[str] = []
    citation_count: int = 0
    risk_level: Literal["none", "low", "high"] = "none"
    needs_review: bool = False


class ToneAnalysis(BaseModel):
    """Tone preservation analysis result."""
    preserved: bool = True
    original_tone: str = "neutral"
    proposed_tone: str = "neutral"
    formality_shift: float = 0.0
    risk_level: Literal["none", "low", "high"] = "none"


class SemanticResult(BaseModel):
    """Result of semantic similarity comparison."""
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    risk_label: Literal["safe", "risky", "dangerous"]
    
    # Enhanced validation (white paper Section 4.4-4.5)
    entity_preserved: bool = True
    entity_details: Optional[EntityPreservation] = None
    polarity_flip: bool = False
    validation_flags: list[str] = []
    
    # Additional validators (white paper Sections 4.6, 5, 9.1)
    claim_analysis: Optional[ClaimAnalysis] = None
    tone_analysis: Optional[ToneAnalysis] = None


# ============================================================================
# PHASE 8: Decision Models
# ============================================================================

class Decision(BaseModel):
    """
    Final decision on whether to allow the proposal.
    
    DECISION VALUES:
    - allowed: Proposal can be shown, meaning preserved
    - allowed_with_warning: Proposal shown with warning, review needed
    - blocked: Proposal not shown, meaning drift too high
    """
    decision: Literal["allowed", "allowed_with_warning", "blocked"]
    reason: str


class RewriteResponse(BaseModel):
    """Complete response for a rewrite request."""
    # Original input
    original_text: str
    intent: str
    
    # AI proposal
    proposed_text: str
    explanation_summary: str
    
    # Semantic validation
    similarity_score: float
    risk_label: Literal["safe", "risky", "dangerous"]
    
    # Enhanced validation (white paper)
    entity_preserved: bool = True
    polarity_flip: bool = False
    validation_flags: list[str] = []
    claim_analysis: Optional[ClaimAnalysis] = None
    tone_analysis: Optional[ToneAnalysis] = None
    
    # Decision
    decision: Literal["allowed", "allowed_with_warning", "blocked"]
    decision_reason: str
    
    # Metadata
    audit_id: UUID


# ============================================================================
# PHASE 9: Audit Models
# ============================================================================

class AuditLogEntry(BaseModel):
    """Audit log entry for an AI interaction."""
    id: UUID
    user_id: UUID
    original_text_hash: str
    proposed_text_hash: str
    similarity_score: float
    risk_label: Literal["safe", "risky", "dangerous"]
    decision: Literal["allowed", "allowed_with_warning", "blocked"]
    created_at: datetime


# ============================================================================
# Error Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None


class RateLimitError(BaseModel):
    """Rate limit exceeded error."""
    error: str = "rate_limit_exceeded"
    limit_type: Literal["minute", "day"]
    retry_after_seconds: Optional[int] = None
