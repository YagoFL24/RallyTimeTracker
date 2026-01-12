import os
import shutil
import sqlite3
import sys


def _get_db_path():
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(appdata, "RallyTimeTracker")
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "datos.db")

        if not os.path.exists(db_path):
            bundled_dir = getattr(sys, "_MEIPASS", None) or os.path.dirname(sys.executable)
            bundled_db = os.path.join(bundled_dir, "datos.db")
            if os.path.exists(bundled_db):
                shutil.copy2(bundled_db, db_path)
        return db_path

    return "datos.db"

def start_connection():
    # Conectar (o crear) una base de datos local
    conexion = sqlite3.connect(_get_db_path())

    # Crear un cursor para ejecutar comandos SQL
    cursor = conexion.cursor()
    
    return conexion, cursor

def close_connection(conexion):
    # Cerrar la conexión
    conexion.close()

def add_competition(competition_name, numberOfStages, participants):
    conexion, cursor = start_connection()

    cursor.execute("INSERT INTO competitions (competition_name, numberOfStages) VALUES (?, ?)", (competition_name, numberOfStages))
    conexion.commit()

    cursor.execute("SELECT id FROM competitions where competition_name = ?", (competition_name,))
    competitionId = cursor.fetchall()


    for participant in participants:
        cursor.execute("INSERT INTO participants (competition_id, participant_name) VALUES (?,?)", (competitionId[0][0], participant))
    conexion.commit()
    
    close_connection(conexion)
    
    
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
    
    
def get_competitions():
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT competition_name FROM competitions ")
    competitions = cursor.fetchall()
    
    close_connection(conexion)
    
    return competitions

def get_competition(competition_name):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT * FROM competitions where competition_name = ?", (competition_name,))
    competition = cursor.fetchall()
    
    close_connection(conexion)
    
    if not competition:
        return None
    return competition[0]

def get_participants(competition_id):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT participant_name FROM participants where competition_id = ?", (competition_id,))
    participants = [p[0] for p in cursor.fetchall()]
    
    close_connection(conexion)
    
    return participants



def add_time(competition_name, time, numberOfStage, participant):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT id FROM competitions where competition_name = ?", (competition_name,))
    competitionId = cursor.fetchall()

    if not competitionId:
        close_connection(conexion)
        return False

    cursor.execute("INSERT INTO times (competition_id, time, numberOfStage, participant) VALUES (?, ?, ?, ?)", (competitionId[0][0], time, numberOfStage, participant))
    conexion.commit()
    
    close_connection(conexion)
    return True
    
def fill_times(competition_name,numberOfStage):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT id FROM competitions where competition_name = ?", (competition_name,))
    competitionId = cursor.fetchall()
    
    if not competitionId:
        close_connection(conexion)
        return False

    cursor.execute("SELECT time FROM times where competition_id = ? and numberOfStage = ? ORDER BY time desc", (competitionId[0][0],numberOfStage))
    worst_time = cursor.fetchone()
    
    if worst_time is None:
        close_connection(conexion)
        return False
    
    
    cursor.execute("SELECT participant FROM times where competition_id = ? and numberOfStage = ? ", (competitionId[0][0],numberOfStage))
    participants = [p[0] for p in cursor.fetchall()]
    
    total_participants = get_participants(competitionId[0][0])
    
    missing_participants = [p for p in total_participants if p not in participants]
    
    for participant in missing_participants:
        cursor.execute("INSERT INTO times (competition_id, time, numberOfStage, participant) VALUES (?, ?, ?, ?)", (competitionId[0][0], worst_time[0] + 10000, numberOfStage, participant))
        
    conexion.commit()
    close_connection(conexion)
    return True
    
def fill_times_penalitation(competition_name, numberOfStage, participant, penalty_ms):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT id FROM competitions where competition_name = ?", (competition_name,))
    competitionId = cursor.fetchall()
    
    if not competitionId:
        close_connection(conexion)
        return False

    cursor.execute("SELECT time FROM times where competition_id = ? and numberOfStage = ? AND participant = ?", (competitionId[0][0],numberOfStage,participant))
    time = cursor.fetchone()
    if time is None:
        close_connection(conexion)
        return False
    time = time[0] + penalty_ms
    
    
    cursor.execute(" UPDATE times SET time = ? WHERE competition_id = ? AND numberOfStage = ? AND participant = ?", (time,competitionId[0][0], numberOfStage, participant))

        
    conexion.commit()
    close_connection(conexion)
    return True
    
    
    
    
    
def get_times(participant, competition_id):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT time FROM times where competition_id = ? and participant = ? ORDER BY numberOfStage", (competition_id, participant))
    times = cursor.fetchall()
    
    close_connection(conexion)
    
    return times
