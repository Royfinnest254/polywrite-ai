"""
STRICT SEMANTIC VALIDATION TESTS

Verifies the Semantic Meaning Validator (SMV) behaves as a STRICT SENSOR.
Thresholds:
- SAFE: >= 0.80
- RISKY: 0.60 <= x < 0.80
- DANGEROUS: < 0.60

These tests use a Mock Embeddings Provider to ensure DETERMINISTIC scores.
We define input pairs and FORCE specific similarity scores to verify the classification logic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.semantic import SemanticValidator, SemanticValidationError
from src.services.embeddings import EmbeddingsProvider
from src.models.schemas import SemanticResult
from src.config import get_settings


class MockEmbeddingsProvider(EmbeddingsProvider):
    """
    Mock provider that returns pre-determined scores.
    This guarantees DETERMINISTIC testing of the threshold logic.
    """
    def __init__(self):
        self.score_map = {}

    def set_score(self, original: str, proposed: str, score: float):
        self.score_map[(original, proposed)] = score

    async def compute_similarity(self, text1: str, text2: str) -> float:
        return self.score_map.get((text1, text2), 0.0)
        
    async def get_embedding(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]  # Dummy


@pytest.fixture
def validator():
    provider = MockEmbeddingsProvider()
    return SemanticValidator(provider), provider


@pytest.mark.asyncio
async def test_pure_paraphrase_safe(validator):
    """
    Test 1: Pure paraphrase (High similarity) -> SAFE
    Expectation: Score >= 0.80
    """
    smv, provider = validator
    
    original = "The system is functioning normally."
    proposed = "The system is operating as expected."
    
    # Force a score of 0.85 (SAFE)
    provider.set_score(original, proposed, 0.85)
    
    result = await smv.validate(original, proposed)
    
    assert result.similarity_score == 0.85
    assert result.risk_label == "safe"


@pytest.mark.asyncio
async def test_tone_strengthening_risky(validator):
    """
    Test 2: Tone strengthening (Moderate similarity) -> RISKY
    Expectation: 0.60 <= Score < 0.80
    """
    smv, provider = validator
    
    original = "This approach might work."
    proposed = "This approach will almost certainly work."
    
    # Force a score of 0.70 (RISKY)
    # Note: With old thresholds (0.75), this would be RISKY.
    # With new thresholds (0.80), this is STILL RISKY.
    provider.set_score(original, proposed, 0.70)
    
    result = await smv.validate(original, proposed)
    
    assert result.similarity_score == 0.70
    assert result.risk_label == "risky"


@pytest.mark.asyncio
async def test_meaning_reversal_dangerous(validator):
    """
    Test 3: Meaning reversal (Low similarity) -> DANGEROUS
    Expectation: Score < 0.60
    """
    smv, provider = validator
    
    original = "We should proceed with the launch."
    proposed = "We should abort the launch."
    
    # Force a score of 0.20 (DANGEROUS)
    provider.set_score(original, proposed, 0.20)
    
    result = await smv.validate(original, proposed)
    
    assert result.similarity_score == 0.20
    assert result.risk_label == "dangerous"


@pytest.mark.asyncio
async def test_boundary_conditions(validator):
    """
    Test exact boundary conditions to verify strict inequalities.
    """
    smv, provider = validator
    
    # EDGE CASE 1: Exactly 0.80 -> SAFE
    t1_orig, t1_prop = "A", "A_Safe"
    provider.set_score(t1_orig, t1_prop, 0.80)
    res1 = await smv.validate(t1_orig, t1_prop)
    assert res1.risk_label == "safe"
    
    # EDGE CASE 2: Exactly 0.79 -> RISKY
    t2_orig, t2_prop = "B", "B_Risky"
    provider.set_score(t2_orig, t2_prop, 0.79)
    res2 = await smv.validate(t2_orig, t2_prop)
    assert res2.risk_label == "risky"
    
    # EDGE CASE 3: Exactly 0.60 -> RISKY
    t3_orig, t3_prop = "C", "C_Risky"
    provider.set_score(t3_orig, t3_prop, 0.60)
    res3 = await smv.validate(t3_orig, t3_prop)
    assert res3.risk_label == "risky"
    
    # EDGE CASE 4: Exactly 0.59 -> DANGEROUS
    t4_orig, t4_prop = "D", "D_Dangerous"
    provider.set_score(t4_orig, t4_prop, 0.59)
    res4 = await smv.validate(t4_orig, t4_prop)
    assert res4.risk_label == "dangerous"


@pytest.mark.asyncio
async def test_failure_modes_prevented(validator):
    """
    Verify strict "Sensor" behavior against specific failure modes via scores.
    """
    smv, provider = validator
    
    original = "Text"
    
    # Scope Expansion -> Low Similarity -> Dangerous
    provider.set_score(original, "Text plus unrelated concepts", 0.55)
    res = await smv.validate(original, "Text plus unrelated concepts")
    assert res.risk_label == "dangerous"
    
    # Certainty Inflation -> Moderate Similarity -> Risky
    provider.set_score(original, "TEXT!", 0.78)
    res = await smv.validate(original, "TEXT!")
    assert res.risk_label == "risky"
