"""Tests for the Db* config repositories using SQLite in-memory as stand-in."""

import pytest
from sqlalchemy import create_engine, text

from config.db_repository import DbOntologyRepository
from config.rules_repository import DbRulesRepository
from config.rules_schema import ComputeRule, RulesConfig
from config.schemas import UnifiedOntologyConfig, AttributeNode
from config.strategies_repository import DbStrategiesRepository
from config.strategies_schema import StrategiesConfig, Strategy


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine with the required tables."""
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.execute(text("""
            CREATE TABLE sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE site_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL REFERENCES sites(id),
                config_type TEXT NOT NULL,
                config_data JSON NOT NULL,
                version TEXT NOT NULL,
                updated_by INTEGER REFERENCES users(id),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(site_id, config_type)
            )
        """))
        conn.execute(text("""
            CREATE TABLE config_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                config_type TEXT NOT NULL,
                action TEXT NOT NULL,
                changed_by INTEGER NOT NULL,
                previous_data JSON,
                new_data JSON,
                diff_json JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text(
            "INSERT INTO sites (id, name, slug) VALUES (1, 'Default', 'default')"
        ))
        conn.execute(text(
            "INSERT INTO users (id, email) VALUES (1, 'admin@test.com')"
        ))
    return eng


@pytest.fixture
def repo(engine):
    return DbOntologyRepository(engine)


@pytest.fixture
def sample_config():
    return UnifiedOntologyConfig(
        version="3.0.0",
        site_id="default",
        nodes={
            "gender": AttributeNode(name="Gender", valueType="STR"),
        },
    )


class TestDbOntologyRepository:
    def test_exists_returns_false_when_empty(self, repo):
        assert repo.exists() is False

    def test_save_and_load(self, repo, sample_config):
        repo.save(sample_config)
        loaded = repo.load()
        assert loaded.version == "3.0.0"
        assert "gender" in loaded.nodes

    def test_exists_returns_true_after_save(self, repo, sample_config):
        repo.save(sample_config)
        assert repo.exists() is True

    def test_load_raises_when_not_found(self, repo):
        with pytest.raises(FileNotFoundError):
            repo.load()

    def test_save_upserts(self, repo, sample_config):
        repo.save(sample_config)
        updated = UnifiedOntologyConfig(
            version="4.0.0",
            site_id="default",
            nodes={},
        )
        repo.save(updated)
        loaded = repo.load()
        assert loaded.version == "4.0.0"

    def test_save_with_audit(self, repo, sample_config, engine):
        repo.save(sample_config, changed_by=1)

        updated = UnifiedOntologyConfig(
            version="4.0.0", site_id="default", nodes={},
        )
        repo.save(updated, changed_by=1)

        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT action, changed_by, diff_json FROM config_audit_log ORDER BY id")
            ).fetchall()

        assert len(rows) == 2
        assert rows[0][0] == "create"
        assert rows[1][0] == "update"
        assert rows[0][1] == 1
        # First save (create) should show added nodes
        import json
        diff_create = json.loads(rows[0][2])
        assert "added" in diff_create
        assert "gender" in diff_create["added"]
        # Second save (update) should show removed nodes
        diff_update = json.loads(rows[1][2])
        assert "removed" in diff_update
        assert "gender" in diff_update["removed"]

    def test_config_type_is_ontology(self, repo, sample_config, engine):
        repo.save(sample_config)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT config_type FROM site_configs WHERE site_id = 1")
            ).fetchone()
        assert row[0] == "ontology"

    def test_different_sites(self, repo, sample_config, engine):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO sites (id, name, slug) VALUES (2, 'Site 2', 'site-2')"
            ))

        repo.save(sample_config, site_id="1")

        config2 = UnifiedOntologyConfig(
            version="4.0.0", site_id="2", nodes={},
        )
        repo.save(config2, site_id="2")

        assert repo.load(site_id="1").version == "3.0.0"
        assert repo.load(site_id="2").version == "4.0.0"


class TestDbRulesRepository:
    def test_save_load_roundtrip(self, engine):
        repo = DbRulesRepository(engine)
        assert repo.exists() is False
        config = RulesConfig(
            version="1.1.0",
            computeRules=[ComputeRule(attribute="gender", type="sql", sql="SELECT 1")],
        )
        repo.save(config)
        assert repo.exists() is True
        loaded = repo.load()
        assert loaded.version == "1.1.0"
        assert loaded.computeRules[0].attribute == "gender"

    def test_save_upserts(self, engine):
        repo = DbRulesRepository(engine)
        repo.save(RulesConfig(version="1.0.0"))
        repo.save(RulesConfig(version="2.0.0"))
        assert repo.load().version == "2.0.0"

    def test_config_type_is_rules(self, engine):
        DbRulesRepository(engine).save(RulesConfig())
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT config_type FROM site_configs WHERE site_id = 1")
            ).fetchone()
        assert row[0] == "rules"


class TestDbStrategiesRepository:
    def test_save_load_roundtrip(self, engine):
        repo = DbStrategiesRepository(engine)
        assert repo.exists() is False
        config = StrategiesConfig(
            version="1.1.0",
            strategies=[Strategy(key="nba", segment="vip", template="Hi {name}")],
        )
        repo.save(config)
        assert repo.exists() is True
        loaded = repo.load()
        assert loaded.version == "1.1.0"
        assert loaded.strategies[0].key == "nba"

    def test_save_upserts(self, engine):
        repo = DbStrategiesRepository(engine)
        repo.save(StrategiesConfig(version="1.0.0"))
        repo.save(StrategiesConfig(version="2.0.0"))
        assert repo.load().version == "2.0.0"

    def test_config_type_is_strategies(self, engine):
        DbStrategiesRepository(engine).save(StrategiesConfig())
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT config_type FROM site_configs WHERE site_id = 1")
            ).fetchone()
        assert row[0] == "strategies"
