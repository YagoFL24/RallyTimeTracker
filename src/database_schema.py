import json
import os
import sqlite3
from pathlib import Path


SCHEMA_VERSION = 3
MAX_SQLITE_INTEGER = (2**63) - 1
MAX_NAME_LENGTH = 255
RESULT_STATUSES = ("pending", "finished", "stage_dnf", "dns", "dsq")
RALLY_STATUSES = ("active", "retired", "disqualified")
REQUIRED_OBJECTS = {
    "idx_participants_competition",
    "idx_results_participant",
    "idx_results_stage",
    "validate_result_stage_insert",
    "validate_result_stage_update",
    "idx_championship_events_competition",
    "idx_championship_event_participants_driver",
    "validate_championship_event_participant_insert",
    "validate_championship_event_participant_update",
}


class DatabaseMigrationError(RuntimeError):
    pass


CORE_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE competitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition_name TEXT NOT NULL COLLATE NOCASE UNIQUE
            CHECK(competition_name = trim(competition_name)
                  AND length(competition_name) BETWEEN 1 AND 255),
        number_of_stages INTEGER NOT NULL
            CHECK(typeof(number_of_stages) = 'integer' AND number_of_stages > 0),
        event_date TEXT
    )
    """,
    """
    CREATE TABLE participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition_id INTEGER NOT NULL,
        participant_name TEXT NOT NULL COLLATE NOCASE
            CHECK(participant_name = trim(participant_name)
                  AND length(participant_name) BETWEEN 1 AND 255),
        rally_status TEXT NOT NULL DEFAULT 'active'
            CHECK(rally_status IN ('active', 'retired', 'disqualified')),
        retired_after_stage INTEGER,
        status_before_disqualification TEXT,
        FOREIGN KEY(competition_id) REFERENCES competitions(id) ON DELETE CASCADE,
        UNIQUE(competition_id, participant_name)
    )
    """,
    """
    CREATE TABLE stage_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participant_id INTEGER NOT NULL,
        stage_number INTEGER NOT NULL
            CHECK(typeof(stage_number) = 'integer' AND stage_number > 0),
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending', 'finished', 'stage_dnf', 'dns', 'dsq')),
        time_ms INTEGER,
        previous_time_ms INTEGER,
        revision_count INTEGER NOT NULL DEFAULT 0 CHECK(revision_count >= 0),
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
        UNIQUE(participant_id, stage_number),
        CHECK(
            (status IN ('finished', 'stage_dnf')
             AND typeof(time_ms) = 'integer' AND time_ms > 0)
            OR
            (status IN ('pending', 'dns', 'dsq') AND time_ms IS NULL)
        )
    )
    """,
    """
    CREATE TABLE schema_migration_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        migrated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        source_table TEXT NOT NULL,
        source_rowid INTEGER,
        reason TEXT NOT NULL,
        legacy_data TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_participants_competition ON participants(competition_id)",
    "CREATE INDEX idx_results_participant ON stage_results(participant_id)",
    "CREATE INDEX idx_results_stage ON stage_results(stage_number)",
    """
    CREATE TRIGGER validate_result_stage_insert
    BEFORE INSERT ON stage_results
    FOR EACH ROW
    WHEN NEW.stage_number > COALESCE((
        SELECT c.number_of_stages
        FROM participants p JOIN competitions c ON c.id = p.competition_id
        WHERE p.id = NEW.participant_id
    ), 0)
    BEGIN
        SELECT RAISE(ABORT, 'stage outside competition range');
    END
    """,
    """
    CREATE TRIGGER validate_result_stage_update
    BEFORE UPDATE OF participant_id, stage_number ON stage_results
    FOR EACH ROW
    WHEN NEW.stage_number > COALESCE((
        SELECT c.number_of_stages
        FROM participants p JOIN competitions c ON c.id = p.competition_id
        WHERE p.id = NEW.participant_id
    ), 0)
    BEGIN
        SELECT RAISE(ABORT, 'stage outside competition range');
    END
    """,
)


