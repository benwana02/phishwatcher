import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_pipeline.email_parser import EmailParser, Email
from datetime import datetime

def test_email_class():
    """Test Email class creation"""
    email = Email(
        message_id="test123",
        sender="john.doe@company.com",
        recipients=["jane.smith@company.com", "admin@company.com"],
        timestamp=datetime.now(),
        subject="Test Email",
        body="This is a test email body.",
        headers={"X-Test": "test"}
    )
    
    assert email.sender == "john.doe@company.com"
    assert len(email.recipients) == 2
    print("✓ Email class test passed")

def test_email_cleaner():
    """Test email address cleaning"""
    from src.data_pipeline.email_parser import Email
    
    # Test different email formats
    test_cases = [
        ("John Doe <john.doe@company.com>", "john.doe@company.com"),
        ("jane.smith@company.com", "jane.smith@company.com"),
        ("\"Bob Jones\" <bob@company.com>", "bob@company.com"),
        ("INVALID", "invalid")
    ]
    
    for input_email, expected in test_cases:
        result = Email._clean_email(input_email)
        assert result == expected, f"Failed: {input_email} -> {result}"
    
    print("✓ Email cleaner test passed")

def test_parser():
    """Test CSV row parsing"""
    parser = EmailParser()
    
    test_row = {
        'message_id': 'msg001',
        'from': 'john.doe@enron.com',
        'to': 'jane.smith@enron.com, bob.jones@enron.com',
        'date': '2001-01-15 09:30:00',
        'subject': 'Meeting',
        'content': 'Let\'s meet at 2 PM.'
    }
    
    email = parser.parse_from_csv_row(test_row)
    
    assert email is not None
    assert email.sender == 'john.doe@enron.com'
    assert len(email.recipients) == 2
    assert 'jane.smith@enron.com' in email.recipients
    
    print("✓ Parser test passed")

if __name__ == "__main__":
    test_email_class()
    test_email_cleaner()
    test_parser()
    print("\n✅ All tests passed!")