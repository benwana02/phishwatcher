"""
Anomaly Detector - Detects behavioral anomalies in emails
"""

import json
import math
from datetime import datetime, time
from typing import Dict, List, Any, Optional, Tuple
import logging
import numpy as np

from .language_analyzer import LanguageAnalyzer
from .network_analyzer import CommunicationNetwork

logger = logging.getLogger(__name__)


class AnomalyScore:
    """Class to hold anomaly scores for an email"""
    
    def __init__(self):
        self.recipient_anomaly = 0.0  # 0-1 score
        self.temporal_anomaly = 0.0   # 0-1 score
        self.content_anomaly = 0.0    # 0-1 score
        self.behavioral_anomaly = 0.0 # 0-1 score
        self.composite_score = 0.0    # Weighted average
        
        # Anomaly reasons
        self.reasons = []
    
    def calculate_composite(self, weights: Dict[str, float] = None):
        """Calculate composite score with weights"""
        if weights is None:
            weights = {
                'recipient': 0.4,
                'temporal': 0.3,
                'content': 0.2,
                'behavioral': 0.1
            }
        
        self.composite_score = (
            weights['recipient'] * self.recipient_anomaly +
            weights['temporal'] * self.temporal_anomaly +
            weights['content'] * self.content_anomaly +
            weights['behavioral'] * self.behavioral_anomaly
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'recipient_anomaly': self.recipient_anomaly,
            'temporal_anomaly': self.temporal_anomaly,
            'content_anomaly': self.content_anomaly,
            'behavioral_anomaly': self.behavioral_anomaly,
            'composite_score': self.composite_score,
            'reasons': self.reasons,
            'risk_level': self.get_risk_level()
        }
    
    def get_risk_level(self) -> str:
        """Get human-readable risk level"""
        if self.composite_score >= 0.8:
            return "CRITICAL"
        elif self.composite_score >= 0.6:
            return "HIGH"
        elif self.composite_score >= 0.4:
            return "MEDIUM"
        elif self.composite_score >= 0.2:
            return "LOW"
        else:
            return "NORMAL"


