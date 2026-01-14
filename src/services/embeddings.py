"""
PHASE 7: Embeddings Provider

Vector embeddings for semantic similarity computation.

CORE PRINCIPLE:
Embeddings are ephemeral measurements, not data assets.
- Use the SAME embedding model for both texts
- Do NOT fine-tune, cache, persist, or train
- Embeddings are computed fresh each time

This module provides:
- Abstract EmbeddingsProvider interface
- PlaceholderEmbeddingsProvider for testing
- OpenAIEmbeddingsProvider for production
- Factory function to get configured provider
"""

from abc import ABC, abstractmethod
from typing import List
import math

from ..config import get_settings


# =============================================================================
# EXCEPTIONS
# =============================================================================

class EmbeddingsError(Exception):
    """
    Raised when embeddings computation fails.
    
    Contains a user-safe message (no internal details exposed).
    """
    def __init__(self, message: str, internal_reason: str = ""):
        self.message = message
        self.internal_reason = internal_reason
        super().__init__(message)


# =============================================================================
# ABSTRACT EMBEDDINGS PROVIDER
# =============================================================================

class EmbeddingsProvider(ABC):
    """
    Abstract base class for embeddings providers.
    
    All providers must implement get_embedding() and inherit
    the cosine similarity computation.
    """
    
    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """
        Get the embedding vector for a piece of text.
        
        Args:
            text: The text to embed
        
        Returns:
            A list of floats representing the embedding vector
            
        Raises:
            EmbeddingsError: If embedding fails
        """
        pass
    
    async def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two pieces of text.
        
        Returns a value between 0 and 1:
        - 1.0 = identical meaning
        - 0.0 = completely different meaning
        
        Uses the SAME embedding model for both texts (required).
        """
        # Validate inputs
        if not text1 or not text1.strip():
            raise EmbeddingsError(
                "Cannot compute similarity: original text is empty",
                internal_reason="Empty text1"
            )
        if not text2 or not text2.strip():
            raise EmbeddingsError(
                "Cannot compute similarity: proposed text is empty",
                internal_reason="Empty text2"
            )
        
        # Get embeddings (SAME model for both)
        emb1 = await self.get_embedding(text1)
        emb2 = await self.get_embedding(text2)
        
        return self._cosine_similarity(emb1, emb2)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Returns value in [0, 1] range.
        """
        if len(vec1) != len(vec2):
            raise EmbeddingsError(
                "Embedding dimension mismatch",
                internal_reason=f"Dimensions: {len(vec1)} vs {len(vec2)}"
            )
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        similarity = dot_product / (magnitude1 * magnitude2)
        
        # Clamp to [0, 1] range (cosine can be negative for opposing vectors)
        return max(0.0, min(1.0, similarity))


# =============================================================================
# PLACEHOLDER PROVIDER (FOR TESTING)
# =============================================================================

class PlaceholderEmbeddingsProvider(EmbeddingsProvider):
    """
    Placeholder embeddings provider for testing without API calls.
    
    Uses character-based hashing to generate deterministic embeddings.
    NOT semantically meaningful, but provides consistent behavior.
    
    Properties:
    - Identical text → identical embedding → similarity 1.0
    - Similar text → similar embedding → high similarity
    - Different text → different embedding → lower similarity
    """
    
    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        Generate a placeholder embedding based on character frequencies.
        
        Deterministic: same text always produces same embedding.
        """
        if not text or not text.strip():
            raise EmbeddingsError(
                "Cannot embed empty text",
                internal_reason="Empty input to get_embedding"
            )
        
        # Normalize text
        text = text.lower().strip()
        
        # Create embedding based on character n-grams
        embedding = [0.0] * self.dimensions
        
        for i, char in enumerate(text):
            # Hash each character with its position
            idx = (ord(char) + i * 7) % self.dimensions
            embedding[idx] += 1.0
        
        # Add bigram information for better similarity detection
        for i in range(len(text) - 1):
            bigram = text[i:i+2]
            idx = (hash(bigram) % self.dimensions)
            embedding[idx] += 0.5
        
        # Add trigram for even better context
        for i in range(len(text) - 2):
            trigram = text[i:i+3]
            idx = (hash(trigram) % self.dimensions)
            embedding[idx] += 0.25
        
        # Normalize the vector
        magnitude = math.sqrt(sum(x * x for x in embedding))
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding


# =============================================================================
# OPENAI PROVIDER (PRODUCTION)
# =============================================================================

class OpenAIEmbeddingsProvider(EmbeddingsProvider):
    """
    Production embeddings provider using OpenAI API.
    
    Uses text-embedding-3-small by default (efficient, high quality).
    """
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        """
        Args:
            api_key: OpenAI API key
            model: Embeddings model (default: text-embedding-3-small)
        """
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise EmbeddingsError(
                "OpenAI integration not available",
                internal_reason="openai package not installed"
            )
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding from OpenAI API."""
        if not text or not text.strip():
            raise EmbeddingsError(
                "Cannot embed empty text",
                internal_reason="Empty input to get_embedding"
            )
        
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text.strip()
            )
            return response.data[0].embedding
            
        except Exception as e:
            raise EmbeddingsError(
                "Failed to compute text embedding. Please try again.",
                internal_reason=f"OpenAI API error: {type(e).__name__}: {e}"
            )


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_embeddings_provider() -> EmbeddingsProvider:
    """
    Get the configured embeddings provider based on settings.
    
    Uses AI_PROVIDER environment variable:
    - "placeholder": PlaceholderEmbeddingsProvider (default, for testing)
    - "openai": OpenAIEmbeddingsProvider (production)
    """
    settings = get_settings()
    
    # Explicit configuration supercedes AI_PROVIDER inference
    if settings.embeddings_provider == "openai":
        if not settings.openai_api_key:
             # Fallback to placeholder if explicit OpenAI requested but no key (safety)
             # or raise Error. Better to raise error if explicitly requested.
            raise EmbeddingsError(
                "OpenAI Embeddings configured but API key is missing",
                internal_reason="OPENAI_API_KEY not set"
            )
        return OpenAIEmbeddingsProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embeddings_model
        )
        
    if settings.embeddings_provider == "placeholder":
        return PlaceholderEmbeddingsProvider()

    # Legacy/Default behavior based on main provider
    if settings.ai_provider == "openai":
        return OpenAIEmbeddingsProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embeddings_model
        )
    
    # Default to placeholder
    return PlaceholderEmbeddingsProvider()
