"""
Entity Preservation Validator

Extracts and validates critical entities (numbers, dates, proper nouns, citations)
to prevent factual drift even when embedding similarity is high.

WHITE PAPER REFERENCE: Section 4.4

PROBLEM SOLVED:
- Original: "In 2020, 50% of users reported..."
- Proposed: "In 2021, 60% of users reported..."
- Embedding similarity: 0.92 (HIGH)
- BUT factual content changed!

This validator catches what embeddings miss.
"""

import re
from typing import List, Dict, Set
from dataclasses import dataclass, field


@dataclass
class EntityExtractionResult:
    """Result of entity extraction from text."""
    numbers: List[str] = field(default_factory=list)
    percentages: List[str] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    years: List[str] = field(default_factory=list)
    proper_nouns: List[str] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    
    def all_entities(self) -> Set[str]:
        """Get all entities as a set for comparison."""
        all_items = (
            self.numbers + 
            self.percentages + 
            self.dates + 
            self.years + 
            self.proper_nouns + 
            self.citations
        )
        return set(all_items)


@dataclass
class EntityValidationResult:
    """Result of entity preservation validation."""
    preserved: bool
    missing: List[str] = field(default_factory=list)
    added: List[str] = field(default_factory=list)
    changed_numbers: List[Dict[str, str]] = field(default_factory=list)
    risk_level: str = "none"  # none, low, high
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "preserved": self.preserved,
            "missing": self.missing,
            "added": self.added,
            "changed_numbers": self.changed_numbers,
            "risk_level": self.risk_level
        }


class EntityValidator:
    """
    Validates that critical entities are preserved between original and proposed text.
    
    ENTITY TYPES:
    1. Numbers (including decimals): 50, 3.14, 1000
    2. Percentages: 50%, 3.5%
    3. Dates: January 15, 2024, 01/15/2024
    4. Years: 2020, 2024
    5. Proper nouns: Names, organizations (capitalized words)
    6. Citations: (Smith, 2020), [1], [citation needed]
    
    VALIDATION LOGIC:
    - Missing critical entities → HIGH RISK
    - Added entities → LOW RISK (might be hallucination)
    - Numbers changed → HIGH RISK
    """
    
    # Regex patterns for entity extraction
    PATTERNS = {
        # Numbers with optional decimals (but not part of percentages)
        "numbers": r'\b\d+(?:\.\d+)?(?!\s*%)\b',
        
        # Percentages
        "percentages": r'\b\d+(?:\.\d+)?\s*%',
        
        # Full dates: Jan 15, 2024 or January 15, 2024 or 01/15/2024
        "dates": r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        
        # Years: 4-digit numbers that look like years (1900-2099)
        "years": r'\b(?:19|20)\d{2}\b',
        
        # Citations: (Author, Year) or [1] or [citation needed]
        "citations": r'\([A-Z][a-z]+(?:\s+(?:et\s+al\.?|&|and)\s+[A-Z][a-z]+)?,?\s*\d{4}\)|\[\d+\]|\[citation\s+needed\]',
        
        # Proper nouns: Capitalized words (2+ chars) not at sentence start
        # This is a simplified heuristic
        "proper_nouns": r'(?<=[.!?]\s)[A-Z][a-z]{2,}|(?<=\s)[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]+)*',
    }
    
    def extract_entities(self, text: str) -> EntityExtractionResult:
        """
        Extract all entities from text.
        
        Args:
            text: The text to extract entities from
            
        Returns:
            EntityExtractionResult with all extracted entities
        """
        if not text or not text.strip():
            return EntityExtractionResult()
        
        result = EntityExtractionResult()
        
        # Extract each entity type
        result.percentages = re.findall(self.PATTERNS["percentages"], text)
        result.numbers = re.findall(self.PATTERNS["numbers"], text)
        result.dates = re.findall(self.PATTERNS["dates"], text, re.IGNORECASE)
        result.years = re.findall(self.PATTERNS["years"], text)
        result.citations = re.findall(self.PATTERNS["citations"], text)
        
        # Proper nouns - more careful extraction
        # Exclude common words that might be capitalized
        common_words = {
            "The", "This", "That", "These", "Those", "It", "They", "We", "You",
            "However", "Therefore", "Furthermore", "Moreover", "Although",
            "Because", "While", "When", "Where", "What", "Which", "Who",
            "Also", "But", "And", "Or", "So", "Yet", "For", "Nor"
        }
        
        proper_noun_matches = re.findall(self.PATTERNS["proper_nouns"], text)
        result.proper_nouns = [
            pn for pn in proper_noun_matches 
            if pn not in common_words and len(pn) > 2
        ]
        
        return result
    
    def validate(
        self, 
        original_text: str, 
        proposed_text: str
    ) -> EntityValidationResult:
        """
        Validate that entities are preserved between original and proposed text.
        
        Args:
            original_text: The original user text
            proposed_text: The AI-proposed rewrite
            
        Returns:
            EntityValidationResult with preservation status
        """
        orig_entities = self.extract_entities(original_text)
        prop_entities = self.extract_entities(proposed_text)
        
        orig_set = orig_entities.all_entities()
        prop_set = prop_entities.all_entities()
        
        # Find missing and added entities
        missing = list(orig_set - prop_set)
        added = list(prop_set - orig_set)
        
        # Check for changed numbers (same count but different values)
        changed_numbers = self._detect_number_changes(
            orig_entities.numbers + orig_entities.percentages,
            prop_entities.numbers + prop_entities.percentages
        )
        
        # Determine risk level
        risk_level = self._compute_risk_level(missing, added, changed_numbers)
        
        # Preserved if no missing critical entities and no number changes
        preserved = (
            len(missing) == 0 and 
            len(changed_numbers) == 0 and
            # Allow added entities (might be clarification) but flag high additions
            len(added) <= 2
        )
        
        return EntityValidationResult(
            preserved=preserved,
            missing=missing,
            added=added,
            changed_numbers=changed_numbers,
            risk_level=risk_level
        )
    
    def _detect_number_changes(
        self, 
        orig_numbers: List[str], 
        prop_numbers: List[str]
    ) -> List[Dict[str, str]]:
        """
        Detect if numbers were changed (not just removed/added).
        
        Example: "50%" → "60%" is a change, not add/remove.
        """
        changes = []
        
        # If same count of numbers but different values, likely a change
        if len(orig_numbers) == len(prop_numbers) and len(orig_numbers) > 0:
            for orig, prop in zip(sorted(orig_numbers), sorted(prop_numbers)):
                if orig != prop:
                    changes.append({
                        "original": orig,
                        "proposed": prop,
                        "type": "number_change"
                    })
        
        return changes
    
    def _compute_risk_level(
        self, 
        missing: List[str], 
        added: List[str],
        changed_numbers: List[Dict]
    ) -> str:
        """
        Compute risk level based on entity changes.
        
        HIGH: Missing entities or changed numbers (factual drift)
        LOW: Added entities only (possible hallucination)
        NONE: No significant changes
        """
        # Any missing entities or changed numbers = HIGH risk
        if missing or changed_numbers:
            return "high"
        
        # Many added entities = LOW risk (suspicious additions)
        if len(added) > 2:
            return "low"
        
        return "none"
