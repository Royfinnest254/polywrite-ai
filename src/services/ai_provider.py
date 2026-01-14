"""
PHASE 6: AI Proposal Generation

Production-grade AI provider for conservative, meaning-preserving text proposals.

CORE PHILOSOPHY:
1. AI does not author text — it proposes edits
2. AI is never trusted — it is supervised
3. AI output must be explainable
4. Meaning preservation takes precedence over fluency
5. Human approval is always required

This module provides:
- Abstract AIProvider interface
- PlaceholderAIProvider for testing
- OpenAIProvider for production
- SanityChecker for post-AI validation
- Factory function to get configured provider
"""

from abc import ABC, abstractmethod
from typing import Literal
import json
import re

from ..models.schemas import AIProposal
from ..config import get_settings


# =============================================================================
# FIXED SYSTEM INSTRUCTION (NON-MODIFIABLE BY USERS)
# =============================================================================

SYSTEM_INSTRUCTION = """You are a professional editor, not an author.
Rewrite the provided text ONLY to improve clarity, readability, or tone.
Preserve the original meaning exactly.
Do NOT add new facts, claims, examples, or conclusions.
Do NOT remove important details.
Do NOT strengthen or weaken arguments.
Stay as close as possible to the original wording.
If uncertain, make minimal changes.

You MUST respond with valid JSON in this exact format:
{
  "proposed_text": "your rewritten text here",
  "explanation_summary": "1-2 sentences describing what you changed"
}"""


# =============================================================================
# INTENT MODIFIERS (LIMITED SCOPE)
# =============================================================================

INTENT_MODIFIERS = {
    "rewrite": "Improve flow and structure while preserving meaning exactly.",
    "humanize": "Make language sound natural and less stiff, without casualization. Maintain formality.",
    "clarify": "Simplify phrasing and sentence structure without simplifying ideas or removing nuance."
}


# =============================================================================
# EXCEPTIONS
# =============================================================================

class AIProposalError(Exception):
    """
    Raised when AI proposal generation fails.
    
    Contains a user-safe message (no internal details exposed).
    """
    def __init__(self, message: str, internal_reason: str = ""):
        self.message = message
        self.internal_reason = internal_reason  # For logging only
        super().__init__(message)


# =============================================================================
# POST-AI SANITY CHECKER
# =============================================================================

class SanityChecker:
    """
    Validates AI output BEFORE passing to semantic validation.
    
    These are basic structural checks, not semantic ones.
    """
    
    # Patterns that indicate structural changes
    STRUCTURAL_PATTERNS = [
        r'^\s*[-*•]\s',           # List items
        r'^\s*\d+\.\s',           # Numbered lists
        r'^#+\s',                   # Markdown headings
        r'\[\d+\]',                # Citations like [1]
        r'^\s*(?:References|Bibliography|Works Cited)\s*$',
    ]
    
    def __init__(self, max_length_expansion: float = 0.30):
        """
        Args:
            max_length_expansion: Maximum allowed length increase (default 30%)
        """
        self.max_length_expansion = max_length_expansion
    
    def check(self, original_text: str, proposed_text: str, explanation: str) -> None:
        """
        Run all sanity checks. Raises AIProposalError if any fail.
        """
        self._check_not_empty(proposed_text, explanation)
        self._check_length_expansion(original_text, proposed_text)
        self._check_no_structural_changes(original_text, proposed_text)
    
    def _check_not_empty(self, proposed_text: str, explanation: str) -> None:
        """Ensure output is not empty."""
        if not proposed_text or not proposed_text.strip():
            raise AIProposalError(
                "AI failed to generate a proposal. Please try again.",
                internal_reason="Empty proposed_text"
            )
        
        if not explanation or not explanation.strip():
            raise AIProposalError(
                "AI failed to explain the changes. Please try again.",
                internal_reason="Empty explanation_summary"
            )
    
    def _check_length_expansion(self, original: str, proposed: str) -> None:
        """Ensure proposal doesn't expand too much."""
        original_len = len(original)
        proposed_len = len(proposed)
        
        max_allowed = original_len * (1 + self.max_length_expansion)
        
        if proposed_len > max_allowed:
            raise AIProposalError(
                "The proposed rewrite is too long. Please try with a shorter selection.",
                internal_reason=f"Length expansion: {original_len} -> {proposed_len} (max: {max_allowed:.0f})"
            )
    
    def _check_no_structural_changes(self, original: str, proposed: str) -> None:
        """Ensure proposal doesn't introduce structural elements not in original."""
        # Only flag patterns that appear in proposed but NOT in original
        for pattern in self.STRUCTURAL_PATTERNS:
            original_has = bool(re.search(pattern, original, re.MULTILINE | re.IGNORECASE))
            proposed_has = bool(re.search(pattern, proposed, re.MULTILINE | re.IGNORECASE))
            
            if proposed_has and not original_has:
                raise AIProposalError(
                    "The proposal contains structural changes (lists, headings, etc.) "
                    "that were not in the original. Please try again.",
                    internal_reason=f"Structural pattern introduced: {pattern}"
                )


