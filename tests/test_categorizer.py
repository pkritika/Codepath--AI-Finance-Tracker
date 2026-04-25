"""
Tests for categorizer.py

Covers:
- _parse_categories_response() : JSON parsing and category validation
- _build_categorization_prompt(): prompt construction
- get_category_summary()        : spending summary by category
- categorize_transactions()     : full flow with mocked API
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from categorizer import (
    CATEGORIES,
    _parse_categories_response,
    _build_categorization_prompt,
    get_category_summary,
    categorize_transactions,
)


# ── _parse_categories_response ──────────────────────────────────────────────

class TestParseCategoriesResponse:

    def test_valid_json_array(self):
        response = '["Food & Dining", "Transport", "Shopping"]'
        result = _parse_categories_response(response, 3)
        assert result == ["Food & Dining", "Transport", "Shopping"]

    def test_markdown_code_block_stripped(self):
        response = '```json\n["Food & Dining", "Transport"]\n```'
        result = _parse_categories_response(response, 2)
        assert result == ["Food & Dining", "Transport"]

    def test_plain_code_block_stripped(self):
        response = '```\n["Food & Dining"]\n```'
        result = _parse_categories_response(response, 1)
        assert result == ["Food & Dining"]

    def test_invalid_category_defaults_to_other(self):
        response = '["Food & Dining", "InvalidCategory"]'
        result = _parse_categories_response(response, 2)
        assert result[1] == "Other"

    def test_case_insensitive_matching(self):
        response = '["food & dining"]'
        result = _parse_categories_response(response, 1)
        assert result == ["Food & Dining"]

    def test_invalid_json_returns_all_other(self):
        result = _parse_categories_response("not valid json", 3)
        assert result == ["Other", "Other", "Other"]

    def test_all_valid_categories_accepted(self):
        response = str(CATEGORIES).replace("'", '"')
        result = _parse_categories_response(response, len(CATEGORIES))
        assert result == CATEGORIES

    def test_empty_response_returns_other(self):
        result = _parse_categories_response("", 2)
        assert result == ["Other", "Other"]


# ── _build_categorization_prompt ────────────────────────────────────────────

class TestBuildCategorizationPrompt:

    def test_prompt_contains_all_transactions(self):
        transactions = [
            {'date': '01/05/2024', 'description': 'STARBUCKS', 'amount': -4.50},
            {'date': '01/06/2024', 'description': 'UBER',      'amount': -15.00},
        ]
        prompt = _build_categorization_prompt(transactions)
        assert "STARBUCKS" in prompt
        assert "UBER" in prompt

    def test_prompt_shows_negative_format(self):
        transactions = [{'date': '01/05/2024', 'description': 'STARBUCKS', 'amount': -4.50}]
        prompt = _build_categorization_prompt(transactions)
        assert "-$4.50" in prompt

    def test_prompt_shows_positive_format_for_income(self):
        transactions = [{'date': '01/05/2024', 'description': 'SALARY', 'amount': 3500.00}]
        prompt = _build_categorization_prompt(transactions)
        assert "+$3500.00" in prompt

    def test_prompt_numbers_transactions(self):
        transactions = [
            {'date': '01/05/2024', 'description': 'STARBUCKS', 'amount': -4.50},
            {'date': '01/06/2024', 'description': 'UBER',      'amount': -15.00},
        ]
        prompt = _build_categorization_prompt(transactions)
        assert "1." in prompt
        assert "2." in prompt

    def test_empty_transactions_returns_prompt(self):
        prompt = _build_categorization_prompt([])
        assert isinstance(prompt, str)


# ── get_category_summary ────────────────────────────────────────────────────

class TestGetCategorySummary:

    def test_returns_dataframe(self, sample_transactions_df):
        df = sample_transactions_df.copy()
        df['category'] = ['Food & Dining', 'Transport', 'Shopping', 'Income', 'Subscriptions']
        summary = get_category_summary(df)
        assert isinstance(summary, pd.DataFrame)

    def test_summary_has_required_columns(self, sample_transactions_df):
        df = sample_transactions_df.copy()
        df['category'] = ['Food & Dining', 'Transport', 'Shopping', 'Income', 'Subscriptions']
        summary = get_category_summary(df)
        assert 'category' in summary.columns
        assert 'count' in summary.columns
        assert 'total_spent' in summary.columns

    def test_income_excluded_from_expenses(self, sample_transactions_df):
        df = sample_transactions_df.copy()
        df['category'] = ['Food & Dining', 'Transport', 'Shopping', 'Income', 'Subscriptions']
        summary = get_category_summary(df)
        assert 'Income' not in summary[summary['total_spent'] > 0]['category'].values

    def test_missing_columns_returns_empty_df(self):
        df = pd.DataFrame({'category': ['Food & Dining'], 'wrong_col': [10.0]})
        summary = get_category_summary(df)
        assert summary.empty

    def test_empty_df_returns_empty_summary(self):
        df = pd.DataFrame(columns=['date', 'description', 'amount', 'category'])
        summary = get_category_summary(df)
        assert summary.empty

    def test_amounts_are_absolute(self, sample_transactions_df):
        df = sample_transactions_df.copy()
        df['category'] = ['Food & Dining', 'Transport', 'Shopping', 'Income', 'Subscriptions']
        summary = get_category_summary(df)
        assert (summary['total_spent'] >= 0).all()


# ── categorize_transactions ─────────────────────────────────────────────────

class TestCategorizeTransactions:

    def test_adds_category_column(self, sample_transactions_df, mock_anthropic_client):
        with patch('categorizer.anthropic.Anthropic', return_value=mock_anthropic_client):
            result = categorize_transactions(sample_transactions_df.copy(), "fake-api-key")
        assert 'category' in result.columns

    def test_category_count_matches_transaction_count(self, sample_transactions_df, mock_anthropic_client):
        with patch('categorizer.anthropic.Anthropic', return_value=mock_anthropic_client):
            result = categorize_transactions(sample_transactions_df.copy(), "fake-api-key")
        assert len(result) == len(sample_transactions_df)

    def test_all_categories_are_valid(self, sample_transactions_df, mock_anthropic_client):
        with patch('categorizer.anthropic.Anthropic', return_value=mock_anthropic_client):
            result = categorize_transactions(sample_transactions_df.copy(), "fake-api-key")
        for cat in result['category']:
            assert cat in CATEGORIES

    def test_empty_df_returns_empty_df(self):
        empty_df = pd.DataFrame(columns=['date', 'description', 'amount'])
        result = categorize_transactions(empty_df, "fake-api-key")
        assert result.empty

    def test_missing_api_key_raises_value_error(self, sample_transactions_df):
        with pytest.raises(ValueError, match="API key is required"):
            categorize_transactions(sample_transactions_df.copy(), "")

    def test_missing_column_raises_value_error(self):
        bad_df = pd.DataFrame({'date': ['01/01/2024'], 'description': ['TEST']})  # missing 'amount'
        with pytest.raises(ValueError, match="Required column 'amount' not found"):
            categorize_transactions(bad_df, "fake-api-key")

    def test_api_error_falls_back_to_other(self, sample_transactions_df):
        """If the API throws an error, all transactions should fall back to 'Other'."""
        mock_client = MagicMock()
        import anthropic
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="Rate limit", request=MagicMock(), body=None
        )
        with patch('categorizer.anthropic.Anthropic', return_value=mock_client):
            result = categorize_transactions(sample_transactions_df.copy(), "fake-api-key")
        assert all(cat == "Other" for cat in result['category'])
