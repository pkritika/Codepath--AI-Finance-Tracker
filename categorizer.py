"""
AI-powered transaction categorization module using Claude.

This module categorizes bank transactions into predefined categories using
Anthropic's Claude API with intelligent batching and error handling.
"""

import anthropic
import pandas as pd
import json
from typing import List, Optional
import time


# Predefined categories for transaction classification
CATEGORIES = [
    "Food & Dining",
    "Transport",
    "Shopping",
    "Entertainment",
    "Utilities",
    "Health",
    "Rent/Housing",
    "Income",
    "Subscriptions",
    "Other"
]


def categorize_transactions(
    df: pd.DataFrame,
    api_key: str,
    batch_size: int = 50,
    date_col: str = "date",
    description_col: str = "description",
    amount_col: str = "amount"
) -> pd.DataFrame:
    """
    Categorize transactions using Claude API.

    Args:
        df: DataFrame with transaction data
        api_key: Anthropic API key
        batch_size: Number of transactions to send per API call (default: 50)
        date_col: Name of the date column
        description_col: Name of the description column
        amount_col: Name of the amount column

    Returns:
        DataFrame with added "category" column

    Raises:
        ValueError: If required columns are missing or API key is invalid
    """
    # Validate inputs
    if df.empty:
        df['category'] = []
        return df

    for col in [date_col, description_col, amount_col]:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found in DataFrame")

    if not api_key or not api_key.strip():
        raise ValueError("API key is required for categorization")

    # Create Anthropic client
    try:
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        raise ValueError(f"Failed to initialize Anthropic client: {e}")

    print(f"Categorizing {len(df)} transactions in batches of {batch_size}...")

    # Process transactions in batches
    all_categories = []
    total_batches = (len(df) + batch_size - 1) // batch_size

    for batch_idx in range(0, len(df), batch_size):
        batch_num = (batch_idx // batch_size) + 1
        batch_df = df.iloc[batch_idx:batch_idx + batch_size]

        print(f"  Processing batch {batch_num}/{total_batches} ({len(batch_df)} transactions)...")

        # Prepare batch data
        batch_transactions = []
        for _, row in batch_df.iterrows():
            batch_transactions.append({
                'date': str(row[date_col]),
                'description': str(row[description_col]),
                'amount': float(row[amount_col])
            })

        # Get categories for this batch
        categories = _categorize_batch(client, batch_transactions)

        # Ensure we got the right number of categories
        if len(categories) != len(batch_transactions):
            print(f"    Warning: Expected {len(batch_transactions)} categories, got {len(categories)}. Filling with 'Other'.")
            # Pad or truncate to match
            while len(categories) < len(batch_transactions):
                categories.append("Other")
            categories = categories[:len(batch_transactions)]

        all_categories.extend(categories)

        # Rate limiting - brief pause between batches
        if batch_idx + batch_size < len(df):
            time.sleep(0.5)

    # Add categories to DataFrame
    df['category'] = all_categories

    # Validate all rows got a category
    if df['category'].isna().any():
        df['category'] = df['category'].fillna('Other')

    print(f"  ✓ Categorization complete!")
    return df


def _categorize_batch(client: anthropic.Anthropic, transactions: List[dict]) -> List[str]:
    """
    Categorize a batch of transactions using Claude.

    Args:
        client: Anthropic client instance
        transactions: List of transaction dicts with date, description, amount

    Returns:
        List of category strings
    """
    # Build the prompt
    prompt = _build_categorization_prompt(transactions)

    try:
        # Call Claude API
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            temperature=0,  # Use 0 for deterministic categorization
            system=_get_system_prompt(),
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extract response text
        response_text = response.content[0].text.strip()

        # Parse JSON response
        categories = _parse_categories_response(response_text, len(transactions))

        return categories

    except anthropic.APIError as e:
        print(f"    API Error: {e}. Defaulting all to 'Other'.")
        return ["Other"] * len(transactions)

    except Exception as e:
        print(f"    Unexpected error: {e}. Defaulting all to 'Other'.")
        return ["Other"] * len(transactions)


def _get_system_prompt() -> str:
    """
    Get the system prompt with category definitions and few-shot examples.

    Returns:
        System prompt string
    """
    return f"""You are a financial transaction categorization expert. Your job is to categorize bank transactions into one of these categories:

**Categories:**
- Food & Dining: Restaurants, cafes, bars, food delivery, groceries, supermarkets
- Transport: Gas stations, public transit, ride shares, parking, tolls, car maintenance
- Shopping: Retail stores, online shopping, clothing, electronics, home goods
- Entertainment: Movies, concerts, streaming services, games, hobbies, events
- Utilities: Electric, water, gas, internet, phone bills, trash service
- Health: Pharmacy, doctor visits, dental, medical supplies, fitness, gym
- Rent/Housing: Rent payments, mortgage, property management, HOA fees
- Income: Salary deposits, payments received, refunds, cashback, interest
- Subscriptions: Recurring services like Netflix, Spotify, software subscriptions, memberships
- Other: Anything that doesn't clearly fit the above categories

**Instructions:**
1. Analyze each transaction's description and amount
2. Consider the merchant name and transaction type
3. If amount is positive, consider if it's Income
4. Return categories as a JSON array in the exact order given
5. Only use the categories listed above (exact spelling)

**Few-shot examples:**

Transaction: "STARBUCKS #12345" | -$4.50
Category: Food & Dining

Transaction: "SHELL GAS STATION" | -$45.00
Category: Transport

Transaction: "AMAZON.COM" | -$89.99
Category: Shopping

Transaction: "SPOTIFY PREMIUM" | -$9.99
Category: Subscriptions

Transaction: "SALARY DEPOSIT" | +$3500.00
Category: Income

Transaction: "CVENTS PHARMACY" | -$25.43
Category: Health

Transaction: "PACIFIC GAS ELECTRIC" | -$120.00
Category: Utilities

Transaction: "PROPERTY MANAGEMENT CO" | -$1800.00
Category: Rent/Housing

Transaction: "AMC THEATRES" | -$24.00
Category: Entertainment

Transaction: "UBER RIDE" | -$15.50
Category: Transport"""


def _build_categorization_prompt(transactions: List[dict]) -> str:
    """
    Build the user prompt with transaction data.

    Args:
        transactions: List of transaction dicts

    Returns:
        Formatted prompt string
    """
    prompt_parts = [
        "Categorize these transactions. Return a JSON array of categories in the same order:\n"
    ]

    for i, txn in enumerate(transactions, 1):
        amount_str = f"+${txn['amount']:.2f}" if txn['amount'] >= 0 else f"-${abs(txn['amount']):.2f}"
        prompt_parts.append(
            f"{i}. {txn['date']} | {txn['description']} | {amount_str}"
        )

    prompt_parts.append("\nReturn only a JSON array of categories, nothing else:")
    return "\n".join(prompt_parts)


def _parse_categories_response(response_text: str, expected_count: int) -> List[str]:
    """
    Parse Claude's response into a list of categories with fallback handling.

    Args:
        response_text: Raw response from Claude
        expected_count: Number of categories expected

    Returns:
        List of category strings
    """
    try:
        # Try to find JSON array in response
        # Handle cases where Claude adds markdown code blocks
        text = response_text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Parse JSON
        categories = json.loads(text)

        # Validate it's a list
        if not isinstance(categories, list):
            raise ValueError("Response is not a JSON array")

        # Validate and clean categories
        cleaned_categories = []
        for cat in categories:
            cat_str = str(cat).strip()

            # Check if it's a valid category
            if cat_str in CATEGORIES:
                cleaned_categories.append(cat_str)
            else:
                # Try to find closest match (case-insensitive)
                matched = False
                for valid_cat in CATEGORIES:
                    if cat_str.lower() == valid_cat.lower():
                        cleaned_categories.append(valid_cat)
                        matched = True
                        break

                if not matched:
                    # Default to Other if category not recognized
                    cleaned_categories.append("Other")

        return cleaned_categories

    except json.JSONDecodeError as e:
        print(f"    JSON parse error: {e}. Defaulting to 'Other'.")
        return ["Other"] * expected_count

    except Exception as e:
        print(f"    Error parsing response: {e}. Defaulting to 'Other'.")
        return ["Other"] * expected_count


def get_category_summary(df: pd.DataFrame, category_col: str = "category", amount_col: str = "amount") -> pd.DataFrame:
    """
    Get summary statistics by category.

    Args:
        df: DataFrame with categorized transactions
        category_col: Name of category column
        amount_col: Name of amount column

    Returns:
        DataFrame with category summaries (category, count, total_spent)
    """
    if category_col not in df.columns or amount_col not in df.columns:
        return pd.DataFrame()

    # Detect if this is a credit card statement or bank statement
    # Credit card: purchases are positive, payments are negative
    # Bank statement: expenses are negative, income is positive

    # Count positive vs negative amounts
    positive_count = (df[amount_col] > 0).sum()
    negative_count = (df[amount_col] < 0).sum()

    # If we have mostly positive amounts, it's likely a credit card statement
    is_credit_card = positive_count > negative_count

    if is_credit_card:
        # For credit card: filter out Income and payments (negative amounts)
        # Keep purchases (positive amounts) excluding Income category
        expenses = df[(df[amount_col] > 0) & (df[category_col] != 'Income')].copy()
    else:
        # For bank statement: filter to expenses only (negative amounts, not Income)
        expenses = df[(df[amount_col] < 0) & (df[category_col] != 'Income')].copy()

    if expenses.empty:
        return pd.DataFrame(columns=['category', 'count', 'total_spent'])

    # Calculate absolute amounts
    expenses['abs_amount'] = expenses[amount_col].abs()

    # Group by category
    summary = expenses.groupby(category_col).agg(
        count=('abs_amount', 'count'),
        total_spent=('abs_amount', 'sum')
    ).reset_index()

    # Rename columns
    summary.columns = ['category', 'count', 'total_spent']

    # Add missing expense categories with $0
    expense_categories = [cat for cat in CATEGORIES if cat != 'Income']
    for cat in expense_categories:
        if cat not in summary['category'].values:
            new_row = pd.DataFrame([{'category': cat, 'count': 0, 'total_spent': 0.0}])
            summary = pd.concat([summary, new_row], ignore_index=True)

    # Sort by total spent
    summary = summary.sort_values('total_spent', ascending=False)

    return summary


def generate_financial_insights(
    df: pd.DataFrame,
    api_key: str,
    date_col: str = "date",
    description_col: str = "description",
    amount_col: str = "amount",
    category_col: str = "category"
) -> list:
    """
    Ask Claude to analyse a categorised transaction DataFrame and return
    a list of personalised, actionable financial insight strings.

    Args:
        df:              Categorised transaction DataFrame.
        api_key:         Anthropic API key.
        date_col:        Name of the date column.
        description_col: Name of the description column.
        amount_col:      Name of the amount column.
        category_col:    Name of the category column.

    Returns:
        List of insight strings (plain text, no markdown symbols).
        Falls back to a single generic string on any error.
    """
    if df.empty or category_col not in df.columns:
        return ["No transaction data available for insights."]

    if not api_key or not api_key.strip():
        return ["API key required to generate insights."]

    # Build a compact spending summary to send to Claude
    summary = get_category_summary(df, category_col, amount_col)

    # Detect statement type
    positive_count = (df[amount_col] > 0).sum()
    negative_count = (df[amount_col] < 0).sum()
    is_credit_card = int(positive_count) > int(negative_count)

    if is_credit_card:
        total_spent = df[(df[amount_col] > 0) & (df[category_col] != 'Income')][amount_col].sum()
        total_income = df[df[amount_col] < 0][amount_col].abs().sum()
    else:
        total_spent = df[df[amount_col] < 0][amount_col].abs().sum()
        total_income = df[df[amount_col] > 0][amount_col].sum()

    num_txns = len(df)
    top_categories = summary[summary['total_spent'] > 0].head(5)

    # Build a readable summary block for Claude
    lines = [
        f"Total transactions: {num_txns}",
        f"Total spent: ${total_spent:.2f}",
        f"Total income / credits: ${total_income:.2f}",
        "",
        "Spending by category:",
    ]
    for _, row in top_categories.iterrows():
        pct = (row['total_spent'] / total_spent * 100) if total_spent > 0 else 0
        lines.append(
            f"  - {row['category']}: ${row['total_spent']:.2f} "
            f"({pct:.1f}% of spend, {int(row['count'])} transactions)"
        )

    spending_summary = "\n".join(lines)

    system_prompt = (
        "You are a friendly, expert personal finance advisor. "
        "Given a user's monthly spending summary, provide exactly 4 concise, "
        "personalised, and actionable financial insights. "
        "Each insight should be a single sentence. "
        "Do NOT use bullet symbols, dashes, asterisks, or markdown. "
        "Return a valid JSON array of 4 plain-text strings."
    )

    user_prompt = (
        f"Here is my spending summary for this period:\n\n{spending_summary}\n\n"
        "Give me 4 short, helpful financial insights based on this data. "
        "Return a JSON array of exactly 4 plain-text strings."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        text = response.content[0].text.strip()

        # Strip markdown code fences
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        insights = json.loads(text)
        if isinstance(insights, list) and insights:
            # Clean any stray symbols
            cleaned = [str(i).lstrip('- •*').strip() for i in insights]
            return cleaned[:6]  # cap at 6

        return ["Unable to parse insights from AI response."]

    except json.JSONDecodeError as e:
        print(f"Insights JSON parse error: {e}")
        return ["Insights temporarily unavailable — check your spending distribution above."]
    except Exception as e:
        print(f"Insights generation error: {e}")
        return ["Insights temporarily unavailable — check your spending distribution above."]


def generate_budget_plan(
    df: pd.DataFrame,
    api_key: str,
    savings_goal: float,
    amount_col: str = "amount",
    category_col: str = "category"
) -> dict:
    """
    Agentic budget planner: Claude plans, acts, and verifies its own work.

    Steps:
      1. PLAN  — analyse spending, identify cuttable categories
      2. ACT   — propose specific dollar targets per category
      3. CHECK — verify total savings meet the goal; flag ambitious cuts (>50%)
      4. OUTPUT — return structured plan + verification notes

    Returns a dict with keys: cuts, total_saving, goal_met, verification, error
    """
    if df.empty or category_col not in df.columns:
        return {"error": "No categorised transaction data available."}

    if not api_key or not api_key.strip():
        return {"error": "API key required to generate a budget plan."}

    if savings_goal <= 0:
        return {"error": "Savings goal must be a positive number."}

    # ── Build spending summary ────────────────────────────────────────────────
    positive_count = (df[amount_col] > 0).sum()
    negative_count = (df[amount_col] < 0).sum()
    is_credit_card = int(positive_count) > int(negative_count)

    if is_credit_card:
        total_spent  = df[(df[amount_col] > 0) & (df[category_col] != 'Income')][amount_col].sum()
        total_income = df[df[amount_col] < 0][amount_col].abs().sum()
    else:
        total_spent  = df[df[amount_col] < 0][amount_col].abs().sum()
        total_income = df[df[amount_col] > 0][amount_col].sum()

    summary = get_category_summary(df, category_col, amount_col)
    cuttable = summary[
        (summary['total_spent'] > 0) &
        (~summary['category'].isin(['Income', 'Rent/Housing']))
    ].sort_values('total_spent', ascending=False)

    category_lines = []
    for _, row in cuttable.iterrows():
        category_lines.append(
            f"  - {row['category']}: ${row['total_spent']:.2f}/month "
            f"({int(row['count'])} transactions)"
        )

    spending_block = "\n".join(category_lines) or "  No cuttable categories found."

    system_prompt = (
        "You are a financial planning agent operating in a structured 4-step workflow.\n\n"

        "STEP 1 — PLAN: Identify which spending categories can realistically be reduced. "
        "Never cut Income or Rent/Housing.\n\n"

        "STEP 2 — ACT: For each cuttable category, propose a specific target monthly amount "
        "that is lower than the current amount.\n\n"

        "STEP 3 — CHECK: Sum all savings. Verify the total meets the savings goal. "
        "Flag any cut that requires more than 50% reduction as ambitious.\n\n"

        "STEP 4 — OUTPUT: Return ONLY a valid JSON object (no markdown, no explanation) "
        "with this exact structure:\n"
        "{\n"
        '  "cuts": [\n'
        '    {\n'
        '      "category": "string",\n'
        '      "current": number,\n'
        '      "target": number,\n'
        '      "saving": number,\n'
        '      "reduction_pct": number,\n'
        '      "realistic": true|false\n'
        "    }\n"
        "  ],\n"
        '  "total_saving": number,\n'
        '  "goal_met": true|false,\n'
        '  "verification": {\n'
        '    "total_adds_up": true|false,\n'
        '    "ambitious_categories": ["category1"],\n'
        '    "agent_notes": ["note1", "note2"]\n'
        "  }\n"
        "}\n\n"
        "realistic = true means the cut is <= 50% of current spending. "
        "A cut > 50% must set realistic = false and add the category to ambitious_categories."
    )

    user_prompt = (
        f"My savings goal: ${savings_goal:.2f}/month\n"
        f"Total monthly income: ${total_income:.2f}\n"
        f"Total monthly expenses: ${total_spent:.2f}\n\n"
        f"Current spending by cuttable category:\n{spending_block}\n\n"
        "Please follow the 4-step agentic workflow and return the JSON budget plan."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        text = response.content[0].text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        plan = json.loads(text)

        # Ensure mandatory keys exist
        plan.setdefault("cuts", [])
        plan.setdefault("total_saving", sum(c.get("saving", 0) for c in plan["cuts"]))
        plan.setdefault("goal_met", plan["total_saving"] >= savings_goal)
        plan.setdefault("verification", {})
        plan["verification"].setdefault("total_adds_up", True)
        plan["verification"].setdefault("ambitious_categories", [])
        plan["verification"].setdefault("agent_notes", [])

        return plan

    except json.JSONDecodeError as e:
        return {"error": f"Could not parse budget plan from AI response: {e}"}
    except Exception as e:
        return {"error": f"Budget plan generation failed: {e}"}
