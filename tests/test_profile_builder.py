#!/usr/bin/env python3
"""
Test the Profile Builder
"""

import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.behavioral_analysis.profile_builder import ProfileBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # Test with sample database
    db_path = "data/emails.db"
    output_path = "data/profiles/profiles.json"
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("Please run the data pipeline first")
        return
    
    # Create output directory
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Build profiles
    print("Building profiles...")
    builder = ProfileBuilder(db_path)
    builder.build_all_profiles(min_emails=3)  # Lower threshold for testing
    
    # Save profiles
    builder.save_profiles(output_path)
    
    # Display statistics
    stats = builder.get_profile_stats()
    print("\n=== Profile Statistics ===")
    print(f"Total profiles built: {stats['total_profiles']}")
    print(f"Average emails per profile: {stats['avg_emails_per_profile']:.1f}")
    print(f"Average unique recipients: {stats['avg_unique_recipients_per_profile']:.1f}")
    
    print("\nTop 5 most active senders:")
    for sender, count in stats['top_senders'][:5]:
        print(f"  {sender}: {count} emails")
    
    # Test loading profiles
    print("\nTesting profile loading...")
    builder2 = ProfileBuilder(db_path)
    builder2.load_profiles(output_path)
    print(f"Successfully loaded {len(builder2.profiles)} profiles")

if __name__ == "__main__":
    main()