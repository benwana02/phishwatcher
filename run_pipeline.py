#!/usr/bin/env python3
"""
Main script to run the data pipeline
"""

import sys
import os
import logging
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from data_pipeline.enron_processor import EnronProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Main pipeline execution"""
    logger = logging.getLogger(__name__)
    
    # Paths
    data_path = "data/enron_dataset/raw/emails.csv"
    output_path = "data/enron_dataset/processed/parsed_emails.json"
    
    # Check if data exists
    if not os.path.exists(data_path):
        logger.error(f"Dataset not found at {data_path}")
        logger.info("Please download the dataset first.")
        return
    
    # Create processor
    logger.info("Initializing Enron Processor...")
    processor = EnronProcessor(data_path)
    
    # Load dataset (small sample for testing)
    logger.info("Loading dataset (sample of 1000 emails)...")
    processor.load_dataset(sample_size=1000)
    
    # Parse emails
    logger.info("Parsing emails...")
    emails = processor.parse_emails()
    
    # Get statistics
    stats = processor.get_stats()
    logger.info("\n=== Dataset Statistics ===")
    for key, value in stats.items():
        if isinstance(value, list):
            logger.info(f"{key}: {value}")
        else:
            logger.info(f"{key}: {value}")
    
    # Save parsed data
    logger.info(f"\nSaving parsed data to {output_path}...")
    processor.save_parsed_data(output_path)
    
    logger.info("\n✅ Data pipeline completed successfully!")
    logger.info(f"Parsed {len(emails)} emails")

if __name__ == "__main__":
    main()