"""
PHASE 8: Decision Engine

Translates semantic risk into system action.

CORE PHILOSOPHY:
1. Measurement ≠ Decision
2. AI must never approve itself
3. The system must be deterministic
4. Humans retain final authority
5. Safety overrides convenience

This engine is intentionally boring.
All complexity belongs in measurement (Phase 7).
Decision logic must be auditable in one glance.
"""

from typing import Literal
from ..models.schemas import SemanticResult, Decision


# =============================================================================
# DECISION MATRIX (EXPLICIT, DETERMINISTIC)
# =============================================================================
#
# | Risk Label | Decision             | Rationale                    |
# |------------|----------------------|------------------------------|
# | safe       | allowed              | Meaning preserved            |
# | risky      | allowed_with_warning | Review needed                |
# | dangerous  | blocked              | Meaning drift too high       |
#
# This matrix is:
# - Explicit (no hidden cases)
# - Deterministic (same input → same output)
# - Auditable (can be verified by inspection)
# - Conservative (false warnings OK, false safety NOT OK)
# =============================================================================


class DecisionEngine:
    """
    Makes decisions based on semantic validation results.
    
    This is a rule-based governor, NOT an optimization engine.
    
    DECISION POLICY (MVP — CONSERVATIVE):
    - safe       → allowed
    - risky      → allowed_with_warning  
    - dangerous  → blocked
    
    The engine is:
    - Pure: No side effects, no database writes
    - Deterministic: Same input always produces same output
    - Context-agnostic: Does not see raw text, embeddings, or user data
    """
    
    def decide(
        self, 
        semantic_result: SemanticResult,
        intent: Literal["rewrite", "humanize", "clarify"] = "rewrite"
    ) -> Decision:
        """
        Make a decision based on the semantic validation result.
        
        INPUT CONTRACT:
        - risk_label: "safe" | "risky" | "dangerous"
        - similarity_score: float in [0.0, 1.0]
        - entity_preserved: bool (white paper 4.4)
        - polarity_flip: bool (white paper 4.5)
        - intent: "rewrite" | "humanize" | "clarify"
        
        OUTPUT CONTRACT:
        - decision: "allowed" | "allowed_with_warning" | "blocked"
        - reason: Human-readable explanation
        
        Args:
            semantic_result: Result from SemanticValidator
            intent: The user's intent (optional, for future tightening)
        
        Returns:
            Decision with decision and reason
        """
        risk_label = semantic_result.risk_label
        score = semantic_result.similarity_score
        
        # Extract enhanced validation fields (with defaults for backwards compat)
        entity_preserved = getattr(semantic_result, 'entity_preserved', True)
        polarity_flip = getattr(semantic_result, 'polarity_flip', False)
        validation_flags = getattr(semantic_result, 'validation_flags', [])
        
        # =================================================================
        # DECISION MATRIX (WHITE PAPER ENHANCED)
        # =================================================================
        
        # PRIORITY 1: Polarity flip ALWAYS blocks (white paper 4.5)
        if polarity_flip:
            return Decision(
                decision="blocked",
                reason="The proposed text reverses the meaning (negation changed). "
                       "This could fundamentally alter your intent. Proposal blocked."
            )
        
        # PRIORITY 2: Entity drift blocks even with high similarity (white paper 4.4)
        if not entity_preserved and score >= 0.80:
            flags_str = "; ".join(validation_flags[:2]) if validation_flags else "Entity changes detected"
            return Decision(
                decision="blocked",
                reason=f"Factual content changed despite high similarity ({score:.1%}). "
                       f"{flags_str}. Proposal blocked to prevent factual drift."
            )
        
        # STANDARD: Risk-label based decisions
        if risk_label == "safe":
            return Decision(
                decision="allowed",
                reason=f"Semantic similarity ({score:.1%}) indicates meaning is preserved."
            )
        
        elif risk_label == "risky":
            warning_suffix = ""
            if validation_flags:
                warning_suffix = f" Note: {validation_flags[0]}"
            return Decision(
                decision="allowed_with_warning",
                reason=f"Semantic similarity ({score:.1%}) is marginal. "
                       f"Please review carefully to ensure meaning is preserved.{warning_suffix}"
            )
        
        elif risk_label == "dangerous":
            block_reason = f"Semantic similarity ({score:.1%}) is too low."
            if validation_flags:
                block_reason += f" Issues: {'; '.join(validation_flags[:2])}"
            return Decision(
                decision="blocked",
                reason=f"{block_reason} "
                       f"The proposed text may significantly alter the original meaning. "
                       f"This proposal has been blocked to protect content integrity."
            )
        
        else:
            # Defensive: should never reach here
            # If we do, fail safe by blocking
            return Decision(
                decision="blocked",
                reason=f"Unknown risk label: {risk_label}. Blocking for safety."
            )
    
    def is_allowed(self, decision: Decision) -> bool:
        """
        Check if a decision allows showing the proposal.
        
        Both 'allowed' and 'allowed_with_warning' permit display.
        """
        return decision.decision in ("allowed", "allowed_with_warning")
    
    def is_blocked(self, decision: Decision) -> bool:
        """Check if a decision blocks the proposal."""
        return decision.decision == "blocked"
    
    def requires_warning(self, decision: Decision) -> bool:
        """Check if the decision requires a warning to be shown."""
        return decision.decision == "allowed_with_warning"


# =============================================================================
# WHY THIS LOGIC IS INTENTIONALLY BORING
# =============================================================================
#
# This decision engine is simple by design, not by accident.
#
# 1. AUDITABILITY: Any engineer can verify correctness by inspection
# 2. PREDICTABILITY: Users and auditors know exactly what to expect
# 3. SAFETY: No clever optimizations that could introduce edge cases
# 4. MAINTAINABILITY: Changes require explicit discussion, not refactoring
# 5. ACCOUNTABILITY: Decisions can be traced to explicit rules
#
# "Boring" is a feature, not a bug.
# Clever decision logic is how systems become deceptive.
# =============================================================================
