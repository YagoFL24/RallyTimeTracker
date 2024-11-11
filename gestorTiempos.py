from persistencia import *

def tiempo_a_milisegundos(tiempo_str):
    minutos, segundos = tiempo_str.split(':')
    minutos = int(minutos)
    segundos = float(segundos)
    return (minutos * 60 * 1000) + (segundos * 1000)

def milisegundos_a_tiempo(milisegundos):
    minutos = milisegundos // (60 * 1000)
    segundos = (milisegundos % (60 * 1000)) / 1000
    return f"{int(minutos)}:{int(segundos):02}.{(milisegundos % 1000):03d}"

def orderParticipants(participants, competition_id):
    
    participantes_tiempos = []
    
    for participant in participants:
        times = get_times(participant, competition_id)
        total_time = 0
        for time in times:
            total_time += time[0]
        participantes_tiempos.append((participant, total_time))
        
    return sorted(participantes_tiempos, key=lambda x: x[1])