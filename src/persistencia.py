import os
import sqlite3
import sys

from database_schema import MAX_NAME_LENGTH, MAX_SQLITE_INTEGER, initialize_database


def _is_strict_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_sqlite_int(value):
    return _is_strict_int(value) and 0 < value <= MAX_SQLITE_INTEGER


def _get_db_path():
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(appdata, "RallyTimeTracker")
    else:
        data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "datos.db")


def start_connection():
    database_path = _get_db_path()
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        initialize_database(connection, database_path)
    except Exception:
        connection.close()
        raise
    return connection, connection.cursor()


def close_connection(connection):
    connection.close()


def _competition_for_stage(cursor, competition_name, stage):
    if not isinstance(competition_name, str) or not competition_name.strip():
        return None
    if not _is_strict_int(stage):
        return None
    cursor.execute(
        "SELECT id, competition_name, number_of_stages, event_date "
        "FROM competitions WHERE competition_name=?",
        (competition_name.strip(),),
    )
    competition = cursor.fetchone()
    if competition is None or not 1 <= stage <= competition["number_of_stages"]:
        return None
    return competition


def _participant(cursor, competition_id, participant_name):
    if not isinstance(participant_name, str) or not participant_name.strip():
        return None
    cursor.execute(
        "SELECT * FROM participants WHERE competition_id=? AND participant_name=?",
        (competition_id, participant_name.strip()),
    )
    return cursor.fetchone()


def add_competition(competition_name, numberOfStages, participants, event_date=None):
    if not isinstance(competition_name, str) or not competition_name.strip():
        return False
    competition_name = competition_name.strip()
    if len(competition_name) > MAX_NAME_LENGTH:
        return False
    if not _is_positive_sqlite_int(numberOfStages):
        return False
    if not isinstance(participants, (list, tuple)) or not participants:
        return False
    normalized = []
    keys = set()
    for participant in participants:
        if not isinstance(participant, str) or not participant.strip():
            return False
        name = participant.strip()
        if len(name) > MAX_NAME_LENGTH or name.casefold() in keys:
            return False
        keys.add(name.casefold())
        normalized.append(name)

    connection, cursor = start_connection()
    try:
        cursor.execute(
            "INSERT INTO competitions "
            "(competition_name, number_of_stages, event_date) VALUES (?, ?, ?)",
            (competition_name, numberOfStages, event_date),
        )
        competition_id = cursor.lastrowid
        for name in normalized:
            cursor.execute(
                "INSERT INTO participants (competition_id, participant_name) "
                "VALUES (?, ?)",
                (competition_id, name),
            )
            participant_id = cursor.lastrowid
            cursor.executemany(
                "INSERT INTO stage_results (participant_id, stage_number) VALUES (?, ?)",
                [(participant_id, stage) for stage in range(1, numberOfStages + 1)],
            )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        connection.close()
        return False
    connection.close()
    return True


def delete_competition(competition_name):
    if not isinstance(competition_name, str) or not competition_name.strip():
        return False
    connection, cursor = start_connection()
    cursor.execute(
        "DELETE FROM competitions WHERE competition_name=?", (competition_name.strip(),)
    )
    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


def get_competitions():
    connection, cursor = start_connection()
    cursor.execute("SELECT competition_name FROM competitions ORDER BY competition_name")
    rows = [tuple(row) for row in cursor.fetchall()]
    connection.close()
    return rows


def get_competition(competition_name):
    if not isinstance(competition_name, str):
        return None
    connection, cursor = start_connection()
    cursor.execute(
        "SELECT id, competition_name, number_of_stages, event_date FROM competitions "
        "WHERE competition_name=?",
        (competition_name.strip(),),
    )
    row = cursor.fetchone()
    connection.close()
    return tuple(row) if row else None


def get_participants(competition_id):
    return [row["participant_name"] for row in get_participant_records(competition_id)]


def get_participant_records(competition_id):
    connection, cursor = start_connection()
    cursor.execute(
        "SELECT id, participant_name, rally_status, retired_after_stage, "
        "status_before_disqualification "
        "FROM participants WHERE competition_id=? ORDER BY id",
        (competition_id,),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return rows


def import_competition_snapshot(snapshot):
    """Inserta una competición ya validada en una única transacción."""
    connection, cursor = start_connection()
    try:
        cursor.execute(
            "INSERT INTO competitions "
            "(competition_name, number_of_stages, event_date) VALUES (?, ?, ?)",
            (snapshot["name"], snapshot["stages"], snapshot.get("event_date")),
        )
        competition_id = cursor.lastrowid
        for participant in snapshot["participants"]:
            cursor.execute(
                "INSERT INTO participants "
                "(competition_id, participant_name, rally_status, "
                "retired_after_stage, status_before_disqualification) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    competition_id,
                    participant["name"],
                    participant["rally_status"],
                    participant.get("retired_after_stage"),
                    participant.get("status_before_disqualification"),
                ),
            )
            participant_id = cursor.lastrowid
            cursor.executemany(
                "INSERT INTO stage_results "
                "(participant_id, stage_number, status, time_ms, "
                "previous_time_ms, revision_count, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        participant_id,
                        result["stage_number"],
                        result["status"],
                        result.get("time_ms"),
                        result.get("previous_time_ms"),
                        result["revision_count"],
                        result["updated_at"],
                    )
                    for result in participant["results"]
                ],
            )
        connection.commit()
    except (KeyError, OverflowError, TypeError, sqlite3.IntegrityError):
        connection.rollback()
        connection.close()
        return False
    connection.close()
    return True


