"""
ML Anomaly Models - the actual unsupervised models named in the proposal
("Isolation Forest, autoencoders, one-class SVMs") which were previously
absent from the codebase (sklearn was only imported for evaluation metrics,
never for detection).

This module trains a model on a POPULATION of per-user feature vectors
(e.g. every user's mean writeprint, or every user's mean behavioral
vector) to catch profiles/emails that are outliers relative to the whole
organisation. It is deliberately kept separate from, and complementary
to, the PER-USER z-score baseline in stylometric_detector.py: the
z-score answers "does this look like how THIS person normally
writes/behaves?", while this model answers "does this look like an
outlier compared to everyone else?". Both were named as valid approaches
in the methodology; combining them is a stronger, ensemble-consistent
design than picking just one.

NEW FILE - does not modify any existing file.
"""
import numpy as np
from typing import List
import logging

from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM

logger = logging.getLogger(__name__)


class VectorAnomalyModel:
    """Wraps an sklearn unsupervised model and normalizes its output to a
    0-1 anomaly score (higher = more anomalous)."""

    def __init__(self, method: str = "isolation_forest", **kwargs):
        self.method = method
        if method == "isolation_forest":
            self.model = IsolationForest(
                n_estimators=kwargs.get("n_estimators", 200),
                contamination=kwargs.get("contamination", 0.1),
                random_state=42,
            )
        elif method == "one_class_svm":
            self.model = OneClassSVM(
                kernel=kwargs.get("kernel", "rbf"),
                nu=kwargs.get("nu", 0.1),
                gamma=kwargs.get("gamma", "scale"),
            )
        else:
            raise ValueError(f"Unknown method: {method}")
        self._fitted = False
        self._score_min = None
        self._score_max = None

    def fit(self, vectors: List[np.ndarray]) -> "VectorAnomalyModel":
        if len(vectors) < 5:
            logger.warning(
                "VectorAnomalyModel: fewer than 5 vectors supplied (%d) -- "
                "model will remain unfitted and anomaly_score() will return "
                "a neutral 0.5 until enough profiles exist.", len(vectors)
            )
            return self
        X = np.vstack(vectors)
        self.model.fit(X)
        raw_scores = self._raw_scores(X)
        self._score_min = float(np.min(raw_scores))
        self._score_max = float(np.max(raw_scores))
        self._fitted = True
        return self

    def _raw_scores(self, X: np.ndarray) -> np.ndarray:
        # For both IsolationForest.score_samples and OneClassSVM.decision_function,
        # HIGHER = more normal, so we flip sign: higher = more anomalous.
        if hasattr(self.model, "score_samples"):
            return -self.model.score_samples(X)
        return -self.model.decision_function(X)

    def anomaly_score(self, vector: np.ndarray) -> float:
        if not self._fitted:
            return 0.5  # neutral score until the model has enough data to train on
        raw = self._raw_scores(vector.reshape(1, -1))[0]
        span = (self._score_max - self._score_min) or 1e-6
        normalized = (raw - self._score_min) / span
        return float(np.clip(normalized, 0.0, 1.0))