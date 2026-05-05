"""
SquadMind – Formatting Utilities
Nigerian currency, percentage, and date helpers.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Union


def format_naira(amount: Union[Decimal, float, int], decimals: int = 0) -> str:
    """Format a number as Nigerian Naira. e.g. ₦4,200,000"""
    val = float(amount)
    if decimals == 0:
        return f"₦{val:,.0f}"
    return f"₦{val:,.{decimals}f}"


def format_percent(value: float, decimals: int = 1) -> str:
    """Format a float as a percentage string. e.g. '12.5%'"""
    return f"{value:.{decimals}f}%"


def format_large_number(n: Union[int, float]) -> str:
    """Shorten large numbers for display: 1500000 → '1.5M'"""
    n = float(n)
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n))


def kobo_to_naira(kobo: Union[int, float]) -> Decimal:
    """Convert Squad API kobo amount to Naira."""
    return Decimal(str(kobo)) / 100


def naira_to_kobo(naira: Union[Decimal, float]) -> int:
    """Convert Naira to kobo for Squad API calls."""
    return int(float(naira) * 100)
