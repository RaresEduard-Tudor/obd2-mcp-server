"""Tests for OBD-II MCP server tools.

Unit tests mock the database layer.
Integration tests use an in-memory SQLite database via a monkeypatch.
"""

import sqlite3

import pytest

import db
import main  # noqa: E402  (project root on pythonpath)

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def memory_db(monkeypatch, tmp_path):
    """Patch db.DB_PATH to a temporary file and seed minimal test data.

    This fixture creates the full schema (with category column) but intentionally
    omits the FTS virtual table so that search_symptoms falls back to LIKE — this
    keeps the test DB simple while still exercising the search logic.
    """
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)

    with sqlite3.connect(test_db) as conn:
        conn.execute(
            """
            CREATE TABLE dtc_codes (
                code        TEXT PRIMARY KEY,
                category    TEXT NOT NULL,
                severity    TEXT NOT NULL DEFAULT 'Warning',
                description TEXT NOT NULL,
                symptoms    TEXT NOT NULL,
                fix         TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO dtc_codes VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "P0300",
                    "Ignition",
                    "Warning",
                    "Random/Multiple Cylinder Misfire Detected",
                    "Rough idle, shaking, flashing check engine light",
                    "Replace spark plugs, ignition coils, or fuel injectors",
                ),
                (
                    "P0420",
                    "Catalytic Converter",
                    "Warning",
                    "Catalyst System Efficiency Below Threshold (Bank 1)",
                    "Check engine light, poor fuel economy, sulfur smell",
                    "Replace catalytic converter; rule out misfires first",
                ),
                (
                    "P0171",
                    "Fuel & Air",
                    "Warning",
                    "System Too Lean (Bank 1)",
                    "Rough idle, hesitation, poor fuel economy, misfires",
                    "Check for vacuum leaks; inspect MAF sensor and injectors",
                ),
                (
                    "C0031",
                    "ABS & Brakes",
                    "Critical",
                    "Right Front Wheel Speed Sensor Circuit Malfunction",
                    "ABS warning light, traction control light disabled",
                    "Replace right front wheel speed sensor",
                ),
            ],
        )
        conn.commit()

    return test_db


# ── db.lookup_code ──────────────────────────────────────────────────────────


class TestLookupCode:
    def test_existing_code_returns_dict(self, memory_db):
        result = db.lookup_code("P0300")
        assert isinstance(result, dict)
        assert result["code"] == "P0300"
        assert "Misfire" in result["description"]

    def test_result_includes_category(self, memory_db):
        result = db.lookup_code("P0300")
        assert result is not None
        assert result["category"] == "Ignition"

    def test_result_includes_severity(self, memory_db):
        result = db.lookup_code("P0300")
        assert result is not None
        assert result["severity"] == "Warning"

    def test_critical_severity_returned(self, memory_db):
        result = db.lookup_code("C0031")
        assert result is not None
        assert result["severity"] == "Critical"

    def test_missing_code_returns_none(self, memory_db):
        result = db.lookup_code("P9999")
        assert result is None


# ── db.search_symptoms ──────────────────────────────────────────────────────


class TestSearchSymptoms:
    def test_symptom_match_returns_results(self, memory_db):
        results = db.search_symptoms("rough idle")
        assert len(results) >= 1
        codes = [r["code"] for r in results]
        assert "P0300" in codes or "P0171" in codes

    def test_no_match_returns_empty_list(self, memory_db):
        results = db.search_symptoms("xyzzy_no_match_ever")
        assert results == []

    def test_limit_respected(self, memory_db):
        results = db.search_symptoms("idle", limit=1)
        assert len(results) <= 1

    def test_results_include_category(self, memory_db):
        results = db.search_symptoms("shaking")
        assert len(results) >= 1
        assert "category" in results[0]


# ── db.list_codes ────────────────────────────────────────────────────────────


class TestListCodes:
    def test_returns_all_codes_without_filter(self, memory_db):
        results = db.list_codes()
        assert len(results) == 4

    def test_category_filter_works(self, memory_db):
        results = db.list_codes(category="Ignition")
        assert len(results) == 1
        assert results[0]["code"] == "P0300"

    def test_unknown_category_returns_empty(self, memory_db):
        results = db.list_codes(category="Nonexistent")
        assert results == []

    def test_results_contain_code_and_description(self, memory_db):
        results = db.list_codes()
        for row in results:
            assert "code" in row
            assert "description" in row

    def test_results_contain_severity(self, memory_db):
        results = db.list_codes()
        for row in results:
            assert "severity" in row

    def test_pagination_offset(self, memory_db):
        all_rows = db.list_codes()
        page2 = db.list_codes(offset=2)
        assert len(page2) == len(all_rows) - 2
        assert page2[0]["code"] == all_rows[2]["code"]

    def test_limit_respected(self, memory_db):
        results = db.list_codes(limit=2)
        assert len(results) == 2


# ── db.get_categories ────────────────────────────────────────────────────────


class TestGetCategories:
    def test_returns_distinct_sorted_categories(self, memory_db):
        cats = db.get_categories()
        assert "Ignition" in cats
        assert "Fuel & Air" in cats
        assert cats == sorted(cats)

    def test_no_duplicates(self, memory_db):
        cats = db.get_categories()
        assert len(cats) == len(set(cats))


# ── db.db_ping ───────────────────────────────────────────────────────────────


class TestDbPing:
    def test_ping_returns_true_when_data_exists(self, memory_db):
        assert db.db_ping() is True

    def test_ping_returns_false_on_bad_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr(db, "DB_PATH", tmp_path / "nonexistent.db")
        # SQLite will create the file but the table won't exist → exception → False
        assert db.db_ping() is False


# ── Tool: get_code_details ───────────────────────────────────────────────────


class TestGetCodeDetails:
    def test_valid_code_returns_dict(self, memory_db):
        result = main.get_code_details("P0300")
        assert isinstance(result, dict)
        assert result["code"] == "P0300"

    def test_result_includes_category(self, memory_db):
        result = main.get_code_details("P0420")
        assert isinstance(result, dict)
        assert result["category"] == "Catalytic Converter"

    def test_result_includes_severity(self, memory_db):
        result = main.get_code_details("P0300")
        assert isinstance(result, dict)
        assert result["severity"] == "Warning"

    def test_critical_severity_surfaced(self, memory_db):
        result = main.get_code_details("C0031")
        assert isinstance(result, dict)
        assert result["severity"] == "Critical"

    def test_normalises_to_uppercase(self, memory_db):
        result = main.get_code_details("p0300")
        assert isinstance(result, dict)
        assert result["code"] == "P0300"

    def test_strips_whitespace(self, memory_db):
        result = main.get_code_details("  P0300  ")
        assert isinstance(result, dict)

    def test_unknown_code_returns_not_found_string(self, memory_db):
        result = main.get_code_details("P9999")
        assert isinstance(result, str)
        assert "P9999" in result

    def test_empty_input_returns_not_found_string(self, memory_db):
        result = main.get_code_details("  ")
        assert isinstance(result, str)


# ── Tool: search_by_symptom ──────────────────────────────────────────────────


class TestSearchBySymptom:
    def test_matching_symptom_returns_list(self, memory_db):
        result = main.search_by_symptom("shaking")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_no_match_returns_string(self, memory_db):
        result = main.search_by_symptom("xyzzy_no_match_ever")
        assert isinstance(result, str)
        result_lower = result.lower()
        assert "no dtc" in result_lower or "not matched" in result_lower

    def test_empty_query_returns_instructions_string(self, memory_db):
        result = main.search_by_symptom("   ")
        assert isinstance(result, str)

    def test_results_contain_expected_keys(self, memory_db):
        results = main.search_by_symptom("misfire")
        assert isinstance(results, list)
        expected = {"code", "category", "severity", "description", "symptoms", "fix"}
        for row in results:
            assert expected <= row.keys()

    def test_limit_parameter_respected(self, memory_db):
        results = main.search_by_symptom("idle", limit=1)
        assert isinstance(results, list)
        assert len(results) <= 1

    def test_offset_parameter_paginates(self, memory_db):
        all_results = main.search_by_symptom("rough idle")
        if isinstance(all_results, list) and len(all_results) > 1:
            offset_results = main.search_by_symptom("rough idle", offset=1)
            assert isinstance(offset_results, list)
            assert len(offset_results) == len(all_results) - 1


# ── Tool: list_codes ─────────────────────────────────────────────────────────


class TestListCodesTool:
    def test_no_category_returns_all(self, memory_db):
        result = main.list_codes()
        assert isinstance(result, list)
        assert len(result) == 4

    def test_empty_string_category_returns_all(self, memory_db):
        result = main.list_codes(category="")
        assert isinstance(result, list)
        assert len(result) == 4

    def test_valid_category_filters(self, memory_db):
        result = main.list_codes(category="Ignition")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["code"] == "P0300"

    def test_severity_filter_works(self, memory_db):
        critical = main.list_codes(severity="Critical")
        assert isinstance(critical, list)
        assert all(r["severity"] == "Critical" for r in critical)
        assert any(r["code"] == "C0031" for r in critical)

    def test_unknown_category_returns_helpful_string(self, memory_db):
        result = main.list_codes(category="Nonexistent")
        assert isinstance(result, str)
        assert "Nonexistent" in result

    def test_whitespace_category_returns_all(self, memory_db):
        result = main.list_codes(category="   ")
        assert isinstance(result, list)

    def test_pagination_limit(self, memory_db):
        result = main.list_codes(limit=2)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_pagination_offset(self, memory_db):
        all_codes = main.list_codes()
        assert isinstance(all_codes, list)
        paged = main.list_codes(offset=2)
        assert isinstance(paged, list)
        assert len(paged) == len(all_codes) - 2


# ── Tool: ping ───────────────────────────────────────────────────────────────


class TestPingTool:
    def test_ping_returns_ok_status(self, memory_db):
        result = main.ping()
        assert isinstance(result, dict)
        assert result["status"] == "ok"

    def test_ping_includes_total_codes(self, memory_db):
        result = main.ping()
        assert result["total_codes"] == 4

    def test_ping_includes_categories(self, memory_db):
        result = main.ping()
        assert "categories" in result
        assert "Ignition" in result["categories"]

    def test_ping_error_when_db_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(db, "DB_PATH", tmp_path / "missing.db")
        result = main.ping()
        assert result["status"] == "error"


# ── Resource: obd2://code/{code} ─────────────────────────────────────────────


class TestResourceCode:
    def test_known_code_returns_formatted_string(self, memory_db):
        result = main.resource_code("P0300")
        assert isinstance(result, str)
        assert "P0300" in result
        assert "Ignition" in result

    def test_severity_included_in_resource(self, memory_db):
        result = main.resource_code("P0300")
        assert "Warning" in result

    def test_critical_severity_in_resource(self, memory_db):
        result = main.resource_code("C0031")
        assert "Critical" in result

    def test_normalises_to_uppercase(self, memory_db):
        result = main.resource_code("p0300")
        assert "P0300" in result

    def test_strips_whitespace(self, memory_db):
        result = main.resource_code("  P0300  ")
        assert "P0300" in result

    def test_unknown_code_returns_not_found_message(self, memory_db):
        result = main.resource_code("P9999")
        assert isinstance(result, str)
        assert "P9999" in result.upper() or "not found" in result.lower()

    def test_result_contains_fix_field(self, memory_db):
        result = main.resource_code("P0420")
        assert "catalytic" in result.lower() or "Fix" in result


# ── Resource: obd2://category/{name} ─────────────────────────────────────────


class TestResourceCategory:
    def test_known_category_lists_codes(self, memory_db):
        result = main.resource_category("Ignition")
        assert isinstance(result, str)
        assert "P0300" in result

    def test_unknown_category_shows_available(self, memory_db):
        result = main.resource_category("Nonexistent")
        assert isinstance(result, str)
        assert "Nonexistent" in result
        # Should list alternatives
        assert "Ignition" in result or "available" in result.lower()

    def test_result_includes_code_count_or_entries(self, memory_db):
        result = main.resource_category("Fuel & Air")
        assert "P0171" in result


# ── Prompt: diagnose ──────────────────────────────────────────────────────────


class TestDiagnosePrompt:
    def test_returns_string(self):
        result = main.diagnose("Engine shaking at idle")
        assert isinstance(result, str)

    def test_contains_symptom(self):
        result = main.diagnose("Rough idle and white smoke")
        assert "Rough idle and white smoke" in result

    def test_no_codes_instructs_search(self):
        result = main.diagnose("Car won't start")
        assert "search_by_symptom" in result

    def test_with_codes_instructs_lookup(self):
        result = main.diagnose("Misfiring", codes="P0300, P0301")
        assert "get_code_details" in result
        assert "P0300" in result

    def test_contains_structured_sections(self):
        result = main.diagnose("Loss of power on acceleration")
        assert "Likely Cause" in result
        assert "Safety" in result

    def test_critical_severity_mentioned_in_safety_section(self):
        result = main.diagnose("Oil pressure warning light")
        assert "Critical" in result


# ── Tool: get_related_codes ───────────────────────────────────────────────────


class TestGetRelatedCodes:
    def test_returns_codes_in_same_category(self, memory_db):
        # P0300 is Ignition; P0420 is Catalytic — no other Ignition codes in fixture
        # so let's use Fuel & Air which has P0171
        result = main.get_related_codes("P0171")
        # Only one Fuel & Air code in fixture — expect empty or helpful string
        assert isinstance(result, (list, str))

    def test_multiple_codes_in_category(self, memory_db):
        # Add a second Ignition code so we can test the return
        import sqlite3 as _sqlite3

        row_data = (
            "P0301",
            "Ignition",
            "Warning",
            "Cylinder 1 Misfire",
            "Rough idle",
            "Replace plug",
        )
        with _sqlite3.connect(memory_db) as conn:
            conn.execute("INSERT INTO dtc_codes VALUES (?, ?, ?, ?, ?, ?)", row_data)
        result = main.get_related_codes("P0300")
        assert isinstance(result, list)
        assert any(r["code"] == "P0301" for r in result)
        # P0300 itself should not appear
        assert all(r["code"] != "P0300" for r in result)

    def test_unknown_code_returns_not_found(self, memory_db):
        result = main.get_related_codes("P9999")
        assert isinstance(result, str)
        assert "P9999" in result

    def test_normalises_to_uppercase(self, memory_db):
        import sqlite3 as _sqlite3

        row_data = (
            "P0301",
            "Ignition",
            "Warning",
            "Cylinder 1 Misfire",
            "Rough idle",
            "Replace plug",
        )
        with _sqlite3.connect(memory_db) as conn:
            conn.execute("INSERT INTO dtc_codes VALUES (?, ?, ?, ?, ?, ?)", row_data)
        result = main.get_related_codes("p0300")
        assert isinstance(result, list)
