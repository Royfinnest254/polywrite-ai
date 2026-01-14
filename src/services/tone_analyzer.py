"""
Tone Analyzer

Analyzes and validates voice/tone preservation between original and proposed text.

WHITE PAPER REFERENCE: Section 9.1 (Failure 2: Tone shift)

PROBLEM SOLVED:
- Original: "The board has decided to restructure the division"
- Proposed: "The board's gonna shake up the division"
- Similarity: 0.88 (REVIEW)
- BUT tone changed from formal to casual!

TONE CATEGORIES:
- formal: Business/legal language
- professional: Standard workplace
- casual: Conversational
- academic: Scholarly writing
- creative: Literary/expressive
"""

import re
from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class ToneAnalysisResult:
    """Result of tone analysis."""
    detected_tone: str
    confidence: float
    formality_score: float  # 0.0 (casual) to 1.0 (formal)
    indicators: Dict[str, int]
    
    def to_dict(self) -> dict:
        return {
            "tone": self.detected_tone,
            "confidence": round(self.confidence, 2),
            "formality_score": round(self.formality_score, 2),
            "indicators": self.indicators
        }


@dataclass
class ToneValidationResult:
    """Result of tone preservation validation."""
    preserved: bool
    original_tone: str
    proposed_tone: str
    formality_shift: float  # Negative = more casual, Positive = more formal
    risk_level: str  # none, low, high
    
    def to_dict(self) -> dict:
        return {
            "preserved": self.preserved,
            "original_tone": self.original_tone,
            "proposed_tone": self.proposed_tone,
            "formality_shift": round(self.formality_shift, 2),
            "risk_level": self.risk_level
        }


