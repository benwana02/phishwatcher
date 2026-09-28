"""
Integration tests for the data pipeline
"""

import sys
import os
import tempfile
import json
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_pipeline.email_parser import EmailParser
from src.data_pipeline.enron_processor import EnronProcessor
from src.data_pipeline.database import EmailDatabase


def create_test_csv():
    """Create a test CSV file"""
    import pandas as pd
    
    test_data = {
        'message_id': ['test001', 'test002'],
        'from': ['john.doe@enron.com', 'jane.smith@enron.com'],
        'to': ['jane.smith@enron.com', 'john.doe@enron.com, bob.jones@enron.com'],
        'date': ['2001-01-15 09:30:00', '2001-01-16 14:00:00'],
        'subject': ['Meeting', 'Project Update'],
        'content': ['Let\'s meet at 2 PM.', 'Here\'s the project update.']
    }
    
    return pd.DataFrame(test_data)


def test_full_pipeline():
    """Test the complete data pipeline"""
    print("Testing full pipeline...")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test CSV
        test_df = create_test_csv()
        csv_path = Path(tmpdir) / "test_emails.csv"
        test_df.to_csv(csv_path, index=False)
        
        # Step 1: Process emails
        processor = EnronProcessor(str(csv_path))
        processor.load_dataset()
        emails = processor.parse_emails()
        
        assert len(emails) == 2, f"Expected 2 emails, got {len(emails)}"
        print("✓ Email parsing successful")
        
        # Step 2: Save to database
        db_path = Path(tmpdir) / "test.db"
        db = EmailDatabase(str(db_path))
        db.connect()
        db.create_tables()
        try:
            db.batch_insert_emails(emails)
        
            email_count = db.get_email_count()
            assert email_count == 2, f"Expected 2 emails in DB, got {email_count}"
            print("✓ Database insertion successful")
        
        # Step 3: Check statistics
            stats = processor.get_stats()
            assert stats['total_emails'] == 2
            assert stats['unique_senders'] == 2
            print("✓ Statistics calculation successful")
        finally:
        
        # Clean up
            db.disconnect()    # always runs, even on failure -- fixes the Windows PermissionError
    
    print("\n✅ All integration tests passed!")


if __name__ == "__main__":
    test_full_pipeline()