# =============================================================================
# ABSTRACT AI PROVIDER
# =============================================================================

class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    @abstractmethod
    async def generate_proposal(
        self, 
        text: str, 
        intent: Literal["rewrite", "humanize", "clarify"]
    ) -> AIProposal:
        """
        Generate a proposed rewrite of the given text.
        
        CORE PRINCIPLE: AI NEVER overwrites text.
        This returns a PROPOSAL that must be validated and approved.
        
        Args:
            text: The original user-selected text
            intent: What the user wants to do
        
        Returns:
            AIProposal with proposed_text and explanation_summary
            
        Raises:
            AIProposalError: If generation fails or sanity checks fail
        """
        pass


# =============================================================================
# PLACEHOLDER PROVIDER (FOR TESTING)
# =============================================================================

class PlaceholderAIProvider(AIProvider):
    """
    Placeholder AI provider for testing without API calls.
    
    Returns deterministic, conservative rewrites.
    """
    
    def __init__(self):
        self.sanity_checker = SanityChecker()
    
    async def generate_proposal(
        self, 
        text: str, 
        intent: Literal["rewrite", "humanize", "clarify"]
    ) -> AIProposal:
        """Generate a placeholder proposal."""
        
        if intent == "rewrite":
            proposed = self._simulate_rewrite(text)
            explanation = "Improved clarity and flow while preserving the original meaning."
        elif intent == "humanize":
            proposed = self._simulate_humanize(text)
            explanation = "Made the text sound more natural while maintaining formality."
        else:  # clarify
            proposed = self._simulate_clarify(text)
            explanation = "Simplified sentence structure without changing the ideas."
        
        # Run sanity checks
        self.sanity_checker.check(text, proposed, explanation)
        
        return AIProposal(
            proposed_text=proposed,
            explanation_summary=explanation
        )
    
    def _simulate_rewrite(self, text: str) -> str:
        """Simulate a conservative rewrite."""
        # Remove filler words
        fillers = [
            ("very ", ""),
            ("really ", ""),
            ("just ", ""),
            ("actually ", ""),
            ("basically ", ""),
        ]
        
        result = text
        changes_made = 0
        
        for old, new in fillers:
            if old in result.lower() and changes_made < 2:
                # Case-insensitive replace
                import re
                result = re.sub(re.escape(old), new, result, count=1, flags=re.IGNORECASE)
                changes_made += 1
        
        # If no changes made, make a minimal structural change
        if result == text:
            # Split into sentences and slightly restructure
            sentences = text.split('. ')
            if len(sentences) > 1:
                # Just clean up spacing
                result = '. '.join(s.strip() for s in sentences if s.strip())
                if not result.endswith('.'):
                    result += '.'
        
        return result if result != text else text
    
    def _simulate_humanize(self, text: str) -> str:
        """Simulate humanization (conservative)."""
        # Replace formal connectors with slightly less formal ones
        replacements = [
            ("Furthermore,", "Also,"),
            ("Moreover,", "Additionally,"),
            ("Therefore,", "So,"),
            ("However,", "But,"),
            ("Nevertheless,", "Still,"),
        ]
        
        result = text
        for old, new in replacements:
            if old in result:
                result = result.replace(old, new, 1)
                break
        
        return result
    
    def _simulate_clarify(self, text: str) -> str:
        """Simulate clarification (conservative)."""
        # Simplify overly complex phrases
        simplifications = [
            ("in order to", "to"),
            ("due to the fact that", "because"),
            ("at this point in time", "now"),
            ("in the event that", "if"),
            ("with regard to", "about"),
        ]
        
        result = text
        for old, new in simplifications:
            if old.lower() in result.lower():
                import re
                result = re.sub(re.escape(old), new, result, count=1, flags=re.IGNORECASE)
                break
        
        return result


