"""
TrackWise AI Reliability Check
================================
Runs the same 10 labeled transactions through Claude 3 times and measures
how consistent the AI's categorization is across runs.

Can be imported as a module (run_reliability_check returns a dict) or
executed directly from the command line.

Usage:
    python reliability_check.py

Requires:
    export ANTHROPIC_API_KEY="sk-ant-..."
"""

import os
import sys
import time
import json
from collections import Counter

import anthropic

# ── Known test transactions with ground-truth labels ─────────────────────────
TEST_TRANSACTIONS = [
    {"date": "01/05/2024", "description": "STARBUCKS #12345",         "amount": -4.50,    "expected": "Food & Dining"},
    {"date": "01/06/2024", "description": "SHELL GAS STATION",        "amount": -52.00,   "expected": "Transport"},
    {"date": "01/07/2024", "description": "AMAZON.COM PURCHASE",      "amount": -89.99,   "expected": "Shopping"},
    {"date": "01/08/2024", "description": "SPOTIFY PREMIUM",          "amount": -9.99,    "expected": "Subscriptions"},
    {"date": "01/09/2024", "description": "DIRECT DEPOSIT SALARY",    "amount": 3500.00,  "expected": "Income"},
    {"date": "01/10/2024", "description": "PACIFIC GAS ELECTRIC",     "amount": -120.00,  "expected": "Utilities"},
    {"date": "01/11/2024", "description": "CVS PHARMACY",             "amount": -25.43,   "expected": "Health"},
    {"date": "01/12/2024", "description": "PROPERTY MANAGEMENT CO",   "amount": -1800.00, "expected": "Rent/Housing"},
    {"date": "01/13/2024", "description": "AMC THEATRES",             "amount": -24.00,   "expected": "Entertainment"},
    {"date": "01/14/2024", "description": "UBER RIDE",                "amount": -15.50,   "expected": "Transport"},
]

SYSTEM_PROMPT = """You are a financial transaction categorization expert. Categorize each transaction into exactly one of:
Food & Dining, Transport, Shopping, Entertainment, Utilities, Health, Rent/Housing, Income, Subscriptions, Other

Return ONLY a JSON array of category strings in the same order as the input. No explanation."""


def build_prompt(transactions):
    lines = ["Categorize these transactions. Return a JSON array:\n"]
    for i, t in enumerate(transactions, 1):
        sign = "+" if t["amount"] >= 0 else "-"
        lines.append(f"{i}. {t['date']} | {t['description']} | {sign}${abs(t['amount']):.2f}")
    lines.append("\nReturn only a JSON array of categories:")
    return "\n".join(lines)


def call_claude(client, transactions, run_num):
    """Call Claude and return list of categories."""
    prompt = build_prompt(transactions)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        categories = json.loads(text)
        if not isinstance(categories, list):
            raise ValueError("Response is not a list")
        return categories

    except Exception as e:
        print(f"  Warning: Run {run_num} error: {e}")
        return ["Other"] * len(transactions)


def run_reliability_check(api_key: str = None) -> dict:
    """
    Run the reliability check and return structured results.

    Args:
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.

    Returns:
        dict with keys:
          - consistency_pct  (float)
          - accuracy_pct     (float)
          - consistent_count (int)
          - correct_count    (int)
          - num_txns         (int)
          - num_runs         (int)
          - model            (str)
          - results          (list of per-transaction dicts)
          - error            (str | None)
    """
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        return {"error": "ANTHROPIC_API_KEY is not set."}

    try:
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        return {"error": f"Failed to initialise Anthropic client: {e}"}

    num_runs = 3
    num_txns = len(TEST_TRANSACTIONS)
    all_results = []

    for run in range(1, num_runs + 1):
        results = call_claude(client, TEST_TRANSACTIONS, run)

        # Pad / trim to match transaction count
        while len(results) < num_txns:
            results.append("Other")
        results = results[:num_txns]
        all_results.append(results)

        if run < num_runs:
            time.sleep(1)

    # ── Analyse ───────────────────────────────────────────────────────────────
    consistent_count = 0
    correct_count = 0
    per_txn_details = []

    for i, txn in enumerate(TEST_TRANSACTIONS):
        runs_for_txn = [all_results[r][i] for r in range(num_runs)]
        mode_cat = Counter(runs_for_txn).most_common(1)[0][0]
        all_agree = len(set(runs_for_txn)) == 1
        matches_expected = mode_cat == txn["expected"]

        if all_agree:
            consistent_count += 1
        if matches_expected:
            correct_count += 1

        per_txn_details.append({
            "description": txn["description"],
            "expected": txn["expected"],
            "run1": runs_for_txn[0],
            "run2": runs_for_txn[1],
            "run3": runs_for_txn[2],
            "consistent": all_agree,
            "correct": matches_expected,
        })

    consistency_pct = round((consistent_count / num_txns) * 100, 1)
    accuracy_pct    = round((correct_count    / num_txns) * 100, 1)

    return {
        "error":            None,
        "consistency_pct":  consistency_pct,
        "accuracy_pct":     accuracy_pct,
        "consistent_count": consistent_count,
        "correct_count":    correct_count,
        "num_txns":         num_txns,
        "num_runs":         num_runs,
        "model":            "claude-sonnet-4-20250514 (temperature=0)",
        "results":          per_txn_details,
    }


# ── CLI entry point ───────────────────────────────────────────────────────────

def _print_results(data: dict):
    print("=" * 70)
    print("  TrackWise AI Reliability Check")
    print("=" * 70)

    if data.get("error"):
        print(f"\n  ERROR: {data['error']}")
        return

    print(f"\n  Transactions : {data['num_txns']}")
    print(f"  Runs         : {data['num_runs']}")
    print(f"  Model        : {data['model']}\n")

    header = f"{'#':<3} {'Transaction':<32} {'Expected':<18} {'Run1':<18} {'Run2':<18} {'Run3':<18} Status"
    print(header)
    print("-" * len(header))

    for i, d in enumerate(data["results"], 1):
        if d["consistent"] and d["correct"]:
            status = "[PASS]"
        elif d["correct"]:
            status = "[INCONSISTENT]"
        else:
            status = "[FAIL]"
        print(
            f"{i:<3} {d['description'][:31]:<32} {d['expected']:<18} "
            f"{d['run1']:<18} {d['run2']:<18} {d['run3']:<18} {status}"
        )

    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Consistency (all {data['num_runs']} runs agree) : "
          f"{data['consistent_count']}/{data['num_txns']}  ->  {data['consistency_pct']:.0f}%")
    print(f"  Accuracy (matches expected)       : "
          f"{data['correct_count']}/{data['num_txns']}  ->  {data['accuracy_pct']:.0f}%")

    c = data["consistency_pct"]
    a = data["accuracy_pct"]
    print("\n  Consistency :", "[PERFECT]" if c == 100 else ("[GOOD]" if c >= 80 else "[WARN]"))
    print("  Accuracy    :", "[GOOD]" if a >= 90 else ("[WARN]" if a >= 70 else "[FAIL]"))
    print()
    print("=" * 70)


if __name__ == "__main__":
    _print_results(run_reliability_check())
