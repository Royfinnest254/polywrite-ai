"""
AI PROMPTING LAYER: Anthropic Claude Provider

Production-grade AI proposal generation using Claude 3.5 Sonnet.

WHY CLAUDE 3.5 SONNET:
1. Excellent instruction following (respects constraints precisely)
2. Low hallucination rate (critical for meaning preservation)
3. Reliable structured output (JSON)
4. Strong safety training (won't override explicit limits)

CORE PRINCIPLE:
The AI has ZERO authority. It only proposes text.
The AI is a junior editor making a suggested revision for approval.

WHAT CLAUDE MUST NOT KNOW:
- Similarity thresholds
- That it's being audited
- That semantic validation exists
- Prior proposals or user history

The AI must be BLIND to governance layers.
"""

import json
from typing import Literal

from ..config import get_settings
from .ai_provider import AIProvider, AIProposal, AIProposalError, SanityChecker


# =============================================================================
# PRODUCTION PROMPT TEMPLATE (ACADEMICALLY RIGOROUS)
# =============================================================================

SYSTEM_INSTRUCTION = """You are a junior editor making a suggested revision for approval.
You have ZERO authority. You only propose text.

ABSOLUTE CONSTRAINTS (VIOLATING ANY = FAILURE):
1. Do NOT add new facts, claims, examples, or conclusions
2. Do NOT change the meaning of any statement
3. Do NOT expand scope beyond the provided text
4. Do NOT add explanations or commentary outside the JSON
5. Do NOT be creative unless the intent explicitly requests it
6. Do NOT use markdown formatting in the proposed text
7. Your output is a PROPOSAL that will be reviewed by humans

TASK:
Given the text and intent, produce a revised version that follows the intent
while strictly preserving all original meaning.

BEFORE OUTPUTTING, SILENTLY VERIFY:
- Did I add any new facts? (must be NO)
- Did I change the meaning? (must be NO)
- Did I expand the scope? (must be NO)
- Is my output roughly similar in length? (must be YES)

OUTPUT FORMAT (JSON only, no other text):
{"proposed_text": "your revised text here", "explanation_summary": "1-2 sentences describing what you changed"}"""


# =============================================================================
# INTENT MODIFIERS (EXPLICIT, AUDITABLE)
# =============================================================================

INTENT_MODIFIERS = {
    "rewrite": """INTENT: REWRITE
Improve flow, structure, and readability.
Preserve meaning EXACTLY.
Do not add new information.
Do not remove important details.
Stay as close as possible to the original wording.""",
    
    "humanize": """INTENT: HUMANIZE
Make the language sound natural and conversational.
Reduce stiffness WITHOUT becoming casual.
Maintain the original level of formality.
Do not add personality or opinions.
Do not alter facts or conclusions.""",
    
    "clarify": """INTENT: CLARIFY
Simplify phrasing WITHOUT simplifying ideas.
Make complex sentences more accessible.
Preserve all technical accuracy.
Do not dumb down the content.
Do not add explanatory examples unless present in original."""
}


# =============================================================================
# ANTHROPIC (CLAUDE) PROVIDER
# =============================================================================

class AnthropicProvider(AIProvider):
    """
    Production AI provider using Anthropic Claude.
    
    API ACCESS:
    - Key from: https://console.anthropic.com
    - Stored in: ANTHROPIC_API_KEY environment variable
    - Never hard-coded, never logged
    
    DATA SENT:
    - Highlighted text only
    - Explicit intent
    - Hard constraints
    
    DATA NEVER SENT:
    - User history
    - Full document
    - Prior proposals
    - Audit logs
    - Embeddings
    """
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        """
        Args:
            api_key: Anthropic API key (from environment)
            model: Model to use (default: claude-3-5-sonnet-20241022)
        """
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise AIProposalError(
                "Anthropic integration not available",
                internal_reason="anthropic package not installed"
            )
        
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.sanity_checker = SanityChecker()
    
    async def generate_proposal(
        self,
        text: str,
        intent: Literal["rewrite", "humanize", "clarify"]
    ) -> AIProposal:
        """
        Generate a proposal using Claude.
        
        Single request per proposal. No retries. No chaining.
        """
        # Build the prompt
        intent_modifier = INTENT_MODIFIERS.get(intent, INTENT_MODIFIERS["rewrite"])
        
        user_message = f"""{intent_modifier}

TEXT TO REVISE:
{text}

Remember: Output ONLY valid JSON with "proposed_text" and "explanation_summary" fields."""
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=SYSTEM_INSTRUCTION,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            # Extract response text
            response_text = response.content[0].text.strip()
            
            # Parse JSON
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                raise AIProposalError(
                    "AI returned invalid format. Please try again.",
                    internal_reason=f"JSON parse failed: {response_text[:200]}"
                )
            
            # Validate required fields
            if "proposed_text" not in result:
                raise AIProposalError(
                    "AI response missing required content.",
                    internal_reason="Missing proposed_text field"
                )
            
            if "explanation_summary" not in result:
                result["explanation_summary"] = "Minor edits for clarity."
            
            proposed_text = result["proposed_text"]
            explanation = result["explanation_summary"]
            
            # Run sanity checks
            self.sanity_checker.check(text, proposed_text, explanation)
            
            return AIProposal(
                proposed_text=proposed_text,
                explanation_summary=explanation
            )
            
        except AIProposalError:
            raise
        except Exception as e:
            raise AIProposalError(
                "AI proposal generation failed. Please try again.",
                internal_reason=f"Anthropic API error: {type(e).__name__}: {e}"
            )


# =============================================================================
# FAILURE MODE PROTECTIONS (EMBEDDED IN PROMPT DESIGN)
# =============================================================================
#
# | Failure Mode              | Protection                                    |
# |---------------------------|-----------------------------------------------|
# | Hallucinated facts        | "Do NOT add new facts, claims, or examples"  |
# | Over-rewriting            | "Stay as close as possible to original"      |
# | Tone drift                | "Maintain original level of formality"       |
# | Scope expansion           | "Do NOT expand scope beyond provided text"   |
# | "Helpful" creativity      | "Do NOT be creative unless intent requests"  |
# | Ignoring constraints      | Silent self-check clause                     |
# | Returning explanations    | "Output ONLY valid JSON"                     |
#
# Post-AI sanity checks catch anything that slips through.
# Semantic validation layer provides independent verification.
# Decision logic enforces final safety based on drift score.
# =============================================================================
