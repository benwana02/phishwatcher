"""
Adaptive Learner - Updates profiles based on new emails
"""

import json
from datetime import datetime
from typing import Dict, Any, List
import logging
import numpy as np

logger = logging.getLogger(__name__)


class AdaptiveLearner:
    """Adaptively updates profiles based on new emails"""
    
    def __init__(self, profiles: Dict[str, Any], learning_rate: float = 0.1):
        self.profiles = profiles
        self.learning_rate = learning_rate  # How quickly to adapt (0-1)
        
    def update_profile(self, sender: str, email_data: Dict[str, Any], 
                      is_legitimate: bool = True):
        """Update sender profile based on new email"""
        if sender not in self.profiles:
            logger.warning(f"Cannot update non-existent profile for {sender}")
            return False
        
        profile = self.profiles[sender]
        
        # Only update if email is legitimate
        if not is_legitimate:
            return False
        
        # Update temporal patterns (exponentially weighted moving average)
        timestamp = email_data['timestamp']
        
        # Update hourly distribution
        hour = timestamp.hour
        current_hour_weight = profile.hourly_distribution[hour]
        total_emails = profile.total_emails
        
        # EWMA update
        new_hour_weight = (1 - self.learning_rate) * current_hour_weight + \
                         self.learning_rate * 1
        
        profile.hourly_distribution[hour] = new_hour_weight
        
        # Update daily distribution
        day = timestamp.weekday()
        current_day_weight = profile.daily_distribution[day]
        new_day_weight = (1 - self.learning_rate) * current_day_weight + \
                        self.learning_rate * 1
        profile.daily_distribution[day] = new_day_weight
        
        # Update recipient frequencies
        recipients = email_data.get('recipients', [])
        for recipient in recipients:
            if recipient in profile.recipient_frequencies:
                current_freq = profile.recipient_frequencies[recipient]
                new_freq = (1 - self.learning_rate) * current_freq + \
                          self.learning_rate * 1
                profile.recipient_frequencies[recipient] = new_freq
            else:
                # New recipient - add with initial weight
                profile.recipient_frequencies[recipient] = self.learning_rate
                profile.unique_recipients.add(recipient)
        
        # Update content patterns
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        
        # Update average lengths (EWMA)
        profile.avg_subject_length = (1 - self.learning_rate) * profile.avg_subject_length + \
                                   self.learning_rate * len(subject)
        profile.avg_body_length = (1 - self.learning_rate) * profile.avg_body_length + \
                                 self.learning_rate * len(body)
        
        # Update last seen
        profile.last_seen = timestamp
        profile.total_emails += 1
        
        logger.info(f"Updated profile for {sender}")
        return True
    
    def batch_update(self, updates: List[Dict[str, Any]]):
        """Batch update profiles"""
        successful_updates = 0
        
        for update in updates:
            sender = update['sender']
            email_data = update['email_data']
            is_legitimate = update.get('is_legitimate', True)
            
            if self.update_profile(sender, email_data, is_legitimate):
                successful_updates += 1
        
        logger.info(f"Batch update completed: {successful_updates}/{len(updates)} successful")
        return successful_updates
    
    def detect_concept_drift(self, sender: str, window_size: int = 50) -> Dict[str, Any]:
        """Detect concept drift in sender behavior"""
        if sender not in self.profiles:
            return {'drift_detected': False, 'reason': 'No profile'}
        
        # This is a placeholder for concept drift detection
        # In a real implementation, you would:
        # 1. Store historical email features
        # 2. Compare recent window to historical patterns
        # 3. Use statistical tests (like KL divergence or chi-square)
        
        profile = self.profiles[sender]
        
        # Simple drift detection based on email frequency
        if profile.total_emails > 100:
            # Check if recent email rate has changed significantly
            # (This is simplified - real implementation would track timestamps)
            recent_emails = min(50, profile.total_emails)
            historical_rate = profile.total_emails / 365  # Assuming daily rate
            
            # If recent rate is 2x historical rate, flag as drift
            recent_rate = recent_emails / 30  # Last 30 days
            drift_ratio = recent_rate / historical_rate if historical_rate > 0 else 1
            
            if drift_ratio > 2.0 or drift_ratio < 0.5:
                return {
                    'drift_detected': True,
                    'drift_ratio': float(drift_ratio),
                    'message': f'Email rate changed by {drift_ratio:.1f}x'
                }
        
        return {
            'drift_detected': False,
            'drift_ratio': 1.0,
            'message': 'No significant drift detected'
        }