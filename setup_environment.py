#!/usr/bin/env python3
"""
Environment setup script for new developers
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a shell command with error handling"""
    print(f"\n🔧 {description}...")
    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"✅ {description} completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during {description}: {e}")
        sys.exit(1)

def main():
    print("="*60)
    print("PhishWatcher - Environment Setup")
    print("="*60)
    
    # Create directories
    print("\n📁 Creating project structure...")
    directories = [
        "data/enron_dataset/raw",
        "data/enron_dataset/processed",
        "data/test_emails",
        "src/data_pipeline",
        "src/utils",
        "tests",
        "notebooks",
        "docs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  Created: {directory}")
    
    # Create virtual environment
    run_command("python -m venv venv", "Creating virtual environment")
    
    # Install requirements
    print("\n📦 Installing requirements...")
    if sys.platform == "win32":
        pip_cmd = "venv\\Scripts\\pip"
    else:
        pip_cmd = "venv/bin/pip"
    
    run_command(f"{pip_cmd} install --upgrade pip", "Upgrading pip")
    run_command(f"{pip_cmd} install -r requirements.txt", "Installing packages")
    
    # Create sample test email
    print("\n📧 Creating sample test email...")
    sample_email = """From: john.doe@enron.com
To: jane.smith@enron.com
Date: 2001-01-15 09:30:00
Subject: Test Email
Content: This is a test email for the pipeline.
"""
    
    with open("data/test_emails/sample.eml", "w") as f:
        f.write(sample_email)
    
    print("\n" + "="*60)
    print("✅ Setup completed successfully!")
    print("\nNext steps:")
    print("1. Activate virtual environment:")
    print("   Windows: venv\\Scripts\\activate")
    print("   Mac/Linux: source venv/bin/activate")
    print("\n2. Download Enron dataset:")
    print("   - Visit: https://www.kaggle.com/datasets/wcukierski/enron-email-dataset")
    print("   - Download emails.csv to data/enron_dataset/raw/")
    print("\n3. Run the pipeline:")
    print("   python run_pipeline.py")
    print("="*60)

if __name__ == "__main__":
    main()