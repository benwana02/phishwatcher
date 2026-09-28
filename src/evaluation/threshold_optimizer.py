"""
Threshold Optimizer - Finds optimal thresholds for anomaly detection
"""

import numpy as np
from typing import Dict, List, Tuple, Any
import json
import matplotlib.pyplot as plt
from sklearn.metrics import f1_score, precision_recall_curve
import logging

logger = logging.getLogger(__name__)


class ThresholdOptimizer:
    """Optimizes thresholds for anomaly detection"""
    
    def __init__(self):
        self.results = []
        self.true_labels = []
        self.predicted_scores = []
        
    def load_evaluation_data(self, true_labels: List[int], predicted_scores: List[float]):
        """Load evaluation data"""
        self.true_labels = true_labels
        self.predicted_scores = predicted_scores
        
        if len(true_labels) != len(predicted_scores):
            raise ValueError("True labels and predicted scores must have the same length")
    
    def evaluate_thresholds(self, thresholds: List[float] = None) -> List[Dict[str, Any]]:
        """Evaluate performance at different thresholds"""
        if thresholds is None:
            thresholds = np.linspace(0.1, 0.9, 17)
        
        results = []
        
        for threshold in thresholds:
            # Predict labels based on threshold
            predicted_labels = [1 if score >= threshold else 0 
                              for score in self.predicted_scores]
            
            # Calculate metrics
            tp = sum(1 for t, p in zip(self.true_labels, predicted_labels) if t == 1 and p == 1)
            fp = sum(1 for t, p in zip(self.true_labels, predicted_labels) if t == 0 and p == 1)
            tn = sum(1 for t, p in zip(self.true_labels, predicted_labels) if t == 0 and p == 0)
            fn = sum(1 for t, p in zip(self.true_labels, predicted_labels) if t == 1 and p == 0)
            
            # Calculate rates
            tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tpr
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            
            results.append({
                'threshold': float(threshold),
                'true_positives': int(tp),
                'false_positives': int(fp),
                'true_negatives': int(tn),
                'false_negatives': int(fn),
                'true_positive_rate': float(tpr),
                'false_positive_rate': float(fpr),
                'precision': float(precision),
                'recall': float(recall),
                'f1_score': float(f1)
            })
        
        self.results = results
        return results
    
    def find_optimal_threshold(self, metric: str = 'f1_score') -> Tuple[float, Dict[str, Any]]:
        """Find optimal threshold based on specified metric"""
        if not self.results:
            self.evaluate_thresholds()
        
        best_result = max(self.results, key=lambda x: x[metric])
        return best_result['threshold'], best_result
    
    def plot_threshold_analysis(self, output_path: str):
        """Plot threshold analysis charts"""
        if not self.results:
            self.evaluate_thresholds()
        
        thresholds = [r['threshold'] for r in self.results]
        f1_scores = [r['f1_score'] for r in self.results]
        precision_scores = [r['precision'] for r in self.results]
        recall_scores = [r['recall'] for r in self.results]
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Plot 1: F1 Score vs Threshold
        axes[0, 0].plot(thresholds, f1_scores, 'b-', linewidth=2, marker='o')
        axes[0, 0].set_xlabel('Threshold')
        axes[0, 0].set_ylabel('F1 Score')
        axes[0, 0].set_title('F1 Score vs Threshold')
        axes[0, 0].grid(True, alpha=0.3)
        
        # Mark optimal threshold
        opt_threshold, opt_metrics = self.find_optimal_threshold()
        axes[0, 0].axvline(x=opt_threshold, color='r', linestyle='--', alpha=0.5)
        axes[0, 0].text(opt_threshold, max(f1_scores) * 0.9, 
                       f'Optimal: {opt_threshold:.3f}', 
                       color='r', ha='center')
        
        # Plot 2: Precision-Recall Curve
        precision, recall, _ = precision_recall_curve(self.true_labels, self.predicted_scores)
        axes[0, 1].plot(recall, precision, 'g-', linewidth=2)
        axes[0, 1].set_xlabel('Recall')
        axes[0, 1].set_ylabel('Precision')
        axes[0, 1].set_title('Precision-Recall Curve')
        axes[0, 1].grid(True, alpha=0.3)
        
        # Plot 3: Precision and Recall vs Threshold
        axes[1, 0].plot(thresholds, precision_scores, 'g-', linewidth=2, label='Precision')
        axes[1, 0].plot(thresholds, recall_scores, 'r-', linewidth=2, label='Recall')
        axes[1, 0].set_xlabel('Threshold')
        axes[1, 0].set_ylabel('Score')
        axes[1, 0].set_title('Precision & Recall vs Threshold')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # Plot 4: TPR vs FPR
        tpr_scores = [r['true_positive_rate'] for r in self.results]
        fpr_scores = [r['false_positive_rate'] for r in self.results]
        axes[1, 1].plot(fpr_scores, tpr_scores, 'purple', linewidth=2)
        axes[1, 1].plot([0, 1], [0, 1], 'k--', alpha=0.5)
        axes[1, 1].set_xlabel('False Positive Rate')
        axes[1, 1].set_ylabel('True Positive Rate')
        axes[1, 1].set_title('TPR vs FPR')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        
        logger.info(f"Threshold analysis plots saved to {output_path}")
    
    def analyze_anomaly_components(self, anomaly_data: List[Dict[str, float]], 
                                 true_labels: List[int]) -> Dict[str, Any]:
        """Analyze contribution of each anomaly component"""
        if not anomaly_data:
            return {}
        
        # Extract component scores
        components = ['recipient', 'temporal', 'content', 'behavioral']
        component_scores = {comp: [] for comp in components}
        
        for data in anomaly_data:
            for comp in components:
                if comp in data:
                    component_scores[comp].append(data[comp])
        
        # Calculate correlation with true labels
        correlations = {}
        for comp, scores in component_scores.items():
            if len(scores) == len(true_labels):
                correlation = np.corrcoef(scores, true_labels)[0, 1]
                correlations[comp] = float(correlation) if not np.isnan(correlation) else 0.0
        
        # Find most important components
        sorted_correlations = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
        
        # Calculate optimal weights based on correlations
        total_correlation = sum(abs(corr) for corr in correlations.values())
        optimal_weights = {}
        
        if total_correlation > 0:
            for comp, corr in correlations.items():
                optimal_weights[comp] = abs(corr) / total_correlation
        
        analysis = {
            'correlations': correlations,
            'most_important': sorted_correlations[0][0] if sorted_correlations else None,
            'optimal_weights': optimal_weights,
            'component_statistics': {
                comp: {
                    'mean': float(np.mean(scores)) if scores else 0,
                    'std': float(np.std(scores)) if scores else 0,
                    'min': float(np.min(scores)) if scores else 0,
                    'max': float(np.max(scores)) if scores else 0
                }
                for comp, scores in component_scores.items()
            }
        }
        
        return analysis
    
    def save_optimization_results(self, output_path: str):
        """Save optimization results"""
        opt_threshold, opt_metrics = self.find_optimal_threshold()
        
        results = {
            'optimal_threshold': opt_threshold,
            'optimal_metrics': opt_metrics,
            'all_threshold_results': self.results,
            'summary': {
                'total_samples': len(self.true_labels),
                'positive_samples': sum(self.true_labels),
                'negative_samples': len(self.true_labels) - sum(self.true_labels)
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=float)
        
        logger.info(f"Optimization results saved to {output_path}")
        
        return results