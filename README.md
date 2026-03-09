# OBD2 MCP Server — "The Diagnostic Oracle"

A Model Context Protocol (MCP) server that gives GitHub Copilot (Agent Mode) expert-level automotive diagnostic knowledge. Highlight a DTC error code in your terminal or describe a symptom in chat and get a full mechanical breakdown — causes, symptoms, and fixes — instantly.

## Why This Exists

Modern AI coding assistants can do more than write code. With MCP, you can give them **domain-specific tools** they can call autonomously. This project turns Copilot into a mechanic's reference manual by exposing OBD-II diagnostic data through a local MCP server.

## Architecture

```
┌───────────────────────────┐
│  VS Code / Copilot        │
│  (Agent Mode Chat)        │
└────────┬──────────────────┘
         │  MCP protocol (stdio)
         ▼
┌───────────────────────────┐
│  obd2-mcp-server          │
│  FastMCP (Python)         │
│                           │
│  9 Tools · 4 Resources    │
│  1 Prompt                 │
│             │             │
│  ┌──────────▼──────────┐  │
│  │  db.py              │  │
│  │  SQLite (obd2.db)   │  │
│  │  FTS5 full-text     │  │
│  └─────────────────────┘  │
└───────────────────────────┘
```

## Tech Stack

| Layer           | Choice                                     |
| --------------- | ------------------------------------------ |
| Language        | Python 3.11+                               |
| Framework       | `mcp` SDK with **FastMCP**                 |
| Database        | SQLite (local `obd2.db`)                   |
| Search          | SQLite FTS5 (full-text symptom search)     |
| Package Manager | `uv`                                       |
| IDE Integration | GitHub Copilot Chat (Agent Mode) + VS Code |

## Data Coverage

**428 DTC codes** across **24 categories** with three severity levels:

| Category                | Codes | | Category               | Codes |
| ----------------------- | :---: |-| ---------------------- | :---: |
| ABS & Brakes            | 36    | | Transmission           | 35    |
| Throttle                | 33    | | Fuel & Air             | 32    |
| Electrical              | 25    | | Ignition               | 20    |
| Variable Valve Timing   | 18    | | Airbag & Safety        | 16    |
| Network & Communication | 16    | | A/C & Climate          | 15    |
| Cooling                 | 15    | | Turbocharger           | 15    |
| EVAP                    | 14    | | Fuel Injectors         | 14    |
| Knock Sensor            | 14    | | Steering               | 14    |
| Crankshaft & Camshaft   | 13    | | Oil                    | 13    |
| Body & Convenience      | 12    | | Catalytic Converter    | 12    |
| EGR                     | 12    | | Hybrid & EV            | 12    |
| Oxygen Sensors          | 12    | | Secondary Air Injection| 10    |

Severity levels: **Critical** (stop driving) · **Warning** (repair soon) · **Info** (emissions / monitor only)

## Tools Reference

| Tool | Parameters | Description |
| ---- | ---------- | ----------- |
| `get_code_details` | `code` | Look up one DTC — category, severity, description, symptoms, and fix |
| `get_codes` | `codes` | Batch look up multiple codes in one call |
| `search_by_symptom` | `text, limit, offset` | Full-text symptom search with pagination |
| `search_codes` | `pattern, limit` | Search by code prefix or wildcard (`P030*`, `C0*`) |
| `list_codes` | `category, severity, limit, offset` | Browse codes with optional filters and pagination |
| `count_codes` | `category, severity` | Count matching codes (pair with `list_codes` for pagination totals) |
| `export_codes` | `format` | Dump all codes as JSON or CSV string |
| `get_related_codes` | `code` | Find other codes in the same system category |
| `ping` | — | Health-check — confirms server and database are running |

## Resources Reference

| Resource URI | Description |
| ------------ | ----------- |
| `obd2://code/{code}` | Single DTC as formatted plain text (e.g. `obd2://code/P0300`) |
| `obd2://category/{name}` | All codes in a category (e.g. `obd2://category/Ignition`) |
| `obd2://severity/{level}` | All codes at a severity level (`Critical`, `Warning`, or `Info`) |
| `obd2://stats` | Total code count with per-category and per-severity breakdown |

## Prompt

| Prompt | Parameters | Description |
| ------ | ---------- | ----------- |
| `diagnose` | `symptoms, codes` | Guided diagnostic walkthrough — describe vehicle symptoms and/or paste known DTC codes |

## Database Schema

**`dtc_codes`**

| Column        | Type    | Example                                          |
| ------------- | ------- | ------------------------------------------------ |
| `code`        | TEXT PK | `P0300`                                          |
| `category`    | TEXT    | `Ignition`                                       |
| `severity`    | TEXT    | `Warning`                                        |
| `description` | TEXT    | `Random/Multiple Cylinder Misfire Detected`      |
| `symptoms`    | TEXT    | `Rough idle, shaking, flashing CEL`              |
| `fix`         | TEXT    | `Replace spark plugs, ignition coils, or fuel injectors` |

Full-text search is powered by a **FTS5 virtual table** (`dtc_codes_fts`) kept in sync with the main table via three SQLite triggers (insert, update, delete).

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- VS Code with GitHub Copilot extension (Agent Mode enabled)

### Installation

```bash
git clone https://github.com/RaresEduard-Tudor/obd2-mcp-server.git
cd obd2-mcp-server

uv sync          # install dependencies
uv run seed.py   # create and populate obd2.db
uv run main.py   # test the server manually (Ctrl+C to stop)
```

### Using with Copilot

1. Open the project in VS Code.
2. The `.vscode/mcp.json` config registers the server automatically.
3. Open Copilot Chat (Agent Mode) and try:
   - *"What does P0300 mean?"*
   - *"Look up P0420, P0171, and C0031 all at once."*
   - *"My car is shaking and the check engine light keeps flashing."*
   - *"Show me all Critical severity ABS codes."*
   - *"How many Transmission codes are there?"*
   - *"Export all codes as CSV."*

### Running Tests

```bash
uv run pytest -v
```

## Project Structure

```
obd2-mcp-server/
├── .vscode/
│   └── mcp.json       # Registers the MCP server with VS Code / Copilot
├── tests/
│   └── test_tools.py  # pytest test suite (141 tests)
├── main.py            # FastMCP server — tool, resource, and prompt definitions
├── db.py              # Database access layer (SQLite helpers and queries)
├── seed.py            # Schema creation and data seeding (source of truth)
├── obd2.db            # SQLite database (gitignored; generated by seed.py)
├── pyproject.toml     # Project metadata and dependencies
├── guidelines.md      # Development guidelines and conventions
└── README.md
```

## License

MIT
