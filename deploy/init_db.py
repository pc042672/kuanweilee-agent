#!/usr/bin/env python3
"""
Database initialization and migration runner.

First deploy:
  python deploy/init_db.py \
    --database-url "postgresql+psycopg2://postgres:pass@host:5432/aicdp" \
    --admin-email "admin@example.com" --admin-name "Admin"

Schema upgrade (just run new migrations):
  python deploy/init_db.py --database-url "postgresql+psycopg2://postgres:pass@host:5432/aicdp"
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
CONFIG_DIR = PROJECT_ROOT / "config"


def _seed_schemas():
    """Pydantic models per seedable config type (validated before insert)."""
    backend_dir = str(PROJECT_ROOT / "backend")
    if backend_dir not in [str(Path(p).resolve()) for p in sys.path if p]:
        sys.path.insert(0, backend_dir)
    from config.rules_schema import RulesConfig
    from config.schemas import UnifiedOntologyConfig
    from config.strategies_schema import StrategiesConfig

    return {
        "ontology": UnifiedOntologyConfig,
        "rules": RulesConfig,
        "strategies": StrategiesConfig,
    }


def run(args):
    engine = create_engine(args.database_url)
    applied = 0
    skipped = 0

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename VARCHAR(256) PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))

        rows = conn.execute(text("SELECT filename FROM schema_migrations")).fetchall()
        done = {r[0] for r in rows}

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            name = path.name
            if name in done:
                print(f"  skip  {name}")
                skipped += 1
                continue

            print(f"  apply {name}")
            sql = path.read_text(encoding="utf-8")
            conn.execute(text(sql))
            conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:f)"),
                {"f": name},
            )
            applied += 1

    print(f"\nMigrations: {applied} applied, {skipped} skipped")

    if args.admin_email:
        _setup_admin(engine, args.admin_email, args.admin_name, args.site_name)

    if args.seed_configs:
        _seed_configs(engine)

    engine.dispose()
    print("\nDone.")


def _seed_configs(engine, site_id=1):
    """Seed site_configs from the shipped config/*.json (skips existing rows).

    Each file is validated through its Pydantic schema so a malformed config
    fails loudly at deploy time, not at first request. Bootstrap inserts
    deliberately skip the audit log (no acting user).
    """
    schemas = _seed_schemas()
    with engine.begin() as conn:
        for config_type, schema in schemas.items():
            path = CONFIG_DIR / f"{config_type}.json"
            if not path.exists():
                print(f"  seed  {config_type}: skipped (no {path.name})")
                continue
            exists = conn.execute(text(
                "SELECT 1 FROM site_configs WHERE site_id = :sid AND config_type = :ct"
            ), {"sid": site_id, "ct": config_type}).fetchone()
            if exists:
                print(f"  seed  {config_type}: skipped (already present)")
                continue
            config = schema(**json.loads(path.read_text(encoding="utf-8")))
            conn.execute(text(
                "INSERT INTO site_configs (site_id, config_type, config_data, version) "
                "VALUES (:sid, :ct, :data, :version)"
            ), {
                "sid": site_id,
                "ct": config_type,
                "data": json.dumps(config.model_dump()),
                "version": config.version,
            })
            print(f"  seed  {config_type}: inserted from {path.name}")


def _setup_admin(engine, email, name, site_name):
    with engine.begin() as conn:
        site_id = conn.execute(text("""
            INSERT INTO sites (name, slug, settings)
            VALUES (:name, 'default', '{"max_iterations": 3}')
            ON CONFLICT (slug) DO UPDATE SET name = :name
            RETURNING id
        """), {"name": site_name}).scalar()

        user_id = conn.execute(text("""
            INSERT INTO users (google_id, email, name)
            VALUES (:gid, :email, :name)
            ON CONFLICT (email) DO UPDATE SET name = :name
            RETURNING id
        """), {"gid": f"init:{email}", "email": email, "name": name}).scalar()

        conn.execute(text("""
            INSERT INTO site_members (site_id, user_id, role)
            VALUES (:sid, :uid, 'owner')
            ON CONFLICT (site_id, user_id) DO UPDATE SET role = 'owner'
        """), {"sid": site_id, "uid": user_id})

        print(f"\nAdmin: {email} (user_id={user_id}) -> site '{site_name}' (id={site_id}) as owner")


def main():
    parser = argparse.ArgumentParser(description="AI-CDP database init & migration runner")
    parser.add_argument("--database-url", required=True, help="PostgreSQL connection string")
    parser.add_argument("--admin-email", help="Admin user email (creates user + owner membership)")
    parser.add_argument("--admin-name", default="Admin", help="Admin display name")
    parser.add_argument("--site-name", default="Default Site", help="Default site name")
    parser.add_argument("--seed-configs", action="store_true",
                        help="Seed site_configs from config/*.json (ontology, rules, strategies)")
    args = parser.parse_args()

    print("Connecting to database...")
    run(args)


if __name__ == "__main__":
    main()