def _record_revision(cursor, participant_id, stage, status, time_ms):
    current = cursor.execute(
        "SELECT status, time_ms, previous_time_ms, revision_count FROM stage_results "
        "WHERE participant_id=? AND stage_number=?",
        (participant_id, stage),
    ).fetchone()
    if current is None:
        return False
    changed = current["status"] != status or current["time_ms"] != time_ms
    revision = current["revision_count"] + (1 if changed and current["status"] != "pending" else 0)
    previous = None
    if changed:
        previous = (
            current["time_ms"]
            if current["time_ms"] is not None
            else current["previous_time_ms"]
        )
    cursor.execute(
        "UPDATE stage_results SET status=?, time_ms=?, previous_time_ms=?, "
        "revision_count=?, updated_at=CURRENT_TIMESTAMP "
        "WHERE participant_id=? AND stage_number=?",
        (status, time_ms, previous, revision, participant_id, stage),
    )
    return True


def add_time(competition_name, time, numberOfStage, participant):
    if not _is_positive_sqlite_int(time):
        return False
    connection, cursor = start_connection()
    competition = _competition_for_stage(cursor, competition_name, numberOfStage)
    person = _participant(cursor, competition["id"], participant) if competition else None
    if person is None or person["rally_status"] == "disqualified":
        connection.close()
        return False
    if (
        person["rally_status"] == "retired"
        and numberOfStage > person["retired_after_stage"]
    ):
        connection.close()
        return False
    try:
        ok = _record_revision(cursor, person["id"], numberOfStage, "finished", time)
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        ok = False
    connection.close()
    return ok


def get_stage_results(competition_id, participant=None):
    connection, cursor = start_connection()
    sql = (
        "SELECT r.stage_number, r.status, r.time_ms, r.previous_time_ms, "
        "r.revision_count, r.updated_at, p.participant_name, p.rally_status, "
        "p.retired_after_stage FROM stage_results r "
        "JOIN participants p ON p.id=r.participant_id WHERE p.competition_id=?"
    )
    params = [competition_id]
    if participant is not None:
        sql += " AND p.participant_name=?"
        params.append(participant.strip())
    sql += " ORDER BY p.id, r.stage_number"
    cursor.execute(sql, params)
    rows = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return rows


def get_times(participant, competition_id):
    rows = get_stage_results(competition_id, participant)
    return [(row["time_ms"],) for row in rows if row["time_ms"] is not None]


def set_stage_status(competition_name, stage, participant, status, time_ms=None):
    if status not in {"pending", "finished", "stage_dnf", "dns", "dsq"}:
        return False
    if status == "finished" and not _is_positive_sqlite_int(time_ms):
        return False
    connection, cursor = start_connection()
    competition = _competition_for_stage(cursor, competition_name, stage)
    person = _participant(cursor, competition["id"], participant) if competition else None
    if person is None:
        connection.close()
        return False
    if (
        person["rally_status"] == "retired"
        and stage > person["retired_after_stage"]
    ):
        connection.close()
        return False
    if status == "stage_dnf" and time_ms is None:
        worst = cursor.execute(
            "SELECT MAX(r.time_ms) FROM stage_results r JOIN participants p "
            "ON p.id=r.participant_id WHERE p.competition_id=? "
            "AND r.stage_number=? AND r.time_ms IS NOT NULL",
            (competition["id"], stage),
        ).fetchone()[0]
        if not _is_positive_sqlite_int(worst) or worst > MAX_SQLITE_INTEGER - 10_000:
            connection.close()
            return False
        time_ms = worst + 10_000
    elif status not in {"stage_dnf", "finished"}:
        time_ms = None
    try:
        ok = _record_revision(cursor, person["id"], stage, status, time_ms)
        if status == "dsq":
            previous = person["rally_status"]
            if previous != "disqualified":
                cursor.execute(
                    "UPDATE participants SET status_before_disqualification=?, "
                    "rally_status='disqualified' WHERE id=?",
                    (previous, person["id"]),
                )
        elif person["rally_status"] == "disqualified":
            remaining = cursor.execute(
                "SELECT COUNT(*) FROM stage_results WHERE participant_id=? "
                "AND status='dsq' AND stage_number<>?",
                (person["id"], stage),
            ).fetchone()[0]
            if remaining == 0:
                restored = person["status_before_disqualification"] or "active"
                cursor.execute(
                    "UPDATE participants SET rally_status=?, "
                    "status_before_disqualification=NULL WHERE id=?",
                    (restored, person["id"]),
                )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        ok = False
    connection.close()
    return ok


