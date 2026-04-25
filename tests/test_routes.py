"""
Tests for Flask routes in app_flask.py

Covers:
- GET  /             : landing page renders
- GET  /dashboard    : dashboard page renders
- GET  /api/data     : returns empty data for fresh session
- GET  /api/export   : returns 400 when no data exists
- 404 handler        : custom 404 page rendered
"""

import pytest
import json
from unittest.mock import patch, MagicMock


class TestLandingPage:

    def test_landing_page_returns_200(self, flask_app):
        response = flask_app.get('/')
        assert response.status_code == 200

    def test_landing_page_is_html(self, flask_app):
        response = flask_app.get('/')
        assert b'html' in response.data.lower() or response.content_type == 'text/html; charset=utf-8'


class TestDashboardPage:

    def test_dashboard_returns_200(self, flask_app):
        response = flask_app.get('/dashboard')
        assert response.status_code == 200

    def test_dashboard_is_html(self, flask_app):
        response = flask_app.get('/dashboard')
        assert response.content_type == 'text/html; charset=utf-8'


class TestGetDataEndpoint:

    def test_returns_empty_data_for_fresh_session(self, flask_app):
        response = flask_app.get('/api/data')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'transactions' in data
        assert data['transactions'] == []
        assert data['count'] == 0

    def test_response_has_required_keys(self, flask_app):
        response = flask_app.get('/api/data')
        data = json.loads(response.data)
        assert 'transactions' in data
        assert 'categorized' in data
        assert 'count' in data


class TestExportEndpoint:

    def test_export_returns_400_when_no_data(self, flask_app):
        response = flask_app.get('/api/export')
        assert response.status_code == 400

    def test_export_error_message(self, flask_app):
        response = flask_app.get('/api/export')
        data = json.loads(response.data)
        assert 'error' in data


class Test404Handler:

    def test_unknown_route_returns_404(self, flask_app):
        response = flask_app.get('/this-page-does-not-exist')
        assert response.status_code == 404
