"""
Tests for the /api/upload and /api/categorize endpoints in app_flask.py

Covers:
- /api/upload   : file validation, successful upload with mocked parser
- /api/categorize: missing API key, no data, successful categorization
"""

import pytest
import json
import io
from unittest.mock import patch, MagicMock
import pandas as pd


# ── /api/upload ─────────────────────────────────────────────────────────────

class TestUploadEndpoint:

    def test_upload_no_file_returns_400(self, flask_app):
        response = flask_app.post('/api/upload')
        assert response.status_code == 400

    def test_upload_wrong_file_type_returns_400(self, flask_app):
        data = {'file': (io.BytesIO(b'not a pdf'), 'statement.txt')}
        response = flask_app.post('/api/upload', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'error' in result

    def test_upload_empty_filename_returns_400(self, flask_app):
        data = {'file': (io.BytesIO(b''), '')}
        response = flask_app.post('/api/upload', data=data, content_type='multipart/form-data')
        assert response.status_code == 400

    def test_successful_upload_returns_transaction_count(self, flask_app):
        """Mock the PDF parser to return sample transactions."""
        mock_df = pd.DataFrame({
            'date': ['01/05/2024', '01/06/2024'],
            'description': ['STARBUCKS', 'UBER'],
            'amount': [-4.50, -15.00]
        })

        with patch('app_flask.extract_transactions', return_value=mock_df):
            fake_pdf = io.BytesIO(b'%PDF-1.4 fake pdf content')
            data = {'file': (fake_pdf, 'statement.pdf')}
            response = flask_app.post('/api/upload', data=data, content_type='multipart/form-data')

        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['success'] is True
        assert result['count'] == 2

    def test_successful_upload_returns_transactions_list(self, flask_app):
        mock_df = pd.DataFrame({
            'date': ['01/05/2024'],
            'description': ['STARBUCKS'],
            'amount': [-4.50]
        })

        with patch('app_flask.extract_transactions', return_value=mock_df):
            fake_pdf = io.BytesIO(b'%PDF-1.4 fake pdf content')
            data = {'file': (fake_pdf, 'statement.pdf')}
            response = flask_app.post('/api/upload', data=data, content_type='multipart/form-data')

        result = json.loads(response.data)
        assert 'transactions' in result
        assert len(result['transactions']) == 1
        assert result['transactions'][0]['description'] == 'STARBUCKS'

    def test_parser_error_returns_400(self, flask_app):
        with patch('app_flask.extract_transactions', side_effect=ValueError("No transactions found")):
            fake_pdf = io.BytesIO(b'%PDF-1.4 fake pdf content')
            data = {'file': (fake_pdf, 'statement.pdf')}
            response = flask_app.post('/api/upload', data=data, content_type='multipart/form-data')

        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'error' in result


# ── /api/categorize ─────────────────────────────────────────────────────────

class TestCategorizeEndpoint:

    def test_categorize_without_api_key_returns_500(self, flask_app):
        with patch.dict('os.environ', {}, clear=True):
            # Remove ANTHROPIC_API_KEY from environment
            import os
            os.environ.pop('ANTHROPIC_API_KEY', None)
            response = flask_app.post('/api/categorize')
        assert response.status_code == 500
        result = json.loads(response.data)
        assert 'error' in result

    def test_categorize_without_uploaded_data_returns_400(self, flask_app):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'fake-key'}):
            response = flask_app.post('/api/categorize')
        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'error' in result

    def test_successful_categorization(self, flask_app, sample_transactions_df):
        """Upload data first, then categorize it with a mocked AI call."""
        categorized_df = sample_transactions_df.copy()
        categorized_df['category'] = ['Food & Dining', 'Transport', 'Shopping', 'Income', 'Subscriptions']

        # First, plant data into the session via upload
        mock_upload_df = sample_transactions_df.copy()
        with patch('app_flask.extract_transactions', return_value=mock_upload_df):
            fake_pdf = io.BytesIO(b'%PDF-1.4 fake pdf content')
            data = {'file': (fake_pdf, 'statement.pdf')}
            flask_app.post('/api/upload', data=data, content_type='multipart/form-data')

        # Now categorize
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'fake-key'}):
            with patch('app_flask.categorize_transactions', return_value=categorized_df):
                response = flask_app.post('/api/categorize')

        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['success'] is True
        assert 'transactions' in result
        assert 'summary' in result
