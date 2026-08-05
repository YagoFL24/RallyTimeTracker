import re

from persistencia import get_times


MAX_SQLITE_INTEGER = (2**63) - 1
COLON_TIME_PATTERN = re.compile(r"^(\d+):([0-5]\d)\.(\d{0,3})$")
COMPACT_TIME_PATTERN = re.compile(r"^(\d+)\.(\d{0,3})$")


# Separa un tiempo tradicional o compacto en minutos, segundos y milisegundos.
def _time_components(time_text):
    colon_match = COLON_TIME_PATTERN.fullmatch(time_text)
    if colon_match:
        minutes_text, seconds_text, milliseconds_text = colon_match.groups()
    else:
        compact_match = COMPACT_TIME_PATTERN.fullmatch(time_text)
        if not compact_match:
            raise ValueError("Formato de tiempo invalido")
        whole_seconds_text, milliseconds_text = compact_match.groups()
        if len(whole_seconds_text) <= 2:
            minutes_text = "0"
            seconds_text = whole_seconds_text
        else:
            minutes_text = whole_seconds_text[:-2]
            seconds_text = whole_seconds_text[-2:]

    minutes = int(minutes_text)
    seconds = int(seconds_text)
    if seconds > 59:
        raise ValueError("Los segundos deben estar entre 00 y 59")
    milliseconds = int(milliseconds_text.ljust(3, "0") or "0")
    return minutes, seconds, milliseconds


# Convierte un string m:ss.xxx o compacto mmss.xxx a milisegundos.
def tiempo_a_milisegundos(tiempo_str):
    if not isinstance(tiempo_str, str):
        raise ValueError("El tiempo debe ser texto")

    minutos, segundos, milisegundos = _time_components(tiempo_str)
    total = (minutos * 60 * 1000) + (segundos * 1000) + milisegundos
    if total <= 0 or total > MAX_SQLITE_INTEGER:
        raise ValueError("El tiempo debe ser positivo y valido")
    return total


# Devuelve cualquier entrada valida en el formato visual canonico m:ss.xxx.
def normalizar_tiempo(tiempo_str):
    return milisegundos_a_tiempo(tiempo_a_milisegundos(tiempo_str))

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
