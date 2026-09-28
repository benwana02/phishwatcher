# PhishWatcher patch: closing the lit-review / implementation gap

## Summary of files

| File | Status | Why |
|---|---|---|
| `src/behavioral_analysis/stylometric_analyzer.py` | **NEW** | Real writeprint features (function words, char/word n-grams, readability) — the stylometric modality the lit review argues for |
| `src/behavioral_analysis/ml_models.py` | **NEW** | Genuine Isolation Forest / One-Class SVM wrapper — the "ML anomaly detection" the proposal names but never implements |
| `src/behavioral_analysis/stylometric_detector.py` | **NEW** | The missing second uni-modal detector (stylometric), fusable with the existing behavioral `AnomalyDetector` |
| `src/utils/impersonation_simulator.py` | **NEW** | Real identity-swapped test cases (style/behavior/full swap) — objective 7, done properly |
| `src/behavioral_analysis/profile_builder.py` | **MODIFIED** (append-only) | Adds a `stylometric_profile` (mean + std vector) to `SenderProfile`, alongside variance tracking |
| `src/behavioral_analysis/ensemble_detector.py` | **MODIFIED** (1 line) | Recognise the new `stylometric_anomaly` component key |
| `app/dashboard.py` | **MODIFIED** (`init_system`) | Wire both detectors into `EnsembleDetector` instead of a single `AnomalyDetector` |
| `run_evaluation.py` | **MODIFIED** (steps 1–3) | Use the ensemble + `ImpersonationSimulator` instead of the single behavioral detector + synthetic filler-text simulator |

**Nothing else changes.** `language_analyzer.py`, `anomaly_detector.py`'s recipient/temporal/network logic, `network_analyzer.py`, `metrics_calculator.py`, `threshold_optimizer.py`, `email_simulator.py`, and all existing tests are untouched and keep working exactly as before — the new stylometric signal is additive, not a replacement of the existing behavioral one.

---

## 1. `src/behavioral_analysis/profile_builder.py`

