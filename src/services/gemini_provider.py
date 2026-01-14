"""
AI PROMPTING LAYER: Google Gemini Provider

Production-grade AI proposal generation using Google Gemini models.
"""

import json
from typing import Literal
from ..config import get_settings
from .ai_provider import AIProvider, AIProposal, AIProposalError, SanityChecker, SYSTEM_INSTRUCTION, INTENT_MODIFIERS

class GeminiProvider(AIProvider):
    """
    Production AI provider using Google Gemini.
    
    API ACCESS:
    - Key from: Google AI Studio
    - Stored in: GEMINI_API_KEY environment variable
    """
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        """
        Args:
            api_key: Google API key
            model: Model to use (default: gemini-1.5-flash)
        """
        try:
            import google.generativeai as genai
        except ImportError:
            raise AIProposalError(
                "Google Generative AI integration not available",
                internal_reason="google-generativeai package not installed"
            )
        
        genai.configure(api_key=api_key)
        self.model_name = model
        self.sanity_checker = SanityChecker()
        
        # Configure model with generation config for JSON
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=SYSTEM_INSTRUCTION
        )
        
        self.generation_config = genai.GenerationConfig(
            temperature=0.3,
            response_mime_type="application/json"
        )
    
    async def generate_proposal(
        self,
        text: str,
        intent: Literal["rewrite", "humanize", "clarify"]
    ) -> AIProposal:
        """
        Generate a proposal using Gemini.
        """
        intent_modifier = INTENT_MODIFIERS.get(intent, INTENT_MODIFIERS["rewrite"])
        
        user_message = f"""{intent_modifier}

TEXT TO REVISE:
{text}

Remember: Output ONLY valid JSON with "proposed_text" and "explanation_summary" fields."""
        
        try:
            # Gemini async generation
            response = await self.model.generate_content_async(
                user_message,
                generation_config=self.generation_config
            )
            
            response_text = response.text
            
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
                internal_reason=f"Gemini API error: {type(e).__name__}: {e}"
            )
