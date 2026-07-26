from decimal import Decimal, InvalidOperation

from gestorTiempos import (
    MAX_SQLITE_INTEGER,
    milisegundos_a_tiempo,
    orderParticipants,
    tiempo_a_milisegundos,
)
from persistencia import (
    add_competition,
    add_time,
    delete_competition,
    fill_times,
    fill_times_penalitation,
    get_competition,
    get_competitions,
    get_participants,
    get_stage_counts,
    get_times,
)


class RallyService:
    MAX_NAME_LENGTH = 255

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
        if not isinstance(name, str):
            return False, "El nombre no puede estar vacio."
        name = name.strip()
        if not name:
            return False, "El nombre no puede estar vacio."
        if len(name) > self.MAX_NAME_LENGTH:
            return False, f"El nombre no puede superar {self.MAX_NAME_LENGTH} caracteres."
        if self.get_competition_info(name):
            return False, "Ya existe una competicion con ese nombre."
        if not self._is_strict_int(stages):
            return False, "El numero de etapas debe ser un entero."
        if stages <= 0:
            return False, "El numero de etapas debe ser mayor que cero."
        if not isinstance(participants, (list, tuple)) or not participants:
            return False, "Debe indicar al menos un participante."

        normalized_participants = []
        participant_keys = set()
        for participant in participants:
            if not isinstance(participant, str) or not participant.strip():
                return False, "Los participantes no pueden estar vacios."
            participant = participant.strip()
            if len(participant) > self.MAX_NAME_LENGTH:
                return False, (
                    f"El nombre de un participante no puede superar "
                    f"{self.MAX_NAME_LENGTH} caracteres."
                )
            participant_key = participant.casefold()
            if participant_key in participant_keys:
                return False, "Los participantes no pueden repetirse."
            participant_keys.add(participant_key)
            normalized_participants.append(participant)

        if not add_competition(name, stages, normalized_participants):
            return False, "No se pudo crear la competicion."
        return True, "Competicion creada."

    # Borra una competicion y sus datos asociados.
    def delete_competition(self, name):
        ok = delete_competition(name)
        if not ok:
            return False, "No existe esa competicion."
        return True, "Competicion borrada."

    # Valida y registra un tiempo en formato string.
    def add_time_str(self, competition_name, participant, stage, time_str):
        competition, participant, error = self._validate_stage_context(
            competition_name, stage, participant
        )
        if error:
            return False, error

        if not isinstance(time_str, str) or not time_str.strip():
            return False, "El tiempo no puede estar vacio."
        time_str = time_str.strip()
        try:
            time_ms = tiempo_a_milisegundos(time_str)
        except (TypeError, ValueError):
            return False, (
                "Formato de tiempo invalido. Use m:ss.xxx, con segundos "
                "entre 00 y 59 y un valor mayor que cero."
            )
        ok = add_time(competition[1], time_ms, stage, participant)
        if not ok:
            return False, "No se pudo guardar el tiempo."
        return True, "Tiempo guardado."

    # Rellena abandonos en una etapa con penalizacion base.
    def fill_missing_times(self, competition_name, stage):
        competition, _participant, error = self._validate_stage_context(
            competition_name, stage
        )
        if error:
            return False, error
        ok = fill_times(competition[1], stage)
        if not ok:
            return False, "No hay tiempos base para esa etapa."
        return True, "Abandonos rellenados."

    # Aplica penalizacion en segundos a un participante.
    def penalize(self, competition_name, stage, participant, penalty_seconds):
        competition, participant, error = self._validate_stage_context(
            competition_name, stage, participant
        )
        if error:
            return False, error

        penalty_ms, error = self._penalty_to_milliseconds(penalty_seconds)
        if error:
            return False, error

        ok = fill_times_penalitation(competition[1], stage, participant, penalty_ms)
        if not ok:
            return False, "No existe tiempo para ese participante/etapa."
        return True, "Penalizacion aplicada."

    # Valida competicion, rango de etapa y pertenencia del participante.
    def _validate_stage_context(self, competition_name, stage, participant=None):
        if not isinstance(competition_name, str) or not competition_name.strip():
            return None, None, "No existe esa competicion."

        competition = get_competition(competition_name.strip())
        if competition is None:
            return None, None, "No existe esa competicion."

        if not self._is_strict_int(stage):
            return None, None, "La etapa debe ser un numero entero."
        if not 1 <= stage <= competition[2]:
            return None, None, f"La etapa debe estar entre 1 y {competition[2]}."

        if participant is None:
            return competition, None, None
        if not isinstance(participant, str) or not participant.strip():
            return None, None, "Debe seleccionar un participante."

        participant = participant.strip()
        if participant not in get_participants(competition[0]):
            return None, None, "El participante no pertenece a la competicion."
        return competition, participant, None

    # Convierte segundos de penalizacion a milisegundos sin perder precision.
    @staticmethod
    def _penalty_to_milliseconds(penalty_seconds):
        if isinstance(penalty_seconds, bool):
            return None, "La penalizacion debe ser un numero valido."
        try:
            seconds = Decimal(str(penalty_seconds))
        except (InvalidOperation, TypeError, ValueError):
            return None, "La penalizacion debe ser un numero valido."

        if not seconds.is_finite() or seconds <= 0:
            return None, "La penalizacion debe ser mayor que cero."

        milliseconds = seconds * 1000
        if milliseconds != milliseconds.to_integral_value():
            return None, "La penalizacion admite como maximo tres decimales."
        penalty_ms = int(milliseconds)
        if penalty_ms > MAX_SQLITE_INTEGER:
            return None, "La penalizacion es demasiado grande."
        return penalty_ms, None

    @staticmethod
    def _is_strict_int(value):
        return isinstance(value, int) and not isinstance(value, bool)

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

    # Determina la etapa con tiempos faltantes mas cercana.
    def get_default_stage(self, competition_id, stages, participants):
        if not participants or stages <= 0:
            return 1
        counts = get_stage_counts(competition_id)
        total = len(participants)
        for stage in range(1, stages + 1):
            if counts.get(stage, 0) < total:
                return stage
        return stages

    @staticmethod
    # Formatea milisegundos a string o placeholder.
    def format_time(ms):
        if ms is None:
            return "--:--.---"
        return milisegundos_a_tiempo(ms)
