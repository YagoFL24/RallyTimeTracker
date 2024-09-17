import sqlite3

def start_connection():
    # Conectar (o crear) una base de datos local
    conexion = sqlite3.connect('datos.db')

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
    
    cursor.execute("DELETE FROM competitions WHERE competition_name = ?", (competition_name,))
    cursor.execute("DELETE FROM participants WHERE competition_id = ?", (competitionId[0][0],))
    cursor.execute("DELETE FROM times WHERE competition_id = ?", (competitionId[0][0],))
    conexion.commit()
    
    close_connection(conexion)
    
    
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

    cursor.execute("INSERT INTO times (competition_id, time, numberOfStage, participant) VALUES (?, ?, ?, ?)", (competitionId[0][0], time, numberOfStage, participant))
    conexion.commit()
    
    close_connection(conexion)
    
def fill_times(competition_name,numberOfStage):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT id FROM competitions where competition_name = ?", (competition_name,))
    competitionId = cursor.fetchall()
    
    cursor.execute("SELECT time FROM times where competition_id = ? and numberOfStage = ? ORDER BY time desc", (competitionId[0][0],numberOfStage))
    worst_time = cursor.fetchone()
    
    
    cursor.execute("SELECT participant FROM times where competition_id = ? and numberOfStage = ? ", (competitionId[0][0],numberOfStage))
    participants = [p[0] for p in cursor.fetchall()]
    
    total_participants = get_participants(competitionId[0][0])
    
    missing_participants = [p for p in total_participants if p not in participants]
    
    for participant in missing_participants:
        cursor.execute("INSERT INTO times (competition_id, time, numberOfStage, participant) VALUES (?, ?, ?, ?)", (competitionId[0][0], worst_time[0], numberOfStage, participant))
        
    conexion.commit()
    close_connection(conexion)
    
    
    
    
    
def get_times(participant, competition_id):
    conexion, cursor = start_connection()
    
    cursor.execute("SELECT time FROM times where competition_id = ? and participant = ? ORDER BY numberOfStage", (competition_id, participant))
    times = cursor.fetchall()
    
    close_connection(conexion)
    
    return times