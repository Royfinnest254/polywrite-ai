"""
Document Intelligence Scanner (M_critique)

Analyzes document structure, consistency, and identifies issues.

WHITE PAPER REFERENCE: Section 5 (The Document Critic)

CORE PRINCIPLE:
- This model NEVER proposes edits
- It only analyzes and critiques what exists
- Read-only, diagnostic mode

ANALYSIS AREAS:
1. Structure: Are claims supported by evidence?
2. Consistency: Do sections contradict each other?
3. Clarity: Are complex ideas explained?
4. Proficiency: Grammar, style, readability
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class Contradiction:
    """A detected contradiction between text segments."""
    segment_1: str
    segment_2: str
    conflict: str
    severity: str = "medium"  # low, medium, high


@dataclass
class ClarityIssue:
    """A clarity or readability issue."""
    text: str
    issue_type: str  # jargon, long_sentence, passive_voice, unclear
    suggestion: str


@dataclass
class DocumentScanResult:
    """Result of document-level intelligence scan."""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    contradictions: List[Contradiction] = field(default_factory=list)
    clarity_issues: List[ClarityIssue] = field(default_factory=list)
    uncited_claims: List[str] = field(default_factory=list)
    structure_score: float = 0.8  # 0.0 to 1.0
    consistency_score: float = 0.8
    clarity_score: float = 0.8
    overall_score: float = 0.8
    
    def to_dict(self) -> dict:
        return {
            "strengths": self.strengths[:5],
            "weaknesses": self.weaknesses[:5],
            "contradictions": [
                {"segment_1": c.segment_1[:50], "segment_2": c.segment_2[:50], "conflict": c.conflict}
                for c in self.contradictions[:3]
            ],
            "clarity_issues": [
                {"text": c.text[:50], "type": c.issue_type}
                for c in self.clarity_issues[:5]
            ],
            "scores": {
                "structure": round(self.structure_score, 2),
                "consistency": round(self.consistency_score, 2),
                "clarity": round(self.clarity_score, 2),
                "overall": round(self.overall_score, 2)
            }
        }


class DocumentScanner:
    """
    Scans documents for structural and logical issues.
    
    DIAGNOSTIC ONLY - never generates alternative text.
    
    CHECKS:
    1. Contradictions: Opposing claims in same document
    2. Clarity: Long sentences, jargon, passive voice
    3. Structure: Logical flow, evidence support
    4. Consistency: Terminology, tense, style
    """
    
    # Contradiction detection patterns (opposing terms)
    OPPOSING_PAIRS = [
        ("increase", "decrease"),
        ("significant", "insignificant"),
        ("effective", "ineffective"),
        ("positive", "negative"),
        ("growth", "decline"),
        ("improve", "worsen"),
        ("support", "oppose"),
        ("confirm", "deny"),
        ("success", "failure"),
        ("benefit", "harm"),
    ]
    
    # Clarity issue patterns
    JARGON_PATTERNS = [
        r'\b(?:synergy|leverage|paradigm|holistic|granular)\b',
        r'\b(?:actionable|scalable|optimize|incentivize)\b',
        r'\b(?:ideation|learnings|takeaways|deliverables)\b',
    ]
    
    PASSIVE_VOICE_PATTERN = r'\b(?:is|are|was|were|been|being)\s+\w+ed\b'
    
    def scan(self, text: str) -> DocumentScanResult:
        """
        Perform a full document scan.
        
        Returns diagnostic analysis, not prescriptive edits.
        """
        if not text or len(text.strip()) < 50:
            return DocumentScanResult(
                weaknesses=["Document too short for meaningful analysis"]
            )
        
        result = DocumentScanResult()
        
        # 1. Check for contradictions
        result.contradictions = self._find_contradictions(text)
        
        # 2. Check for clarity issues
        result.clarity_issues = self._find_clarity_issues(text)
        
        # 3. Identify strengths and weaknesses
        result.strengths, result.weaknesses = self._analyze_structure(text)
        
        # 4. Calculate scores
        result.structure_score = self._calculate_structure_score(text)
        result.consistency_score = self._calculate_consistency_score(text, result.contradictions)
        result.clarity_score = self._calculate_clarity_score(text, result.clarity_issues)
        result.overall_score = (
            result.structure_score * 0.3 + 
            result.consistency_score * 0.4 + 
            result.clarity_score * 0.3
        )
        
        return result
    
    def compare(
        self, 
        original_text: str, 
        proposed_text: str
    ) -> Dict[str, any]:
        """
        Compare document quality between original and proposed.
        
        Returns whether proposed maintains or improves document quality.
        """
        orig_scan = self.scan(original_text)
        prop_scan = self.scan(proposed_text)
        
        # Compare scores
        structure_delta = prop_scan.structure_score - orig_scan.structure_score
        consistency_delta = prop_scan.consistency_score - orig_scan.consistency_score
        clarity_delta = prop_scan.clarity_score - orig_scan.clarity_score
        overall_delta = prop_scan.overall_score - orig_scan.overall_score
        
        # Determine if quality maintained
        quality_maintained = overall_delta >= -0.1  # Allow small decreases
        new_issues = len(prop_scan.contradictions) > len(orig_scan.contradictions)
        
        return {
            "quality_maintained": quality_maintained and not new_issues,
            "score_change": round(overall_delta, 2),
            "new_contradictions": new_issues,
            "clarity_change": round(clarity_delta, 2),
            "original_score": round(orig_scan.overall_score, 2),
            "proposed_score": round(prop_scan.overall_score, 2),
        }
    
    def _find_contradictions(self, text: str) -> List[Contradiction]:
        """
        Find potential contradictions in text.
        
        Looks for opposing claims that might conflict.
        """
        contradictions = []
        sentences = self._split_sentences(text)
        
        if len(sentences) < 2:
            return []
        
        # Check each pair of opposing terms
        for term1, term2 in self.OPPOSING_PAIRS:
            sentences_with_term1 = [s for s in sentences if term1 in s.lower()]
            sentences_with_term2 = [s for s in sentences if term2 in s.lower()]
            
            # If both terms appear, flag as potential contradiction
            if sentences_with_term1 and sentences_with_term2:
                contradictions.append(Contradiction(
                    segment_1=sentences_with_term1[0][:100],
                    segment_2=sentences_with_term2[0][:100],
                    conflict=f"Text contains both '{term1}' and '{term2}' claims",
                    severity="medium"
                ))
        
        # Check for direct negation contradictions
        for i, sent1 in enumerate(sentences):
            for sent2 in sentences[i+1:]:
                if self._are_contradictory(sent1, sent2):
                    contradictions.append(Contradiction(
                        segment_1=sent1[:100],
                        segment_2=sent2[:100],
                        conflict="Potential logical contradiction",
                        severity="high"
                    ))
        
        return contradictions[:5]  # Limit to top 5
    
    def _are_contradictory(self, sent1: str, sent2: str) -> bool:
        """
        Check if two sentences are potentially contradictory.
        
        Simple heuristic: same subject + negation difference
        """
        s1_lower = sent1.lower()
        s2_lower = sent2.lower()
        
        # Check for "not" / "no" difference on similar content
        s1_negated = " not " in s1_lower or " no " in s1_lower
        s2_negated = " not " in s2_lower or " no " in s2_lower
        
        if s1_negated != s2_negated:
            # Check if sentences share significant content
            s1_words = set(s1_lower.split())
            s2_words = set(s2_lower.split())
            overlap = len(s1_words & s2_words)
            
            if overlap >= 3:  # Significant word overlap
                return True
        
        return False
    
    def _find_clarity_issues(self, text: str) -> List[ClarityIssue]:
        """
        Find clarity and readability issues.
        """
        issues = []
        sentences = self._split_sentences(text)
        
        for sentence in sentences:
            # Check for long sentences
            word_count = len(sentence.split())
            if word_count > 40:
                issues.append(ClarityIssue(
                    text=sentence[:80] + "...",
                    issue_type="long_sentence",
                    suggestion="Consider breaking into shorter sentences"
                ))
            
            # Check for excessive passive voice
            passive_count = len(re.findall(self.PASSIVE_VOICE_PATTERN, sentence))
            if passive_count >= 2:
                issues.append(ClarityIssue(
                    text=sentence[:80] + "...",
                    issue_type="passive_voice",
                    suggestion="Consider using active voice"
                ))
            
            # Check for jargon
            for pattern in self.JARGON_PATTERNS:
                if re.search(pattern, sentence, re.IGNORECASE):
                    issues.append(ClarityIssue(
                        text=sentence[:80] + "...",
                        issue_type="jargon",
                        suggestion="Consider simpler terminology"
                    ))
                    break
        
        return issues[:10]  # Limit to top 10
    
    def _analyze_structure(self, text: str) -> tuple:
        """
        Analyze document structure strengths and weaknesses.
        """
        strengths = []
        weaknesses = []
        
        sentences = self._split_sentences(text)
        word_count = len(text.split())
        
        # Check for logical connectors (good structure)
        connectors = len(re.findall(
            r'\b(?:therefore|however|furthermore|moreover|consequently|thus)\b',
            text, re.IGNORECASE
        ))
        if connectors >= 2:
            strengths.append("Good use of logical connectors")
        
        # Check for varied sentence length
        lengths = [len(s.split()) for s in sentences]
        if lengths:
            variance = max(lengths) - min(lengths)
            if variance > 10:
                strengths.append("Varied sentence structure")
            else:
                weaknesses.append("Monotonous sentence length")
        
        # Check for evidence markers
        evidence = len(re.findall(
            r'\b(?:for example|such as|according to|studies show)\b',
            text, re.IGNORECASE
        ))
        if evidence >= 1:
            strengths.append("Claims supported with examples/evidence")
        elif word_count > 200:
            weaknesses.append("Limited evidence or examples provided")
        
        # Check for clear topic sentences (capitalized starts after periods)
        if len(sentences) >= 3:
            strengths.append("Multiple complete sentences")
        
        return strengths, weaknesses
    
    def _calculate_structure_score(self, text: str) -> float:
        """Calculate structure quality score."""
        score = 0.7  # Base
        
        # Bonus for logical connectors
        connectors = len(re.findall(
            r'\b(?:therefore|however|furthermore|moreover)\b', 
            text, re.IGNORECASE
        ))
        score += min(0.15, connectors * 0.03)
        
        # Bonus for evidence
        evidence = len(re.findall(
            r'\b(?:for example|such as|according to)\b', 
            text, re.IGNORECASE
        ))
        score += min(0.15, evidence * 0.05)
        
        return min(1.0, score)
    
    def _calculate_consistency_score(
        self, 
        text: str, 
        contradictions: List[Contradiction]
    ) -> float:
        """Calculate consistency score."""
        score = 1.0
        
        # Penalize contradictions
        score -= len(contradictions) * 0.15
        
        # Check for tense consistency (simplified)
        past_tense = len(re.findall(r'\b\w+ed\b', text))
        present_tense = len(re.findall(r'\b(?:is|are|has|have)\b', text))
        
        # Large tense imbalance might indicate inconsistency
        if past_tense > 0 and present_tense > 0:
            ratio = min(past_tense, present_tense) / max(past_tense, present_tense)
            if ratio > 0.5:  # Mixed tenses
                score -= 0.1
        
        return max(0.3, score)
    
    def _calculate_clarity_score(
        self, 
        text: str, 
        clarity_issues: List[ClarityIssue]
    ) -> float:
        """Calculate clarity score."""
        score = 1.0
        
        # Penalize clarity issues
        score -= len(clarity_issues) * 0.08
        
        # Check average sentence length
        sentences = self._split_sentences(text)
        if sentences:
            avg_length = sum(len(s.split()) for s in sentences) / len(sentences)
            if avg_length > 30:
                score -= 0.15
            elif avg_length < 8:
                score -= 0.1
        
        return max(0.3, score)
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
