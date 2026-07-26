import re

from persistencia import get_times


MAX_SQLITE_INTEGER = (2**63) - 1
TIME_PATTERN = re.compile(r"^(\d+):([0-5]\d)\.(\d{3})$")

# Convierte un string de tiempo m:ss.xxx a milisegundos.
def tiempo_a_milisegundos(tiempo_str):
    if not isinstance(tiempo_str, str):
        raise ValueError("El tiempo debe ser texto con formato m:ss.xxx")

    match = TIME_PATTERN.fullmatch(tiempo_str)
    if not match:
        raise ValueError("Formato de tiempo invalido")

    minutos, segundos, milisegundos = (int(value) for value in match.groups())
    total = (minutos * 60 * 1000) + (segundos * 1000) + milisegundos
    if total <= 0 or total > MAX_SQLITE_INTEGER:
        raise ValueError("El tiempo debe ser positivo y valido")
    return total

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
