from gestorTiempos import milisegundos_a_tiempo, tiempo_a_milisegundos, orderParticipants
from persistencia import (
    add_competition,
    add_time,
    delete_competition,
    fill_times,
    fill_times_penalitation,
    get_competition,
    get_competitions,
    get_participants,
    get_times,
)


class RallyService:
    # Devuelve nombres de competiciones disponibles.
    def list_competitions(self):
        return [c[0] for c in get_competitions()]

    # Carga datos completos de una competicion para la UI.
    def get_competition_info(self, competition_name):
        competition = get_competition(competition_name)
        if competition is None:
            return None
        competition_id, name, stages = competition
        participants = get_participants(competition_id)
        leaderboard = self._build_leaderboard(competition_id, stages, participants)
        return {
            "id": competition_id,
            "name": name,
            "stages": stages,
            "participants": participants,
            "leaderboard": leaderboard,
        }

    # Valida y crea una competicion con participantes.
    def create_competition(self, name, stages, participants):
        name = (name or "").strip()
        if not name:
            return False, "El nombre no puede estar vacio."
        if self.get_competition_info(name):
            return False, "Ya existe una competicion con ese nombre."
        if stages <= 0:
            return False, "El numero de etapas debe ser mayor que cero."
        participants = [p.strip() for p in participants if p.strip()]
        if not participants:
            return False, "Debe indicar al menos un participante."
        add_competition(name, stages, participants)
        return True, "Competicion creada."

    # Borra una competicion y sus datos asociados.
    def delete_competition(self, name):
        ok = delete_competition(name)
        if not ok:
            return False, "No existe esa competicion."
        return True, "Competicion borrada."

    # Valida y registra un tiempo en formato string.
    def add_time_str(self, competition_name, participant, stage, time_str):
        time_str = (time_str or "").strip()
        if not time_str:
            return False, "El tiempo no puede estar vacio."
        try:
            time_ms = tiempo_a_milisegundos(time_str)
        except Exception:
            return False, "Formato de tiempo invalido. Use m:ss.xxx"
        ok = add_time(competition_name, time_ms, stage, participant)
        if not ok:
            return False, "No se pudo guardar el tiempo."
        return True, "Tiempo guardado."

    # Rellena abandonos en una etapa con penalizacion base.
    def fill_missing_times(self, competition_name, stage):
        ok = fill_times(competition_name, stage)
        if not ok:
            return False, "No hay tiempos base para esa etapa."
        return True, "Abandonos rellenados."

    # Aplica penalizacion en segundos a un participante.
    def penalize(self, competition_name, stage, participant, penalty_seconds):
        if penalty_seconds <= 0:
            return False, "La penalizacion debe ser mayor que cero."
        penalty_ms = int(penalty_seconds * 1000)
        ok = fill_times_penalitation(competition_name, stage, participant, penalty_ms)
        if not ok:
            return False, "No existe tiempo para ese participante/etapa."
        return True, "Penalizacion aplicada."

    # Construye la clasificacion con tiempos por tramo.
    def _build_leaderboard(self, competition_id, stages, participants):
        leaderboard = []
        ordered = orderParticipants(participants, competition_id)
        best_time = ordered[0][1] if ordered else 0
        for rank, (participant, total_time) in enumerate(ordered, start=1):
            times_raw = [t[0] for t in get_times(participant, competition_id)]
            stage_times = []
            for i in range(stages):
                stage_times.append(times_raw[i] if i < len(times_raw) else None)
            diff = total_time - best_time if rank > 1 else 0
            leaderboard.append(
                {
                    "rank": rank,
                    "participant": participant,
                    "stage_times": stage_times,
                    "total": total_time,
                    "diff": diff,
                }
            )
        return leaderboard

    @staticmethod
    # Formatea milisegundos a string o placeholder.
    def format_time(ms):
        if ms is None:
            return "--:--.---"
        return milisegundos_a_tiempo(ms)
