#!/usr/bin/env python3
"""
Pilot runner — two representative inputs, saves each result as HTML.
Usage: python run_pilot.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from src.loop import run_verification
from src.formatter import render_html

RUNS = [
    {
        "slug": "phishing_paypal",
        "input": (
            "URGENT: Your PayPal account has been suspended due to suspicious activity. "
            "Click the link below immediately to verify your identity or your account will be permanently closed. "
            "Verify now: http://paypal-secure-verify.xyz/confirm"
        ),
    },
    {
        "slug": "bbc_inflation",
        "input": (
            "BBC News, 17 July 2025: UK inflation fell to 2.1% in June, down from 2.3% in May, "
            "according to figures published today by the Office for National Statistics. "
            "The Bank of England said the fall was in line with its forecast and that interest rate "
            "decisions would continue to be guided by incoming data."
        ),
    },
]

out_dir = Path(__file__).parent / "run_results"
out_dir.mkdir(exist_ok=True)

for run in RUNS:
    print(f"\n→ Checking: {run['slug']}...")
    response = run_verification(run["input"])
    html = render_html(response)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = out_dir / f"{run['slug']}_{ts}.html"
    filename.write_text(html, encoding="utf-8")
    print(f"  Risk: {response.get('risk_level')}  Confidence: {int(response.get('confidence', 0)*100)}%")
    print(f"  Saved: {filename.name}")

print("\nDone.")
