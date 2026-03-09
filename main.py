"""OBD-II Diagnostic Oracle — FastMCP server entry point.

Exposes four tools to GitHub Copilot (Agent Mode):
  • get_code_details  — look up a specific DTC code
  • search_by_symptom — full-text symptom search (FTS5)
  • list_codes        — enumerate codes, optionally filtered by category
  • ping              — health-check: confirms the server and database are running
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

import db

logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
logger = logging.getLogger(__name__)

mcp = FastMCP("obd2-diagnostic")


@mcp.tool()
def get_code_details(code: str) -> dict | str:
    """Look up a specific OBD-II Diagnostic Trouble Code (DTC).

    Returns the code's category, description, common symptoms, and recommended fix.
    Call this tool when the user provides a DTC code such as P0300 or P0420.

    Args:
        code: The DTC code to look up (e.g. "P0300"). Case-insensitive.
    """
    normalized = code.strip().upper()
    result = db.lookup_code(normalized)
    if result is None:
        return f"DTC code '{normalized}' was not found in the database."
    return result


@mcp.tool()
def search_by_symptom(text: str) -> list[dict] | str:
    """Search OBD-II codes by symptom description or free-text query.

    Uses full-text search (FTS5) so word-order doesn't matter — "engine shaking"
    and "shaking engine" both work. Use this tool when the user describes a car
    problem in plain language, e.g. "my car is shaking", "rough idle",
    "check engine light flashing", or "stalling at traffic lights".
    Returns matching DTC codes with their category, description, symptoms, and fixes.

    Args:
        text: Free-text description of the symptom or problem.
    """
    query = text.strip()
    if not query:
        return "Please provide a symptom description to search for."
    try:
        results = db.search_symptoms(query)
    except Exception as exc:
        logger.error("FTS search failed: %s", exc)
        return f"Search failed: {exc}"
    if not results:
        return f"No DTC codes matched the symptom description: '{query}'."
    return results


@mcp.tool()
def list_codes(category: str = "") -> list[dict] | str:
    """List available OBD-II DTC codes, optionally filtered by category.

    Returns a concise list of code + description pairs. Useful for browsing
    all codes or finding what's available within a specific system category.

    Available categories: Fuel & Air, Ignition, Oxygen Sensors,
    Catalytic Converter, EVAP, EGR, Transmission, Electrical, Throttle,
    Cooling, Oil, ABS & Brakes.

    Call with no argument (or category="") to list all codes.

    Args:
        category: Optional category name to filter by (case-sensitive).
    """
    cat = category.strip() or None
    results = db.list_codes(category=cat)
    if not results:
        if cat:
            available = db.get_categories()
            return (
                f"No codes found for category '{cat}'. "
                f"Available categories: {', '.join(available)}."
            )
        return "No codes found in the database."
    return results


@mcp.tool()
def ping() -> dict:
    """Health-check tool. Confirms the OBD-II MCP server is running and the database is accessible.

    Returns a status dict with 'status' ('ok' or 'error') and 'total_codes' count.
    Call this to verify the server is operational before running other tools.
    """
    if db.db_ping():
        with db.get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM dtc_codes").fetchone()[0]
            categories = db.get_categories()
        return {
            "status": "ok",
            "total_codes": total,
            "categories": categories,
        }
    return {"status": "error", "detail": "Database unreachable or empty."}


if __name__ == "__main__":
    mcp.run()
