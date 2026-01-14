"""
AI PROMPTING LAYER: DeepSeek Provider

Production-grade AI proposal generation using DeepSeek models (OpenAI-compatible).
"""

import json
from typing import Literal
from ..config import get_settings
from .ai_provider import AIProvider, AIProposal, AIProposalError, SanityChecker, SYSTEM_INSTRUCTION, INTENT_MODIFIERS

class DeepSeekProvider(AIProvider):
    """
    Production AI provider using DeepSeek (via OpenAI SDK).
    
    API ACCESS:
    - Key from: DeepSeek Platform
    - Base URL: https://api.deepseek.com
    - Stored in: DEEPSEEK_API_KEY environment variable
    """
    
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        """
        Args:
            api_key: DeepSeek API key
            model: Model to use (default: deepseek-chat)
        """
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise AIProposalError(
                "OpenAI SDK integration not available",
                internal_reason="openai package not installed (required for DeepSeek)"
            )
        
        # Configure client for DeepSeek
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = model
        self.sanity_checker = SanityChecker()
    
    async def generate_proposal(
        self, 
        text: str, 
        intent: Literal["rewrite", "humanize", "clarify"]
    ) -> AIProposal:
        """Generate a proposal using DeepSeek."""
        
        # Build the user message with intent modifier
        intent_modifier = INTENT_MODIFIERS.get(intent, "")
        user_message = f"{intent_modifier}\n\nText to edit:\n\n{text}"
        
        try:
            # DeepSeek supports JSON mode via response_format={'type': 'json_object'}
            # Reference: https://api-docs.deepseek.com/guides/json_mode
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
                internal_reason=f"DeepSeek API error: {type(e).__name__}: {e}"
            )
