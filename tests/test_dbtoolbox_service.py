"""Tests for dbtoolbox QueryService + declarative sqltools (SQLite double)."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from dbtoolbox.dialects import DialectAdapter
from dbtoolbox.errors import PolicyViolation
from dbtoolbox.policy import SecurityPolicy
from dbtoolbox.service import QueryService, serialize_row, serialize_value
from dbtoolbox.sqltools import ParamDef, SQLToolDef, coerce_args, parse_tool_defs, run_sql_tool


class _SQLiteSource:
    """Duck-typed Source double backed by in-memory SQLite."""

    def __init__(self):
        self.engine = create_engine("sqlite://")
        self.dialect = DialectAdapter(
            name="sqlite", url_template="", sqlglot_dialect="sqlite"
        )
        with self.engine.begin() as conn:
            conn.execute(text("CREATE TABLE items (id INTEGER, name TEXT)"))
            for i in range(20):
                conn.execute(
                    text("INSERT INTO items VALUES (:i, :n)"),
                    {"i": i, "n": f"item{i}"},
                )


@pytest.fixture
def service():
    return QueryService(
        _SQLiteSource(),
        SecurityPolicy(allowed_tables=None, max_rows=10, export_max_rows=15),
    )


class TestSerialization:
    def test_serialize_value_types(self):
        assert serialize_value(date(2026, 6, 11)) == "2026-06-11"
        assert serialize_value(datetime(2026, 6, 11, 1, 2, 3)) == "2026-06-11T01:02:03"
        assert serialize_value(Decimal("1.5")) == 1.5
        assert serialize_value(b"abc") == "abc"
        assert serialize_value(42) == 42

    def test_serialize_row(self):
        row = {"d": date(2026, 1, 1), "n": Decimal("2"), "s": "x"}
        assert serialize_row(row) == {"d": "2026-01-01", "n": 2.0, "s": "x"}


class TestExecute:
    def test_returns_rows(self, service):
        rows = service.execute("SELECT id, name FROM items WHERE id < 3 ORDER BY id")
        assert [r["id"] for r in rows] == [0, 1, 2]

    def test_policy_max_rows_caps_unlimited_query(self, service):
        rows = service.execute("SELECT * FROM items")
        assert len(rows) == 10  # policy.max_rows

    def test_explicit_limit_below_cap(self, service):
        rows = service.execute("SELECT * FROM items", limit=5)
        assert len(rows) == 5

    def test_explicit_limit_above_cap_is_min_ed(self, service):
        rows = service.execute("SELECT * FROM items", limit=99)
        assert len(rows) == 10

    def test_named_params_bind(self, service):
        rows = service.execute(
            "SELECT name FROM items WHERE id = :id", params={"id": 7}
        )
        assert rows == [{"name": "item7"}]

    def test_policy_violation_raises(self, service):
        with pytest.raises(PolicyViolation):
            service.execute("DELETE FROM items")

    def test_export_uses_export_cap(self, service):
        rows = service.export("SELECT * FROM items")
        assert len(rows) == 15  # policy.export_max_rows

    def test_export_policy_violation_raises(self, service):
        with pytest.raises(PolicyViolation):
            service.export("DROP TABLE items")


class TestPreview:
    GOLDEN_SUCCESS_KEYS = {"success", "data", "row_count", "sql", "message"}
    GOLDEN_ERROR_KEYS = {"success", "data", "row_count", "sql", "error", "error_type", "suggestion"}

    def test_success_shape(self, service):
        """DE-agent contract: these exact keys must be present."""
        result = service.preview("SELECT * FROM items", limit=3)
        assert set(result.keys()) == self.GOLDEN_SUCCESS_KEYS
        assert result["success"] is True
        assert result["row_count"] == 3

    def test_policy_error_shape(self, service):
        result = service.preview("UPDATE items SET name = 'x'")
        assert set(result.keys()) == self.GOLDEN_ERROR_KEYS
        assert result["success"] is False
        assert result["error_type"] == "policy_violation"

    def test_db_error_shape(self, service):
        result = service.preview("SELECT nope FROM missing_table")
        assert result["success"] is False
        assert set(result.keys()) == self.GOLDEN_ERROR_KEYS


class TestDryRun:
    def test_valid(self, service):
        result = service.dry_run("SELECT * FROM items")
        assert result["valid"] is True
        assert "plan" in result

    def test_policy_invalid(self, service):
        result = service.dry_run("INSERT INTO items VALUES (1, 'x')")
        assert result["valid"] is False
        assert result["error_type"] == "policy_violation"

    def test_db_invalid(self, service):
        result = service.dry_run("SELECT * FROM missing_table")
        assert result["valid"] is False


class TestSqlTools:
    TOOL = SQLToolDef(
        name="items_by_id",
        description="Lookup item by id",
        statement="SELECT name FROM items WHERE id = :id",
        parameters=(ParamDef(name="id", type="integer"),),
    )

    def test_coerce_casts_types(self):
        assert coerce_args(self.TOOL, {"id": "7"}) == {"id": 7}

    def test_coerce_rejects_bad_value(self):
        with pytest.raises(ValueError):
            coerce_args(self.TOOL, {"id": "not-a-number"})

    def test_coerce_missing_required(self):
        with pytest.raises(ValueError):
            coerce_args(self.TOOL, {})

    def test_coerce_drops_unknown_args(self):
        assert "evil" not in coerce_args(self.TOOL, {"id": 1, "evil": "x"})

    def test_default_applied(self):
        tool = SQLToolDef(
            name="t", description="", statement="SELECT 1",
            parameters=(ParamDef(name="limit", type="integer", required=False, default=5),),
        )
        assert coerce_args(tool, {}) == {"limit": 5}

    def test_run_sql_tool(self, service):
        result = run_sql_tool(service, self.TOOL, {"id": 3})
        assert result["success"] is True
        assert result["data"] == [{"name": "item3"}]

    def test_run_sql_tool_invalid_args(self, service):
        result = run_sql_tool(service, self.TOOL, {})
        assert result["success"] is False
        assert result["error_type"] == "invalid_arguments"

    def test_parse_tool_defs_rejects_non_select(self):
        config = {"tools": [
            {"name": "good", "statement": "SELECT 1", "description": ""},
            {"name": "evil", "statement": "DELETE FROM items", "description": ""},
            {"statement": "SELECT 2"},  # missing name
        ]}
        tools = parse_tool_defs(config, SecurityPolicy())
        assert [t.name for t in tools] == ["good"]


class TestSourceUrlEscaping:
    def test_credentials_with_metacharacters_survive_url_build(self):
        from dbtoolbox.sources import Source, SourceConfig

        config = SourceConfig(
            db_type="greenplum",
            host="43.202.27.202",
            port=5432,
            dbname="dev",
            user="c_dev_user",
            password="p@ss$w:rd/65$321",
        )
        url = Source(config).engine.url
        assert url.host == "43.202.27.202"
        assert url.username == "c_dev_user"
        assert url.password == "p@ss$w:rd/65$321"
        assert url.database == "dev"
