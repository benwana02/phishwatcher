"""
Evaluation Metrics Calculator
"""

import numpy as np
from typing import List, Dict, Any, Tuple
import matplotlib.pyplot as plt
from sklearn.metrics import (
    confusion_matrix, accuracy_score, precision_score, 
    recall_score, f1_score, roc_curve, auc
)
import json
import logging

logger = logging.getLogger(__name__)


class EvaluationMetrics:
    """Calculates and stores evaluation metrics"""
    
    def __init__(self):
        self.true_labels = []
        self.predicted_scores = []
        self.predicted_labels = []
        self.threshold = 0.5  # Default threshold
        
    def add_result(self, true_label: int, predicted_score: float, threshold: float = None):
        """Add a single result"""
        if threshold is None:
            threshold = self.threshold
        
        self.true_labels.append(true_label)
        self.predicted_scores.append(predicted_score)
        self.predicted_labels.append(1 if predicted_score >= threshold else 0)
    
    def add_batch(self, true_labels: List[int], predicted_scores: List[float], threshold: float = None):
        """Add a batch of results"""
        for true_label, score in zip(true_labels, predicted_scores):
            self.add_result(true_label, score, threshold)
    
    def calculate_metrics(self) -> Dict[str, float]:
        """Calculate all metrics"""
        if not self.true_labels:
            return {}
        
        # Convert to numpy arrays
        y_true = np.array(self.true_labels)
        y_pred = np.array(self.predicted_labels)
        y_scores = np.array(self.predicted_scores)
        
        # Basic metrics
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        
        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
        
        # ROC curve and AUC
        if len(np.unique(y_true)) > 1:
            fpr, tpr, _ = roc_curve(y_true, y_scores)
            roc_auc = auc(fpr, tpr)
        else:
            fpr, tpr, roc_auc = [], [], 0.5
        
        metrics = {
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'true_positives': int(tp),
            'false_positives': int(fp),
            'true_negatives': int(tn),
            'false_negatives': int(fn),
            'roc_auc': float(roc_auc),
            'threshold': float(self.threshold),
            'total_samples': len(y_true)
        }
        
        # Calculate rates
        if tp + fn > 0:
            metrics['true_positive_rate'] = tp / (tp + fn)
        if fp + tn > 0:
            metrics['false_positive_rate'] = fp / (fp + tn)
        
        return metrics
    
    def find_optimal_threshold(self) -> Tuple[float, Dict[str, float]]:
        """Find the threshold that maximizes F1 score"""
        if not self.true_labels:
            return 0.5, {}
        
        y_true = np.array(self.true_labels)
        y_scores = np.array(self.predicted_scores)
        
        best_f1 = 0
        best_threshold = 0.5
        best_metrics = {}
        
        # Test thresholds from 0.1 to 0.9
        thresholds = np.linspace(0.1, 0.9, 17)
        
        for threshold in thresholds:
            y_pred = (y_scores >= threshold).astype(int)
            
            # Calculate F1 score
            if len(np.unique(y_true)) > 1 and len(np.unique(y_pred)) > 1:
                f1 = f1_score(y_true, y_pred, zero_division=0)
            else:
                f1 = 0
            
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold
                
                # Store metrics for this threshold
                self.threshold = threshold
                self.predicted_labels = list(y_pred)
                best_metrics = self.calculate_metrics()
        
        return best_threshold, best_metrics
    
    def plot_roc_curve(self, output_path: str):
        """Plot ROC curve"""
        if not self.true_labels:
            return
        
        y_true = np.array(self.true_labels)
        y_scores = np.array(self.predicted_scores)
        
        if len(np.unique(y_true)) < 2:
            logger.warning("Cannot plot ROC curve with only one class")
            return
        
        fpr, tpr, _ = roc_curve(y_true, y_scores)
        roc_auc = auc(fpr, tpr)
        
        plt.figure(figsize=(10, 8))
        plt.plot(fpr, tpr, color='darkorange', lw=2, 
                label=f'ROC curve (AUC = {roc_auc:.3f})')
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver Operating Characteristic (ROC) Curve')
        plt.legend(loc="lower right")
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        
        logger.info(f"ROC curve saved to {output_path}")
    
    def plot_confusion_matrix(self, output_path: str):
        """Plot confusion matrix"""
        if not self.true_labels:
            return
        
        cm = confusion_matrix(self.true_labels, self.predicted_labels)
        
        plt.figure(figsize=(8, 6))
        
        # Create heatmap
        im = plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        plt.title('Confusion Matrix')
        plt.colorbar(im)
        
        # Add text annotations
        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                plt.text(j, i, format(cm[i, j], 'd'),
                        ha="center", va="center",
                        color="white" if cm[i, j] > thresh else "black")
        
        tick_marks = np.arange(2)
        plt.xticks(tick_marks, ['Normal', 'Phishing'])
        plt.yticks(tick_marks, ['Normal', 'Phishing'])
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        
        logger.info(f"Confusion matrix saved to {output_path}")
    
    def save_results(self, output_path: str):
        """Save evaluation results to JSON"""
        metrics = self.calculate_metrics()
        
        results = {
            'metrics': metrics,
            'raw_data': {
                'true_labels': self.true_labels,
                'predicted_scores': self.predicted_scores,
                'predicted_labels': self.predicted_labels
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=float)
        
        logger.info(f"Evaluation results saved to {output_path}")
    
    def generate_report(self, output_path: str):
        """Generate a comprehensive evaluation report"""
        metrics = self.calculate_metrics()
        
        # Find optimal threshold
        optimal_threshold, optimal_metrics = self.find_optimal_threshold()
        
        report = f"""PhishWatcher Evaluation Report
{"="*60}

BASIC METRICS (Threshold: {self.threshold:.3f})
{"-"*60}
Accuracy:    {metrics.get('accuracy', 0):.3f}
Precision:   {metrics.get('precision', 0):.3f}
Recall:      {metrics.get('recall', 0):.3f}
F1 Score:    {metrics.get('f1_score', 0):.3f}
ROC AUC:     {metrics.get('roc_auc', 0):.3f}

CONFUSION MATRIX
{"-"*60}
True Positives:  {metrics.get('true_positives', 0)}
False Positives: {metrics.get('false_positives', 0)}
True Negatives:  {metrics.get('true_negatives', 0)}
False Negatives: {metrics.get('false_negatives', 0)}

OPTIMAL THRESHOLD ANALYSIS
{"-"*60}
Optimal Threshold: {optimal_threshold:.3f}
Optimal F1 Score:  {optimal_metrics.get('f1_score', 0):.3f}

PERFORMANCE AT OPTIMAL THRESHOLD
{"-"*60}
Accuracy:  {optimal_metrics.get('accuracy', 0):.3f}
Precision: {optimal_metrics.get('precision', 0):.3f}
Recall:    {optimal_metrics.get('recall', 0):.3f}

DATASET INFORMATION
{"-"*60}
Total Samples: {metrics.get('total_samples', 0)}
Threshold:     {self.threshold:.3f}

RECOMMENDATIONS
{"-"*60}
"""
        
        if optimal_threshold != self.threshold:
            report += f"• Consider changing threshold from {self.threshold:.3f} to {optimal_threshold:.3f}\n"
        
        if metrics.get('precision', 0) < 0.7:
            report += "• Low precision: Too many false positives. Consider increasing threshold.\n"
        
        if metrics.get('recall', 0) < 0.7:
            report += "• Low recall: Too many false negatives. Consider decreasing threshold.\n"
        
        if metrics.get('roc_auc', 0) < 0.7:
            report += "• Model needs improvement: ROC AUC below 0.7 indicates poor discrimination.\n"
        
        with open(output_path, 'w') as f:
            f.write(report)
        
        logger.info(f"Evaluation report saved to {output_path}")
        
        return report