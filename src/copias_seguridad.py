import os
import re
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from database_schema import SCHEMA_VERSION
from persistencia import get_database_path, start_connection


MAX_STARTUP_BACKUPS = 10
BACKUP_PATTERN = re.compile(
    r"^backup_(\d{8})_(\d{6})_(\d{6})_([a-z_]+)\.db$"
)
REASONS = {"startup", "manual", "pre_import", "pre_restore"}
REASON_LABELS = {
    "startup": "Arranque",
    "manual": "Manual",
    "pre_import": "Antes de importar",
    "pre_restore": "Antes de restaurar",
}
REQUIRED_TABLES = {"competitions", "participants", "stage_results"}


class BackupError(RuntimeError):
    pass


def get_backup_directory():
    directory = Path(get_database_path()).parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _backup_info(path):
    path = Path(path)
    match = BACKUP_PATTERN.match(path.name)
    reason = match.group(4) if match else "manual"
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "reason": reason,
        "reason_label": REASON_LABELS.get(reason, reason.replace("_", " ").title()),
        "created_at": datetime.fromtimestamp(stat.st_mtime),
        "size": stat.st_size,
    }


def list_backups():
    backups = [
        _backup_info(path)
        for path in get_backup_directory().glob("backup_*.db")
        if path.is_file()
    ]
    return sorted(backups, key=lambda item: item["created_at"], reverse=True)


def create_backup(reason="manual"):
    if reason not in REASONS:
        raise BackupError("Motivo de copia de seguridad no válido.")
    now = datetime.now()
    filename = f"backup_{now:%Y%m%d_%H%M%S_%f}_{reason}.db"
    try:
        destination = get_backup_directory() / filename
        source, _cursor = start_connection()
    except (OSError, sqlite3.DatabaseError) as exc:
        raise BackupError(f"No se pudo preparar la copia: {exc}") from exc
    target = None
    try:
        target = sqlite3.connect(destination)
        source.backup(target)
        target.commit()
    except (OSError, sqlite3.DatabaseError) as exc:
        if target is not None:
            target.close()
        source.close()
        destination.unlink(missing_ok=True)
        raise BackupError(f"No se pudo crear la copia: {exc}") from exc
    target.close()
    source.close()
    try:
        validate_backup(destination)
    except BackupError:
        destination.unlink(missing_ok=True)
        raise
    if reason == "startup":
        _prune_startup_backups()
    return _backup_info(destination)


def _prune_startup_backups():
    startup_backups = [
        item for item in list_backups() if item["reason"] == "startup"
    ]
    for old_backup in startup_backups[MAX_STARTUP_BACKUPS:]:
        try:
            Path(old_backup["path"]).unlink()
        except OSError as exc:
            raise BackupError(f"No se pudo rotar la copia {old_backup['name']}.") from exc


def validate_backup(source):
    path = Path(source)
    if not path.is_file():
        raise BackupError("El archivo de copia no existe.")
    connection = None
    try:
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        integrity = connection.execute("PRAGMA quick_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise BackupError("La copia está dañada según SQLite.")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            raise BackupError(
                f"La copia usa el esquema v{version}; se necesita v{SCHEMA_VERSION}."
            )
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not REQUIRED_TABLES.issubset(tables):
            raise BackupError("La copia no contiene todas las tablas necesarias.")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise BackupError("La copia contiene referencias inválidas.")
    except BackupError:
        raise
    except (OSError, sqlite3.DatabaseError) as exc:
        raise BackupError(f"No se pudo validar la copia: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()
    return True


def restore_backup(source):
    source_path = Path(source)
    validate_backup(source_path)
    safety_backup = create_backup("pre_restore")
    database_path = Path(get_database_path())
    database_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="restore_", suffix=".db", dir=database_path.parent
    )
    os.close(handle)
    temporary_path = Path(temporary_name)
    source_connection = None
    target_connection = None
    try:
        source_connection = sqlite3.connect(
            f"file:{source_path.resolve()}?mode=ro", uri=True
        )
        target_connection = sqlite3.connect(temporary_path)
        source_connection.backup(target_connection)
        target_connection.commit()
        target_connection.close()
        target_connection = None
        source_connection.close()
        source_connection = None
        validate_backup(temporary_path)
        os.replace(temporary_path, database_path)
        connection, _cursor = start_connection()
        connection.close()
    except (BackupError, OSError, sqlite3.DatabaseError) as exc:
        raise BackupError(f"No se pudo restaurar la copia: {exc}") from exc
    finally:
        if target_connection is not None:
            target_connection.close()
        if source_connection is not None:
            source_connection.close()
        temporary_path.unlink(missing_ok=True)
    return safety_backup
