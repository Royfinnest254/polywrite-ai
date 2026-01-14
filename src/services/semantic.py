"""
PHASE 7: Semantic Validator (SMV)

A FIRST-CLASS, INDEPENDENT SYSTEM COMPONENT.
Compares original and proposed text to quantify semantic similarity
and classify meaning drift risk.

CORE PRINCIPLE (NON-NEGOTIABLE):
Meaning is NOT judged by an LLM.
Meaning is NOT judged by heuristics.
Meaning is judged numerically using vector embeddings.

This validator is a SENSOR, not a BRAIN.
It must:
- be deterministic
- be explainable in principle (cosine similarity)
- be model-agnostic
- produce the same output for same input every time
- NOT call an LLM or modify text

INPUT CONTRACT (STRICT):
The SMV receives ONLY:
1. original_text (string)
2. proposed_text (string)

OUTPUT CONTRACT:
{
  "similarity_score": float between 0.0 and 1.0,
  "risk_label": one of ["safe", "risky", "dangerous"]
}
"""

from ..config import get_settings
from ..models.schemas import SemanticResult
from .embeddings import EmbeddingsProvider, EmbeddingsError


# =============================================================================
# EXCEPTIONS
# =============================================================================

class SemanticValidationError(Exception):
    """
    Raised when semantic validation fails.
    
    Contains a user-safe message.
    """
    def __init__(self, message: str, internal_reason: str = ""):
        self.message = message
        self.internal_reason = internal_reason
        super().__init__(message)


# =============================================================================
# SEMANTIC VALIDATOR (SMV)
# =============================================================================

