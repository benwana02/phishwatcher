"""
Profile Builder - Creates behavioral profiles for email senders
"""

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, time
from typing import Dict, List, Any
from .language_analyzer import LanguageAnalyzer
from .stylometric_analyzer import StylometricAnalyzer
import sqlite3
import logging
import numpy as np

# Import language analyzer
from .language_analyzer import LanguageAnalyzer

logger = logging.getLogger(__name__)


class SenderProfile:
    """Class to store a sender's behavioral profile"""

    def __init__(self, sender_email: str):
        self.sender_email = sender_email
        self.total_emails = 0
        self.first_seen = None
        self.last_seen = None

        # Recipient patterns
        self.recipient_frequencies = Counter()  # {recipient: count}
        self.unique_recipients = set()

        # Temporal patterns
        self.hourly_distribution = [0] * 24  # Count for each hour (0-23)
        self.daily_distribution = [0] * 7    # Count for each day (0=Monday)

        # Content patterns
        self.avg_subject_length = 0
        self.avg_body_length = 0
        self.common_greetings = Counter()
        self.common_signoffs = Counter()

        # Email type patterns
        self.internal_ratio = 0  # % emails to internal addresses
        self.external_ratio = 0  # % emails to external addresses

        # Language patterns
        self.language_profile = {
            'avg_sentence_length': 0,
            'formality_score': 0,
            'urgency_score': 0,
            'exclamation_density': 0,
            'sample_size': 0
        }

        self.stylometric_profile = {
            'mean_vector': [],   # list, not np.ndarray, so it stays JSON-serializable
            'std_vector': [],
            'sample_size': 0,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary for JSON storage"""
        result = {
            'sender_email': self.sender_email,
            'total_emails': self.total_emails,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'recipient_frequencies': dict(self.recipient_frequencies),
            'unique_recipients_count': len(self.unique_recipients),
            'hourly_distribution': self.hourly_distribution,
            'daily_distribution': self.daily_distribution,
            'avg_subject_length': self.avg_subject_length,
            'avg_body_length': self.avg_body_length,
            'common_greetings': dict(self.common_greetings),
            'common_signoffs': dict(self.common_signoffs),
            'internal_ratio': self.internal_ratio,
            'external_ratio': self.external_ratio,
            'language_profile': self.language_profile,
            'stylometric_profile': self.stylometric_profile
        }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SenderProfile':
        """Create profile from dictionary"""
        profile = cls(data['sender_email'])
        profile.total_emails = data['total_emails']
        profile.first_seen = datetime.fromisoformat(data['first_seen']) if data['first_seen'] else None
        profile.last_seen = datetime.fromisoformat(data['last_seen']) if data['last_seen'] else None

        # Rebuild counters
        profile.recipient_frequencies = Counter(data['recipient_frequencies'])
        profile.unique_recipients = set(data['recipient_frequencies'].keys())

        profile.hourly_distribution = data['hourly_distribution']
        profile.daily_distribution = data['daily_distribution']
        profile.avg_subject_length = data['avg_subject_length']
        profile.avg_body_length = data['avg_body_length']
        profile.common_greetings = Counter(data['common_greetings'])
        profile.common_signoffs = Counter(data['common_signoffs'])
        profile.internal_ratio = data['internal_ratio']
        profile.external_ratio = data['external_ratio']
        profile.language_profile = data.get('language_profile', {
            'avg_sentence_length': 0,
            'formality_score': 0,
            'urgency_score': 0,
            'exclamation_density': 0,
            'sample_size': 0
        })
        profile.stylometric_profile = data.get('stylometric_profile', {
            'mean_vector': [], 'std_vector': [], 'sample_size': 0,
        })

        return profile


class ProfileBuilder:
    """Builds behavioral profiles from email database"""

    # Common greetings and signoffs to track
    GREETINGS = ['hi', 'hello', 'dear', 'hey', 'good morning', 'good afternoon']
    SIGNOFFS = ['regards', 'thanks', 'thank you', 'best', 'sincerely', 'cheers']

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.profiles: Dict[str, SenderProfile] = {}
        self.language_analyzer = LanguageAnalyzer()
        self.stylometric_analyzer = StylometricAnalyzer()

    def extract_greeting(self, email_body: str) -> str:
        """Extract greeting from email body (first 50 chars)"""
        body_start = email_body[:50].lower().strip()

        for greeting in self.GREETINGS:
            if body_start.startswith(greeting):
                return greeting

        # Check for "Dear [Name]" pattern
        if body_start.startswith('dear '):
            return 'dear'

        return 'unknown'

    def extract_signoff(self, email_body: str) -> str:
        """Extract signoff from email body (last 100 chars)"""
        body_end = email_body[-100:].lower().strip()

        for signoff in self.SIGNOFFS:
            if signoff in body_end:
                return signoff

        return 'unknown'

    def build_profile_for_sender(self, sender_email: str, min_emails: int = 5) -> SenderProfile:
        """Build profile for a specific sender"""
        profile = SenderProfile(sender_email)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all emails for this sender, including message_id
        query = """
        SELECT message_id, timestamp, subject, body
        FROM emails
        WHERE sender = ?
        """
        cursor.execute(query, (sender_email,))
        rows = cursor.fetchall()

        if len(rows) < min_emails:
            logger.warning(f"Sender {sender_email} has only {len(rows)} emails (minimum {min_emails})")
            conn.close()
            return None

        total_subject_length = 0
        total_body_length = 0
        internal_emails = 0
        external_emails = 0
        sender_domain = sender_email.split('@')[-1]
        language_data = []  # Collect language features for each email
        body_texts = []

        for message_id, timestamp_str, subject, body in rows:
            timestamp = datetime.fromisoformat(timestamp_str)

            # Update first/last seen
            if profile.first_seen is None or timestamp < profile.first_seen:
                profile.first_seen = timestamp
            if profile.last_seen is None or timestamp > profile.last_seen:
                profile.last_seen = timestamp

            # Get recipients for this email from the recipients table
            cursor.execute(
                "SELECT recipient_email FROM recipients WHERE message_id = ?",
                (message_id,)
            )
            recipient_rows = cursor.fetchall()
            recipients = [r[0] for r in recipient_rows]

            for recipient in recipients:
                profile.recipient_frequencies[recipient] += 1
                profile.unique_recipients.add(recipient)

                # Check if internal (same domain)
                recipient_domain = recipient.split('@')[-1] if '@' in recipient else ''
                if sender_domain == recipient_domain:
                    internal_emails += 1
                else:
                    external_emails += 1

            # Update temporal patterns
            profile.hourly_distribution[timestamp.hour] += 1
            profile.daily_distribution[timestamp.weekday()] += 1

            # Update content patterns
            total_subject_length += len(subject)
            total_body_length += len(body)

            # Extract greeting and signoff
            greeting = self.extract_greeting(body)
            signoff = self.extract_signoff(body)
            profile.common_greetings[greeting] += 1
            profile.common_signoffs[signoff] += 1

            # Analyze language
            language_analysis = self.language_analyzer.analyze_email(subject, body)
            language_data.append(language_analysis)
            body_texts.append(f"{subject} {body}")

            profile.total_emails += 1

        # Calculate averages
        if profile.total_emails > 0:
            profile.avg_subject_length = total_subject_length / profile.total_emails
            profile.avg_body_length = total_body_length / profile.total_emails

            total_recipient_instances = internal_emails + external_emails
            if total_recipient_instances > 0:
                profile.internal_ratio = internal_emails / total_recipient_instances
                profile.external_ratio = external_emails / total_recipient_instances

        # Calculate average language features
        if language_data:
            profile.language_profile = {
                'avg_sentence_length': np.mean([d.get('avg_sentence_length', 0) for d in language_data]),
                'formality_score': np.mean([d.get('formality_score', 0.5) for d in language_data]),
                'urgency_score': np.mean([d.get('urgency_score', 0) for d in language_data]),
                'exclamation_density': np.mean([d.get('exclamation_density', 0) for d in language_data]),
                'sample_size': len(language_data),
            }
            
        # builds the per-user writeprint (mean + std)
        if body_texts:
            mean_vec, std_vec = self.stylometric_analyzer.build_writeprint(body_texts)
            if mean_vec is not None:
                profile.stylometric_profile = {
                    'mean_vector': mean_vec.tolist(),
                    'std_vector': std_vec.tolist(),
                    'sample_size': len(body_texts),
                }    

        conn.close()
        return profile

    def build_all_profiles(self, min_emails: int = 5):
        """Build profiles for all senders with sufficient emails"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all senders with enough emails
        query = """
        SELECT sender, COUNT(*) as email_count
        FROM emails
        GROUP BY sender
        HAVING email_count >= ?
        """
        cursor.execute(query, (min_emails,))
        senders = cursor.fetchall()

        logger.info(f"Building profiles for {len(senders)} senders...")

        for idx, (sender, count) in enumerate(senders, 1):
            logger.info(f"[{idx}/{len(senders)}] Building profile for {sender} ({count} emails)")
            profile = self.build_profile_for_sender(sender, min_emails)
            if profile:
                self.profiles[sender] = profile

        conn.close()
        logger.info(f"Built {len(self.profiles)} profiles")

    def save_profiles(self, output_path: str):
        """Save all profiles to JSON file"""
        profiles_dict = {
            sender: profile.to_dict()
            for sender, profile in self.profiles.items()
        }

        with open(output_path, 'w') as f:
            json.dump(profiles_dict, f, indent=2, default=str)

        logger.info(f"Saved {len(self.profiles)} profiles to {output_path}")

    def load_profiles(self, input_path: str):
        """Load profiles from JSON file"""
        with open(input_path, 'r') as f:
            profiles_dict = json.load(f)

        self.profiles = {
            sender: SenderProfile.from_dict(data)
            for sender, data in profiles_dict.items()
        }

        logger.info(f"Loaded {len(self.profiles)} profiles from {input_path}")

    def get_profile_stats(self) -> Dict[str, Any]:
        """Get statistics about the built profiles"""
        if not self.profiles:
            return {}

        profile_counts = len(self.profiles)
        avg_emails_per_profile = np.mean([p.total_emails for p in self.profiles.values()])
        avg_unique_recipients = np.mean([len(p.unique_recipients) for p in self.profiles.values()])

        # Find most active senders
        top_senders = sorted(
            self.profiles.items(),
            key=lambda x: x[1].total_emails,
            reverse=True
        )[:10]

        return {
            'total_profiles': profile_counts,
            'avg_emails_per_profile': avg_emails_per_profile,
            'avg_unique_recipients_per_profile': avg_unique_recipients,
            'top_senders': [(s, p.total_emails) for s, p in top_senders]
        }