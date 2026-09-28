"""
Stylometric Anomaly Detector - the second uni-modal detector required by
the proposal ("train separate anomaly detection models ... on the
behavioural and stylometric feature spaces"). anomaly_detector.py already
implements the BEHAVIOURAL detector (recipient/temporal/network); this
file implements the STYLOMETRIC counterpart, using the real writeprint
vectors from stylometric_analyzer.py plus the Isolation Forest wrapper
from ml_models.py.

Its analyze_email() return shape deliberately mirrors what
ensemble_detector.py already expects (a dict with 'composite_score' and
a known component key), so wiring it into EnsembleDetector alongside
the existing AnomalyDetector needs only a one-line addition to
ensemble_detector.py's component key list (see CHANGES.md).

NEW FILE - does not modify any existing file.
"""
import logging
from typing import Dict, Any, List

import numpy as np

from .stylometric_analyzer import StylometricAnalyzer
from .ml_models import VectorAnomalyModel

logger = logging.getLogger(__name__)


class StylometricAnomalyDetector:
    def __init__(self, profiles: Dict[str, Any], use_population_model: bool = True):
        """
        profiles: the same {sender_email: SenderProfile} dict already
        passed to anomaly_detector.AnomalyDetector, AFTER
        profile_builder.py has been updated to populate
        `profile.stylometric_profile` (see CHANGES.md).
        """
        self.profiles = profiles
        self.analyzer = StylometricAnalyzer()
        self.population_model = None
        if use_population_model:
            self._fit_population_model()

    def _fit_population_model(self):
        vectors = []
        for profile in self.profiles.values():
            style_profile = getattr(profile, "stylometric_profile", None)
            if style_profile and style_profile.get("mean_vector"):
                vectors.append(np.array(style_profile["mean_vector"]))
        if len(vectors) >= 5:
            self.population_model = VectorAnomalyModel(method="isolation_forest").fit(vectors)
            logger.info("Fitted population Isolation Forest on %d user writeprints", len(vectors))
        else:
            logger.warning(
                "Not enough profiles with stylometric data (%d) to fit a population "
                "Isolation Forest -- falling back to per-user z-score baseline only.",
                len(vectors),
            )

    def analyze_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        sender = email_data.get("sender")
        subject = email_data.get("subject", "")
        body = email_data.get("body", "")
        reasons: List[str] = []

        if sender not in self.profiles:
            return {
                "stylometric_anomaly": 1.0,
                "composite_score": 1.0,
                "reasons": ["Sender has no stylometric profile"],
            }

        profile = self.profiles[sender]
        style_profile = getattr(profile, "stylometric_profile", None)
        if not style_profile or not style_profile.get("mean_vector"):
            # Backward-compatible: profiles built before this patch (or with
            # too few emails) simply don't contribute a stylometric signal.
            return {"stylometric_anomaly": 0.0, "composite_score": 0.0, "reasons": []}

        # ADD: don't trust a writeprint baseline built from too few emails —
        # per-feature std estimates are unreliable below roughly a dozen samples.
        if style_profile.get("sample_size", 0) < 10:
            return {"stylometric_anomaly": 0.0, "composite_score": 0.0,
                    "reasons": [f"Insufficient history ({style_profile.get('sample_size', 0)} emails) "
                                f"for a reliable writeprint baseline"]}

        features = self.analyzer.extract_features(f"{subject} {body}")
        vector = features["vector"]
        mean = np.array(style_profile["mean_vector"])
        std = np.array(style_profile["std_vector"])

        z_scores = np.abs((vector - mean) / std)
        per_user_score = float(np.clip(np.mean(z_scores) / 4.0, 0.0, 1.0))

        if per_user_score > 0.6:
            reasons.append(
                f"Writing style deviates from {sender}'s historical writeprint "
                f"(avg |z| = {np.mean(z_scores):.2f})"
            )

        if self.population_model is not None:
            population_score = self.population_model.anomaly_score(vector)
            composite = 0.7 * per_user_score + 0.3 * population_score
        else:
            composite = per_user_score

        return {
            "stylometric_anomaly": composite,
            "composite_score": composite,
            "reasons": reasons,
        }