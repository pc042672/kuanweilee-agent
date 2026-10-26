"""Tests for dbtoolbox.policy — SQL validation (sqlglot AST, fail-closed)."""

import pytest

from dbtoolbox.policy import SecurityPolicy, validate_sql

ALLOWED = frozenset({"report.smb_abandon_list", "data.icem_item"})
POLICY = SecurityPolicy(allowed_tables=ALLOWED)
OPEN_POLICY = SecurityPolicy()  # no allowlist configured


class TestSelectOnly:
    """Ports the SQLSafetyPlugin injection cases to the dbtoolbox layer."""

    @pytest.mark.parametrize("sql", [
        "DROP TABLE report.smb_abandon_list",
        "TRUNCATE TABLE data.icem_item",
        "DELETE FROM report.smb_abandon_list WHERE 1=1",
        "ALTER TABLE data.icem_item ADD COLUMN x INT",
        "INSERT INTO report.smb_abandon_list VALUES (1)",
        "UPDATE data.icem_item SET price = 0",
        "CREATE TABLE evil (id INT)",
        "GRANT ALL ON data.icem_item TO PUBLIC",
        "REVOKE ALL ON data.icem_item FROM PUBLIC",
        "COPY (SELECT 1) TO PROGRAM 'cat'",
        "SET TRANSACTION READ WRITE",
        "SHOW search_path",
    ])
    def test_blocks_non_select(self, sql):
        result = validate_sql(sql, OPEN_POLICY)
        assert not result.valid
        assert result.error_type in ("policy_violation", "parse_error")

    @pytest.mark.parametrize("sql", [
        "SELECT * FROM report.smb_abandon_list",
        "SELECT sitemember FROM report.smb_abandon_list WHERE is_abandont = 1",
        "WITH carts AS (SELECT * FROM report.smb_abandon_list) SELECT * FROM carts",
        "EXPLAIN SELECT * FROM report.smb_abandon_list",
        "SELECT a.* FROM report.smb_abandon_list a JOIN data.icem_item i ON 1=1",
        "SELECT * FROM report.smb_abandon_list UNION SELECT * FROM report.smb_abandon_list",
    ])
    def test_allows_reads(self, sql):
        result = validate_sql(sql, POLICY)
        assert result.valid, result.error

    def test_blocks_multi_statement(self):
        result = validate_sql("SELECT 1; DROP TABLE report.smb_abandon_list", OPEN_POLICY)
        assert not result.valid
        assert result.error_type == "policy_violation"
        assert "Multiple SQL statements" in result.error

    def test_blocks_explain_when_disallowed(self):
        policy = SecurityPolicy(allow_explain=False)
        result = validate_sql("EXPLAIN SELECT 1", policy)
        assert not result.valid

    def test_explain_inner_statement_is_validated(self):
        result = validate_sql("EXPLAIN DELETE FROM report.smb_abandon_list", OPEN_POLICY)
        assert not result.valid

    def test_blocks_empty_sql(self):
        result = validate_sql("   ;  ", OPEN_POLICY)
        assert not result.valid

    def test_parse_error_fails_closed(self):
        result = validate_sql("SELEC * FRM x %%% garbage", OPEN_POLICY)
        assert not result.valid
        assert result.error_type in ("parse_error", "policy_violation")


class TestTableAuthorization:
    def test_blocks_unauthorized_table(self):
        result = validate_sql("SELECT * FROM secret.payroll", POLICY)
        assert not result.valid
        assert result.error_type == "table_authorization"
        assert "secret.payroll" in result.error

    def test_blocks_quoted_identifier_bypass(self):
        result = validate_sql('SELECT * FROM "secret"."payroll"', POLICY)
        assert not result.valid
        assert result.error_type == "table_authorization"

    def test_allows_quoted_authorized_table(self):
        result = validate_sql('SELECT * FROM "report"."smb_abandon_list"', POLICY)
        assert result.valid, result.error

    def test_blocks_unauthorized_in_subquery(self):
        sql = "SELECT * FROM (SELECT * FROM secret.payroll) sub"
        result = validate_sql(sql, POLICY)
        assert not result.valid

    def test_blocks_union_mixing_authorized_and_not(self):
        sql = "SELECT id FROM data.icem_item UNION SELECT id FROM secret.payroll"
        result = validate_sql(sql, POLICY)
        assert not result.valid

    def test_cte_alias_not_treated_as_table(self):
        sql = "WITH tmp AS (SELECT * FROM data.icem_item) SELECT * FROM tmp"
        result = validate_sql(sql, POLICY)
        assert result.valid, result.error

    def test_information_schema_exempt(self):
        sql = "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"
        result = validate_sql(sql, POLICY)
        assert result.valid, result.error

    def test_no_allowlist_means_no_table_check(self):
        result = validate_sql("SELECT * FROM anything.goes", OPEN_POLICY)
        assert result.valid

    def test_extracted_tables_reported(self):
        result = validate_sql(
            "SELECT * FROM report.smb_abandon_list JOIN data.icem_item ON 1=1", POLICY
        )
        assert result.tables == frozenset({"report.smb_abandon_list", "data.icem_item"})


class TestRegexEscapeHatch:
    REGEX_POLICY = SecurityPolicy(allowed_tables=ALLOWED, parser="regex")

    def test_allows_select(self):
        result = validate_sql("SELECT * FROM report.smb_abandon_list", self.REGEX_POLICY)
        assert result.valid, result.error

    def test_blocks_dml(self):
        result = validate_sql("DELETE FROM report.smb_abandon_list", self.REGEX_POLICY)
        assert not result.valid

    def test_blocks_unauthorized_table(self):
        result = validate_sql("SELECT * FROM secret.payroll", self.REGEX_POLICY)
        assert not result.valid
        assert result.error_type == "table_authorization"
