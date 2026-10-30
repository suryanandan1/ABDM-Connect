"""Small in-place schema upgrades for existing SQLite databases (Alembic is planned, see docs/PRODUCTION_PLAN.md).

Upgrade 1 (HIP + HIU hospitals): consents and access requests can point to a lab report OR a
doctor consultation, so `report_id` becomes nullable and `consultation_id` is added.
SQLite cannot change a column's NOT NULL, so each table is rebuilt with the documented
procedure: create the new table, copy the rows, drop the old table, rename the new one.
The database file is copied to `<name>.bak-hip-hiu` first.

Upgrade 3 (ABHA): patients get abha_number, abha_address and abha_verified_at. These are new
nullable columns, so a plain ALTER TABLE ADD COLUMN is enough; uniqueness comes from unique indexes.
"""
import shutil
from pathlib import Path

import bcrypt
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateTable

from .database import engine
from .models import AccessRequest, Consent

TABLES = (Consent.__table__, AccessRequest.__table__)


def needs_upgrade(conn):
    tables = inspect(conn).get_table_names()
    return any(t.name in tables and "consultation_id" not in {c["name"] for c in inspect(conn).get_columns(t.name)}
               for t in TABLES)


def upgrade(eng=engine):
    """Apply pending upgrades. Safe to call on every start: does nothing when up to date."""
    from .seed import SAMPLE_PASSWORD  # imported here: seed.py imports this module

    renamed = rename_identifiers(eng, SAMPLE_PASSWORD)
    abha = add_abha_columns(eng)
    return upgrade_hip_hiu(eng) or renamed or abha


def upgrade_hip_hiu(eng):
    """Upgrade 1: consents and access requests may point to a report or a consultation."""
    with eng.connect() as conn:
        if not needs_upgrade(conn):
            return False
    path = eng.url.database
    if path and path != ":memory:" and Path(path).exists():
        backup = Path(f"{path}.bak-hip-hiu")
        if not backup.exists():
            shutil.copy2(path, backup)

    with eng.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")  # must be set outside a transaction
        conn.commit()
        try:
            with conn.begin():
                for table in TABLES:
                    old_columns = [c["name"] for c in inspect(conn).get_columns(table.name)]
                    create = str(CreateTable(table).compile(eng)).replace(
                        f"CREATE TABLE {table.name} ", f"CREATE TABLE {table.name}_new ", 1)
                    conn.execute(text(create))
                    cols = ", ".join(old_columns)
                    conn.execute(text(f"INSERT INTO {table.name}_new ({cols}) SELECT {cols} FROM {table.name}"))
                    conn.execute(text(f"DROP TABLE {table.name}"))
                    conn.execute(text(f"ALTER TABLE {table.name}_new RENAME TO {table.name}"))
                problems = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                if problems:
                    raise RuntimeError(f"foreign key check failed after upgrade: {problems[:5]}")
        finally:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            conn.commit()
    return True


# Values written by earlier versions of the app. They appear here only so old databases can be cleaned up.
LEGACY_PREFIX = "DEMO-"
LEGACY_NAME_SUFFIXES = (" (Demo Lab)", " (Demo)")
LEGACY_ADMIN_NAME = "Demo Administrator"
LEGACY_SAMPLE_PASSWORD = "Demo@1234"
LEGACY_PATIENT_COLUMN, LEGACY_FACILITY_COLUMN = "demo_id", "demo_code"


def rename_identifiers(eng, new_sample_password):
    """Upgrade 2: old identifier columns become patient_code/facility_code and old placeholder values are cleaned."""
    with eng.connect() as conn:
        tables = inspect(conn).get_table_names()
        if "patients" not in tables:
            return False
        pcols = {c["name"] for c in inspect(conn).get_columns("patients")}
        fcols = {c["name"] for c in inspect(conn).get_columns("facilities")}
    if LEGACY_PATIENT_COLUMN not in pcols and LEGACY_FACILITY_COLUMN not in fcols:
        return False
    path = eng.url.database
    if path and path != ":memory:" and Path(path).exists():
        backup = Path(f"{path}.bak-rename")
        if not backup.exists():
            shutil.copy2(path, backup)

    with eng.begin() as conn:
        if LEGACY_PATIENT_COLUMN in pcols:
            conn.execute(text(f"ALTER TABLE patients RENAME COLUMN {LEGACY_PATIENT_COLUMN} TO patient_code"))
        if LEGACY_FACILITY_COLUMN in fcols:
            conn.execute(text(f"ALTER TABLE facilities RENAME COLUMN {LEGACY_FACILITY_COLUMN} TO facility_code"))
        n = len(LEGACY_PREFIX)
        conn.execute(text(f"UPDATE patients SET patient_code = substr(patient_code, {n + 1}) WHERE patient_code LIKE :p"),
                     {"p": LEGACY_PREFIX + "%"})
        conn.execute(text(f"UPDATE facilities SET facility_code = substr(facility_code, {n + 1}) WHERE facility_code LIKE :p"),
                     {"p": LEGACY_PREFIX + "%"})
        names = {row.name for row in conn.execute(text("SELECT name FROM facilities"))}
        for fid, name in conn.execute(text("SELECT id, name FROM facilities")).all():
            for suffix in LEGACY_NAME_SUFFIXES:
                if name.endswith(suffix) and name[: -len(suffix)] not in names:
                    conn.execute(text("UPDATE facilities SET name = :n WHERE id = :i"), {"n": name[: -len(suffix)], "i": fid})
                    names.add(name[: -len(suffix)])
                    break
        conn.execute(text("UPDATE users SET full_name = 'System Administrator' WHERE full_name = :n"), {"n": LEGACY_ADMIN_NAME})
        # Accounts still on the old, publicly known sample password move to the new sample password.
        for uid, pw_hash in conn.execute(text("SELECT id, password_hash FROM users")).all():
            if bcrypt.checkpw(LEGACY_SAMPLE_PASSWORD.encode(), pw_hash.encode()):
                conn.execute(text("UPDATE users SET password_hash = :h, token_version = token_version + 1 WHERE id = :i"),
                             {"h": bcrypt.hashpw(new_sample_password.encode(), bcrypt.gensalt()).decode(), "i": uid})
    return True


ABHA_COLUMNS = {"abha_number": "VARCHAR(17)", "abha_address": "VARCHAR(100)", "abha_verified_at": "DATETIME"}


def add_abha_columns(eng):
    """Upgrade 3: ABHA identity columns on patients (same names and indexes as models.Patient creates)."""
    with eng.connect() as conn:
        if "patients" not in inspect(conn).get_table_names():
            return False
        missing = [c for c in ABHA_COLUMNS if c not in {col["name"] for col in inspect(conn).get_columns("patients")}]
    if not missing:
        return False
    with eng.begin() as conn:
        for column in missing:
            conn.execute(text(f"ALTER TABLE patients ADD COLUMN {column} {ABHA_COLUMNS[column]}"))
        for column in ("abha_number", "abha_address"):
            conn.execute(text(f"CREATE UNIQUE INDEX IF NOT EXISTS ix_patients_{column} ON patients ({column})"))
    return True
