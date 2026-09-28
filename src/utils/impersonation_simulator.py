"""
Impersonation Simulator - generates GENUINE internal-impersonation test
cases by swapping REAL per-user behaviour and/or writing style between
actual Enron senders, rather than synthetic filler text with injected
keywords.

utils/email_simulator.py is left completely UNCHANGED. It still has a
legitimate use: generic "does the system flag obviously weird traffic"
stress-testing (its 'suspicious'/'phishing' patterns). But its test
cases are not impersonation -- no other real person's identity is
involved -- so it cannot be used to answer RQ1, which is specifically
about detecting one user impersonating another. This module produces
the impersonation-specific cases objective 7 calls for:

  - normal        : a sender's own real email (no swap)              label 0
  - style_swap     : impersonator's real body, victim's real behaviour  label 1
  - behavior_swap  : victim's real body, impersonator's real behaviour  label 1
  - full_swap      : impersonator's real body AND real behaviour        label 1

Because the body text in every case is a real historical email (never
placeholder/filler text, never a keyword injected on top), a detector
cannot "win" by keyword-matching a synthetic marker -- it has to
actually recognise a real foreign writing style or a real foreign
communication pattern. This removes the circularity in the original
evaluation (see CHANGES.md, item 4).

NEW FILE - does not modify any existing file.
"""
import random
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional


class ImpersonationSimulator:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _fetch_emails(self, sender: str, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT message_id, timestamp, subject, body FROM emails "
            "WHERE sender = ? ORDER BY RANDOM() LIMIT ?",
            (sender, limit),
        )
        rows = cursor.fetchall()
        emails = []
        for message_id, timestamp_str, subject, body in rows:
            cursor.execute(
                "SELECT recipient_email FROM recipients WHERE message_id = ?",
                (message_id,),
            )
            recipients = [r[0] for r in cursor.fetchall()]
            emails.append({
                "message_id": message_id,
                "timestamp": datetime.fromisoformat(timestamp_str),
                "subject": subject,
                "body": body,
                "recipients": recipients,
            })
        conn.close()
        return emails

    def generate_normal(self, sender: str) -> Optional[Dict[str, Any]]:
        emails = self._fetch_emails(sender, limit=1)
        if not emails:
            return None
        email = emails[0]
        return {**email, "sender": sender, "true_label": 0, "case_type": "normal"}

    def generate_style_swap(self, victim: str, impersonator: str) -> Optional[Dict[str, Any]]:
        """Impersonator's real writing sent under the victim's real
        recipients/timing -- ONLY the writing style is anomalous."""
        victim_emails = self._fetch_emails(victim, limit=5)
        impersonator_emails = self._fetch_emails(impersonator, limit=5)
        if not victim_emails or not impersonator_emails:
            return None
        behavior_source = random.choice(victim_emails)
        style_source = random.choice(impersonator_emails)
        return {
            "sender": victim,
            "recipients": behavior_source["recipients"],
            "timestamp": behavior_source["timestamp"],
            "subject": style_source["subject"],
            "body": style_source["body"],
            "true_label": 1,
            "case_type": "style_swap",
        }

    def generate_behavior_swap(self, victim: str, impersonator: str) -> Optional[Dict[str, Any]]:
        """Victim's real writing sent at the impersonator's real
        recipients/timing -- ONLY the communication pattern is anomalous."""
        victim_emails = self._fetch_emails(victim, limit=5)
        impersonator_emails = self._fetch_emails(impersonator, limit=5)
        if not victim_emails or not impersonator_emails:
            return None
        style_source = random.choice(victim_emails)
        behavior_source = random.choice(impersonator_emails)
        return {
            "sender": victim,
            "recipients": behavior_source["recipients"],
            "timestamp": behavior_source["timestamp"],
            "subject": style_source["subject"],
            "body": style_source["body"],
            "true_label": 1,
            "case_type": "behavior_swap",
        }

    def generate_full_swap(self, victim: str, impersonator: str) -> Optional[Dict[str, Any]]:
        """Impersonator's real writing AND real behaviour, labelled as the
        victim -- both modalities anomalous."""
        impersonator_emails = self._fetch_emails(impersonator, limit=1)
        if not impersonator_emails:
            return None
        source = impersonator_emails[0]
        return {
            "sender": victim,
            "recipients": source["recipients"],
            "timestamp": source["timestamp"],
            "subject": source["subject"],
            "body": source["body"],
            "true_label": 1,
            "case_type": "full_swap",
        }

    def generate_test_set(self, senders: List[str], n_cases: int = 200,
                           normal_ratio: float = 0.7) -> List[Dict[str, Any]]:
        """Balanced mix drawn entirely from real emails. Use this in place
        of EmailSimulator.generate_test_set() for impersonation evaluation
        (see run_evaluation.py diff in CHANGES.md)."""
        cases: List[Dict[str, Any]] = []
        n_normal = int(n_cases * normal_ratio)
        n_swap = n_cases - n_normal
        swap_generators = {
            "style_swap": self.generate_style_swap,
            "behavior_swap": self.generate_behavior_swap,
            "full_swap": self.generate_full_swap,
        }

        for _ in range(n_normal):
            sender = random.choice(senders)
            case = self.generate_normal(sender)
            if case:
                cases.append(case)

        swap_types = list(swap_generators.keys())
        for _ in range(n_swap):
            if len(senders) < 2:
                break
            victim, impersonator = random.sample(senders, 2)
            swap_type = random.choice(swap_types)
            case = swap_generators[swap_type](victim, impersonator)
            if case:
                cases.append(case)

        random.shuffle(cases)
        return cases