def fill_times(competition_name, numberOfStage):
    connection, cursor = start_connection()
    competition = _competition_for_stage(cursor, competition_name, numberOfStage)
    if competition is None:
        connection.close()
        return False
    worst = cursor.execute(
        "SELECT MAX(r.time_ms) FROM stage_results r JOIN participants p "
        "ON p.id=r.participant_id WHERE p.competition_id=? "
        "AND r.stage_number=? AND r.time_ms IS NOT NULL",
        (competition["id"], numberOfStage),
    ).fetchone()[0]
    if not _is_positive_sqlite_int(worst) or worst > MAX_SQLITE_INTEGER - 10_000:
        connection.close()
        return False
    abandonment = worst + 10_000
    cursor.execute(
        "UPDATE stage_results SET status='stage_dnf', time_ms=?, "
        "updated_at=CURRENT_TIMESTAMP WHERE stage_number=? AND status='pending' "
        "AND participant_id IN (SELECT id FROM participants "
        "WHERE competition_id=? AND rally_status='active')",
        (abandonment, numberOfStage, competition["id"]),
    )
    connection.commit()
    connection.close()
    return True


def fill_times_penalitation(competition_name, numberOfStage, participant, penalty_ms):
    if not _is_positive_sqlite_int(penalty_ms):
        return False
    connection, cursor = start_connection()
    competition = _competition_for_stage(cursor, competition_name, numberOfStage)
    person = _participant(cursor, competition["id"], participant) if competition else None
    if person is None:
        connection.close()
        return False
    result = cursor.execute(
        "SELECT status, time_ms FROM stage_results WHERE participant_id=? "
        "AND stage_number=?",
        (person["id"], numberOfStage),
    ).fetchone()
    if (
        result is None
        or result["status"] not in {"finished", "stage_dnf"}
        or result["time_ms"] > MAX_SQLITE_INTEGER - penalty_ms
    ):
        connection.close()
        return False
    ok = _record_revision(
        cursor,
        person["id"],
        numberOfStage,
        result["status"],
        result["time_ms"] + penalty_ms,
    )
    connection.commit()
    connection.close()
    return ok


def retire_participant(competition_name, stage, participant, completed_stage):
    connection, cursor = start_connection()
    competition = _competition_for_stage(cursor, competition_name, stage)
    person = _participant(cursor, competition["id"], participant) if competition else None
    if person is None or person["rally_status"] == "disqualified":
        connection.close()
        return False
    if completed_stage:
        result = cursor.execute(
            "SELECT status FROM stage_results WHERE participant_id=? AND stage_number=?",
            (person["id"], stage),
        ).fetchone()
        if result is None or result["status"] not in {"finished", "stage_dnf"}:
            connection.close()
            return False
    connection.close()
    if not completed_stage and not set_stage_status(
        competition_name, stage, participant, "stage_dnf"
    ):
        return False
    connection, cursor = start_connection()
    person = _participant(cursor, competition["id"], participant)
    cursor.execute(
        "UPDATE participants SET rally_status='retired', retired_after_stage=? "
        "WHERE id=?",
        (stage, person["id"]),
    )
    connection.commit()
    connection.close()
    return True


def reactivate_participant(competition_name, participant):
    connection, cursor = start_connection()
    cursor.execute(
        "SELECT p.id FROM participants p JOIN competitions c "
        "ON c.id=p.competition_id WHERE c.competition_name=? "
        "AND p.participant_name=? AND p.rally_status='retired'",
        (competition_name.strip(), participant.strip()),
    )
    row = cursor.fetchone()
    if row is None:
        connection.close()
        return False
    cursor.execute(
        "UPDATE participants SET rally_status='active', retired_after_stage=NULL "
        "WHERE id=?",
        (row["id"],),
    )
    connection.commit()
    connection.close()
    return True


def get_stage_counts(competition_id):
    connection, cursor = start_connection()
    cursor.execute(
        "SELECT r.stage_number, SUM(CASE WHEN r.status <> 'pending' THEN 1 ELSE 0 END) "
        "FROM stage_results r JOIN participants p ON p.id=r.participant_id "
        "WHERE p.competition_id=? AND p.rally_status='active' GROUP BY r.stage_number "
        "HAVING SUM(CASE WHEN r.status <> 'pending' THEN 1 ELSE 0 END) > 0",
        (competition_id,),
    )
    counts = {row[0]: row[1] for row in cursor.fetchall()}
    connection.close()
    return counts
