import os
import sqlite3
import sys


MAX_SQLITE_INTEGER = (2**63) - 1
MAX_NAME_LENGTH = 255


def _is_strict_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_sqlite_int(value):
    return _is_strict_int(value) and 0 < value <= MAX_SQLITE_INTEGER


def _get_competition_for_stage(cursor, competition_name, number_of_stage):
    if not isinstance(competition_name, str) or not competition_name.strip():
        return None
    if not _is_strict_int(number_of_stage):
        return None

    cursor.execute(
        "SELECT id, competition_name, numberOfStages FROM competitions "
        "WHERE competition_name = ?",
        (competition_name.strip(),),
    )
    competition = cursor.fetchone()
    if competition is None or not _is_strict_int(competition[2]):
        return None
    if not 1 <= number_of_stage <= competition[2]:
        return None
    return competition


def _participant_exists(cursor, competition_id, participant):
    if not isinstance(participant, str) or not participant.strip():
        return False
    cursor.execute(
        "SELECT 1 FROM participants WHERE competition_id = ? AND participant_name = ?",
        (competition_id, participant.strip()),
    )
    return cursor.fetchone() is not None


# Resuelve la ruta de la base de datos segun entorno.
def _get_db_path():
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(appdata, "RallyTimeTracker")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "datos.db")

    data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "datos.db")


# Crea tablas base si no existen.
def _initialize_schema(conexion):
    cursor = conexion.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS competitions (id INTEGER PRIMARY KEY AUTOINCREMENT, competition_name varchar2(255) UNIQUE, numberOfStages int)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS participants (competition_id int, participant_name varchar2(255), foreign key(competition_id) references competiciones(id))"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS times (competition_id int, time int, numberOfStage int, participant varchar2(255), foreign key(competition_id) references competitions(id))"
    )
    conexion.commit()

# Abre conexion y cursor a SQLite.
def start_connection():
    # Conectar (o crear) una base de datos local
    conexion = sqlite3.connect(_get_db_path())
    _initialize_schema(conexion)

    # Crear un cursor para ejecutar comandos SQL
    cursor = conexion.cursor()
    
    return conexion, cursor

# Cierra conexion activa.
def close_connection(conexion):
    # Cerrar la conexión
    conexion.close()

# Inserta una competicion y sus participantes.
def add_competition(competition_name, numberOfStages, participants):
    if not isinstance(competition_name, str) or not competition_name.strip():
        return False
    competition_name = competition_name.strip()
    if len(competition_name) > MAX_NAME_LENGTH:
        return False
    if not _is_strict_int(numberOfStages) or numberOfStages <= 0:
        return False
    if not isinstance(participants, (list, tuple)) or not participants:
        return False

    normalized_participants = []
    participant_keys = set()
    for participant in participants:
        if not isinstance(participant, str) or not participant.strip():
            return False
        participant = participant.strip()
        if len(participant) > MAX_NAME_LENGTH:
            return False
        participant_key = participant.casefold()
        if participant_key in participant_keys:
            return False
        participant_keys.add(participant_key)
        normalized_participants.append(participant)

    conexion, cursor = start_connection()
    try:
        cursor.execute(
            "INSERT INTO competitions (competition_name, numberOfStages) VALUES (?, ?)",
            (competition_name, numberOfStages),
        )
        competition_id = cursor.lastrowid
        cursor.executemany(
            "INSERT INTO participants (competition_id, participant_name) VALUES (?, ?)",
            [(competition_id, participant) for participant in normalized_participants],
        )
        conexion.commit()
    except sqlite3.IntegrityError:
        conexion.rollback()
        close_connection(conexion)
        return False

    close_connection(conexion)
    return True
    
    
# Elimina una competicion y sus datos asociados.
def delete_competition(competition_name):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT id FROM competitions where competition_name = ?", (competition_name,))
    competitionId = cursor.fetchall()
    
    if not competitionId:
        close_connection(conexion)
        return False

    cursor.execute("DELETE FROM competitions WHERE competition_name = ?", (competition_name,))
    cursor.execute("DELETE FROM participants WHERE competition_id = ?", (competitionId[0][0],))
    cursor.execute("DELETE FROM times WHERE competition_id = ?", (competitionId[0][0],))
    conexion.commit()
    
    close_connection(conexion)
    return True
    
    
# Devuelve lista de competiciones.
def get_competitions():
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT competition_name FROM competitions ")
    competitions = cursor.fetchall()
    
    close_connection(conexion)
    
    return competitions

# Devuelve una competicion por nombre.
def get_competition(competition_name):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT * FROM competitions where competition_name = ?", (competition_name,))
    competition = cursor.fetchall()
    
    close_connection(conexion)
    
    if not competition:
        return None
    return competition[0]

