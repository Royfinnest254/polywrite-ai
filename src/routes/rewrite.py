"""
PHASE 5-8: Rewrite Routes
The main AI-powered text rewriting endpoints.

This brings together all the phases:
- Phase 5: Input validation
- Phase 6: AI proposal generation
- Phase 7: Semantic validation
- Phase 8: Decision engine
- Phase 9: Audit logging
"""

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from ..middleware.auth import get_current_user, get_supabase_client
from ..models.schemas import (
    UserContext, 
    RewriteRequest, 
    RewriteResponse,
    RateLimitError,
    SemanticResult,
    AuditLogEntry
)
from ..services import (
    RateLimiter,
    PlaceholderEmbeddingsProvider,
    SemanticValidator,
    DecisionEngine,
    AuditLogger,
    InputValidator,
    InputValidationError,
    AIProposalError,
    get_ai_provider
)
from ..services.rate_limiter import RateLimitExceeded
from ..config import get_settings


router = APIRouter(prefix="/api", tags=["Rewrite"])


@router.post("/rewrite", response_model=RewriteResponse)
async def rewrite_text(
    request: RewriteRequest,
    user: UserContext = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Rewrite, humanize, or clarify user-selected text.
    
    PHASE 5: Input Validation (GATE)
    - Validates intent (rewrite, humanize, clarify)
    - Validates text presence and length (20-1800 chars)
    - Blocks full-document attempts
    - All validations must pass before ANY AI call
    
    PHASE 6: AI Proposal
    - Generates proposed text with sanity checks
    - AI NEVER overwrites - only proposes
    - Conservative by design, meaning-preserving
    
    PHASE 7: Semantic Validation
    - Computes similarity score
    - Assigns risk label
    
    PHASE 8: Decision
    - safe → allowed
    - risky → flagged
    - dangerous → blocked
    
    PHASE 9: Audit
    - Logs the entire interaction
    """
    settings = get_settings()
    # supabase client injected via Depends
    
    # =========================================================================
    # PHASE 4: Rate Limiting
    # =========================================================================
    rate_limiter = RateLimiter(supabase)
    
    try:
        await rate_limiter.check_and_increment(user)
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "limit_type": e.limit_type,
                "retry_after_seconds": e.retry_after_seconds
            }
        )
    
    # =========================================================================
    # PHASE 5: Input Validation (GATE - runs BEFORE any AI call)
    # =========================================================================
    input_validator = InputValidator()
    
    try:
        input_validator.validate(
            selected_text=request.selected_text,
            intent=request.intent
        )
    except InputValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    
    # =========================================================================
    # PHASE 6: AI Proposal Generation (with sanity checks)
    # =========================================================================
    ai_provider = get_ai_provider()
    
    try:
        proposal = await ai_provider.generate_proposal(
            text=request.selected_text,
            intent=request.intent
        )
    except AIProposalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    
    # =========================================================================
    # PHASE 7: Semantic Validation
    # =========================================================================
    from ..services import get_embeddings_provider, SemanticValidationError
    
    embeddings_provider = get_embeddings_provider()
    semantic_validator = SemanticValidator(embeddings_provider)
    
    try:
        semantic_result = await semantic_validator.validate(
            original_text=request.selected_text,
            proposed_text=proposal.proposed_text
        )
    except SemanticValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    
    # =========================================================================
    # PHASE 8: Decision Engine
    # =========================================================================
    decision_engine = DecisionEngine()
    decision = decision_engine.decide(semantic_result)
    
    # =========================================================================
    # PHASE 9: Audit Logging (AFTER decision is final)
    # =========================================================================
    audit_logger = AuditLogger(supabase)
    audit_id = await audit_logger.log_interaction(
        user=user,
        action_type=request.intent,
        original_text=request.selected_text,
        proposed_text=proposal.proposed_text,
        semantic_result=semantic_result,
        decision=decision
    )
    
    # =========================================================================
    # Build Response
    # =========================================================================
    return RewriteResponse(
        original_text=request.selected_text,
        intent=request.intent,
        proposed_text=proposal.proposed_text,
        explanation_summary=proposal.explanation_summary,
        similarity_score=semantic_result.similarity_score,
        risk_label=semantic_result.risk_label,
        # Enhanced validation fields
        entity_preserved=semantic_result.entity_preserved,
        polarity_flip=semantic_result.polarity_flip,
        validation_flags=semantic_result.validation_flags,
        claim_analysis=semantic_result.claim_analysis,
        tone_analysis=semantic_result.tone_analysis,
        # Decision
        decision=decision.decision,
        decision_reason=decision.reason,
        audit_id=audit_id
    )


@router.get("/thresholds")
async def get_thresholds(user: UserContext = Depends(get_current_user)):
    """
    Get the current semantic similarity thresholds.
    
    Useful for debugging and understanding the decision boundaries.
    """
    embeddings_provider = PlaceholderEmbeddingsProvider()
    semantic_validator = SemanticValidator(embeddings_provider)
    
    return semantic_validator.get_thresholds()


@router.get("/audit-logs", response_model=list[AuditLogEntry])
async def get_audit_logs(
    user: UserContext = Depends(get_current_user),
    limit: int = 100,
    supabase: Client = Depends(get_supabase_client)
):
    """
    Get the current user's audit logs.
    
    Users can only see their own logs (enforced by RLS).
    """
    audit_logger = AuditLogger(supabase)
    
    return await audit_logger.get_user_logs(user, limit=limit)
