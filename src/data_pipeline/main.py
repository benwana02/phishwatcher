"""
Main data pipeline - integrates all components
"""

import logging
from pathlib import Path
from datetime import datetime
import json

from src.data_pipeline.enron_processor import EnronProcessor
from src.data_pipeline.database import EmailDatabase


def run_full_pipeline(data_path: str, sample_size: int = 5000):
    """
    Run the complete data pipeline
    
    Args:
        data_path: Path to Enron CSV
        sample_size: Number of emails to process (use None for all)
    """
    logger = logging.getLogger(__name__)
    
    start_time = datetime.now()
    logger.info(f"Starting pipeline at {start_time}")
    
    # Step 1: Process Enron dataset
    logger.info("Step 1: Processing Enron dataset...")
    processor = EnronProcessor(data_path)
    processor.load_dataset(sample_size=sample_size)
    emails = processor.parse_emails()
    
    # Step 2: Save statistics
    stats = processor.get_stats()
    stats_path = Path("data/enron_dataset/processed/stats.json")
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Statistics saved to {stats_path}")
    
    # Step 3: Store in database
    logger.info("Step 2: Storing in database...")
    db = EmailDatabase("data/emails.db")
    db.connect()
    db.create_tables()
    db.batch_insert_emails(emails)
    
    # Step 4: Generate report
    total_emails = db.get_email_count()
    sender_stats = db.get_sender_stats(limit=5)
    
    db.disconnect()
    
    # Step 5: Print summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info("\n" + "="*50)
    logger.info("PIPELINE COMPLETED SUCCESSFULLY")
    logger.info("="*50)
    logger.info(f"Total emails processed: {total_emails}")
    logger.info(f"Unique senders: {stats.get('unique_senders', 'N/A')}")
    logger.info(f"Unique recipients: {stats.get('unique_recipients', 'N/A')}")
    logger.info(f"Processing time: {duration}")
    logger.info("\nTop 5 senders:")
    for idx, row in sender_stats.iterrows():
        logger.info(f"  {row['email']}: {row['total_emails']} emails")
    
    return {
        'total_emails': total_emails,
        'processing_time': str(duration),
        'stats': stats
    }


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run pipeline with sample data
    data_path = "data/enron_dataset/raw/emails.csv"
    
    # Check if data exists
    if not Path(data_path).exists():
        print(f"Error: Dataset not found at {data_path}")
        print("Please download the dataset first.")
        exit(1)
    
    # Run with small sample for testing
    run_full_pipeline(data_path, sample_size=100000)