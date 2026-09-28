"""
Email Simulator - Creates test emails for anomaly detection
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json

class EmailSimulator:
    """Creates simulated emails for testing"""
    
    def __init__(self, profiles_path: str = None):
        self.profiles = {}
        if profiles_path:
            self.load_profiles(profiles_path)
        
        # Common test patterns
        self.test_patterns = {
            'normal': {
                'recipient_variation': 0.1,
                'time_variation': 2,  # hours
                'subject_variation': 0.2,
            },
            'suspicious': {
                'recipient_variation': 1.0,
                'time_variation': 12,  # hours
                'subject_variation': 1.0,
            },
            'phishing': {
                'recipient_variation': 1.0,
                'time_variation': 24,  # hours
                'subject_variation': 2.0,
                'urgency_keywords': ['urgent', 'immediate', 'verify', 'password', 'account'],
            }
        }
    
    def load_profiles(self, profiles_path: str):
        """Load sender profiles"""
        with open(profiles_path, 'r') as f:
            profiles_dict = json.load(f)
        
        # Convert to simplified format
        for sender, profile in profiles_dict.items():
            self.profiles[sender] = {
                'common_recipients': list(profile.get('recipient_frequencies', {}).keys())[:10],
                'typical_hours': [i for i, count in enumerate(profile.get('hourly_distribution', [])) if count > 0],
                'avg_subject_length': profile.get('avg_subject_length', 50),
                'avg_body_length': profile.get('avg_body_length', 500),
            }
    
    def generate_email(self, sender: str, pattern: str = 'normal') -> Dict[str, Any]:
        """Generate a test email"""
        if sender not in self.profiles:
            # Create a basic profile for new sender
            self.profiles[sender] = {
                'common_recipients': ['colleague1@company.com', 'colleague2@company.com'],
                'typical_hours': [9, 10, 11, 14, 15, 16],
                'avg_subject_length': 50,
                'avg_body_length': 500,
            }
        
        profile = self.profiles[sender]
        pattern_config = self.test_patterns[pattern]
        
        # Generate recipients
        if random.random() < pattern_config['recipient_variation'] or not profile['common_recipients']:
            # Unusual recipient
            recipients = [f'unusual_{random.randint(1,100)}@external.com']
        else:
            # Normal recipient
            recipients = random.sample(
                profile['common_recipients'], 
                min(random.randint(1, 3), len(profile['common_recipients']))
            )
        
        # Generate timestamp
        if profile['typical_hours']:
            typical_hour = random.choice(profile['typical_hours'])
            hour_variation = random.randint(-pattern_config['time_variation'], 
                                           pattern_config['time_variation'])
            hour = (typical_hour + hour_variation) % 24
        else:
            hour = random.randint(0, 23)
        
        # Create timestamp (within last 30 days)
        days_ago = random.randint(0, 30)
        timestamp = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23))
        timestamp = timestamp.replace(hour=hour, minute=random.randint(0, 59))
        
        # Generate subject
        base_subject_length = profile['avg_subject_length']
        subject_variation = random.uniform(-pattern_config['subject_variation'], 
                                          pattern_config['subject_variation'])
        subject_length = int(base_subject_length * (1 + subject_variation))
        
        if pattern == 'phishing' and 'urgency_keywords' in pattern_config:
            keyword = random.choice(pattern_config['urgency_keywords'])
            subject = f"URGENT: {keyword.capitalize()} Required - {'x' * max(10, subject_length - 20)}"
        else:
            subject = f"Test Subject {'x' * max(5, subject_length - 12)}"
        
        # Generate body
        base_body_length = profile['avg_body_length']
        body_length = int(base_body_length * random.uniform(0.5, 1.5))
        body = f"This is a test email body. {'x' * max(100, body_length - 100)}"
        
        return {
            'sender': sender,
            'recipients': recipients,
            'timestamp': timestamp,
            'subject': subject,
            'body': body,
            'pattern': pattern  # For evaluation
        }
    
    def generate_test_set(self, num_emails: int = 100) -> List[Dict[str, Any]]:
        """Generate a test set with mixed patterns"""
        test_emails = []
        
        # Define distribution of patterns
        patterns = ['normal'] * 70 + ['suspicious'] * 20 + ['phishing'] * 10
        
        # Get available senders or create new ones
        if self.profiles:
            senders = list(self.profiles.keys())
        else:
            senders = [f'sender{i}@company.com' for i in range(1, 11)]
        
        for _ in range(num_emails):
            sender = random.choice(senders)
            pattern = random.choice(patterns)
            email = self.generate_email(sender, pattern)
            test_emails.append(email)
        
        return test_emails
    
    def save_test_set(self, emails: List[Dict[str, Any]], output_path: str):
        """Save test set to JSON file"""
        # Convert datetime to string
        serializable_emails = []
        for email in emails:
            email_copy = email.copy()
            email_copy['timestamp'] = email_copy['timestamp'].isoformat()
            serializable_emails.append(email_copy)
        
        with open(output_path, 'w') as f:
            json.dump(serializable_emails, f, indent=2, default=str)
    
    def load_test_set(self, input_path: str) -> List[Dict[str, Any]]:
        """Load test set from JSON file"""
        with open(input_path, 'r') as f:
            emails = json.load(f)
        
        # Convert timestamp strings back to datetime
        for email in emails:
            email['timestamp'] = datetime.fromisoformat(email['timestamp'])
        
        return emails