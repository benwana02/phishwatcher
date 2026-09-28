"""
Stylometric Analyzer - extracts genuine authorship/writeprint features:
function-word frequencies, character/word n-grams, sentence-level metrics,
and a readability score.

This is the STYLOMETRIC modality described in the proposal/literature
review (cf. Afroz et al. 2014; Mackenzie et al. 2020) which was previously
missing from the codebase. `language_analyzer.py` is left completely
untouched -- it still computes phishing-cue heuristics (urgency,
formality, punctuation) and continues to feed `content_anomaly` in
anomaly_detector.py exactly as before. This module is ADDITIVE: it is a
new, separate signal, not a replacement.

NEW FILE - does not modify any existing file. Safe to drop in.
"""
import re
import hashlib
from collections import Counter
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
from nltk.tokenize import word_tokenize, sent_tokenize

# A fixed, order-stable function-word list. Frequencies of these words are
# one of the most well-established authorship signals in the stylometry
# literature (they are topic-independent, unlike content words).
FUNCTION_WORDS = [
    "a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet",
    "in", "on", "at", "by", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "to", "from",
    "up", "down", "of", "off", "over", "under", "again", "further", "then",
    "once", "i", "you", "he", "she", "it", "we", "they", "this", "that",
    "these", "those", "who", "whom", "which", "what", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "shall", "should", "may", "might", "must",
    "can", "could", "not", "no", "if", "because", "while", "as",
]

# Character/word n-grams are hashed into a fixed number of buckets
# ("feature hashing") so the vector length stays constant regardless of
# each user's vocabulary size -- required for a stable per-user baseline
# and for feeding a downstream ML model (see ml_models.py).
N_CHAR_BUCKETS = 24
N_WORD_BUCKETS = 24
N_SCALAR_FEATURES = 7  # see extract_features() for the exact list/order

VECTOR_LENGTH = len(FUNCTION_WORDS) + N_CHAR_BUCKETS + N_WORD_BUCKETS + N_SCALAR_FEATURES


def _stable_hash(token: str, n_buckets: int) -> int:
    """Deterministic hash -> bucket index.

    NOTE: Python's built-in hash() is randomized per-process for str
    objects (PYTHONHASHSEED), so it MUST NOT be used here -- it would
    make a writeprint built during training incompatible with the same
    text scored in a later process. hashlib is stable across runs/processes.
    """
    digest = hashlib.md5(token.encode("utf-8")).hexdigest()
    return int(digest, 16) % n_buckets


def _syllable_count(word: str) -> int:
    word = word.lower()
    vowels = "aeiouy"
    count = 0
    prev_was_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


class StylometricAnalyzer:
    """Extracts a fixed-length numeric writeprint vector from raw email text."""

    VECTOR_LENGTH = VECTOR_LENGTH

    def extract_features(self, text: str) -> Dict[str, Any]:
        """Returns a dict containing the fixed-length 'vector' (numpy array,
        length == StylometricAnalyzer.VECTOR_LENGTH) plus a few human-
        readable scalar fields useful for logging/explainability."""
        text = text or ""
        words = word_tokenize(text.lower())
        alpha_words = [w for w in words if w.isalpha()]
        sentences = sent_tokenize(text) or [text]

        function_vec = self._function_word_vector(alpha_words)
        char_vec = self._hashed_ngram_vector(self._char_ngrams(text.lower(), n=3), N_CHAR_BUCKETS)
        word_vec = self._hashed_ngram_vector(self._word_ngrams(alpha_words, n=2), N_WORD_BUCKETS)

        sent_lengths = [len(word_tokenize(s)) for s in sentences] or [0]
        avg_sentence_length = float(np.mean(sent_lengths))
        sentence_length_std = float(np.std(sent_lengths))
        avg_word_length = float(np.mean([len(w) for w in alpha_words])) if alpha_words else 0.0
        type_token_ratio = len(set(alpha_words)) / max(len(alpha_words), 1)

        n_words = max(len(words), 1)
        comma_rate = text.count(",") / n_words * 100
        semicolon_rate = text.count(";") / n_words * 100

        flesch = self._flesch_reading_ease(alpha_words, sentences)

        scalar_features = np.array([
            avg_sentence_length, sentence_length_std, avg_word_length,
            type_token_ratio, comma_rate, semicolon_rate, flesch,
        ])

        vector = np.concatenate([function_vec, char_vec, word_vec, scalar_features])

        return {
            "vector": vector,
            "avg_sentence_length": avg_sentence_length,
            "sentence_length_std": sentence_length_std,
            "avg_word_length": avg_word_length,
            "type_token_ratio": type_token_ratio,
            "flesch_reading_ease": flesch,
        }

    def build_writeprint(self, texts: List[str]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Build a per-user baseline: mean vector + std vector across the
        user's historical emails. This is the "statistical profile (mean
        AND variance)" the methodology section promises but the original
        profile_builder.py only computed as a mean."""
        vectors = [self.extract_features(t)["vector"] for t in texts if t and t.strip()]
        if not vectors:
            return None, None
        matrix = np.vstack(vectors)
        mean = matrix.mean(axis=0)
        std = matrix.std(axis=0)
        std[std < 1e-3] = 1e-3  # avoid divide-by-zero for near-constant features
        return mean, std

    # -- internals -----------------------------------------------------

    def _function_word_vector(self, words: List[str]) -> np.ndarray:
        total = max(len(words), 1)
        counts = Counter(words)
        return np.array([counts.get(fw, 0) / total * 1000 for fw in FUNCTION_WORDS])

    def _char_ngrams(self, text: str, n: int) -> List[str]:
        text = re.sub(r"\s+", " ", text)
        if len(text) < n:
            return []
        return [text[i:i + n] for i in range(len(text) - n + 1)]

    def _word_ngrams(self, words: List[str], n: int) -> List[str]:
        if len(words) < n:
            return []
        return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]

    def _hashed_ngram_vector(self, ngrams: List[str], n_buckets: int) -> np.ndarray:
        vec = np.zeros(n_buckets)
        for ng in ngrams:
            vec[_stable_hash(ng, n_buckets)] += 1
        total = vec.sum()
        if total > 0:
            vec = vec / total
        return vec

    def _flesch_reading_ease(self, words: List[str], sentences: List[str]) -> float:
        n_words = max(len(words), 1)
        n_sentences = max(len(sentences), 1)
        n_syllables = sum(_syllable_count(w) for w in words) or 1
        score = 206.835 - 1.015 * (n_words / n_sentences) - 84.6 * (n_syllables / n_words)
        return float(np.clip(score, 0, 100))