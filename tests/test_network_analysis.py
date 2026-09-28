#!/usr/bin/env python3
"""
Test Network Analysis
"""

import sys
import os
import logging
import networkx as nx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.behavioral_analysis.network_analyzer import CommunicationNetwork
from src.behavioral_analysis.profile_builder import ProfileBuilder
from src.behavioral_analysis.anomaly_detector import AnomalyDetector
from src.utils.email_simulator import EmailSimulator
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # Paths
    db_path = "data/emails.db"
    profiles_path = "data/profiles/profiles.json"
    network_path = "data/network/communication_network.json"
    
    # Step 1: Build or load network
    if os.path.exists(network_path):
        print("Loading existing network...")
        network = CommunicationNetwork()
        network.load_network(network_path)
    else:
        print("Building communication network...")
        network = CommunicationNetwork()
        network.build_from_database(db_path, limit=1000)  # Limit for testing
        
        # Save network
        os.makedirs(os.path.dirname(network_path), exist_ok=True)
        network.save_network(network_path)
    
    # Step 2: Visualize network
    print("\nCreating network visualization...")
    visualization_path = "data/network/network_visualization.png"
    
    # Get top senders for highlighting
    top_senders = sorted(
        [(node, data['email_count']) for node, data in network.nodes.items() 
         if data.get('type') == 'sender'],
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    highlight_nodes = [sender for sender, _ in top_senders]
    network.visualize_network(visualization_path, highlight_nodes)
    print(f"Visualization saved to {visualization_path}")
    
    # Step 3: Analyze network metrics
    print("\n=== Network Analysis ===")
    print(f"Total nodes: {network.graph.number_of_nodes()}")
    print(f"Total edges: {network.graph.number_of_edges()}")
    print(f"Network density: {nx.density(network.graph):.4f}")
    
    # Analyze top senders
    print("\nTop 5 Senders:")
    for sender, count in top_senders:
        analysis = network.analyze_sender_network(sender)
        print(f"\n{sender}:")
        print(f"  Emails sent: {count}")
        print(f"  Unique recipients: {analysis.get('outdegree', 0)}")
        print(f"  Top recipients: {len(analysis.get('top_recipients', []))}")
    
    # Step 4: Test anomaly detection with network
    print("\n=== Network-Based Anomaly Detection ===")
    
    # Load profiles
    if os.path.exists(profiles_path):
        builder = ProfileBuilder(db_path)
        builder.load_profiles(profiles_path)
        
        # Create detector with network
        detector = AnomalyDetector(builder.profiles, network)
        
        # Test some scenarios
        test_cases = [
            {
                'sender': top_senders[0][0] if top_senders else 'test@company.com',
                'recipients': ['unknown@external.com'],
                'timestamp': datetime.now(),
                'subject': 'Test email to unknown recipient',
                'body': 'This is a test.'
            },
            {
                'sender': top_senders[0][0] if top_senders else 'test@company.com',
                'recipients': [top_senders[0][0]],  # Sending to themselves
                'timestamp': datetime.now(),
                'subject': 'Test email to self',
                'body': 'This is a test.'
            }
        ]
        
        for i, test_email in enumerate(test_cases):
            print(f"\nTest Case {i+1}:")
            print(f"  Sender: {test_email['sender']}")
            print(f"  Recipients: {test_email['recipients']}")
            
            score = detector.analyze_email(test_email)
            print(f"  Network Anomaly Score: {score.behavioral_anomaly:.3f}")
            print(f"  Composite Score: {score.composite_score:.3f}")
            
            if score.reasons:
                print(f"  Reasons: {', '.join(score.reasons[:2])}")
    
    else:
        print("No profiles found. Please run profile builder first.")

if __name__ == "__main__":
    main()