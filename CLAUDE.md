# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TrackWise is a Flask-based expense tracking application that extracts transactions from bank statement PDFs using a multi-layer parsing approach and categorizes them using Claude AI (Anthropic's API).

## Development Commands

### Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Run Flask development server
python app_flask.py
# Server runs at http://localhost:5000

# Note: README.md mentions streamlit but the codebase uses Flask
```

### Environment Variables
```bash
# Required for AI categorization feature
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Architecture

### Core Processing Pipeline

**PDF Parsing (pdf_parser.py)**
1. **Page Scoring**: Filter pages containing transactions vs legal/terms pages
   - Scores based on date patterns (+2), amounts (+2), transaction keywords (+3)
   - Deducts points for legal keywords (-3)
   - Pages with score ≥3 are processed
2. **Three-Layer Extraction**:
   - Layer 1: Table extraction with heuristic column detection (`extract_from_table`)
   - Layer 2: Regex-based text parsing (`extract_from_text`)
   - Layer 3: OCR fallback (optional, not implemented but referenced)
3. **Validation & Cleaning**: Deduplication, amount normalization, header removal

**AI Categorization (categorizer.py)**
- Batch processing: 50 transactions per API call with 0.5s delay between batches
- Uses Claude Sonnet 4 (`claude-sonnet-4-20250514`) with temperature=0 for deterministic results
- 10 predefined categories: Food & Dining, Transport, Shopping, Entertainment, Utilities, Health, Rent/Housing, Income, Subscriptions, Other
- Robust JSON parsing with markdown code block handling
- Fallback to "Other" category on errors
- Auto-detects credit card vs bank statements based on positive/negative amount ratios

### Data Flow

1. User uploads PDF → `/api/upload` endpoint
2. `extract_transactions()` parses PDF → returns DataFrame
3. Transactions stored server-side in temp JSON files (session-based)
4. User triggers categorization → `/api/categorize` endpoint
5. `categorize_transactions()` sends batches to Claude API
6. Results stored server-side with category column added
7. Dashboard displays transactions with analytics

### Session Management

The app uses a hybrid approach:
- Flask session stores a `data_id` (UUID)
- Actual transaction data stored in `/tmp/trackwise_data/{data_id}.json`
- This avoids cookie size limits for large transaction sets

### Key Files

- `app_flask.py`: Flask application with routes and API endpoints
- `pdf_parser.py`: Production-grade multi-layer PDF transaction parser
- `categorizer.py`: AI-powered categorization using Claude API
- `static/js/`: Frontend JavaScript (dashboard.js, upload.js, cursor.js)
- `templates/`: HTML templates (index.html, dashboard.html, 404.html)

## Important Implementation Details

### PDF Parser Patterns
- `DATE_RE`: Matches dates in formats like MM/DD/YYYY, YYYY-MM-DD, "Jan 12, 2024"
- `AMOUNT_RE`: Matches currency amounts with $, commas, negatives, parentheses
- Column detection uses scoring heuristics on first 5 data rows
- Amounts in parentheses are treated as negative (accounting convention)

### Categorization Specifics
- API key read from environment variable `ANTHROPIC_API_KEY` (server-side only, not exposed to client)
- System prompt includes few-shot examples for better accuracy
- Response parsing handles both raw JSON and markdown-wrapped JSON
- Case-insensitive category matching with fallback
- `get_category_summary()` auto-detects credit card vs bank statement format

### Security Notes
- File uploads limited to 16MB (`MAX_CONTENT_LENGTH`)
- Only PDF files allowed (`allowed_file` validation)
- Uploaded files saved with `secure_filename()`
- Temporary files cleaned up immediately after processing
- API key never sent to client (server-side only)

## Common Development Patterns

### Adding New Transaction Categories
1. Add category to `CATEGORIES` list in categorizer.py:316
2. Update system prompt in `_get_system_prompt()` with category definition and examples
3. Update frontend visualizations if needed (dashboard.js)

### Modifying Parser Logic
- Page scoring logic: `is_transaction_page()` in pdf_parser.py:45
- Column detection heuristics: `_guess_columns()` in pdf_parser.py:163
- Validation rules: `clean_transactions()` in pdf_parser.py:132

### API Endpoint Structure
All API endpoints follow pattern:
- Accept POST with JSON/form data
- Return JSON with `{success: bool, ...}` or `{error: string}`
- Use `_load_data()` and `_save_data()` for session persistence
