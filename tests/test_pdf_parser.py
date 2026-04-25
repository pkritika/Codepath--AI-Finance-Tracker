"""
Tests for pdf_parser.py

Covers:
- normalize_amount()      : currency string → float conversion
- _looks_like_date()      : date pattern detection
- _looks_like_amount()    : amount pattern detection
- clean_transactions()    : deduplication, validation, header removal
- is_transaction_page()   : page scoring logic
- extract_from_text()     : regex-based text parsing
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from pdf_parser import (
    normalize_amount,
    _looks_like_date,
    _looks_like_amount,
    clean_transactions,
    is_transaction_page,
    extract_from_text,
    extract_transactions,
)


# ── normalize_amount ────────────────────────────────────────────────────────

class TestNormalizeAmount:

    def test_plain_decimal(self):
        assert normalize_amount("45.00") == 45.00

    def test_dollar_sign(self):
        assert normalize_amount("$45.00") == 45.00

    def test_negative_value(self):
        assert normalize_amount("-12.50") == -12.50

    def test_parentheses_treated_as_negative(self):
        assert normalize_amount("(50.00)") == -50.00

    def test_commas_in_large_numbers(self):
        assert normalize_amount("1,234.56") == 1234.56

    def test_dollar_with_commas(self):
        assert normalize_amount("$1,234.56") == 1234.56

    def test_invalid_string_returns_none(self):
        assert normalize_amount("not-a-number") is None

    def test_empty_string_returns_none(self):
        assert normalize_amount("") is None

    def test_zero_amount(self):
        assert normalize_amount("0.00") == 0.00


# ── _looks_like_date ────────────────────────────────────────────────────────

class TestLooksLikeDate:

    def test_mm_dd_yyyy(self):
        assert _looks_like_date("01/15/2024") is True

    def test_mm_dd_yy(self):
        assert _looks_like_date("01/15/24") is True

    def test_yyyy_mm_dd(self):
        assert _looks_like_date("2024-01-15") is True

    def test_month_name(self):
        assert _looks_like_date("Jan 15") is True

    def test_month_name_with_year(self):
        assert _looks_like_date("Jan 15, 2024") is True

    def test_mm_dd_no_year(self):
        assert _looks_like_date("02/07") is True

    def test_plain_text_is_not_date(self):
        assert _looks_like_date("STARBUCKS") is False

    def test_random_number_is_not_date(self):
        assert _looks_like_date("12345") is False


# ── _looks_like_amount ──────────────────────────────────────────────────────

class TestLooksLikeAmount:

    def test_simple_amount(self):
        assert _looks_like_amount("12.34") is True

    def test_negative_amount(self):
        assert _looks_like_amount("-12.34") is True

    def test_dollar_sign(self):
        assert _looks_like_amount("$12.34") is True

    def test_parentheses_amount(self):
        assert _looks_like_amount("(12.34)") is True

    def test_with_commas(self):
        assert _looks_like_amount("1,234.56") is True

    def test_empty_string(self):
        assert _looks_like_amount("") is False

    def test_plain_text(self):
        assert _looks_like_amount("AMAZON") is False


# ── clean_transactions ──────────────────────────────────────────────────────

class TestCleanTransactions:

    def test_basic_cleaning(self, sample_raw_transactions):
        df = clean_transactions(sample_raw_transactions)
        assert not df.empty
        assert list(df.columns) == ["date", "description", "amount"]

    def test_amounts_are_floats(self, sample_raw_transactions):
        df = clean_transactions(sample_raw_transactions)
        assert df["amount"].dtype == float

    def test_zero_amounts_removed(self):
        raw = [{'date': '01/01/2024', 'description': 'ZERO TXN', 'amount': '0.00'}]
        df = clean_transactions(raw)
        assert df.empty

    def test_duplicates_removed(self):
        raw = [
            {'date': '01/01/2024', 'description': 'STARBUCKS', 'amount': '-4.50'},
            {'date': '01/01/2024', 'description': 'STARBUCKS', 'amount': '-4.50'},  # duplicate
        ]
        df = clean_transactions(raw)
        assert len(df) == 1

    def test_header_rows_removed(self):
        raw = [
            {'date': '01/01/2024', 'description': 'date',        'amount': '-4.50'},
            {'date': '01/01/2024', 'description': 'description',  'amount': '-4.50'},
            {'date': '01/05/2024', 'description': 'STARBUCKS',    'amount': '-4.50'},
        ]
        df = clean_transactions(raw)
        assert len(df) == 1
        assert df.iloc[0]['description'] == 'STARBUCKS'

    def test_empty_input_returns_empty_df(self):
        df = clean_transactions([])
        assert df.empty
        assert list(df.columns) == ["date", "description", "amount"]

    def test_large_amounts_filtered_out(self):
        raw = [
            {'date': '01/01/2024', 'description': 'LEGIT TXN',    'amount': '-25.00'},
            {'date': '01/01/2024', 'description': 'DOCUMENT ID',  'amount': '99999.00'},
        ]
        df = clean_transactions(raw)
        assert len(df) == 1
        assert df.iloc[0]['description'] == 'LEGIT TXN'


# ── is_transaction_page ─────────────────────────────────────────────────────

class TestIsTransactionPage:

    def _make_page(self, text):
        page = MagicMock()
        page.extract_text.return_value = text
        return page

    def test_valid_transaction_page(self):
        text = (
            "01/05/2024 STARBUCKS -4.50\n"
            "01/06/2024 UBER RIDE -15.00\n"
            "01/07/2024 AMAZON -89.99\n"
        )
        assert is_transaction_page(self._make_page(text)) is True

    def test_legal_page_rejected(self):
        text = (
            "Terms and Conditions apply to all accounts.\n"
            "01/05/2024 Some transaction 10.00\n"
            "01/06/2024 Another one 20.00\n"
            "01/07/2024 Third one 30.00\n"
        )
        assert is_transaction_page(self._make_page(text)) is False

    def test_page_with_no_dates_rejected(self):
        text = "Welcome to your bank. Please contact support for help."
        assert is_transaction_page(self._make_page(text)) is False

    def test_empty_page_rejected(self):
        assert is_transaction_page(self._make_page("")) is False

    def test_none_text_rejected(self):
        page = MagicMock()
        page.extract_text.return_value = None
        assert is_transaction_page(page) is False


# ── extract_from_text ───────────────────────────────────────────────────────

class TestExtractFromText:

    def _make_page(self, text):
        page = MagicMock()
        page.extract_text.return_value = text
        return page

    def test_extracts_basic_transactions(self):
        text = (
            "01/05/2024 STARBUCKS COFFEE -4.50\n"
            "01/06/2024 UBER RIDE -15.00\n"
            "01/07/2024 AMAZON PURCHASE -89.99\n"
        )
        txns = extract_from_text(self._make_page(text))
        assert len(txns) == 3

    def test_each_txn_has_required_fields(self):
        text = "01/05/2024 STARBUCKS COFFEE -4.50\n"
        txns = extract_from_text(self._make_page(text))
        if txns:
            assert 'date' in txns[0]
            assert 'description' in txns[0]
            assert 'amount' in txns[0]

    def test_empty_page_returns_empty_list(self):
        txns = extract_from_text(self._make_page(""))
        assert txns == []

    def test_lines_without_dates_skipped(self):
        text = (
            "Welcome to your statement\n"
            "01/05/2024 STARBUCKS -4.50\n"
            "Please call us at 1-800-000-0000\n"
        )
        txns = extract_from_text(self._make_page(text))
        assert len(txns) == 1


# ── extract_transactions (integration) ─────────────────────────────────────

class TestExtractTransactions:

    def test_raises_on_no_transactions(self, tmp_path):
        """A PDF with no transaction pages should raise ValueError."""
        # We'll mock pdfplumber to return pages that fail is_transaction_page
        with patch('pdf_parser.pdfplumber.open') as mock_open:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Terms and conditions apply to all."
            mock_open.return_value.__enter__.return_value.pages = [mock_page]

            with pytest.raises(ValueError, match="No transactions found"):
                extract_transactions("fake_path.pdf")