class ToneAnalyzer:
    """
    Analyzes text tone and validates tone preservation.
    
    FORMALITY INDICATORS:
    - Formal: passive voice, complex sentences, no contractions
    - Casual: contractions, slang, first person, short sentences
    - Academic: citations, hedging language, technical terms
    - Professional: action verbs, clear structure, measured tone
    """
    
    # Tone indicator patterns
    FORMAL_INDICATORS = [
        r'\b(?:therefore|furthermore|moreover|consequently|subsequently)\b',
        r'\b(?:shall|hereby|pursuant|notwithstanding|whereas)\b',
        r'\b(?:it\s+is\s+(?:evident|clear|apparent|notable))\b',
        r'\b(?:one\s+(?:must|should|may|might))\b',
        r'\b(?:the\s+(?:aforementioned|above-mentioned|undersigned))\b',
    ]
    
    CASUAL_INDICATORS = [
        r"\b(?:gonna|wanna|gotta|kinda|sorta)\b",
        r"\b(?:yeah|yep|nope|okay|ok)\b",
        r"\b(?:like|literally|basically|actually|honestly)\b",
        r"\b(?:stuff|things|guy|guys|cool|awesome)\b",
        r"(?:n't|'ll|'ve|'re|'d)\b",  # Contractions
        r"!{2,}",  # Multiple exclamation marks
        r"\b(?:lol|omg|btw|imo|tbh)\b",
    ]
    
    ACADEMIC_INDICATORS = [
        r'\b(?:hypothesis|methodology|empirical|theoretical)\b',
        r'\b(?:furthermore|thus|hence|accordingly)\b',
        r'\b(?:significant(?:ly)?|considerable|substantial)\b',
        r'\b(?:findings|results|analysis|conclusion)\b',
        r'\([A-Z][a-z]+,?\s*\d{4}\)',  # Citations
        r'\b(?:it\s+(?:appears|seems|suggests)\s+that)\b',  # Hedging
    ]
    
    PROFESSIONAL_INDICATORS = [
        r'\b(?:implement|execute|deliver|optimize|leverage)\b',
        r'\b(?:stakeholder|initiative|strategy|objective)\b',
        r'\b(?:moving\s+forward|going\s+forward|at\s+this\s+time)\b',
        r'\b(?:please\s+(?:note|see|find|review))\b',
        r'\b(?:best\s+(?:practices|regards)|kind\s+regards)\b',
    ]
    
    def analyze(self, text: str) -> ToneAnalysisResult:
        """
        Analyze the tone of text.
        
        Returns tone classification with confidence score.
        """
        if not text or not text.strip():
            return ToneAnalysisResult(
                detected_tone="neutral",
                confidence=0.0,
                formality_score=0.5,
                indicators={}
            )
        
        text_lower = text.lower()
        
        # Count indicators for each tone
        indicators = {
            "formal": self._count_matches(text_lower, self.FORMAL_INDICATORS),
            "casual": self._count_matches(text_lower, self.CASUAL_INDICATORS),
            "academic": self._count_matches(text_lower, self.ACADEMIC_INDICATORS),
            "professional": self._count_matches(text_lower, self.PROFESSIONAL_INDICATORS),
        }
        
        # Calculate formality score
        formality_score = self._calculate_formality(text, indicators)
        
        # Determine dominant tone
        detected_tone, confidence = self._determine_tone(indicators, len(text))
        
        return ToneAnalysisResult(
            detected_tone=detected_tone,
            confidence=confidence,
            formality_score=formality_score,
            indicators=indicators
        )
    
    def validate(
        self, 
        original_text: str, 
        proposed_text: str
    ) -> ToneValidationResult:
        """
        Validate that tone is preserved between original and proposed.
        
        Flags significant tone shifts that might be inappropriate.
        """
        orig_analysis = self.analyze(original_text)
        prop_analysis = self.analyze(proposed_text)
        
        # Calculate formality shift
        formality_shift = prop_analysis.formality_score - orig_analysis.formality_score
        
        # Determine if tone is preserved
        # Allow small shifts, flag large ones
        tone_changed = orig_analysis.detected_tone != prop_analysis.detected_tone
        large_shift = abs(formality_shift) > 0.25
        
        preserved = not (tone_changed and large_shift)
        
        # Determine risk level
        risk_level = self._compute_risk_level(
            tone_changed, 
            formality_shift,
            orig_analysis.detected_tone
        )
        
        return ToneValidationResult(
            preserved=preserved,
            original_tone=orig_analysis.detected_tone,
            proposed_tone=prop_analysis.detected_tone,
            formality_shift=formality_shift,
            risk_level=risk_level
        )
    
    def _count_matches(self, text: str, patterns: list) -> int:
        """Count total matches for a list of patterns."""
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, text, re.IGNORECASE))
        return count
    
    def _calculate_formality(self, text: str, indicators: Dict[str, int]) -> float:
        """
        Calculate formality score from 0.0 (very casual) to 1.0 (very formal).
        """
        # Base score
        score = 0.5
        
        # Adjust based on indicators
        formal_weight = indicators.get("formal", 0) * 0.1
        academic_weight = indicators.get("academic", 0) * 0.08
        professional_weight = indicators.get("professional", 0) * 0.05
        casual_weight = indicators.get("casual", 0) * 0.12
        
        score += formal_weight + academic_weight + professional_weight
        score -= casual_weight
        
        # Check for contractions (reduces formality)
        contractions = len(re.findall(r"(?:n't|'ll|'ve|'re|'d|'s)\b", text))
        score -= contractions * 0.03
        
        # Check for passive voice (increases formality)
        passive = len(re.findall(r'\b(?:is|are|was|were|been|being)\s+\w+ed\b', text))
        score += passive * 0.02
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))
    
    def _determine_tone(
        self, 
        indicators: Dict[str, int], 
        text_length: int
    ) -> Tuple[str, float]:
        """
        Determine the dominant tone and confidence.
        """
        if text_length < 20:
            return "neutral", 0.3
        
        total_indicators = sum(indicators.values())
        
        if total_indicators == 0:
            return "neutral", 0.5
        
        # Find dominant tone
        max_tone = max(indicators, key=indicators.get)
        max_count = indicators[max_tone]
        
        # Calculate confidence based on dominance
        confidence = min(0.95, (max_count / max(total_indicators, 1)) * 0.7 + 0.3)
        
        # If no clear winner, return neutral
        if max_count < 2:
            return "neutral", 0.4
        
        return max_tone, confidence
    
    def _compute_risk_level(
        self, 
        tone_changed: bool, 
        formality_shift: float,
        original_tone: str
    ) -> str:
        """
        Compute risk level based on tone shift.
        
        HIGH: Formal -> Casual (inappropriate casualization)
        LOW: Other tone shifts
        NONE: No significant shift
        """
        # Large shift from formal to casual = high risk
        if original_tone in ("formal", "academic") and formality_shift < -0.25:
            return "high"
        
        # Any tone change with significant shift = low risk
        if tone_changed and abs(formality_shift) > 0.15:
            return "low"
        
        # Large formality shift without tone change = low risk
        if abs(formality_shift) > 0.30:
            return "low"
        
        return "none"
