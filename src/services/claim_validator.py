"""
Claim & Citation Validator

Detects factual claims in text and flags unsupported/uncited assertions.

WHITE PAPER REFERENCE: Section 4.6

PROBLEM SOLVED:
- AI can generate plausible-sounding facts that are false
- New factual claims without citations should be flagged
- Prevents fabrication of statistics, studies, causation claims

CLAIM TYPES DETECTED:
1. Statistics: "50% of users...", "3 million people..."
2. Causation: "X causes Y", "leads to", "results in"
3. Authority: "studies show", "research indicates", "experts say"
4. Temporal: "In 2020...", "since the 1990s..."
"""

import re
from typing import List, Dict
from dataclasses import dataclass, field


@dataclass
class Claim:
    """A factual claim detected in text."""
    text: str
    claim_type: str  # statistic, causation, authority, temporal
    needs_citation: bool = True
    has_citation: bool = False
    start_pos: int = 0
    end_pos: int = 0


@dataclass
class ClaimValidationResult:
    """Result of claim and citation validation."""
    claims_detected: List[Claim] = field(default_factory=list)
    uncited_claims: List[str] = field(default_factory=list)
    citation_count: int = 0
    risk_level: str = "none"  # none, low, high
    
    def to_dict(self) -> dict:
        return {
            "claims_detected": len(self.claims_detected),
            "uncited_claims": self.uncited_claims[:5],  # Limit for response
            "citation_count": self.citation_count,
            "risk_level": self.risk_level,
            "needs_review": len(self.uncited_claims) > 0
        }