# =============================================================================
# OPENAI PROVIDER (PRODUCTION)
# =============================================================================

class OpenAIProvider(AIProvider):
    """
    Production AI provider using OpenAI API.
    
    Uses structured JSON output for reliable parsing.
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Args:
            api_key: OpenAI API key
            model: Model to use (default: gpt-4o-mini)
        """
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise AIProposalError(
                "OpenAI integration not available. Please install: pip install openai",
                internal_reason="openai package not installed"
            )
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.sanity_checker = SanityChecker()
    
    async def generate_proposal(
        self, 
        text: str, 
        intent: Literal["rewrite", "humanize", "clarify"]
    ) -> AIProposal:
        """Generate a proposal using OpenAI."""
        
        # Build the user message with intent modifier
        intent_modifier = INTENT_MODIFIERS.get(intent, "")
        user_message = f"{intent_modifier}\n\nText to edit:\n\n{text}"
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # Low temperature for conservative output
                max_tokens=2000
            )
            
            # Parse response
            content = response.choices[0].message.content
            if not content:
                raise AIProposalError(
                    "AI returned an empty response. Please try again.",
                    internal_reason="Empty API response"
                )
            
            try:
                result = json.loads(content)
            except json.JSONDecodeError as e:
                raise AIProposalError(
                    "AI returned an invalid response. Please try again.",
                    internal_reason=f"JSON parse error: {e}"
                )
            
            # Extract fields
            proposed_text = result.get("proposed_text", "")
            explanation = result.get("explanation_summary", "")
            
            # Run sanity checks
            self.sanity_checker.check(text, proposed_text, explanation)
            
            return AIProposal(
                proposed_text=proposed_text,
                explanation_summary=explanation
            )
            
        except AIProposalError:
            raise  # Re-raise our own errors
        except Exception as e:
            # Catch all other errors (API errors, network errors, etc.)
            raise AIProposalError(
                "Failed to generate proposal. Please try again later.",
                internal_reason=f"OpenAI API error: {type(e).__name__}: {e}"
            )


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_ai_provider() -> AIProvider:
    """
    Get the configured AI provider based on settings.
    
    Uses AI_PROVIDER environment variable:
    - "placeholder": PlaceholderAIProvider (default, for testing)
    - "openai": OpenAIProvider (GPT-4)
    - "anthropic": AnthropicProvider (Claude - recommended)
    """
    settings = get_settings()
    
    if settings.ai_provider == "deepseek":
        if not settings.deepseek_api_key:
            raise AIProposalError(
                "DeepSeek is configured but API key is missing.",
                internal_reason="DEEPSEEK_API_KEY not set"
            )
        from .deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model
        )

    if settings.ai_provider == "gemini":
        if not settings.gemini_api_key:
            raise AIProposalError(
                "Gemini is configured but API key is missing.",
                internal_reason="GEMINI_API_KEY not set"
            )
        from .gemini_provider import GeminiProvider
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model
        )

    if settings.ai_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise AIProposalError(
                "Anthropic is configured but API key is missing.",
                internal_reason="ANTHROPIC_API_KEY not set"
            )
        # Import here to avoid circular imports
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model
        )
    
    if settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise AIProposalError(
                "OpenAI is configured but API key is missing.",
                internal_reason="OPENAI_API_KEY not set"
            )
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model
        )
    
    # Default to placeholder
    return PlaceholderAIProvider()