# Devuelve participantes de una competicion.
def get_participants(competition_id):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT participant_name FROM participants where competition_id = ?", (competition_id,))
    participants = [p[0] for p in cursor.fetchall()]
    
    close_connection(conexion)
    
    return participants



# Inserta o actualiza un tiempo de participante.
def add_time(competition_name, time, numberOfStage, participant):
    if not _is_positive_sqlite_int(time):
        return False

    conexion, cursor = start_connection()
    competition = _get_competition_for_stage(cursor, competition_name, numberOfStage)
    if competition is None or not _participant_exists(cursor, competition[0], participant):
        close_connection(conexion)
        return False

    participant = participant.strip()
    cursor.execute(
        "SELECT 1 FROM times WHERE competition_id = ? AND numberOfStage = ? "
        "AND participant = ?",
        (competition[0], numberOfStage, participant),
    )
    existing_time = cursor.fetchone()

    if existing_time is not None:
        cursor.execute(
            "UPDATE times SET time = ? WHERE competition_id = ? "
            "AND numberOfStage = ? AND participant = ?",
            (time, competition[0], numberOfStage, participant),
        )
    else:
        cursor.execute(
            "INSERT INTO times (competition_id, time, numberOfStage, participant) "
            "VALUES (?, ?, ?, ?)",
            (competition[0], time, numberOfStage, participant),
        )
    conexion.commit()

    close_connection(conexion)
    return True

# Rellena abandonos con penalizacion base.
def fill_times(competition_name, numberOfStage):
    conexion, cursor = start_connection()
    competition = _get_competition_for_stage(cursor, competition_name, numberOfStage)
    if competition is None:
        close_connection(conexion)
        return False

    cursor.execute(
        "SELECT time FROM times WHERE competition_id = ? AND numberOfStage = ? "
        "ORDER BY time DESC",
        (competition[0], numberOfStage),
    )
    worst_time = cursor.fetchone()
    if worst_time is None or not _is_positive_sqlite_int(worst_time[0]):
        close_connection(conexion)
        return False

    abandonment_time = worst_time[0] + 10000
    if abandonment_time > MAX_SQLITE_INTEGER:
        close_connection(conexion)
        return False

    cursor.execute(
        "SELECT participant FROM times WHERE competition_id = ? AND numberOfStage = ?",
        (competition[0], numberOfStage),
    )
    participants = [p[0] for p in cursor.fetchall()]

    cursor.execute(
        "SELECT participant_name FROM participants WHERE competition_id = ?",
        (competition[0],),
    )
    total_participants = [p[0] for p in cursor.fetchall()]
    missing_participants = [p for p in total_participants if p not in participants]

    for participant in missing_participants:
        cursor.execute(
            "INSERT INTO times (competition_id, time, numberOfStage, participant) "
            "VALUES (?, ?, ?, ?)",
            (competition[0], abandonment_time, numberOfStage, participant),
        )

    conexion.commit()
    close_connection(conexion)
    return True

# Aplica penalizacion en milisegundos.
def fill_times_penalitation(competition_name, numberOfStage, participant, penalty_ms):
    if not _is_positive_sqlite_int(penalty_ms):
        return False

    conexion, cursor = start_connection()
    competition = _get_competition_for_stage(cursor, competition_name, numberOfStage)
    if competition is None or not _participant_exists(cursor, competition[0], participant):
        close_connection(conexion)
        return False

    participant = participant.strip()
    cursor.execute(
        "SELECT time FROM times WHERE competition_id = ? AND numberOfStage = ? "
        "AND participant = ?",
        (competition[0], numberOfStage, participant),
    )
    time = cursor.fetchone()
    if time is None or not _is_positive_sqlite_int(time[0]):
        close_connection(conexion)
        return False

    penalized_time = time[0] + penalty_ms
    if penalized_time > MAX_SQLITE_INTEGER:
        close_connection(conexion)
        return False

    cursor.execute(
        "UPDATE times SET time = ? WHERE competition_id = ? "
        "AND numberOfStage = ? AND participant = ?",
        (penalized_time, competition[0], numberOfStage, participant),
    )

    conexion.commit()
    close_connection(conexion)
    return True
    
    
    
    
    
# Obtiene tiempos por participante y etapa.
def get_times(participant, competition_id):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT time FROM times where competition_id = ? and participant = ? ORDER BY numberOfStage", (competition_id, participant))
    times = cursor.fetchall()
    
    close_connection(conexion)
    
    return times

# Devuelve conteos de tiempos por etapa.
def get_stage_counts(competition_id):
    conexion, cursor = start_connection()

    cursor.execute(
        "SELECT numberOfStage, COUNT(*) FROM times WHERE competition_id = ? GROUP BY numberOfStage",
        (competition_id,),
    )
    counts = {row[0]: row[1] for row in cursor.fetchall()}

    close_connection(conexion)
    return counts