Two small, additive edits. Nothing existing is removed or renamed, so `to_dict()`/`from_dict()` stay backward-compatible with profiles.json files built before this patch (old files simply won't have the new field, and `from_dict` defaults it to empty).

**Edit A — add the import, near the top:**
```python
from .language_analyzer import LanguageAnalyzer
from .stylometric_analyzer import StylometricAnalyzer   # ADD THIS LINE
```

**Edit B — in `SenderProfile.__init__`, add a new attribute next to `language_profile`:**
```python
        self.language_profile = {
            'avg_sentence_length': 0,
            'formality_score': 0,
            'urgency_score': 0,
            'exclamation_density': 0,
            'sample_size': 0
        }
        # ADD THIS BLOCK:
        self.stylometric_profile = {
            'mean_vector': [],   # list, not np.ndarray, so it stays JSON-serializable
            'std_vector': [],
            'sample_size': 0,
        }
```

**Edit C — in `SenderProfile.to_dict()`, add one line to the returned dict:**
```python
            'language_profile': self.language_profile,
            'stylometric_profile': self.stylometric_profile,   # ADD THIS LINE
```

**Edit D — in `SenderProfile.from_dict()`, add the matching load (uses `.get` so old files without the field still load fine):**
```python
        profile.language_profile = data.get('language_profile', {...})   # unchanged
        profile.stylometric_profile = data.get('stylometric_profile', {  # ADD THIS BLOCK
            'mean_vector': [], 'std_vector': [], 'sample_size': 0,
        })
```

**Edit E — in `ProfileBuilder.__init__`, add the analyzer instance:**
```python
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.profiles: Dict[str, SenderProfile] = {}
        self.language_analyzer = LanguageAnalyzer()
        self.stylometric_analyzer = StylometricAnalyzer()   # ADD THIS LINE
```

**Edit F — in `build_profile_for_sender`, collect body texts alongside the existing `language_data` list, then build the writeprint after the loop.**

Where the loop currently does:
```python
            language_analysis = self.language_analyzer.analyze_email(subject, body)
            language_data.append(language_analysis)
```
add one line right after it:
```python
            language_analysis = self.language_analyzer.analyze_email(subject, body)
            language_data.append(language_analysis)
            body_texts.append(f"{subject} {body}")   # ADD THIS LINE
```
(and initialise `body_texts = []` next to the existing `language_data = []` before the loop starts).

Then, after the existing block that computes `profile.language_profile = {...}` from `language_data`, add:
```python
        # ADD THIS BLOCK — builds the per-user writeprint (mean + std)
        if body_texts:
            mean_vec, std_vec = self.stylometric_analyzer.build_writeprint(body_texts)
            if mean_vec is not None:
                profile.stylometric_profile = {
                    'mean_vector': mean_vec.tolist(),
                    'std_vector': std_vec.tolist(),
                    'sample_size': len(body_texts),
                }
```

No other function in this file changes. `build_all_profiles`, `save_profiles`, `load_profiles`, `get_profile_stats` are untouched.

---

## 2. `src/behavioral_analysis/ensemble_detector.py`

One-line change so the ensemble picks up the new detector's score. Find:
```python
                for key in ['recipient_anomaly', 'temporal_anomaly',
                            'content_anomaly', 'behavioral_anomaly']:
```
Replace with:
```python
                for key in ['recipient_anomaly', 'temporal_anomaly',
                            'content_anomaly', 'behavioral_anomaly',
                            'stylometric_anomaly']:                   # ADDED
```
Everything else in the file (weighting, `optimize_weights`, confidence calculation) works unchanged, since it already generically iterates over whatever `detectors` list it's given.

---

## 3. `app/dashboard.py`

`init_system()` currently builds a single `AnomalyDetector` and assigns it directly to `DETECTOR`. Change it to build both uni-modal detectors and fuse them, matching "train separate anomaly detection models ... then fuse" in the methodology.

Find:
```python
from src.behavioral_analysis.profile_builder import ProfileBuilder, SenderProfile
from src.behavioral_analysis.anomaly_detector import AnomalyDetector
from src.behavioral_analysis.network_analyzer import CommunicationNetwork
from src.utils.email_simulator import EmailSimulator
```
Add two imports:
```python
from src.behavioral_analysis.stylometric_detector import StylometricAnomalyDetector   # ADD
from src.behavioral_analysis.ensemble_detector import EnsembleDetector                 # ADD
```

Find, inside `init_system()`:
```python
        # Create detector
        DETECTOR = AnomalyDetector(PROFILES, NETWORK)
```
Replace with:
```python
        # Create the two uni-modal detectors named in the proposal, then fuse them
        behavioral_detector = AnomalyDetector(PROFILES, NETWORK)
        stylometric_detector = StylometricAnomalyDetector(PROFILES)
        DETECTOR = EnsembleDetector(
            [behavioral_detector, stylometric_detector],
            weights=[0.5, 0.5],
        )
```

Everything downstream that calls `DETECTOR.analyze_email(...)` (e.g. the `/analyze` route) already receives a dict back from `EnsembleDetector.analyze_email` with an `ensemble_composite` field instead of an `AnomalyScore` object with a `.composite_score` attribute — check the `/analyze` route body (not shown in the extract) for any place it does `score.composite_score` or `score.to_dict()`, and change those specific two references to `result['ensemble_composite']` / `result` respectively. This is the only place the object-vs-dict shape change is visible to calling code.

---

## 4. `run_evaluation.py`

Replace the single detector + synthetic-filler dataset with the ensemble + real identity-swapped dataset. This directly fixes the circularity described earlier: the old "phishing" class was synthetic text with injected keywords scored by the same heuristic that looks for those keywords.

**Imports** — find:
```python
from src.behavioral_analysis.anomaly_detector import AnomalyDetector
from src.behavioral_analysis.network_analyzer import CommunicationNetwork
from src.utils.email_simulator import EmailSimulator
```
Add:
```python
from src.behavioral_analysis.stylometric_detector import StylometricAnomalyDetector   # ADD
from src.behavioral_analysis.ensemble_detector import EnsembleDetector                 # ADD
from src.utils.impersonation_simulator import ImpersonationSimulator                   # ADD
# NOTE: EmailSimulator import can stay -- keep it if you still want to run the
# original generic-anomaly stress test separately; it's just no longer used
# for the impersonation-accuracy evaluation below.
```

**Step 1** — find:
```python
    detector = AnomalyDetector(builder.profiles, network)
    simulator = EmailSimulator(profiles_path)
```
Replace with:
```python
    behavioral_detector = AnomalyDetector(builder.profiles, network)
    stylometric_detector = StylometricAnomalyDetector(builder.profiles)
    detector = EnsembleDetector([behavioral_detector, stylometric_detector], weights=[0.5, 0.5])
    simulator = ImpersonationSimulator(db_path)
```

**Step 2** — find the whole block that builds `test_emails`/`true_labels` from `simulator.generate_test_set` + the manual `phishing_emails` loop, and replace it with:
```python
    senders = list(builder.profiles.keys())
    test_cases = simulator.generate_test_set(senders, n_cases=200, normal_ratio=0.7)
    test_emails = test_cases
    true_labels = [case['true_label'] for case in test_cases]

    print(f"Generated {len(test_emails)} test emails "
          f"({true_labels.count(0)} normal, {true_labels.count(1)} impersonation)")

    eval_dataset_path = os.path.join(output_dir, "evaluation_dataset.json")
    with open(eval_dataset_path, 'w') as f:
        json.dump(
            [{**c, 'timestamp': c['timestamp'].isoformat()} for c in test_cases],
            f, indent=2, default=str,
        )
```
(`ImpersonationSimulator` doesn't need `save_test_set`/`load_test_set` — the inline `json.dump` above replaces that call, since `EmailSimulator`'s own save/load methods are tied to its own email dict shape and are left untouched for its own use elsewhere.)

**Step 3** — `detector.analyze_email(email)` now returns a dict (`ensemble_composite`, `ensemble_components`, ...) rather than an `AnomalyScore` object. Find:
```python
        score = detector.analyze_email(email)
        predicted_scores.append(score.composite_score)
        components = {
            'recipient': score.recipient_anomaly,
            'temporal': score.temporal_anomaly,
            'content': score.content_anomaly,
            'behavioral': score.behavioral_anomaly
        }
```
Replace with:
```python
        result = detector.analyze_email(email)
        predicted_scores.append(result['ensemble_composite'])
        components = {
            'recipient': result['ensemble_components'].get('recipient_anomaly', 0.0),
            'temporal': result['ensemble_components'].get('temporal_anomaly', 0.0),
            'content': result['ensemble_components'].get('content_anomaly', 0.0),
            'behavioral': result['ensemble_components'].get('behavioral_anomaly', 0.0),
            'stylometric': result['ensemble_components'].get('stylometric_anomaly', 0.0),
        }
```

Steps 4–7 (metrics, plots, thresholding, reports) are untouched — `EvaluationMetrics` and `ThresholdOptimizer` only ever consumed `true_labels`/`predicted_scores`/`anomaly_components`, whose shapes are unchanged by this patch.

---

## What this does and doesn't fix

**Now genuinely implemented, matching the lit review's claims:**
- A real stylometric feature space (function words, n-grams, readability), not phishing-keyword heuristics.
- Two separately-trained uni-modal detectors fused by the existing weighted ensemble.
- A real Isolation Forest, satisfying the "ML anomaly detection" claim (rather than sklearn appearing only in metrics code).
- Impersonation test cases built from real swapped identities, so RQ1 can be evaluated on the thing it's actually asking about.
- Per-user statistical baselines now include variance (std), not just mean.

**Still worth flagging in your write-up rather than silently claiming:**
- The Isolation Forest here operates at the *population* level (is this profile/email an outlier vs. everyone else); the *per-user* anomaly detection is still a z-score/statistical method, not a trained model per user — training one ML model per user isn't realistic on Enron-scale per-user email counts, so state that design choice explicitly rather than letting the "Isolation Forest" line in the proposal imply otherwise.
- Explainability is still "reasons" strings, not a systematic feature-attribution method (e.g. SHAP) — fine for a proof-of-concept, but call it what it is in the report.
