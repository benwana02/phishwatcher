#!/usr/bin/env python3
"""
Test the Anomaly Detector
"""

import sys
import os
import json
import logging
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.behavioral_analysis.profile_builder import ProfileBuilder
from src.behavioral_analysis.anomaly_detector import AnomalyDetector
from src.utils.email_simulator import EmailSimulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # Paths
    profiles_path = "data/profiles/profiles.json"
    test_output_path = "data/test_sets/test_emails.json"
    
    # Step 1: Load or create profiles
    if os.path.exists(profiles_path):
        print("Loading existing profiles...")
        builder = ProfileBuilder("data/emails.db")
        builder.load_profiles(profiles_path)
    else:
        print("No profiles found. Please run profile builder first.")
        return
    
    # Step 2: Create anomaly detector
    print("\nCreating anomaly detector...")
    detector = AnomalyDetector(builder.profiles)
    
    # Step 3: Generate test emails
    print("\nGenerating test emails...")
    simulator = EmailSimulator(profiles_path)
    test_emails = simulator.generate_test_set(num_emails=50)
    
    # Save test set for later use
    os.makedirs(os.path.dirname(test_output_path), exist_ok=True)
    simulator.save_test_set(test_emails, test_output_path)
    print(f"Saved test set to {test_output_path}")
    
    # Step 4: Analyze test emails
    print("\nAnalyzing test emails...")
    results = detector.analyze_batch(test_emails)
    
    # Step 5: Display results
    print("\n=== Anomaly Detection Results ===")
    print(f"Analyzed {len(results)} emails")
    
    # Categorize by risk level
    risk_counts = {'NORMAL': 0, 'LOW': 0, 'MEDIUM': 0, 'HIGH': 0, 'CRITICAL': 0}
    
    for i, result in enumerate(results[:10]):  # Show first 10
        email = result['email_data']
        score = result['anomaly_score']
        
        print(f"\nEmail {i+1}:")
        print(f"  Sender: {email['sender']}")
        print(f"  Pattern: {email.get('pattern', 'unknown')}")
        print(f"  Composite Score: {score['composite_score']:.3f}")
        print(f"  Risk Level: {score['risk_level']}")
        
        if score['reasons']:
            print(f"  Reasons: {', '.join(score['reasons'][:2])}")
        
        risk_counts[score['risk_level']] += 1
    
    # Show summary
    print("\n=== Summary ===")
    for risk_level, count in risk_counts.items():
        percentage = (count / len(results)) * 100
        print(f"{risk_level}: {count} emails ({percentage:.1f}%)")
    
    # Calculate detection accuracy for phishing emails
    phishing_emails = [r for r in results if r['email_data'].get('pattern') == 'phishing']
    if phishing_emails:
        detected_phishing = [r for r in phishing_emails 
                           if r['anomaly_score']['risk_level'] in ['HIGH', 'CRITICAL']]
        
        print(f"\nPhishing Detection:")
        print(f"  Total phishing emails: {len(phishing_emails)}")
        print(f"  Detected as high/critical risk: {len(detected_phishing)}")
        print(f"  Detection rate: {(len(detected_phishing)/len(phishing_emails)*100):.1f}%")
    
    # Save detailed results
    detailed_results = []
    for result in results:
        email_copy = result['email_data'].copy()
        email_copy['timestamp'] = email_copy['timestamp'].isoformat()
        detailed_results.append({
            'email': email_copy,
            'analysis': result['anomaly_score']
        })
    
    results_path = "data/test_sets/anomaly_results.json"
    with open(results_path, 'w') as f:
        json.dump(detailed_results, f, indent=2)
    
    print(f"\nDetailed results saved to {results_path}")

if __name__ == "__main__":
    main()