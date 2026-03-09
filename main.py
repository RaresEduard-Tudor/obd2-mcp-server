"""OBD-II Diagnostic Oracle — FastMCP server entry point.

Tools:
  • get_code_details   — look up a specific DTC code (includes severity)
  • get_codes          — batch look up multiple DTC codes in one call
  • search_by_symptom  — full-text symptom search (FTS5) with pagination
  • search_codes       — search codes by prefix or wildcard pattern
  • list_codes         — enumerate codes, filtered by category/severity, with pagination
  • get_related_codes  — find other codes in the same system category
  • ping               — health-check: confirms the server and database are running

Resources:
  • obd2://code/{code}      — single DTC as a resource (e.g. obd2://code/P0300)
  • obd2://category/{name}  — all codes in a category as a resource

Prompts:
  • diagnose — guided diagnostic walkthrough for a described vehicle problem
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
def get_codes(codes: list[str]) -> list[dict] | str:
    """Look up multiple OBD-II DTC codes in a single call.

    More efficient than calling get_code_details repeatedly when a vehicle
    has thrown several fault codes at once.  Returns full details for every
    found code; unknown codes are listed in a ``not_found`` entry appended
    to the result list.

    Args:
        codes: List of DTC codes (e.g. ["P0300", "P0420", "P0171"]).
               Case-insensitive.
    """
    if not codes:
        return "Please provide at least one DTC code."
    normalized = [c.strip().upper() for c in codes if c.strip()]
    if not normalized:
        return "Please provide at least one DTC code."
    results = db.lookup_codes(normalized)
    found = {r["code"] for r in results}
    missing = [c for c in normalized if c not in found]
    if missing:
        results = list(results) + [{"not_found": missing}]
    return results


@mcp.tool()
def search_codes(pattern: str, limit: int = 50) -> list[dict] | str:
    """Search OBD-II codes by code prefix or wildcard pattern.

    Supports prefix matching and glob-style wildcards:
      - "P030"  → matches P0300–P0309
      - "P03*"  → matches all P03xx codes
      - "P0?00" → matches P0000, P0100, P0200, …
      - "C0*"   → all ABS/Chassis C0 codes
      - "B*"    → all body codes

    Useful when the user asks "show me all P030x misfires" or
    "what B-codes do you have?".

    Args:
        pattern: Code prefix or wildcard pattern. Case-insensitive.
        limit:   Maximum results (default 50, max 200).
    """
    pat = pattern.strip().upper()
    if not pat:
        return "Please provide a code prefix or pattern."
    results = db.search_code_prefix(pat, limit=min(limit, 200))
    if not results:
        return f"No codes found matching pattern '{pat}'."
    return results


@mcp.tool()
def search_by_symptom(text: str, limit: int = 10, offset: int = 0) -> list[dict] | str:
    """Search OBD-II codes by symptom description or free-text query.

    Uses full-text search (FTS5) so word-order doesn't matter — "engine shaking"
    and "shaking engine" both work. Use this tool when the user describes a car
    problem in plain language, e.g. "my car is shaking", "rough idle",
    "check engine light flashing", or "stalling at traffic lights".
    Returns matching DTC codes with their category, severity, description, symptoms, and fixes.

    Args:
        text:   Free-text description of the symptom or problem.
        limit:  Maximum number of results to return (default 10, max 50).
        offset: Number of results to skip for pagination (default 0).
    """
    query = text.strip()
    if not query:
        return "Please provide a symptom description to search for."
    try:
        results = db.search_symptoms(query, limit=min(limit, 50))
    except Exception as exc:
        logger.error("FTS search failed: %s", exc)
        return f"Search failed: {exc}"
    if not results:
        return f"No DTC codes matched the symptom description: '{query}'."
    return results[offset:]


@mcp.tool()
def list_codes(
    category: str = "", severity: str = "", limit: int = 50, offset: int = 0
) -> list[dict] | str:
    """List available OBD-II DTC codes, optionally filtered by category and/or severity.

    Returns code + category + severity + description. Supports pagination via
    limit/offset. Useful for browsing all codes or finding what's available
    within a specific system category or urgency level.

    Severity levels: Critical (stop driving), Warning (repair soon), Info (emissions only).

    Available categories: Fuel & Air, Ignition, Oxygen Sensors,
    Catalytic Converter, EVAP, EGR, Transmission, Electrical, Throttle,
    Cooling, Oil, ABS & Brakes, Variable Valve Timing, Crankshaft & Camshaft,
    Knock Sensor, Fuel Injectors, Turbocharger, Secondary Air Injection,
    A/C & Climate, Network & Communication, Steering.

    Args:
        category: Optional category name to filter by (case-sensitive).
        severity: Optional severity level to filter by: Critical, Warning, or Info.
        limit:    Maximum number of results (default 50).
        offset:   Number of results to skip for pagination (default 0).
    """
    cat = category.strip() or None
    sev = severity.strip() or None
    results = db.list_codes(category=cat, limit=min(limit, 200), offset=offset)
    if sev:
        results = [r for r in results if r.get("severity") == sev]
    if not results:
        if cat or sev:
            available_cats = db.get_categories()
            return (
                "No codes found"
                + (f" for category '{cat}'" if cat else "")
                + (f" with severity '{sev}'" if sev else "")
                + f". Available categories: {', '.join(available_cats)}."
            )
        return "No codes found in the database."
    return results


@mcp.tool()
def get_related_codes(code: str) -> list[dict] | str:
    """Find other OBD-II codes in the same system category as the given code.

    Useful for exploring related faults after identifying a primary code.
    For example, if P0300 (random misfire) is found, this returns other
    Ignition codes that may also be relevant.

    Args:
        code: A DTC code (e.g. "P0300"). Case-insensitive.
    """
    normalized = code.strip().upper()
    results = db.get_related_codes(normalized)
    if not results:
        # Check whether the code itself exists to give a better message
        if db.lookup_code(normalized) is None:
            return f"DTC code '{normalized}' was not found in the database."
        return f"No other codes found in the same category as '{normalized}'."
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


# ── Resources ────────────────────────────────────────────────────────────────


@mcp.resource("obd2://code/{code}")
def resource_code(code: str) -> str:
    """Expose a single DTC code as an MCP resource.

    URI format: obd2://code/P0300
    Returns the code details as formatted plain text, or a not-found message.
    """
    row = db.lookup_code(code.strip().upper())
    if row is None:
        return f"DTC code '{code.upper()}' was not found in the database."
    return (
        f"Code:        {row['code']}\n"
        f"Category:    {row['category']}\n"
        f"Severity:    {row['severity']}\n"
        f"Description: {row['description']}\n"
        f"Symptoms:    {row['symptoms']}\n"
        f"Fix:         {row['fix']}\n"
    )


@mcp.resource("obd2://category/{name}")
def resource_category(name: str) -> str:
    """Expose all codes in a category as an MCP resource.

    URI format: obd2://category/Ignition
    Returns a plain-text list of codes with descriptions, or a not-found message.
    """
    rows = db.list_codes(category=name)
    if not rows:
        available = db.get_categories()
        return (
            f"No codes found for category '{name}'.\n"
            f"Available categories: {', '.join(available)}"
        )
    lines = [f"Category: {name}", f"Total codes: {len(rows)}", ""]
    for row in rows:
        lines.append(f"  {row['code']}  —  {row['description']}")
    return "\n".join(lines)


# ── Prompts ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def diagnose(symptoms: str, codes: str = "") -> str:
    """Generate a structured diagnostic walkthrough for a vehicle problem.

    Args:
        symptoms: Plain-language description of what the vehicle is doing wrong.
        codes:    Optional comma-separated DTC codes already retrieved from the car
                  (e.g. "P0300, P0171"). Leave blank if none are known.
    """
    parts = [
        "You are an expert automotive diagnostic technician.",
        "The driver has reported the following issue with their vehicle:",
        f"  {symptoms.strip()}",
    ]

    if codes.strip():
        code_list = [c.strip().upper() for c in codes.split(",") if c.strip()]
        parts.append(
            "\nThe following OBD-II Diagnostic Trouble Codes (DTCs) have been "
            f"retrieved from the vehicle: {', '.join(code_list)}."
        )
        parts.append(
            "Use the get_code_details tool to look up each code, then synthesise "
            "the results into a coherent diagnosis."
        )
    else:
        parts.append(
            "\nNo DTC codes have been retrieved yet. "
            "Use the search_by_symptom tool to find relevant codes, "
            "then use get_code_details to look up the most likely candidates."
        )

    parts += [
        "",
        "Please provide a structured diagnostic response with these sections:",
        "1. **Likely Cause(s)** — ranked from most to least probable.",
        "2. **Immediate Safety Concerns** — if any code has severity 'Critical', "
        "state clearly that the vehicle should NOT be driven until repaired.",
        "3. **Step-by-Step Diagnosis** — what to inspect or test first, in order.",
        "4. **Estimated Repair** — typical DIY difficulty (Easy / Moderate / Advanced) "
        "and whether a specialist should be consulted.",
        "5. **Preventative Notes** — what could have caused this and how to avoid recurrence.",
    ]

    return "\n".join(parts)


if __name__ == "__main__":
    mcp.run()
