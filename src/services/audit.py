"""
PHASE 9: Audit Logger

Immutable logging of all AI interactions for accountability.

CORE PURPOSE:
1. Who initiated an AI-assisted action?
2. What kind of action was it?
3. What did the system decide?
4. Why did it decide that?
5. When did it happen?

WITHOUT storing user content.

FUNDAMENTAL PRINCIPLES:
1. Log decisions, not documents
2. Store proofs (hashes), not text
3. Append-only, immutable records
4. Separation of concerns: logging does not influence decisions
5. Privacy by design

This layer is PASSIVE, not ACTIVE.
It must NOT influence AI generation, semantic validation, or decision logic.
"""

import hashlib
from typing import Literal
from uuid import UUID
from supabase import Client

from ..models.schemas import (
    UserContext, 
    SemanticResult, 
    Decision, 
    AuditLogEntry
)


# =============================================================================
# HASHING UTILITY (CRYPTOGRAPHIC, DETERMINISTIC)
# =============================================================================

def hash_text(text: str) -> str:
    """
    Compute SHA-256 hash of text content.
    
    REQUIREMENTS:
    - One-way cryptographic hash
    - Deterministic (same input → same output)
    - Hash ONLY the text content
    - Never store salts with user data
    
    PURPOSE:
    - Prove integrity without storing content
    - Enable audits without privacy violations
    - Detect duplicate requests
    - Verify specific text was processed
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =============================================================================
# AUDIT LOGGER
# =============================================================================

class AuditLogger:
    """
    Logs all AI interactions to the database.
    
    Log entries are IMMUTABLE:
    - Inserts ONLY (no updates, no deletes)
    - Write access restricted to service/backend role
    - Read access limited to owning user
    
    WHAT IS LOGGED:
    - user_id (unique identifier)
    - timestamp (UTC, auto-generated)
    - action_type (rewrite | humanize | clarify)
    - original_text_hash (SHA-256)
    - proposed_text_hash (SHA-256)
    - similarity_score (float)
    - risk_label (safe | risky | dangerous)
    - decision (allowed | allowed_with_warning | blocked)
    
    WHAT IS NOT LOGGED:
    - Raw text content
    - Embeddings or vectors
    - AI prompts or model outputs
    - User documents
    """
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
    
    async def log_interaction(
        self,
        user: UserContext,
        action_type: Literal["rewrite", "humanize", "clarify"],
        original_text: str,
        proposed_text: str,
        semantic_result: SemanticResult,
        decision: Decision
    ) -> UUID:
        """
        Log an AI interaction.
        
        WHEN TO CALL:
        - ONLY AFTER semantic validation completes
        - ONLY AFTER decision logic produces a final verdict
        
        DO NOT CALL:
        - For intermediate AI drafts
        - For failed input validations
        - For aborted requests
        
        Only log FINALIZED system behavior.
        
        Args:
            user: The user who made the request
            action_type: The type of AI action (rewrite, humanize, clarify)
            original_text: The original text (will be hashed, not stored)
            proposed_text: The proposed text (will be hashed, not stored)
            semantic_result: Result of semantic validation
            decision: Final decision
        
        Returns:
            The UUID of the created audit log entry
        """
        # Hash texts for privacy (we NEVER store raw content)
        original_hash = hash_text(original_text)
        proposed_hash = hash_text(proposed_text)
        
        result = self.supabase.table("audit_logs").insert({
            "user_id": str(user.user_id),
            "original_text_hash": original_hash,
            "proposed_text_hash": proposed_hash,
            "similarity_score": semantic_result.similarity_score,
            "risk_label": semantic_result.risk_label,
            "decision": decision.decision
        }).execute()
        
        return UUID(result.data[0]["id"])
    
    async def get_user_logs(
        self, 
        user: UserContext, 
        limit: int = 100
    ) -> list[AuditLogEntry]:
        """
        Get audit logs for a user.
        
        Users can ONLY see their own logs (enforced by RLS).
        """
        result = self.supabase.table("audit_logs").select("*").eq(
            "user_id", str(user.user_id)
        ).order("created_at", desc=True).limit(limit).execute()
        
        return [AuditLogEntry(**row) for row in result.data]


# =============================================================================
# FUTURE EXTENSIONS (NON-MVP, CLEARLY LABELED)
# =============================================================================
#
# 1. Admin audit access (internal roles viewing logs)
# 2. Aggregated statistics (without exposing individual records)
# 3. Retention policies (legal compliance)
# 4. Export functionality (GDPR data requests)
# 5. Anomaly detection (flagging unusual patterns)
#
# These are explicitly NOT implemented in MVP.
# =============================================================================
