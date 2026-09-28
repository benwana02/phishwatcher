import pandas as pd
"""
Email Parser Module
Handles parsing of email files and extraction of metadata
"""

import re
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Email:
    """Class to represent a single email"""
    message_id: str
    sender: str
    recipients: List[str]
    timestamp: datetime
    subject: str
    body: str
    headers: Dict[str, str]
    
    def __post_init__(self):
        """Clean email addresses after initialization"""
        self.sender = self._clean_email(self.sender)
        self.recipients = [self._clean_email(r) for r in self.recipients]
    
    @staticmethod
    def _clean_email(email_str: str) -> str:
        """Extract just the email address from a string"""
        # Remove angle brackets and extract email
        email_match = re.search(r'<?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>?', email_str)
        if email_match:
            return email_match.group(1).lower()
        return email_str.lower()


class EmailParser:
    """Parser for different email formats"""
    
    def __init__(self):
        self.email_pattern = re.compile(
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        )
    
    def parse_from_csv_row(self, row: dict) -> Optional[Email]:
        """
        Parse email from a CSV row (Enron dataset format)
        
        Args:
            row: Dictionary with email data
            
        Returns:
            Email object or None if parsing fails
        """
        try:
            # Extract message ID (create one if missing)
            message_id = row.get('message_id', f"enron_{hash(str(row))}")
            
            # Parse sender
            sender = row.get('from', '')
            if not sender:
                return None
            
            # Parse recipients
            to_field = row.get('to', '')
            cc_field = row.get('cc', '')
            bcc_field = row.get('bcc', '')
            
            recipients = []
            for field in [to_field, cc_field, bcc_field]:
                if pd.isna(field):
                    continue
                # Split multiple recipients
                field_recipients = [r.strip() for r in str(field).split(',') if r.strip()]
                recipients.extend(field_recipients)
            
            # Parse timestamp
            date_str = row.get('date', '')
            try:
                timestamp = pd.to_datetime(date_str, errors='coerce')
                if pd.isna(timestamp):
                    timestamp = datetime.now()
            except:
                timestamp = datetime.now()
            
            # Get subject and body
            subject = str(row.get('subject', '')).strip()
            body = str(row.get('content', '')).strip()
            
            # Extract headers (simplified for CSV)
            headers = {
                'X-From': row.get('from', ''),
                'X-To': row.get('to', ''),
                'X-CC': row.get('cc', ''),
                'X-BCC': row.get('bcc', ''),
                'X-Folder': row.get('folder', '')
            }
            
            return Email(
                message_id=message_id,
                sender=sender,
                recipients=recipients,
                timestamp=timestamp,
                subject=subject,
                body=body,
                headers=headers
            )
            
        except Exception as e:
            logger.error(f"Error parsing email row: {e}")
            return None