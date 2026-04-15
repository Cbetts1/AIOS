"""
Capability Forge OS — Intent router.

Matches an intent string against the capability registry.
If no match is found, delegates to the generator.
"""

from typing import List, Optional, Set, Tuple

from core.models import Capability

# Common English stop-words that should not contribute to match scores.
_STOP_WORDS: Set[str] = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "with",
    "and", "or", "but", "is", "are", "was", "were", "be", "been",
    "it", "its", "that", "this", "these", "those", "from", "by",
    "as", "into", "up", "out", "not", "no", "can", "will", "do",
    "does", "did", "has", "have", "had", "i", "me", "my", "we",
}

_MIN_TOKEN_LEN = 3  # ignore tokens shorter than this (catches "a", "an", etc.)


def _tokenize(text: str) -> Set[str]:
    tokens = set(text.lower().replace("_", " ").split())
    return {t for t in tokens if len(t) >= _MIN_TOKEN_LEN and t not in _STOP_WORDS}


def _score(intent_tokens: Set[str], cap: Capability) -> int:
    """
    Return a non-negative relevance score for *cap* against *intent_tokens*.

    Higher is better.  Zero means no meaningful overlap.
    Requires at least 2 distinct token matches to avoid single-word
    false positives (e.g. 'file' matching every file-related capability).
    """
    matched: Set[str] = set()
    score = 0

    # Name match carries the most weight
    name_tokens = _tokenize(cap.name)
    overlap = intent_tokens & name_tokens
    score += len(overlap) * 3
    matched |= overlap

    # Description tokens
    desc_tokens = _tokenize(cap.description)
    overlap = intent_tokens & desc_tokens
    score += len(overlap) * 2
    matched |= overlap

    # Input field names
    for inp in cap.inputs:
        inp_tokens = _tokenize(inp)
        overlap = intent_tokens & inp_tokens
        score += len(overlap)
        matched |= overlap

    # Require at least 2 distinct matching tokens to avoid false positives
    if len(matched) < 2:
        return 0

    return score


class CapabilityRouter:
    """Routes an intent string to the best matching capability."""

    def route(
        self,
        intent: str,
        capabilities: List[Capability],
    ) -> Tuple[Optional[Capability], bool]:
        """
        Return ``(capability, was_generated)`` where *was_generated* is
        ``False`` when an existing capability was matched and ``True`` when
        the caller must generate a new one.

        If a match is found the best-scoring active capability is returned.
        If no active capability scores above zero, ``(None, True)`` is
        returned to signal that generation is needed.
        """
        if not intent.strip():
            return None, False

        intent_tokens = _tokenize(intent)
        if not intent_tokens:
            return None, True

        scored: List[Tuple[int, Capability]] = []
        for cap in capabilities:
            if not cap.ai_routable:
                continue
            s = _score(intent_tokens, cap)
            if s > 0:
                scored.append((s, cap))

        if not scored:
            return None, True

        scored.sort(key=lambda t: t[0], reverse=True)
        return scored[0][1], False