class AnomalyDetector:
    """Detects anomalies by comparing emails to sender profiles and network relationships"""
    
    def __init__(self, profiles: Dict[str, Any], network: CommunicationNetwork = None):
        self.profiles = profiles
        self.language_analyzer = LanguageAnalyzer()
        self.network = network
    
    def calculate_recipient_anomaly(self, sender: str, recipients: List[str]) -> Tuple[float, List[str]]:
        """Calculate anomaly based on recipients"""
        if sender not in self.profiles:
            return 1.0, ["Sender has no behavioral profile"]
        
        profile = self.profiles[sender]
        anomaly_score = 0.0
        reasons = []
        
        # Calculate score for each recipient
        for recipient in recipients:
            if recipient in profile.recipient_frequencies:
                # Recipient is known, check frequency
                frequency = profile.recipient_frequencies[recipient]
                total_emails = profile.total_emails
                probability = frequency / total_emails
                
                # Low probability = more anomalous
                recipient_score = 1 - probability
                anomaly_score = max(anomaly_score, recipient_score)
                
                if recipient_score > 0.7:
                    reasons.append(f"Rare recipient: {recipient} (probability: {probability:.3f})")
            else:
                # Unknown recipient - highly anomalous
                anomaly_score = 1.0
                reasons.append(f"Unknown recipient: {recipient}")
        
        # Normalize by number of recipients
        if recipients:
            anomaly_score = min(anomaly_score * len(recipients), 1.0)
        
        return anomaly_score, reasons
    
    def calculate_temporal_anomaly(self, sender: str, timestamp: datetime) -> Tuple[float, List[str]]:
        """Calculate anomaly based on sending time"""
        if sender not in self.profiles:
            return 1.0, ["Sender has no behavioral profile"]
        
        profile = self.profiles[sender]
        hour = timestamp.hour
        day = timestamp.weekday()
        
        # Get hour probability
        hour_count = profile.hourly_distribution[hour]
        total_emails = profile.total_emails
        
        if total_emails == 0:
            return 0.0, []
        
        hour_probability = hour_count / total_emails
        
        # Get day probability
        day_count = profile.daily_distribution[day]
        day_probability = day_count / total_emails
        
        # Calculate anomaly scores (1 - probability)
        hour_anomaly = 1 - hour_probability
        day_anomaly = 1 - day_probability
        
        # Combine scores (weight hour more heavily)
        anomaly_score = (hour_anomaly * 0.7) + (day_anomaly * 0.3)
        
        reasons = []
        if hour_anomaly > 0.8:
            reasons.append(f"Unusual hour: {hour}:00 (probability: {hour_probability:.3f})")
        if day_anomaly > 0.8:
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            reasons.append(f"Unusual day: {day_names[day]} (probability: {day_probability:.3f})")
        
        return anomaly_score, reasons
    
    def calculate_language_anomaly(self, sender: str, subject: str, body: str) -> Tuple[float, List[str]]:
        """Calculate anomaly based on language patterns"""
        if sender not in self.profiles:
            return 1.0, ["Sender has no behavioral profile"]
        
        profile = self.profiles[sender]
        
        # Analyze current email
        current_analysis = self.language_analyzer.analyze_email(subject, body)
        
        # Get sender's language profile
        sender_profile = profile.language_profile if hasattr(profile, 'language_profile') else {}
        
        if not sender_profile:
            return 0.0, []
        
        anomaly_score = 0.0
        reasons = []
        
        # Check sentence length
        current_sent_len = current_analysis.get('avg_sentence_length', 0)
        profile_sent_len = sender_profile.get('avg_sentence_length', 0)
        
        if profile_sent_len > 0:
            sent_ratio = current_sent_len / profile_sent_len
            if sent_ratio < 0.5 or sent_ratio > 2.0:
                sent_anomaly = abs(1 - sent_ratio) / 2
                anomaly_score = max(anomaly_score, sent_anomaly)
                reasons.append(f"Unusual sentence length (ratio: {sent_ratio:.2f})")
        
        # Check formality
        current_formality = current_analysis.get('formality_score', 0.5)
        profile_formality = sender_profile.get('formality_score', 0.5)
        
        if abs(current_formality - profile_formality) > 0.4:
            formality_anomaly = abs(current_formality - profile_formality)
            anomaly_score = max(anomaly_score, formality_anomaly)
            reasons.append(f"Unusual formality level (diff: {abs(current_formality - profile_formality):.2f})")
        
        # Check urgency
        current_urgency = current_analysis.get('urgency_score', 0)
        if current_urgency > 0.7:
            anomaly_score = max(anomaly_score, current_urgency)
            reasons.append(f"High urgency language (score: {current_urgency:.2f})")
        
        # Check excessive punctuation
        if current_analysis.get('excessive_punctuation', 0) > 0:
            anomaly_score = max(anomaly_score, 0.8)
            reasons.append("Excessive punctuation detected")
        
        return anomaly_score, reasons
    
    def calculate_network_anomaly(self, sender: str, recipients: List[str]) -> Tuple[float, List[str]]:
        """Calculate anomaly based on network relationships"""
        if not self.network:
            return 0.0, ["No network data available"]
        
        anomaly_score = 0.0
        reasons = []
        
        for recipient in recipients:
            relationship_analysis = self.network.detect_anomalous_relationships(sender, recipient)
            
            if relationship_analysis['is_anomalous']:
                # Use the confidence as anomaly score
                recipient_score = relationship_analysis['confidence']
                anomaly_score = max(anomaly_score, recipient_score)
                
                if relationship_analysis['reasons']:
                    reasons.extend(relationship_analysis['reasons'])
        
        return anomaly_score, reasons
    
    def analyze_email(self, email_data: Dict[str, Any]) -> AnomalyScore:
        """
        Analyze a single email for anomalies
        
        email_data should contain:
        - sender: str
        - recipients: List[str]
        - timestamp: datetime
        - subject: str
        - body: str
        """
        score = AnomalyScore()
        
        # Extract data
        sender = email_data.get('sender')
        recipients = email_data.get('recipients', [])
        timestamp = email_data.get('timestamp')
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        
        if not sender:
            score.reasons.append("No sender specified")
            score.calculate_composite()
            return score
        
        # Calculate individual anomaly scores
        recipient_score, recipient_reasons = self.calculate_recipient_anomaly(sender, recipients)
        temporal_score, temporal_reasons = self.calculate_temporal_anomaly(sender, timestamp)
        language_score, language_reasons = self.calculate_language_anomaly(sender, subject, body)
        network_score, network_reasons = self.calculate_network_anomaly(sender, recipients)
        
        # Update scores (content_anomaly now holds language-based anomaly)
        score.recipient_anomaly = recipient_score
        score.temporal_anomaly = temporal_score
        score.content_anomaly = language_score
        score.behavioral_anomaly = network_score
        
        # Collect all reasons
        score.reasons = recipient_reasons + temporal_reasons + language_reasons + network_reasons
        
        # Calculate composite score
        score.calculate_composite()
        
        return score
    
    def analyze_batch(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze multiple emails"""
        results = []
        
        for email_data in emails:
            score = self.analyze_email(email_data)
            result = {
                'email_data': email_data,
                'anomaly_score': score.to_dict()
            }
            results.append(result)
        
        return results