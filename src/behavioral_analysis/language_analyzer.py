"""
Language Analyzer - Analyzes writing style and language patterns
"""

import re
from collections import Counter
from typing import Dict, List, Tuple, Any
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
import logging

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

logger = logging.getLogger(__name__)


class LanguageAnalyzer:
    """Analyzes language patterns in emails"""
    
    URGENCY_WORDS = {
        'urgent', 'immediately', 'asap', 'critical', 'emergency',
        'verify', 'confirm', 'password', 'account', 'login',
        'suspended', 'terminated', 'action required', 'deadline'
    }
    
    FORMALITY_INDICATORS = {
        'formal': {'sincerely', 'regards', 'respectfully', 'cordially', 'yours truly'},
        'informal': {'cheers', 'thanks', 'thank you', 'best', 'talk soon', 'bye'}
    }
    
    def __init__(self):
        self.stop_words = set(stopwords.words('english'))
        
    def analyze_email(self, subject: str, body: str) -> Dict[str, Any]:
        """Analyze language patterns in an email"""
        # Combine subject and body for analysis
        full_text = f"{subject} {body}".lower()
        
        # Tokenize
        words = word_tokenize(full_text)
        sentences = sent_tokenize(full_text)
        
        # Calculate basic metrics
        analysis = {
            'word_count': len(words),
            'sentence_count': len(sentences),
            'avg_sentence_length': len(words) / max(len(sentences), 1),
            'unique_word_ratio': len(set(words)) / max(len(words), 1),
        }
        
        # Analyze urgency
        urgency_score = self._calculate_urgency_score(full_text, words)
        analysis['urgency_score'] = urgency_score
        
        # Analyze formality
        formality_score = self._calculate_formality_score(full_text)
        analysis['formality_score'] = formality_score
        
        # Analyze punctuation patterns
        punctuation_analysis = self._analyze_punctuation(full_text)
        analysis.update(punctuation_analysis)
        
        # Analyze common word patterns
        word_analysis = self._analyze_word_patterns(words)
        analysis.update(word_analysis)
        
        return analysis
    
    def _calculate_urgency_score(self, text: str, words: List[str]) -> float:
        """Calculate urgency score based on urgency words"""
        urgency_count = sum(1 for word in words if word in self.URGENCY_WORDS)
        
        # Also check for all caps words (common in urgency)
        all_caps_words = re.findall(r'\b[A-Z]{2,}\b', text)
        all_caps_score = len(all_caps_words) * 0.1
        
        # Check for exclamation marks
        exclamation_score = text.count('!') * 0.05
        
        total_score = min((urgency_count * 0.2) + all_caps_score + exclamation_score, 1.0)
        return total_score
    
    def _calculate_formality_score(self, text: str) -> float:
        """Calculate formality score (0=informal, 1=formal)"""
        formal_count = sum(1 for word in self.FORMALITY_INDICATORS['formal'] if word in text)
        informal_count = sum(1 for word in self.FORMALITY_INDICATORS['informal'] if word in text)
        
        total = formal_count + informal_count
        if total == 0:
            return 0.5  # Neutral
        
        formality_score = formal_count / total
        return formality_score
    
    def _analyze_punctuation(self, text: str) -> Dict[str, float]:
        """Analyze punctuation patterns"""
        analysis = {
            'exclamation_density': text.count('!') / max(len(text), 1) * 100,
            'question_density': text.count('?') / max(len(text), 1) * 100,
            'all_caps_ratio': len(re.findall(r'\b[A-Z]{2,}\b', text)) / max(len(text.split()), 1),
        }
        
        # Check for excessive punctuation
        analysis['excessive_punctuation'] = 1.0 if (
            text.count('!!!') > 0 or 
            text.count('??') > 0 or
            text.count('?!') > 0
        ) else 0.0
        
        return analysis
    
    def _analyze_word_patterns(self, words: List[str]) -> Dict[str, Any]:
        """Analyze word usage patterns"""
        # Remove stopwords
        content_words = [w for w in words if w.isalpha() and w not in self.stop_words]
        
        if not content_words:
            return {'common_words': [], 'word_frequency': {}}
        
        # Count word frequencies
        word_freq = Counter(content_words)
        common_words = word_freq.most_common(10)
        
        return {
            'common_words': common_words,
            'word_frequency': dict(word_freq)
        }
    
    def compare_profiles(self, profile1: Dict[str, Any], profile2: Dict[str, Any]) -> float:
        """Compare two language profiles, return similarity score (0-1)"""
        # Extract features to compare
        features1 = {
            'avg_sentence_length': profile1.get('avg_sentence_length', 0),
            'formality_score': profile1.get('formality_score', 0.5),
            'exclamation_density': profile1.get('exclamation_density', 0),
        }
        
        features2 = {
            'avg_sentence_length': profile2.get('avg_sentence_length', 0),
            'formality_score': profile2.get('formality_score', 0.5),
            'exclamation_density': profile2.get('exclamation_density', 0),
        }
        
        # Calculate similarity for each feature
        similarities = []
        for key in features1:
            if key in features2:
                val1 = features1[key]
                val2 = features2[key]
                
                # Normalize and compare
                if key == 'avg_sentence_length':
                    # Sentence length similarity (assuming normal range 5-30 words)
                    max_diff = 25
                    diff = abs(val1 - val2)
                    similarity = max(0, 1 - (diff / max_diff))
                else:
                    # For 0-1 scores
                    similarity = 1 - abs(val1 - val2)
                
                similarities.append(similarity)
        
        # Return average similarity
        return sum(similarities) / len(similarities) if similarities else 0.5