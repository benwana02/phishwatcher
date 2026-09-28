# Data Pipeline Documentation

## Overview
The data pipeline processes the Enron email dataset and stores it in a structured format for behavioral analysis.

## Components

### 1. Email Parser (`email_parser.py`)
- Parses email data from CSV format
- Extracts and cleans email addresses
- Converts to structured `Email` objects

### 2. Enron Processor (`enron_processor.py`)
- Loads Enron dataset from CSV
- Handles data cleaning and validation
- Provides statistics about the dataset

### 3. Database (`database.py`)
- SQLite database for persistent storage
- Stores emails, recipients, and sender information
- Provides querying capabilities

## Usage

### Quick Start
```python
from src.data_pipeline.main import run_full_pipeline

# Process 1000 emails
results = run_full_pipeline("data/enron_dataset/raw/emails.csv", sample_size=1000)