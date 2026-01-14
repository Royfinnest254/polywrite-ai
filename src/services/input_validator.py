"""
PHASE 5: Input Validation Service

This is the GATE before any AI call. It guarantees:
- No empty or whitespace-only input
- No inputs below minimum length (20 chars)
- No inputs above maximum length (1800 chars)
- Only valid intents (rewrite, humanize, clarify)
- No full-document processing attempts

If ANY condition fails → block with clear, human-readable error.
"""

from typing import Literal
import re


# =============================================================================
# CONSTANTS (DO NOT CHANGE WITHOUT DISCUSSION)
# =============================================================================

MIN_TEXT_LENGTH = 20
MAX_TEXT_LENGTH = 1800
ALLOWED_INTENTS = frozenset(["rewrite", "humanize", "clarify"])

# Heuristics for full-document detection
MAX_NEWLINES = 50  # Excessive newlines indicate document
BIBLIOGRAPHY_PATTERNS = [
    r"\[\d+\]",  # [1], [2], etc.
    r"^\s*References\s*$",
    r"^\s*Bibliography\s*$",
    r"^\s*Works Cited\s*$",
]


# =============================================================================
# EXCEPTION CLASS
# =============================================================================

class InputValidationError(Exception):
    """
    Raised when input fails validation.
    
    Contains a human-readable message suitable for returning to the user.
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# =============================================================================
# INPUT VALIDATOR SERVICE
# =============================================================================

class InputValidator:
    """
    Validates user input BEFORE any AI processing occurs.
    
    This is a GATE, not intelligence. It enforces strict rules
    to ensure predictable costs and semantic validation accuracy.
    """
    
    def validate(
        self, 
        selected_text: str, 
        intent: str
    ) -> None:
        """
        Validate both selected_text and intent.
        
        Raises InputValidationError if any validation fails.
        Returns None if all validations pass.
        
        Execution order:
        1. Intent validation (fail fast on invalid intent)
        2. Presence check (not empty)
        3. Whitespace check
        4. Minimum length
        5. Maximum length
        6. Full-document detection
        """
        self._validate_intent(intent)
        self._validate_presence(selected_text)
        self._validate_not_whitespace_only(selected_text)
        self._validate_min_length(selected_text)
        self._validate_max_length(selected_text)
        self._detect_document_patterns(selected_text)
    
    def _validate_intent(self, intent: str) -> None:
        """Validate that intent is one of the allowed values."""
        if not intent:
            raise InputValidationError(
                "Please specify what you want to do: rewrite, humanize, or clarify."
            )
        
        if intent not in ALLOWED_INTENTS:
            raise InputValidationError(
                f"Unknown intent '{intent}'. "
                f"Please choose: rewrite, humanize, or clarify."
            )
    
    def _validate_presence(self, text: str) -> None:
        """Validate that text is present (not empty)."""
        if not text:
            raise InputValidationError(
                "No text selected. Please highlight the text you want to modify."
            )
    
    def _validate_not_whitespace_only(self, text: str) -> None:
        """Validate that text is not whitespace only."""
        if text.strip() == "":
            raise InputValidationError(
                "Selected text contains only whitespace. "
                "Please select actual text content."
            )
    
    def _validate_min_length(self, text: str) -> None:
        """Validate minimum text length."""
        # Use stripped length for meaningful content
        stripped = text.strip()
        if len(stripped) < MIN_TEXT_LENGTH:
            raise InputValidationError(
                f"Selected text is too short ({len(stripped)} characters). "
                f"Minimum is {MIN_TEXT_LENGTH} characters. "
                "Please select a more complete passage."
            )
    
    def _validate_max_length(self, text: str) -> None:
        """
        Validate maximum text length.
        
        HARD LIMIT: 1800 characters.
        No chunking. No truncation. No warnings. Hard stop.
        """
        if len(text) > MAX_TEXT_LENGTH:
            raise InputValidationError(
                f"Selected text is too long ({len(text)} characters). "
                f"Maximum is {MAX_TEXT_LENGTH} characters. "
                "PolyWrite works on selected passages. "
                "Please highlight a specific section."
            )
    
    def _detect_document_patterns(self, text: str) -> None:
        """
        Detect if input appears to be a full document section.
        
        Current heuristics:
        - Excessive newlines (>50)
        - Bibliography-like patterns
        
        This is intentionally basic for MVP.
        """
        # Check for excessive newlines
        newline_count = text.count('\n')
        if newline_count > MAX_NEWLINES:
            raise InputValidationError(
                "Input appears to be a full document section. "
                "PolyWrite works on selected passages. "
                "Please highlight a specific section to modify."
            )
        
        # Check for bibliography patterns (basic heuristic)
        for pattern in BIBLIOGRAPHY_PATTERNS:
            if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
                # Only reject if combined with length > 500
                # (a single [1] citation is fine)
                if len(text) > 500:
                    raise InputValidationError(
                        "Input appears to contain references or bibliography. "
                        "PolyWrite works on prose passages. "
                        "Please select the text you want to modify, "
                        "excluding reference lists."
                    )
                break