CHAMPIONSHIP_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE drivers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        official_name TEXT NOT NULL COLLATE NOCASE UNIQUE
            CHECK(official_name = trim(official_name)
                  AND length(official_name) BETWEEN 1 AND 255),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE driver_aliases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id INTEGER NOT NULL,
        alias TEXT NOT NULL COLLATE NOCASE UNIQUE
            CHECK(alias = trim(alias) AND length(alias) BETWEEN 1 AND 255),
        FOREIGN KEY(driver_id) REFERENCES drivers(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE championships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        championship_name TEXT NOT NULL COLLATE NOCASE UNIQUE
            CHECK(championship_name = trim(championship_name)
                  AND length(championship_name) BETWEEN 1 AND 255),
        stage_win_bonus INTEGER NOT NULL DEFAULT 5
            CHECK(typeof(stage_win_bonus) = 'integer' AND stage_win_bonus >= 0),
        manually_finalized INTEGER NOT NULL DEFAULT 0
            CHECK(manually_finalized IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE championship_points (
        championship_id INTEGER NOT NULL,
        position INTEGER NOT NULL
            CHECK(typeof(position) = 'integer' AND position > 0),
        points INTEGER NOT NULL
            CHECK(typeof(points) = 'integer' AND points >= 0),
        PRIMARY KEY(championship_id, position),
        FOREIGN KEY(championship_id) REFERENCES championships(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE championship_drivers (
        championship_id INTEGER NOT NULL,
        driver_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'active'
            CHECK(status IN ('active', 'withdrawn')),
        PRIMARY KEY(championship_id, driver_id),
        FOREIGN KEY(championship_id) REFERENCES championships(id) ON DELETE CASCADE,
        FOREIGN KEY(driver_id) REFERENCES drivers(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE championship_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        championship_id INTEGER NOT NULL,
        competition_id INTEGER NOT NULL,
        event_order INTEGER NOT NULL
            CHECK(typeof(event_order) = 'integer' AND event_order > 0),
        FOREIGN KEY(championship_id) REFERENCES championships(id) ON DELETE CASCADE,
        FOREIGN KEY(competition_id) REFERENCES competitions(id) ON DELETE RESTRICT,
        UNIQUE(championship_id, competition_id),
        UNIQUE(championship_id, event_order)
    )
    """,
    """
    CREATE TABLE championship_event_participants (
        event_id INTEGER NOT NULL,
        driver_id INTEGER NOT NULL,
        participant_id INTEGER,
        participates INTEGER NOT NULL DEFAULT 1 CHECK(participates IN (0, 1)),
        PRIMARY KEY(event_id, driver_id),
        FOREIGN KEY(event_id) REFERENCES championship_events(id) ON DELETE CASCADE,
        FOREIGN KEY(driver_id) REFERENCES drivers(id) ON DELETE RESTRICT,
        FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE RESTRICT,
        UNIQUE(event_id, participant_id),
        CHECK((participates = 1 AND participant_id IS NOT NULL) OR participates = 0)
    )
    """,
    "CREATE INDEX idx_championship_events_competition "
    "ON championship_events(competition_id)",
    "CREATE INDEX idx_championship_event_participants_driver "
    "ON championship_event_participants(driver_id)",
    """
    CREATE TRIGGER validate_championship_event_participant_insert
    BEFORE INSERT ON championship_event_participants
    FOR EACH ROW
    WHEN NOT EXISTS (
        SELECT 1 FROM championship_events e
        JOIN championship_drivers d
          ON d.championship_id = e.championship_id
         AND d.driver_id = NEW.driver_id
        WHERE e.id = NEW.event_id
    ) OR (
        NEW.participant_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM championship_events e
            JOIN participants p ON p.competition_id = e.competition_id
            WHERE e.id = NEW.event_id AND p.id = NEW.participant_id
        )
    )
    BEGIN
        SELECT RAISE(ABORT, 'invalid championship event participant');
    END
    """,
    """
    CREATE TRIGGER validate_championship_event_participant_update
    BEFORE UPDATE OF event_id, driver_id, participant_id
    ON championship_event_participants
    FOR EACH ROW
    WHEN NOT EXISTS (
        SELECT 1 FROM championship_events e
        JOIN championship_drivers d
          ON d.championship_id = e.championship_id
         AND d.driver_id = NEW.driver_id
        WHERE e.id = NEW.event_id
    ) OR (
        NEW.participant_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM championship_events e
            JOIN participants p ON p.competition_id = e.competition_id
            WHERE e.id = NEW.event_id AND p.id = NEW.participant_id
        )
    )
    BEGIN
        SELECT RAISE(ABORT, 'invalid championship event participant');
    END
    """,
)


SCHEMA_STATEMENTS = CORE_SCHEMA_STATEMENTS + CHAMPIONSHIP_SCHEMA_STATEMENTS


def initialize_database(connection, database_path):
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    tables = _user_tables(connection)

    if version == SCHEMA_VERSION:
        _verify_schema(connection)
        return
    if version not in (0, 1, 2):
        raise DatabaseMigrationError(
            f"Version SQLite no soportada: {version}; maxima: {SCHEMA_VERSION}."
        )
    if not tables:
        _create_fresh_schema(connection)
        return
    if version == 2:
        if not _looks_like_v2_schema(connection):
            raise DatabaseMigrationError("El esquema SQLite v2 existente no es compatible.")
        _create_backup(connection, database_path, 2)
        _migrate_v2_schema(connection)
        _verify_schema(connection)
        return
    if _looks_like_current_schema(connection):
        _verify_schema(connection)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
        return
    if _looks_like_v2_schema(connection):
        _create_backup(connection, database_path, 2)
        _migrate_v2_schema(connection)
        _verify_schema(connection)
        return
    if not _looks_like_legacy_schema(connection):
        raise DatabaseMigrationError("El esquema SQLite existente no es compatible.")

    _create_backup(connection, database_path, 1)
    _migrate_legacy_schema(connection)
    _verify_schema(connection)


def _user_tables(connection):
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    }


def _columns(connection, table):
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _looks_like_legacy_schema(connection):
    tables = _user_tables(connection)
    return (
        {"competitions", "participants", "times"}.issubset(tables)
        and {"id", "competition_name", "numberOfStages"}.issubset(
            _columns(connection, "competitions")
        )
        and {"competition_id", "participant_name"}.issubset(
            _columns(connection, "participants")
        )
        and {"competition_id", "time", "numberOfStage", "participant"}.issubset(
            _columns(connection, "times")
        )
    )


def _looks_like_v2_schema(connection):
    tables = _user_tables(connection)
    return (
        {"competitions", "participants", "stage_results", "schema_migration_log"}
        .issubset(tables)
        and {"id", "competition_name", "number_of_stages", "event_date"}.issubset(
            _columns(connection, "competitions")
        )
        and {"id", "competition_id", "participant_name", "rally_status"}.issubset(
            _columns(connection, "participants")
        )
        and {"participant_id", "stage_number", "status", "time_ms"}.issubset(
            _columns(connection, "stage_results")
        )
    )


def _looks_like_current_schema(connection):
    tables = _user_tables(connection)
    return (
        _looks_like_v2_schema(connection)
        and {
            "drivers",
            "driver_aliases",
            "championships",
            "championship_points",
            "championship_drivers",
            "championship_events",
            "championship_event_participants",
        }.issubset(tables)
        and {"id", "official_name"}.issubset(_columns(connection, "drivers"))
        and {"id", "championship_name", "stage_win_bonus"}.issubset(
            _columns(connection, "championships")
        )
        and {"championship_id", "competition_id", "event_order"}.issubset(
            _columns(connection, "championship_events")
        )
    )


def _create_schema_objects(connection):
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)


def _create_championship_schema_objects(connection):
    for statement in CHAMPIONSHIP_SCHEMA_STATEMENTS:
        connection.execute(statement)


def _create_fresh_schema(connection):
    try:
        connection.execute("BEGIN IMMEDIATE")
        _create_schema_objects(connection)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
    except sqlite3.DatabaseError as exc:
        connection.rollback()
        raise DatabaseMigrationError("No se pudo crear el esquema SQLite.") from exc


def _create_backup(connection, database_path, version):
    database_path = Path(database_path)
    backup_path = database_path.with_name(
        f"{database_path.stem}.v{version}.backup{database_path.suffix}"
    )
    if backup_path.exists():
        return backup_path
    temp_path = backup_path.with_name(f"{backup_path.name}.{os.getpid()}.tmp")
    backup_connection = None
    try:
        backup_connection = sqlite3.connect(temp_path)
        connection.backup(backup_connection)
        backup_connection.close()
        backup_connection = None
        os.replace(temp_path, backup_path)
    except (OSError, sqlite3.DatabaseError) as exc:
        if backup_connection is not None:
            backup_connection.close()
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise DatabaseMigrationError(
            f"No se pudo crear el backup previo en {backup_path}."
        ) from exc
    return backup_path


def _migrate_v2_schema(connection):
    try:
        connection.execute("BEGIN IMMEDIATE")
        _create_championship_schema_objects(connection)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
    except sqlite3.DatabaseError as exc:
        connection.rollback()
        raise DatabaseMigrationError(
            "No se pudo migrar SQLite v2 a v3; se conserva el backup."
        ) from exc


def _migrate_legacy_schema(connection):
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("ALTER TABLE competitions RENAME TO competitions_v1")
        connection.execute("ALTER TABLE participants RENAME TO participants_v1")
        connection.execute("ALTER TABLE times RENAME TO times_v1")
        _create_schema_objects(connection)

        competition_stages = _migrate_competitions(connection)
        participant_maps = _migrate_participants(connection, competition_stages)
        _migrate_results(connection, competition_stages, participant_maps)
        _create_pending_results(connection)

        connection.execute("DROP TABLE times_v1")
        connection.execute("DROP TABLE participants_v1")
        connection.execute("DROP TABLE competitions_v1")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise DatabaseMigrationError("La migracion genero claves foraneas invalidas.")
        connection.commit()
    except (sqlite3.DatabaseError, DatabaseMigrationError) as exc:
        connection.rollback()
        if isinstance(exc, DatabaseMigrationError):
            raise
        raise DatabaseMigrationError(
            "No se pudo migrar SQLite; se conserva el backup."
        ) from exc
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def _migrate_competitions(connection):
    result = {}
    rows = connection.execute(
        "SELECT id, competition_name, numberOfStages FROM competitions_v1 ORDER BY id"
    )
    for competition_id, name, stages in rows:
        if not _valid_id(competition_id) or not _valid_name(name) or not _positive_int(stages):
            raise DatabaseMigrationError("Existe una competicion antigua no valida.")
        try:
            connection.execute(
                "INSERT INTO competitions "
                "(id, competition_name, number_of_stages) VALUES (?, ?, ?)",
                (competition_id, name.strip(), stages),
            )
        except sqlite3.IntegrityError as exc:
            raise DatabaseMigrationError("Existen competiciones antiguas duplicadas.") from exc
        result[competition_id] = stages
    return result


def _migrate_participants(connection, competition_stages):
    exact = {}
    folded = {}
    rows = connection.execute(
        "SELECT rowid, competition_id, participant_name "
        "FROM participants_v1 ORDER BY rowid"
    )
    for rowid, competition_id, name in rows:
        payload = {"competition_id": competition_id, "participant_name": name}
        if competition_id not in competition_stages or not _valid_name(name):
            _log_issue(connection, "participants", rowid, "invalid participant", payload)
            continue
        normalized = name.strip()
        key = (competition_id, normalized.casefold())
        if key in folded:
            exact[(competition_id, name)] = folded[key]
            _log_issue(connection, "participants", rowid, "duplicate merged", payload)
            continue
        cursor = connection.execute(
            "INSERT INTO participants (competition_id, participant_name) VALUES (?, ?)",
            (competition_id, normalized),
        )
        participant_id = cursor.lastrowid
        folded[key] = participant_id
        exact[(competition_id, name)] = participant_id
        exact[(competition_id, normalized)] = participant_id
    return exact, folded


def _migrate_results(connection, competition_stages, participant_maps):
    exact, folded = participant_maps
    rows = connection.execute(
        "SELECT rowid, competition_id, time, numberOfStage, participant "
        "FROM times_v1 ORDER BY rowid"
    )
    for rowid, competition_id, time_ms, stage, name in rows:
        payload = {
            "competition_id": competition_id,
            "time": time_ms,
            "numberOfStage": stage,
            "participant": name,
        }
        if (
            competition_id not in competition_stages
            or not _positive_int(time_ms)
            or time_ms > MAX_SQLITE_INTEGER
            or not _positive_int(stage)
            or stage > competition_stages[competition_id]
            or not isinstance(name, str)
        ):
            _log_issue(connection, "times", rowid, "invalid result", payload)
            continue
        participant_id = exact.get((competition_id, name))
        if participant_id is None:
            participant_id = folded.get((competition_id, name.strip().casefold()))
        if participant_id is None:
            _log_issue(connection, "times", rowid, "unknown participant", payload)
            continue
        existing = connection.execute(
            "SELECT time_ms, revision_count FROM stage_results "
            "WHERE participant_id=? AND stage_number=?",
            (participant_id, stage),
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO stage_results "
                "(participant_id, stage_number, status, time_ms) "
                "VALUES (?, ?, 'finished', ?)",
                (participant_id, stage, time_ms),
            )
        else:
            connection.execute(
                "UPDATE stage_results SET previous_time_ms=time_ms, time_ms=?, "
                "revision_count=revision_count+1, updated_at=CURRENT_TIMESTAMP "
                "WHERE participant_id=? AND stage_number=?",
                (time_ms, participant_id, stage),
            )
            payload["replaced_time_ms"] = existing[0]
            _log_issue(connection, "times", rowid, "duplicate result replaced", payload)


def _create_pending_results(connection):
    participants = connection.execute(
        "SELECT p.id, c.number_of_stages FROM participants p "
        "JOIN competitions c ON c.id=p.competition_id"
    ).fetchall()
    for participant_id, stages in participants:
        connection.executemany(
            "INSERT OR IGNORE INTO stage_results (participant_id, stage_number) "
            "VALUES (?, ?)",
            [(participant_id, stage) for stage in range(1, stages + 1)],
        )


def _log_issue(connection, source, rowid, reason, payload):
    connection.execute(
        "INSERT INTO schema_migration_log "
        "(source_table, source_rowid, reason, legacy_data) VALUES (?, ?, ?, ?)",
        (source, rowid, reason, json.dumps(payload, ensure_ascii=False, default=str)),
    )


def _verify_schema(connection):
    if not _looks_like_current_schema(connection):
        raise DatabaseMigrationError("El esquema SQLite v3 esta incompleto.")
    objects = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('index', 'trigger')"
        )
    }
    missing = REQUIRED_OBJECTS - objects
    if missing:
        raise DatabaseMigrationError(
            f"Faltan objetos de integridad SQLite: {', '.join(sorted(missing))}."
        )
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise DatabaseMigrationError("Las claves foraneas SQLite no estan activas.")
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise DatabaseMigrationError("La base contiene claves foraneas invalidas.")


def _positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _valid_id(value):
    return _positive_int(value) and value <= MAX_SQLITE_INTEGER


def _valid_name(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= MAX_NAME_LENGTH
