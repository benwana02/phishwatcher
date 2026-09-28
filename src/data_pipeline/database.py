"""
Database module for storing email data
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import logging
from typing import List, Optional
import pandas as pd

from .email_parser import Email

logger = logging.getLogger(__name__)


class EmailDatabase:
    """SQLite database for storing parsed emails"""
    
    def __init__(self, db_path: str = "data/emails.db"):
        """
        Initialize database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        
    def connect(self):
        """Connect to SQLite database"""
        self.conn = sqlite3.connect(self.db_path)
        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON")
        
    def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def create_tables(self):
        """Create database tables"""
        if not self.conn:
            self.connect()
        
        cursor = self.conn.cursor()
        
        # Emails table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                message_id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                subject TEXT,
                body TEXT,
                body_length INTEGER,
                headers TEXT
            )
        ''')
        
        # Recipients table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                recipient_type TEXT DEFAULT 'to',
                FOREIGN KEY (message_id) REFERENCES emails (message_id) ON DELETE CASCADE
            )
        ''')
        
        # Senders table (for quick lookup)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS senders (
                email TEXT PRIMARY KEY,
                first_seen DATETIME,
                last_seen DATETIME,
                total_emails INTEGER DEFAULT 0
            )
        ''')
        
        self.conn.commit()
        logger.info("Database tables created successfully")
    
    def insert_email(self, email: Email):
        """
        Insert a single email into the database
        
        Args:
            email: Email object to insert
        """
        if not self.conn:
            self.connect()
        
        cursor = self.conn.cursor()
        
        try:
            # Insert into emails table
            cursor.execute('''
                INSERT OR REPLACE INTO emails 
                (message_id, sender, timestamp, subject, body, body_length, headers)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                email.message_id,
                email.sender,
                email.timestamp.isoformat(),
                email.subject,
                email.body,
                len(email.body),
                str(email.headers)
            ))
            
            # Insert recipients
            for recipient in email.recipients:
                cursor.execute('''
                    INSERT INTO recipients (message_id, recipient_email)
                    VALUES (?, ?)
                ''', (email.message_id, recipient))
            
            # Update senders table
            cursor.execute('''
                INSERT OR IGNORE INTO senders (email, first_seen, last_seen, total_emails)
                VALUES (?, ?, ?, 1)
            ''', (email.sender, email.timestamp.isoformat(), email.timestamp.isoformat()))
            
            cursor.execute('''
                UPDATE senders 
                SET last_seen = ?, total_emails = total_emails + 1
                WHERE email = ?
            ''', (email.timestamp.isoformat(), email.sender))
            
            self.conn.commit()
            
        except sqlite3.Error as e:
            logger.error(f"Error inserting email {email.message_id}: {e}")
            self.conn.rollback()
    
    def batch_insert_emails(self, emails: List[Email]):
        """
        Insert multiple emails efficiently
        
        Args:
            emails: List of Email objects
        """
        logger.info(f"Inserting {len(emails)} emails into database...")
        
        if not self.conn:
            self.connect()
        
        # Use transaction for better performance
        cursor = self.conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        
        try:
            for email in emails:
                # Insert email
                cursor.execute('''
                    INSERT OR REPLACE INTO emails 
                    (message_id, sender, timestamp, subject, body, body_length, headers)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    email.message_id,
                    email.sender,
                    email.timestamp.isoformat(),
                    email.subject,
                    email.body,
                    len(email.body),
                    str(email.headers)
                ))
                
                # Insert recipients
                for recipient in email.recipients:
                    cursor.execute('''
                        INSERT INTO recipients (message_id, recipient_email)
                        VALUES (?, ?)
                    ''', (email.message_id, recipient))
            
            cursor.execute("COMMIT")
            logger.info(f"Successfully inserted {len(emails)} emails")
            
        except sqlite3.Error as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Error in batch insert: {e}")
    
    def get_email_count(self) -> int:
        """Get total number of emails in database"""
        if not self.conn:
            self.connect()
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM emails")
        return cursor.fetchone()[0]
    
    def get_sender_stats(self, limit: int = 10) -> pd.DataFrame:
        """
        Get statistics for top senders
        
        Args:
            limit: Number of top senders to return
            
        Returns:
            DataFrame with sender statistics
        """
        if not self.conn:
            self.connect()
        
        query = '''
            SELECT 
                email,
                total_emails,
                first_seen,
                last_seen
            FROM senders
            ORDER BY total_emails DESC
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, self.conn, params=(limit,))
        return df


def create_sample_database():
    """Create a sample database for testing"""
    db = EmailDatabase("data/sample.db")
    db.connect()
    db.create_tables()
    
    # Create a few sample emails
    from datetime import datetime
    from email_parser import Email
    
    sample_emails = [
        Email(
            message_id="test1",
            sender="john.doe@enron.com",
            recipients=["jane.smith@enron.com"],
            timestamp=datetime(2001, 1, 15, 9, 30),
            subject="Meeting",
            body="Let's meet at 2 PM.",
            headers={}
        ),
        Email(
            message_id="test2",
            sender="jane.smith@enron.com",
            recipients=["john.doe@enron.com", "bob.jones@enron.com"],
            timestamp=datetime(2001, 1, 16, 14, 0),
            subject="Project Update",
            body="Here's the project update.",
            headers={}
        )
    ]
    
    db.batch_insert_emails(sample_emails)
    print(f"Database created with {db.get_email_count()} emails")
    
    # Show sender stats
    stats = db.get_sender_stats()
    print("\nSender Statistics:")
    print(stats)
    
    db.disconnect()


if __name__ == "__main__":
    create_sample_database()