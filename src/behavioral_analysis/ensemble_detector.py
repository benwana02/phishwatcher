"""
Ensemble Detector - Combines multiple detection methods
"""

from typing import List, Dict, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)


class EnsembleDetector:
    """Combines multiple anomaly detection methods"""
    
    def __init__(self, detectors: List[Any], weights: List[float] = None):
        self.detectors = detectors
        
        if weights is None:
            # Equal weights by default
            self.weights = [1.0 / len(detectors)] * len(detectors)
        else:
            if len(weights) != len(detectors):
                raise ValueError("Weights must match number of detectors")
            # Normalize weights
            total = sum(weights)
            self.weights = [w / total for w in weights]
    
    def analyze_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze email using ensemble of detectors"""
        results = []
        component_scores = {}
        
        for i, detector in enumerate(self.detectors):
            try:
                result = detector.analyze_email(email_data)
                
                if hasattr(result, 'to_dict'):
                    result_dict = result.to_dict()
                else:
                    result_dict = result
                
                results.append(result_dict)
                
                # Extract component scores if available
                for key in ['recipient_anomaly', 'temporal_anomaly', 
                           'content_anomaly', 'behavioral_anomaly', 'stylometric_anomaly']:
                    if key in result_dict:
                        if key not in component_scores:
                            component_scores[key] = []
                        component_scores[key].append(result_dict[key])
                
            except Exception as e:
                logger.error(f"Detector {i} failed: {e}")
                results.append({'composite_score': 0.5, 'error': str(e)})
        
        # Calculate ensemble scores
        ensemble_composite = 0.0
        for i, result in enumerate(results):
            if 'composite_score' in result:
                ensemble_composite += result['composite_score'] * self.weights[i]
        
        # Calculate ensemble component scores (average)
        ensemble_components = {}
        for component, scores in component_scores.items():
            if scores:
                # Weighted average based on detector weights
                weighted_avg = sum(s * w for s, w in zip(scores, self.weights[:len(scores)]))
                ensemble_components[component] = weighted_avg
        
        # Calculate confidence (agreement between detectors)
        if len(results) > 1:
            composite_scores = [r.get('composite_score', 0.5) for r in results]
            confidence = 1.0 - np.std(composite_scores)  # Higher std = lower confidence
        else:
            confidence = 0.5
        
        # Determine risk level
        if ensemble_composite >= 0.8:
            risk_level = "CRITICAL"
        elif ensemble_composite >= 0.6:
            risk_level = "HIGH"
        elif ensemble_composite >= 0.4:
            risk_level = "MEDIUM"
        elif ensemble_composite >= 0.2:
            risk_level = "LOW"
        else:
            risk_level = "NORMAL"
        
        ensemble_result = {
            'ensemble_composite': float(ensemble_composite),
            'ensemble_components': ensemble_components,
            'confidence': float(confidence),
            'risk_level': risk_level,
            'detector_results': results,
            'weights': self.weights
        }
        
        # Add reasons from all detectors
        all_reasons = []
        for result in results:
            if 'reasons' in result and result['reasons']:
                all_reasons.extend(result['reasons'])
        
        # Remove duplicates
        ensemble_result['reasons'] = list(set(all_reasons))[:10]  # Limit to 10 reasons
        
        return ensemble_result
    
    def optimize_weights(self, evaluation_data: List[Dict[str, Any]]) -> List[float]:
        """Optimize detector weights based on evaluation data"""
        # This is a simplified optimization
        # In practice, you would use grid search or gradient descent
        
        n_detectors = len(self.detectors)
        
        # Store individual detector performances
        detector_performances = []
        
        for i, detector in enumerate(self.detectors):
            detector_scores = []
            true_labels = []
            
            for data_point in evaluation_data:
                email_data = data_point['email']
                true_label = data_point.get('true_label', 0)
                
                try:
                    result = detector.analyze_email(email_data)
                    if hasattr(result, 'composite_score'):
                        score = result.composite_score
                    elif isinstance(result, dict) and 'composite_score' in result:
                        score = result['composite_score']
                    else:
                        score = 0.5
                    
                    detector_scores.append(score)
                    true_labels.append(true_label)
                    
                except Exception as e:
                    logger.error(f"Detector {i} failed during optimization: {e}")
                    detector_scores.append(0.5)
                    true_labels.append(true_label)
            
            # Calculate F1 score for this detector
            if len(set(true_labels)) > 1:
                # Convert scores to binary predictions (threshold = 0.5)
                predictions = [1 if s >= 0.5 else 0 for s in detector_scores]
                
                # Calculate precision and recall
                tp = sum(1 for t, p in zip(true_labels, predictions) if t == 1 and p == 1)
                fp = sum(1 for t, p in zip(true_labels, predictions) if t == 0 and p == 1)
                fn = sum(1 for t, p in zip(true_labels, predictions) if t == 1 and p == 0)
                
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            else:
                f1 = 0.5  # Neutral performance
            
            detector_performances.append(f1)
        
        # Set weights proportional to performance
        total_performance = sum(detector_performances)
        if total_performance > 0:
            new_weights = [p / total_performance for p in detector_performances]
        else:
            new_weights = [1.0 / n_detectors] * n_detectors
        
        self.weights = new_weights
        logger.info(f"Optimized weights: {new_weights}")
        
        return new_weights