from persistencia import *

# Convierte un string de tiempo m:ss.xxx a milisegundos.
def tiempo_a_milisegundos(tiempo_str):
    minutos, segundos = tiempo_str.split(':')
    minutos = int(minutos)
    segundos = float(segundos)
    return (minutos * 60 * 1000) + (segundos * 1000)

# Convierte milisegundos a string m:ss.xxx.
def milisegundos_a_tiempo(milisegundos):
    minutos = milisegundos // (60 * 1000)
    segundos = (milisegundos % (60 * 1000)) / 1000
    return f"{int(minutos)}:{int(segundos):02}.{(milisegundos % 1000):03d}"

# Ordena participantes por tiempo total acumulado.
def orderParticipants(participants, competition_id):
    
    participantes_tiempos = []
    
    for participant in participants:
        times = get_times(participant, competition_id)
        total_time = 0
        for time in times:
            total_time += time[0]
        participantes_tiempos.append((participant, total_time))
        
    return sorted(participantes_tiempos, key=lambda x: x[1])