class ClaimValidator:
    """
    Detects factual claims and validates citation requirements.
    
    DETECTION PATTERNS:
    1. Statistics: Numbers with context (%, million, etc.)
    2. Causation: Causal language patterns
    3. Authority: Appeals to research/experts
    4. Temporal: Time-bound assertions
    
    CITATION PATTERNS:
    - Academic: (Author, Year), (Author et al., Year)
    - Numeric: [1], [2,3], [1-5]
    - Inline: "according to [source]"
    """
    
    # Claim detection patterns
    CLAIM_PATTERNS = {
        "statistic": [
            r'\b\d+(?:\.\d+)?%\s+of\s+\w+',  # "50% of users"
            r'\b\d+(?:\.\d+)?\s*(?:million|billion|thousand)\b',  # "3 million"
            r'\b(?:approximately|about|nearly|over|under)\s+\d+',  # "approximately 500"
            r'\baverage(?:d|s)?\s+(?:of\s+)?\d+',  # "averaged 50"
        ],
        "causation": [
            r'\b(?:causes?|caused)\s+(?:a\s+)?(?:significant|major|minor)?\s*\w+',
            r'\b(?:leads?\s+to|led\s+to)\b',
            r'\b(?:results?\s+in|resulted\s+in)\b',
            r'\b(?:due\s+to|because\s+of)\b',
            r'\b(?:contributes?\s+to|contributed\s+to)\b',
            r'\b(?:associated\s+with)\b',
        ],
        "authority": [
            r'\b(?:studies?\s+(?:show|indicate|suggest|found|reveal))',
            r'\b(?:research\s+(?:shows?|indicates?|suggests?|found))',
            r'\b(?:according\s+to\s+(?:experts?|scientists?|researchers?))',
            r'\b(?:experts?\s+(?:say|believe|agree|suggest))',
            r'\b(?:it\s+(?:has\s+been|is)\s+(?:shown|proven|demonstrated))',
            r'\b(?:evidence\s+(?:shows?|suggests?|indicates?))',
        ],
        "temporal": [
            r'\b(?:since|from)\s+(?:the\s+)?\d{4}',  # "since 2020"
            r'\b(?:in|during)\s+(?:the\s+)?\d{4}',   # "in 2020"
            r'\bover\s+the\s+(?:past|last)\s+\d+\s+(?:years?|decades?|months?)',
        ],
    }
    
    # Citation patterns
    CITATION_PATTERNS = [
        r'\([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}\)',  # (Smith, 2020) or (Smith et al., 2020)
        r'\([A-Z][a-z]+\s+(?:&|and)\s+[A-Z][a-z]+,?\s*\d{4}\)',  # (Smith & Jones, 2020)
        r'\[\d+(?:[-,]\d+)*\]',  # [1] or [1,2] or [1-5]
        r'\[\d+(?:,\s*\d+)+\]',  # [1, 2, 3]
        r'(?:according\s+to|as\s+(?:stated|reported)\s+(?:by|in))\s+[A-Z]',  # according to Smith
    ]
    
    def extract_claims(self, text: str) -> List[Claim]:
        """
        Extract all factual claims from text.
        
        Returns list of Claim objects with type and position.
        """
        if not text or not text.strip():
            return []
        
        claims = []
        
        for claim_type, patterns in self.CLAIM_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Get surrounding context (up to 100 chars)
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()
                    
                    claims.append(Claim(
                        text=context,
                        claim_type=claim_type,
                        needs_citation=True,
                        start_pos=match.start(),
                        end_pos=match.end()
                    ))
        
        # Deduplicate overlapping claims
        claims = self._deduplicate_claims(claims)
        
        return claims
    
    def count_citations(self, text: str) -> int:
        """Count the number of citations in text."""
        if not text:
            return 0
        
        count = 0
        for pattern in self.CITATION_PATTERNS:
            count += len(re.findall(pattern, text))
        
        return count
    
    def validate(
        self, 
        original_text: str, 
        proposed_text: str
    ) -> ClaimValidationResult:
        """
        Validate claims and citations between original and proposed text.
        
        FLAGS:
        - New claims in proposed that weren't in original → needs citation
        - Claims without nearby citations → flagged
        - Removed citations from original → warning
        """
        orig_claims = self.extract_claims(original_text)
        prop_claims = self.extract_claims(proposed_text)
        
        orig_citations = self.count_citations(original_text)
        prop_citations = self.count_citations(proposed_text)
        
        # Find new claims in proposed text (not in original)
        orig_claim_texts = {c.text.lower()[:50] for c in orig_claims}
        new_claims = [
            c for c in prop_claims 
            if c.text.lower()[:50] not in orig_claim_texts
        ]
        
        # Check if new claims have citations nearby
        uncited_claims = []
        for claim in new_claims:
            # Check for citation within 200 chars of claim
            claim_region = proposed_text[
                max(0, claim.start_pos - 50):
                min(len(proposed_text), claim.end_pos + 200)
            ]
            
            has_citation = any(
                re.search(pattern, claim_region) 
                for pattern in self.CITATION_PATTERNS
            )
            
            if not has_citation:
                uncited_claims.append(claim.text[:80] + "...")
        
        # Determine risk level
        risk_level = self._compute_risk_level(
            new_claims, 
            uncited_claims, 
            orig_citations, 
            prop_citations
        )
        
        return ClaimValidationResult(
            claims_detected=prop_claims,
            uncited_claims=uncited_claims,
            citation_count=prop_citations,
            risk_level=risk_level
        )
    
    def _deduplicate_claims(self, claims: List[Claim]) -> List[Claim]:
        """Remove overlapping claims, keeping the longer one."""
        if not claims:
            return []
        
        # Sort by position
        claims.sort(key=lambda c: (c.start_pos, -c.end_pos))
        
        result = []
        last_end = -1
        
        for claim in claims:
            if claim.start_pos >= last_end:
                result.append(claim)
                last_end = claim.end_pos
        
        return result
    
    def _compute_risk_level(
        self, 
        new_claims: List[Claim],
        uncited_claims: List[str],
        orig_citations: int,
        prop_citations: int
    ) -> str:
        """
        Compute risk level based on claim/citation analysis.
        
        HIGH: Many new uncited claims (potential fabrication)
        LOW: Some new claims with citations, or citations removed
        NONE: No significant changes
        """
        # Many uncited new claims = high risk
        if len(uncited_claims) >= 3:
            return "high"
        
        # Some uncited claims = low risk
        if len(uncited_claims) >= 1:
            return "low"
        
        # Citations removed = low risk
        if prop_citations < orig_citations:
            return "low"
        
        return "none"
