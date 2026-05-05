"""
SquadMind – Standardised API Response Envelope
Every API response follows this structure so the frontend
can handle them uniformly without parsing branching logic.

{
  "success": true,
  "message": "...",
  "data": { ... },
  "error": null
}
"""

from __future__ import annotations

from typing import Any, Optional


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200,
) -> dict:
    """Standard success envelope. Always return this from route handlers."""
    return {
        "success": True,
        "message": message,
        "data": data,
        "error": None,
    }


def error_response(
    message: str,
    error: Optional[str] = None,
    data: Any = None,
) -> dict:
    """Standard error envelope. Typically raised via HTTPException instead."""
    return {
        "success": False,
        "message": message,
        "data": data,
        "error": error or message,
    }


def paginated_response(
    items: list,
    total: int,
    page: int,
    page_size: int,
    message: str = "Success",
) -> dict:
    """Convenience wrapper for paginated list responses."""
    total_pages = (total + page_size - 1) // page_size
    return success_response(
        data={
            "items": items,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        },
        message=message,
    )
