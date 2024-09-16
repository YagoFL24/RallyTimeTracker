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

    cursor.execute("SELECT id FROM competitions where competition_name = ?", (competition_name))
    competitionId = cursor.fetchall()


    for participant in participants:
        cursor.execute("INSERT INTO participants (competition_id, participant_name) VALUES (?,?)", (competitionId[0][0], participant))
    conexion.commit
    
    close_connection()

