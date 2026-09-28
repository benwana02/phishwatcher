"""
Enron Dataset Processor
Handles loading and processing of the Enron email dataset
"""

import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm
import logging
from typing import List, Optional, Dict, Any
import json
import email
from email.utils import parsedate_to_datetime
import re

from .email_parser import EmailParser, Email

logger = logging.getLogger(__name__)


class EnronProcessor:
    """Process the Enron email dataset"""
    
    def __init__(self, data_path: str):
        """
        Initialize processor with path to dataset
        
        Args:
            data_path: Path to Enron CSV file
        """
        self.data_path = Path(data_path)
        self.parser = EmailParser()
        self.emails: List[Email] = []
        self.df: Optional[pd.DataFrame] = None
        self._has_raw_content = False
        
    def load_dataset(self, sample_size: Optional[int] = None) -> pd.DataFrame:
        """
        Load the Enron dataset from CSV
        
        Args:
            sample_size: If provided, load only this many rows (for testing)
            
        Returns:
            DataFrame with raw email data
        """
        logger.info(f"Loading dataset from {self.data_path}")
        
        if not self.data_path.exists():
            raise FileNotFoundError(f"Dataset not found at {self.data_path}")
        
        # Load CSV with error handling
        try:
            if sample_size:
                # Read sample for testing
                self.df = pd.read_csv(self.data_path, nrows=sample_size)
                logger.info(f"Loaded sample of {sample_size} rows")
            else:
                # Read full dataset
                self.df = pd.read_csv(self.data_path)
                logger.info(f"Loaded {len(self.df)} rows")
                
        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            raise

        # Normalize column names: lowercase and strip whitespace
        self.df.columns = self.df.columns.str.lower().str.strip()
        logger.info(f"Columns after normalization: {self.df.columns.tolist()}")
        
        # Basic cleaning
        self._clean_dataframe()
        
        return self.df
    
    def _clean_dataframe(self):
        """Clean the raw DataFrame and detect raw content column"""
        content_columns = ['content', 'message', 'body', 'text', 'raw']

        # If the dataframe already has real 'from' and 'date' columns, it's
        # pre-split -- don't reinterpret a same-named 'content' column as a
        # raw RFC822 blob just because the column name matches.
        has_presplit_columns = 'from' in self.df.columns and 'date' in self.df.columns

        found_content = None
        if not has_presplit_columns:
            for col in content_columns:
                if col in self.df.columns:
                    found_content = col
                    break
        
        if found_content:
            self._has_raw_content = True
            logger.info(f"Found raw email content in column: '{found_content}'")
            # Rename to 'content' for consistency
            if found_content != 'content':
                self.df.rename(columns={found_content: 'content'}, inplace=True)
            # Fill NaN in content with empty string – use .loc to avoid chained assignment warning
            self.df.loc[:, 'content'] = self.df['content'].fillna('')
        else:
            # Standard column mapping for pre-parsed CSV
            column_mappings = {
                'from': ['from', 'sender', 'from_address', 'fromemail', 'from_email'],
                'to': ['to', 'recipient', 'to_address', 'toemail', 'to_email'],
                'cc': ['cc', 'cc_address'],
                'bcc': ['bcc', 'bcc_address'],
                'subject': ['subject', 'subj', 'email_subject'],
                'content': ['content', 'body', 'message', 'text', 'email_body']
            }
            
            # Map actual columns to standard names
            for standard_name, possible_names in column_mappings.items():
                existing_col = next((col for col in possible_names if col in self.df.columns), None)
                if existing_col and existing_col != standard_name:
                    self.df.rename(columns={existing_col: standard_name}, inplace=True)
                    logger.debug(f"Renamed column '{existing_col}' to '{standard_name}'")
            
            # Fill missing text columns
            text_columns = ['from', 'to', 'cc', 'bcc', 'subject', 'content']
            for col in text_columns:
                if col in self.df.columns:
                    self.df.loc[:, col] = self.df[col].fillna('')
                else:
                    logger.warning(f"Column '{col}' not found in dataset – skipping")
            
            # Check if we have a sender column
            if 'from' not in self.df.columns:
                raise KeyError(
                    "No sender column found and no raw content column detected.\n"
                    f"Available columns: {self.df.columns.tolist()}\n"
                    f"Expected one of: {content_columns} for raw content, or a sender column."
                )
            
            # Drop rows without sender
            initial_count = len(self.df)
            self.df = self.df[self.df['from'].notna() & (self.df['from'] != '')]
            logger.info(f"Removed {initial_count - len(self.df)} rows without sender")
    
    def _parse_raw_email(self, raw_content: str) -> Optional[Dict[str, Any]]:
        """
        Parse raw email content into fields and headers
        
        Args:
            raw_content: Raw email string (headers + body)
            
        Returns:
            Dictionary with parsed fields and headers, or None if parsing fails
        """
        try:
            msg = email.message_from_string(raw_content)
            
            # Extract headers as dictionary
            headers = dict(msg.items())
            
            # Extract specific fields
            from_addr = msg.get('From', '')
            to_addr = msg.get('To', '')
            cc_addr = msg.get('Cc', '')
            bcc_addr = msg.get('Bcc', '')  # Bcc usually not present in headers
            subject = msg.get('Subject', '')
            date_str = msg.get('Date', '')
            
            # Parse date
            timestamp = None
            if date_str:
                try:
                    timestamp = parsedate_to_datetime(date_str)
                except:
                    pass
            
            # Get body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain':
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode('utf-8', errors='ignore')
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='ignore')
            
            return {
                'from': from_addr,
                'to': to_addr,
                'cc': cc_addr,
                'bcc': bcc_addr,
                'subject': subject,
                'body': body,
                'timestamp': timestamp,
                'headers': headers  # Include all headers for Email constructor
            }
        except Exception as e:
            logger.debug(f"Failed to parse raw email: {e}")
            return None
    
    def parse_emails(self, max_emails: Optional[int] = None) -> List[Email]:
        """
        Parse emails from the loaded dataset
        
        Args:
            max_emails: Maximum number of emails to parse (for testing)
            
        Returns:
            List of parsed Email objects
        """
        if self.df is None:
            self.load_dataset()
        
        self.emails = []
        failed_count = 0
        
        # Determine how many rows to process
        process_df = self.df
        if max_emails:
            process_df = self.df.head(max_emails)
        
        logger.info(f"Parsing {len(process_df)} emails...")
        
        # Parse each row
        for idx, row in tqdm(process_df.iterrows(), total=len(process_df), desc="Parsing emails"):
            if self._has_raw_content:
                # Parse from raw content column
                raw_content = row.get('content', '')
                if not raw_content:
                    failed_count += 1
                    continue
                
                parsed = self._parse_raw_email(raw_content)
                if not parsed:
                    failed_count += 1
                    continue
                
                # Build Email object with headers
                email_obj = Email(
                    message_id=str(idx),  # Generate a dummy ID
                    sender=parsed['from'],
                    recipients=self._split_addresses(parsed['to']) + 
                               self._split_addresses(parsed['cc']) + 
                               self._split_addresses(parsed['bcc']),
                    timestamp=parsed['timestamp'],
                    subject=parsed['subject'],
                    body=parsed['body'],
                    headers=parsed['headers']  # Added headers
                )
                self.emails.append(email_obj)
            else:
                # Use existing EmailParser for pre-parsed CSV
                email = self.parser.parse_from_csv_row(row.to_dict())
                if email:
                    self.emails.append(email)
                else:
                    failed_count += 1
        
        logger.info(f"Successfully parsed {len(self.emails)} emails, failed: {failed_count}")
        return self.emails
    
    def _split_addresses(self, addr_str: str) -> List[str]:
        """Split a comma-separated address string into a list"""
        if not addr_str:
            return []
        # Simple split by comma; you may want more robust parsing
        return [addr.strip() for addr in addr_str.split(',') if addr.strip()]
    
    def save_parsed_data(self, output_path: str):
        """
        Save parsed emails to JSON format
        
        Args:
            output_path: Path to save the parsed data
        """
        if not self.emails:
            logger.warning("No emails parsed yet. Running parse_emails() first.")
            self.parse_emails()
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert emails to dictionaries
        email_dicts = []
        for email in self.emails:
            email_dict = {
                'message_id': email.message_id,
                'sender': email.sender,
                'recipients': email.recipients,
                'timestamp': email.timestamp.isoformat() if email.timestamp else None,
                'subject': email.subject,
                'body_preview': email.body[:200] + "..." if len(email.body) > 200 else email.body,
                'body_length': len(email.body),
                'recipient_count': len(email.recipients)
                # Note: headers are omitted from saved JSON to keep it compact
            }
            email_dicts.append(email_dict)
        
        # Save to JSON
        with open(output_path, 'w') as f:
            json.dump(email_dicts, f, indent=2)
        
        logger.info(f"Saved {len(email_dicts)} emails to {output_path}")
    
    def get_stats(self) -> dict:
        """Get basic statistics about the parsed emails"""
        if not self.emails:
            return {}
        
        total_emails = len(self.emails)
        
        # Count unique senders and recipients
        all_senders = [email.sender for email in self.emails if email.sender]
        all_recipients = [recipient for email in self.emails for recipient in email.recipients if recipient]
        
        stats = {
            'total_emails': total_emails,
            'unique_senders': len(set(all_senders)),
            'unique_recipients': len(set(all_recipients)),
            'avg_recipients_per_email': np.mean([len(email.recipients) for email in self.emails]) if self.emails else 0,
            'total_recipient_instances': len(all_recipients),
            'sample_senders': list(set(all_senders))[:5] if all_senders else []
        }
        
        return stats