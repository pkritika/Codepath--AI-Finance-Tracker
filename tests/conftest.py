"""
Shared fixtures and configuration for all TrackWise tests.
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ── Sample Data Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def sample_transactions_df():
    """A small DataFrame of realistic transactions for testing."""
    return pd.DataFrame({
        'date': ['01/05/2024', '01/07/2024', '01/10/2024', '01/12/2024', '01/15/2024'],
        'description': ['STARBUCKS #1234', 'UBER RIDE', 'AMAZON.COM', 'SALARY DEPOSIT', 'NETFLIX'],
        'amount': [-4.50, -15.00, -89.99, 3500.00, -15.99]
    })


@pytest.fixture
def sample_raw_transactions():
    """Raw list of transaction dicts as returned by the PDF parser."""
    return [
        {'date': '01/05/2024', 'description': 'STARBUCKS #1234', 'amount': '-4.50'},
        {'date': '01/07/2024', 'description': 'UBER RIDE',       'amount': '-15.00'},
        {'date': '01/10/2024', 'description': 'AMAZON.COM',      'amount': '-89.99'},
    ]


@pytest.fixture
def mock_anthropic_client():
    """A mocked Anthropic client that returns a predictable category list."""
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='["Food & Dining", "Transport", "Shopping", "Income", "Subscriptions"]')]
    client.messages.create.return_value = mock_response
    return client


@pytest.fixture
def flask_app():
    """Create a Flask test client with test configuration."""
    from app_flask import app
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    with app.test_client() as client:
        with app.app_context():
            yield client
