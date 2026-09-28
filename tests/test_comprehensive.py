#!/usr/bin/env python3
"""
Comprehensive Test Suite for PhishWatcher
"""

import sys
import os
import json
import logging
from datetime import datetime
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.behavioral_analysis.profile_builder import ProfileBuilder, SenderProfile
from src.behavioral_analysis.anomaly_detector import AnomalyDetector, AnomalyScore
from src.behavioral_analysis.network_analyzer import CommunicationNetwork
from src.behavioral_analysis.language_analyzer import LanguageAnalyzer
from src.utils.email_simulator import EmailSimulator

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise for tests

class TestPhishWatcher:
    """Comprehensive test class for PhishWatcher"""

    @classmethod
    def setup_class(cls):
        """Set up test environment"""
        # Create test data directory
        os.makedirs('tests/test_data', exist_ok=True)

        # Create a small test database
        cls.create_test_database()

        # Initialize components
        cls.profile_builder = ProfileBuilder('tests/test_data/test.db')
        cls.language_analyzer = LanguageAnalyzer()
        cls.network = CommunicationNetwork()

    @classmethod
    def create_test_database(cls):
        """Create a small test database matching the real production schema"""
        import sqlite3

        conn = sqlite3.connect('tests/test_data/test.db')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                message_id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                subject TEXT,
                body TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                recipient_email TEXT,
                recipient_type TEXT
            )
        ''')

        test_emails = [
            ('1', 'john@company.com', '2024-01-15 09:00:00', 'Meeting', "Hi team, let's meet at 2 PM."),
            ('2', 'john@company.com', '2024-01-16 10:30:00', 'Project Update', 'Here is the project update.'),
            ('3', 'jane@company.com', '2024-01-16 14:00:00', 'Report', 'Please find the report attached.'),
            ('4', 'john@company.com', '2024-01-17 15:00:00', 'URGENT: Account Verification',
             'Verify your account immediately! Click here: http://fake.com'),
        ]
        cursor.executemany(
            'INSERT OR REPLACE INTO emails (message_id, sender, timestamp, subject, body) VALUES (?, ?, ?, ?, ?)',
            test_emails
        )

        test_recipients = [
            ('1', 'jane@company.com', 'to'), ('1', 'bob@company.com', 'to'),
            ('2', 'jane@company.com', 'to'),
            ('3', 'john@company.com', 'to'), ('3', 'admin@company.com', 'to'),
            ('4', 'unusual@external.com', 'to'),
        ]
        cursor.executemany(
            'INSERT INTO recipients (message_id, recipient_email, recipient_type) VALUES (?, ?, ?)',
            test_recipients
        )

        conn.commit()
        conn.close()
    
    def test_language_analyzer(self):
        """Test language analysis functionality"""
        # Test normal email
        normal_analysis = self.language_analyzer.analyze_email(
            'Meeting',
            'Hi team, let\'s meet at 2 PM to discuss the project.'
        )

        assert 'word_count' in normal_analysis
        assert normal_analysis['urgency_score'] < 0.3  # Not urgent

        # Test phishing email
        phishing_analysis = self.language_analyzer.analyze_email(
            'URGENT: Account Verification',
            'Verify your account IMMEDIATELY!!! Click here: http://fake.com'
        )

        assert phishing_analysis['urgency_score'] > 0.5  # Urgent
        assert phishing_analysis['excessive_punctuation'] == 1.0  # Has '!!!'
    
    def test_anomaly_detector(self):
        """Test anomaly detection functionality"""
        # Build profiles first
        self.profile_builder.build_all_profiles(min_emails=2)
        
        # Create detector
        detector = AnomalyDetector(self.profile_builder.profiles)
        
        # Test normal email
        normal_email = {
            'sender': 'john@company.com',
            'recipients': ['jane@company.com'],
            'timestamp': datetime(2024, 1, 16, 10, 0, 0),
            'subject': 'Regular update',
            'body': 'Here is the regular update.'
        }
        
        normal_score = detector.analyze_email(normal_email)
        assert normal_score.composite_score < 0.4  # Low anomaly
        
        # Test suspicious email
        suspicious_email = {
            'sender': 'john@company.com',
            'recipients': ['unknown@external.com'],
            'timestamp': datetime(2024, 1, 16, 3, 0, 0),  # 3 AM
            'subject': 'URGENT: Verify your account NOW!',
            'body': 'Click here to verify: http://suspicious.com'
        }
        
        suspicious_score = detector.analyze_email(suspicious_email)
        assert suspicious_score.composite_score > 0.6  # High anomaly
        assert len(suspicious_score.reasons) > 0
    
    def test_network_analyzer(self):
        """Test network analysis functionality"""
        # Build network
        self.network.build_from_database('tests/test_data/test.db')
        
        # Check network properties
        assert self.network.graph.number_of_nodes() >= 3
        assert self.network.graph.number_of_edges() >= 3
        
        # Analyze sender network
        analysis = self.network.analyze_sender_network('john@company.com')
        assert analysis['outdegree'] == 3  # Sent to 3 unique recipients
        
        # Test anomalous relationship detection
        relationship = self.network.detect_anomalous_relationships(
            'john@company.com',
            'unknown@external.com'
        )
        
        # Since this is a known relationship in test data, it shouldn't be anomalous
        # unless we add more specific tests
        assert 'edge_data' in relationship
    
    def test_email_simulator(self):
        """Test email simulator functionality"""
        # Create simulator
        simulator = EmailSimulator()
        
        # Generate normal email
        normal_email = simulator.generate_email('test@company.com', 'normal')
        
        assert 'sender' in normal_email
        assert 'recipients' in normal_email
        assert 'subject' in normal_email
        assert 'body' in normal_email
        assert normal_email['pattern'] == 'normal'
        
        # Generate phishing email
        phishing_email = simulator.generate_email('test@company.com', 'phishing')
        
        assert phishing_email['pattern'] == 'phishing'
        assert 'URGENT' in phishing_email['subject']  # Phishing emails have urgency
        
        # Generate test set
        test_set = simulator.generate_test_set(num_emails=10)
        assert len(test_set) == 10
        
        # Save and load test set
        simulator.save_test_set(test_set, 'tests/test_data/test_set.json')
        loaded_set = simulator.load_test_set('tests/test_data/test_set.json')
        
        assert len(loaded_set) == 10
    
    def test_integration(self):
        """Test integration of all components"""
        # Build all components
        self.profile_builder.build_all_profiles(min_emails=2)
        self.network.build_from_database('tests/test_data/test.db')
        
        # Create integrated detector
        detector = AnomalyDetector(
            self.profile_builder.profiles,
            self.network
        )
        
        # Create simulator with profiles
        simulator = EmailSimulator('tests/test_data/profiles.json')
        
        # Generate and test emails
        test_emails = simulator.generate_test_set(num_emails=5)
        
        results = detector.analyze_batch(test_emails)
        
        assert len(results) == 5
        
        # Check that all emails were analyzed
        for result in results:
            assert 'anomaly_score' in result
            assert 'composite_score' in result['anomaly_score']
            
            # Scores should be between 0 and 1
            score = result['anomaly_score']['composite_score']
            assert 0 <= score <= 1

def run_all_tests():
    """Run all tests and generate report"""
    print("Running comprehensive tests...")
    print("="*60)
    
    test_suite = TestPhishWatcher()
    test_suite.setup_class()
    
    tests = [
        ('Profile Builder', test_suite.test_profile_builder),
        ('Language Analyzer', test_suite.test_language_analyzer),
        ('Anomaly Detector', test_suite.test_anomaly_detector),
        ('Network Analyzer', test_suite.test_network_analyzer),
        ('Email Simulator', test_suite.test_email_simulator),
        ('Integration', test_suite.test_integration),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            test_func()
            results.append((test_name, 'PASSED', ''))
            print(f"✓ {test_name}: PASSED")
        except Exception as e:
            results.append((test_name, 'FAILED', str(e)))
            print(f"✗ {test_name}: FAILED - {e}")
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, status, _ in results if status == 'PASSED')
    total = len(results)
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    # Save detailed report
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_tests': total,
        'passed': passed,
        'failed': total - passed,
        'success_rate': passed/total*100,
        'details': [
            {
                'test': name,
                'status': status,
                'error': error
            }
            for name, status, error in results
        ]
    }
    
    with open('tests/test_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nDetailed report saved to: tests/test_report.json")
    
    return all(status == 'PASSED' for _, status, _ in results)

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)