class SemanticValidator:
    """
    Validates that proposed text preserves the semantic meaning
    of the original text.
    
    SEMANTIC REPRESENTATION:
    - Uses vector embeddings (same model, same dim, same normalization)
    - Computes cosine similarity in [0.0, 1.0]
    
    THRESHOLDING (CRITICAL):
    - SAFE:      similarity >= 0.85
    - RISKY:     0.60 <= similarity < 0.85
    - DANGEROUS: similarity < 0.60
    
    ENHANCED VALIDATION (White Paper Sections 4.4-4.5):
    - Entity preservation check (numbers, dates, proper nouns)
    - Polarity flip detection (negation reversal)
    """
    
    # Negation words for polarity detection
    NEGATION_WORDS = {
        'not', 'no', 'never', 'neither', 'nor', 'none', 'nobody', 
        'nothing', 'nowhere', "n't", "cannot", "can't", "won't", 
        "wouldn't", "shouldn't", "couldn't", "doesn't", "don't",
        "didn't", "isn't", "aren't", "wasn't", "weren't"
    }
    
    def __init__(self, embeddings_provider: EmbeddingsProvider):
        """
        Args:
            embeddings_provider: The provider to use for text embeddings
        """
        self.embeddings = embeddings_provider
        self.settings = get_settings()
        
        # Import validators
        from .entity_validator import EntityValidator
        from .claim_validator import ClaimValidator
        from .tone_analyzer import ToneAnalyzer
        
        self.entity_validator = EntityValidator()
        self.claim_validator = ClaimValidator()
        self.tone_analyzer = ToneAnalyzer()
    
    async def validate(
        self, 
        original_text: str, 
        proposed_text: str
    ) -> SemanticResult:
        """
        Compare original and proposed text semantically.
        
        This function performs:
        1. Embedding-based similarity check
        2. Entity preservation check (white paper 4.4)
        3. Polarity flip detection (white paper 4.5)
        
        Args:
            original_text: The user's original text
            proposed_text: The AI's proposed rewrite
        
        Returns:
            SemanticResult with similarity_score, risk_label, and enhanced fields
            
        Raises:
            SemanticValidationError: If validation cannot be performed
        """
        # Validate inputs
        if not original_text or not original_text.strip():
            raise SemanticValidationError(
                "Cannot validate: original text is empty",
                internal_reason="Empty original_text"
            )
        
        if not proposed_text or not proposed_text.strip():
            raise SemanticValidationError(
                "Cannot validate: proposed text is empty",
                internal_reason="Empty proposed_text"
            )
        
        validation_flags = []
        
        # Step 1: Compute semantic similarity using embeddings
        try:
            similarity_score = await self.embeddings.compute_similarity(
                original_text, 
                proposed_text
            )
        except EmbeddingsError as e:
            raise SemanticValidationError(
                "Failed to compute semantic similarity",
                internal_reason=e.internal_reason
            )
        
        # Step 2: Entity preservation check (white paper 4.4)
        entity_result = self.entity_validator.validate(original_text, proposed_text)
        entity_preserved = entity_result.preserved
        
        if not entity_preserved:
            if entity_result.missing:
                validation_flags.append(
                    f"Missing entities: {', '.join(entity_result.missing[:3])}"
                )
            if entity_result.changed_numbers:
                for change in entity_result.changed_numbers[:2]:
                    validation_flags.append(
                        f"Number changed: {change['original']} → {change['proposed']}"
                    )
        
        # Step 3: Polarity flip detection (white paper 4.5)
        polarity_flip = self._detect_polarity_flip(original_text, proposed_text)
        
        if polarity_flip:
            validation_flags.append("Polarity reversal detected (negation changed)")
        
        # Step 4: Claim and citation analysis (white paper 4.6)
        claim_result = self.claim_validator.validate(original_text, proposed_text)
        if claim_result.uncited_claims:
            validation_flags.append(
                f"Uncited claims: {len(claim_result.uncited_claims)} detected"
            )
        
        # Step 5: Tone preservation check (white paper 9.1)
        tone_result = self.tone_analyzer.validate(original_text, proposed_text)
        if not tone_result.preserved:
            validation_flags.append(
                f"Tone shift: {tone_result.original_tone} → {tone_result.proposed_tone}"
            )
        
        # Step 6: Determine risk label based on ALL validation results
        risk_label = self._compute_risk_label(
            similarity_score, 
            entity_preserved,
            polarity_flip
        )
        
        # Build response objects
        from ..models.schemas import EntityPreservation, ClaimAnalysis, ToneAnalysis
        
        entity_details = EntityPreservation(
            preserved=entity_result.preserved,
            missing=entity_result.missing,
            added=entity_result.added,
            changed_numbers=entity_result.changed_numbers,
            risk_level=entity_result.risk_level
        )
        
        claim_analysis = ClaimAnalysis(
            claims_detected=len(claim_result.claims_detected),
            uncited_claims=claim_result.uncited_claims[:5],
            citation_count=claim_result.citation_count,
            risk_level=claim_result.risk_level,
            needs_review=len(claim_result.uncited_claims) > 0
        )
        
        tone_analysis = ToneAnalysis(
            preserved=tone_result.preserved,
            original_tone=tone_result.original_tone,
            proposed_tone=tone_result.proposed_tone,
            formality_shift=tone_result.formality_shift,
            risk_level=tone_result.risk_level
        )
        
        return SemanticResult(
            similarity_score=round(similarity_score, 3),
            risk_label=risk_label,
            entity_preserved=entity_preserved,
            entity_details=entity_details,
            polarity_flip=polarity_flip,
            validation_flags=validation_flags,
            claim_analysis=claim_analysis,
            tone_analysis=tone_analysis
        )
    
    def _detect_polarity_flip(self, original: str, proposed: str) -> bool:
        """
        Detect if proposed text reverses the polarity of the original.
        
        WHITE PAPER SECTION 4.5:
        "This approach is clearly not effective" → "This approach is clearly effective"
        Similarity: 0.93 (HIGH) but logically contradictory!
        
        Returns True if negation status changed.
        """
        orig_lower = original.lower()
        prop_lower = proposed.lower()
        
        # Count negation words in each text
        orig_negations = sum(1 for word in self.NEGATION_WORDS if word in orig_lower.split())
        prop_negations = sum(1 for word in self.NEGATION_WORDS if word in prop_lower.split())
        
        # Also check for contracted negations within words
        orig_has_nt = "n't" in orig_lower
        prop_has_nt = "n't" in prop_lower
        
        # Polarity flip if one has negation and the other doesn't
        orig_is_negated = (orig_negations > 0) or orig_has_nt
        prop_is_negated = (prop_negations > 0) or prop_has_nt
        
        return orig_is_negated != prop_is_negated
    
    def _compute_risk_label(
        self, 
        similarity: float,
        entity_preserved: bool,
        polarity_flip: bool
    ) -> str:
        """
        Map similarity score to risk label using FIXED thresholds.
        
        ENHANCED LOGIC (White Paper):
        - Polarity flip → ALWAYS dangerous
        - Entity not preserved + high similarity → dangerous (factual drift)
        - Standard similarity thresholds otherwise
        
        DETERMINISTIC CLASSIFICATION:
        - similarity >= 0.85     → "safe" (if no other issues)
        - 0.60 <= similarity < 0.85 → "risky"  
        - similarity < 0.60     → "dangerous"
        """
        # WHITE PAPER: Polarity flip ALWAYS blocks, regardless of similarity
        if polarity_flip:
            return "dangerous"
        
        # WHITE PAPER 4.4: High similarity BUT entity changed → dangerous
        # This catches "50% in 2020" → "60% in 2021" (similarity 0.92 but wrong)
        if similarity >= self.settings.threshold_safe and not entity_preserved:
            return "dangerous"
        
        # Standard threshold-based classification
        if similarity >= self.settings.threshold_safe and entity_preserved:
            return "safe"
        elif similarity >= self.settings.threshold_risky:
            return "risky"
        else:
            return "dangerous"
    
    def get_thresholds(self) -> dict:
        """
        Get current threshold configuration.
        """
        return {
            "safe_threshold": self.settings.threshold_safe,
            "risky_threshold": self.settings.threshold_risky,
            "classification": {
                "safe": f"similarity >= {self.settings.threshold_safe} AND entities preserved AND no polarity flip",
                "risky": f"{self.settings.threshold_risky} <= similarity < {self.settings.threshold_safe}",
                "dangerous": f"similarity < {self.settings.threshold_risky} OR polarity flip OR entity drift"
            },
            "enhanced_checks": ["entity_preservation", "polarity_detection"],
            "note": "White paper enhanced validation: 0.85/0.60 thresholds with entity & polarity checks"
        }
