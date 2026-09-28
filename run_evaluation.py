#!/usr/bin/env python3
"""
Run Comprehensive Evaluation of PhishWatcher
"""

import sys
import os
import json
import logging
import random
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.evaluation.metrics_calculator import EvaluationMetrics
from src.evaluation.threshold_optimizer import ThresholdOptimizer
from src.behavioral_analysis.profile_builder import ProfileBuilder
from src.behavioral_analysis.anomaly_detector import AnomalyDetector
from src.behavioral_analysis.network_analyzer import CommunicationNetwork
from src.utils.email_simulator import EmailSimulator
from src.behavioral_analysis.stylometric_detector import StylometricAnomalyDetector   # ADD
from src.behavioral_analysis.ensemble_detector import EnsembleDetector                 # ADD
from src.utils.impersonation_simulator import ImpersonationSimulator                   # ADD
# NOTE: EmailSimulator import can stay -- keep it if you still want to run the
# original generic-anomaly stress test separately; it's just no longer used
# for the impersonation-accuracy evaluation below.

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def run_comprehensive_evaluation():
    """Run comprehensive evaluation"""
    print("Running Comprehensive Evaluation")
    print("="*60)
    
    # Paths
    db_path = "data/emails.db"
    profiles_path = "data/profiles/profiles.json"
    network_path = "data/network/communication_network.json"
    output_dir = "evaluation_results"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Step 1: Load or build system
    print("\n1. Loading system components...")
    
    if not os.path.exists(profiles_path):
        print("Building profiles...")
        builder = ProfileBuilder(db_path)
        builder.build_all_profiles(min_emails=3)
        builder.save_profiles(profiles_path)
    else:
        builder = ProfileBuilder(db_path)
        builder.load_profiles(profiles_path)
    
    if not os.path.exists(network_path):
        print("Building network...")
        network = CommunicationNetwork()
        network.build_from_database(db_path, limit=1000)
        network.save_network(network_path)
    else:
        network = CommunicationNetwork()
        network.load_network(network_path)
    
    behavioral_detector = AnomalyDetector(builder.profiles, network)
    stylometric_detector = StylometricAnomalyDetector(builder.profiles)
    detector = EnsembleDetector([behavioral_detector, stylometric_detector], weights=[0.5, 0.5])
    simulator = ImpersonationSimulator(db_path)
    
    # Step 2: Generate evaluation dataset
    print("\n2. Generating evaluation dataset...")
    
    # Generate mixed dataset
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
    
    # Step 3: Run detection and collect scores
    print("\n3. Running anomaly detection...")
    
    predicted_scores = []
    anomaly_components = []
    
    for i, email in enumerate(test_emails):
        if i % 20 == 0:
            print(f"  Processed {i}/{len(test_emails)} emails...")
        
        result = detector.analyze_email(email)
        predicted_scores.append(result['ensemble_composite'])
        components = {
            'recipient': result['ensemble_components'].get('recipient_anomaly', 0.0),
            'temporal': result['ensemble_components'].get('temporal_anomaly', 0.0),
            'content': result['ensemble_components'].get('content_anomaly', 0.0),
            'behavioral': result['ensemble_components'].get('behavioral_anomaly', 0.0),
            'stylometric': result['ensemble_components'].get('stylometric_anomaly', 0.0),
        }
        anomaly_components.append(components)
    
    # Step 4: Calculate metrics
    print("\n4. Calculating evaluation metrics...")
    
    metrics_calculator = EvaluationMetrics()
    metrics_calculator.add_batch(true_labels, predicted_scores)
    
    # Calculate basic metrics
    metrics = metrics_calculator.calculate_metrics()
    
    print(f"\nBasic Metrics (Threshold: {metrics_calculator.threshold:.3f})")
    print("-"*40)
    print(f"Accuracy:  {metrics['accuracy']:.3f}")
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall:    {metrics['recall']:.3f}")
    print(f"F1 Score:  {metrics['f1_score']:.3f}")
    print(f"ROC AUC:   {metrics['roc_auc']:.3f}")
    
    # Step 5: Find optimal threshold
    print("\n5. Finding optimal threshold...")
    
    optimizer = ThresholdOptimizer()
    optimizer.load_evaluation_data(true_labels, predicted_scores)
    optimizer.evaluate_thresholds()
    
    opt_threshold, opt_metrics = optimizer.find_optimal_threshold()
    
    print(f"Optimal Threshold: {opt_threshold:.3f}")
    print(f"Optimal F1 Score:  {opt_metrics['f1_score']:.3f}")
    
    # Step 6: Generate plots and reports
    print("\n6. Generating plots and reports...")
    
    # Generate plots
    metrics_calculator.plot_roc_curve(os.path.join(output_dir, "roc_curve.png"))
    metrics_calculator.plot_confusion_matrix(os.path.join(output_dir, "confusion_matrix.png"))
    optimizer.plot_threshold_analysis(os.path.join(output_dir, "threshold_analysis.png"))
    
    # Generate component analysis
    component_analysis = optimizer.analyze_anomaly_components(anomaly_components, true_labels)
    
    print("\nComponent Analysis:")
    print("-"*40)
    for component, correlation in component_analysis['correlations'].items():
        importance = "✓" if abs(correlation) > 0.3 else " "
        print(f"  {importance} {component:12s}: {correlation:+.3f}")
    
    # Generate reports
    metrics_calculator.save_results(os.path.join(output_dir, "metrics_results.json"))
    metrics_calculator.generate_report(os.path.join(output_dir, "evaluation_report.txt"))
    optimizer.save_optimization_results(os.path.join(output_dir, "optimization_results.json"))
    
    # Save component analysis
    with open(os.path.join(output_dir, "component_analysis.json"), 'w') as f:
        json.dump(component_analysis, f, indent=2)
    
    # Step 7: Summary
    print("\n" + "="*60)
    print("EVALUATION COMPLETE")
    print("="*60)
    
    summary = f"""
Summary:
--------
• Dataset: {len(test_emails)} emails (balanced)
• Best F1 Score: {opt_metrics['f1_score']:.3f} at threshold {opt_threshold:.3f}
• ROC AUC: {metrics['roc_auc']:.3f}
• Most Important Feature: {component_analysis.get('most_important', 'N/A')}

Recommendations:
---------------
"""
    
    if opt_threshold != 0.5:
        summary += f"• Change threshold from 0.500 to {opt_threshold:.3f}\n"
    
    if metrics['precision'] < 0.8:
        summary += "• Focus on reducing false positives\n"
    
    if metrics['recall'] < 0.8:
        summary += "• Focus on reducing false negatives\n"
    
    # Add component-specific recommendations
    for component, correlation in component_analysis.get('correlations', {}).items():
        if abs(correlation) < 0.2:
            summary += f"• Consider improving {component} anomaly detection\n"
    
    summary += f"\nFiles saved to: {output_dir}/"
    
    print(summary)
    
    # Save summary
    with open(os.path.join(output_dir, "summary.txt"), 'w') as f:
        f.write(summary)
    
    return {
        'success': True,
        'optimal_threshold': opt_threshold,
        'optimal_f1': opt_metrics['f1_score'],
        'roc_auc': metrics['roc_auc'],
        'output_dir': output_dir
    }

if __name__ == "__main__":
    try:
        results = run_comprehensive_evaluation()
        print(f"\n✅ Evaluation completed successfully!")
        print(f"   Results saved to: {results['output_dir']}")
    except Exception as e:
        print(f"\n❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)