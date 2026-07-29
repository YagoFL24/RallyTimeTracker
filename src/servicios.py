from decimal import Decimal, InvalidOperation

from copias_seguridad import (
    BackupError,
    create_backup,
    get_backup_directory,
    list_backups,
    restore_backup,
)
from gestorTiempos import (
    MAX_SQLITE_INTEGER,
    milisegundos_a_tiempo,
    tiempo_a_milisegundos,
)
from intercambio import (
    ExchangeError,
    export_data as write_export_file,
    export_pdf as write_classification_pdf,
    read_data as read_import_file,
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
    get_participant_records,
    get_stage_results,
    import_competition_snapshot,
    reactivate_participant,
    retire_participant,
    set_stage_status,
)


class RallyService:
    MAX_NAME_LENGTH = 255
    STATUS_LABELS = {
        "pending": "Pendiente",
        "finished": "Finalizado",
        "stage_dnf": "No finalizado",
        "dns": "No presentado",
        "dsq": "Descalificado",
    }
    STATUS_VALUES = {label: value for value, label in STATUS_LABELS.items()}

    # Devuelve nombres de competiciones disponibles.
    def list_competitions(self):
        return [c[0] for c in get_competitions()]

    # Carga datos completos de una competicion para la UI.
    def get_competition_info(self, competition_name):
        competition = get_competition(competition_name)
        if competition is None:
            return None
        competition_id, name, stages, event_date = competition
        participant_records = get_participant_records(competition_id)
        participants = [row["participant_name"] for row in participant_records]
        results = get_stage_results(competition_id)
        leaderboard = self._build_leaderboard(
            competition_id, stages, participant_records, results
        )
        return {
            "id": competition_id,
            "name": name,
            "stages": stages,
            "event_date": event_date,
            "participants": participants,
            "participant_records": participant_records,
            "results": results,
            "leaderboard": leaderboard,
        }

    # Exporta todos los datos de una competición a CSV o Excel.
    def export_competition(self, competition_name, destination):
        competition = self.get_competition_info(competition_name)
        if competition is None:
            return False, "No existe esa competición."
        try:
            write_export_file(competition, destination)
        except (ExchangeError, OSError) as exc:
            return False, f"No se pudo exportar: {exc}"
        return True, "Competición exportada correctamente."

    # Importa un archivo validado como una competición nueva.
    def import_competition(self, source):
        try:
            snapshot = read_import_file(source)
        except (ExchangeError, OSError) as exc:
            return False, f"No se pudo importar: {exc}", None
        snapshot["name"] = self._available_import_name(snapshot["name"])
        try:
            create_backup("pre_import")
        except BackupError as exc:
            return False, f"No se pudo crear la copia previa: {exc}", None
        if not import_competition_snapshot(snapshot):
            return False, "No se pudo guardar la competición importada.", None
        return (
            True,
            f"Competición importada como '{snapshot['name']}'.",
            snapshot["name"],
        )

    # Genera una clasificación paginada y lista para imprimir.
    def export_classification_pdf(self, competition_name, destination):
        competition = self.get_competition_info(competition_name)
        if competition is None:
            return False, "No existe esa competición."
        try:
            write_classification_pdf(competition, destination)
        except (ExchangeError, OSError) as exc:
            return False, f"No se pudo crear el PDF: {exc}"
        return True, "Clasificación PDF guardada correctamente."

    # Crea una copia consistente de la base SQLite actual.
    def create_database_backup(self, reason="manual"):
        try:
            backup = create_backup(reason)
        except BackupError as exc:
            return False, str(exc), None
        return True, f"Copia creada: {backup['name']}.", backup

    def list_database_backups(self):
        try:
            return list_backups(), str(get_backup_directory()), None
        except (BackupError, OSError) as exc:
            return [], "", str(exc)

    # Restaura una copia tras guardar automáticamente el estado actual.
    def restore_database_backup(self, source):
        try:
            safety_backup = restore_backup(source)
        except BackupError as exc:
            return False, str(exc), None
        return (
            True,
            "Base restaurada correctamente. "
            f"Copia preventiva: {safety_backup['name']}.",
            safety_backup,
        )

    # Resume el estado operativo de un tramo para el panel de carrera.
    def get_stage_dashboard(self, competition_name, stage=None):
        competition = self.get_competition_info(competition_name)
        if competition is None:
            return None
        if stage is None:
            stage = self.get_default_stage(
                competition["id"],
                competition["stages"],
                competition["participants"],
            )
        if not self._is_strict_int(stage) or not 1 <= stage <= competition["stages"]:
            return None

        records = {
            row["participant_name"]: row
            for row in competition["participant_records"]
        }
        stage_results = {
            row["participant_name"]: row
            for row in competition["results"]
            if row["stage_number"] == stage
        }
        rows = []
        for participant_name in competition["participants"]:
            record = records[participant_name]
            result = stage_results[participant_name]
            pending = (
                record["rally_status"] == "active"
                and result["status"] == "pending"
            )
            modified = result["revision_count"] > 0
            display_result_status = result["status"]
            if (
                record["rally_status"] == "disqualified"
                and result["time_ms"] is None
            ):
                display_result_status = "dsq"
                result_label = self.STATUS_LABELS["dsq"]
            elif (
                record["rally_status"] == "retired"
                and record["retired_after_stage"] < stage
                and result["status"] == "pending"
            ):
                result_label = "No participa"
            else:
                result_label = self.STATUS_LABELS[result["status"]]
            alerts = []
            if pending:
                alerts.append("Pendiente")
            if modified:
                alerts.append("Resultado modificado")
            rows.append(
                {
                    "participant": participant_name,
                    "rally_status": record["rally_status"],
                    "rally_status_label": {
                        "active": "Activo",
                        "retired": "Retirado",
                        "disqualified": "Descalificado",
                    }[record["rally_status"]],
                    "result_status": display_result_status,
                    "result_status_label": result_label,
                    "time_ms": result["time_ms"],
                    "previous_time_ms": result["previous_time_ms"],
                    "revision_count": result["revision_count"],
                    "pending": pending,
                    "modified": modified,
                    "alert": " · ".join(alerts) if alerts else "-",
                }
            )
        rows.sort(
            key=lambda row: (
                not row["pending"],
                not row["modified"],
                row["participant"].casefold(),
            )
        )
        counts = {
            "total": len(rows),
            "pending": sum(row["pending"] for row in rows),
            "finished": sum(row["result_status"] == "finished" for row in rows),
            "stage_dnf": sum(row["result_status"] == "stage_dnf" for row in rows),
            "dns": sum(row["result_status"] == "dns" for row in rows),
            "dsq": sum(row["result_status"] == "dsq" for row in rows),
            "modified": sum(row["modified"] for row in rows),
        }
        return {
            "competition": competition["name"],
            "stage": stage,
            "stages": competition["stages"],
            "counts": counts,
            "rows": rows,
        }

    def _available_import_name(self, original_name):
        existing = {name.casefold() for name in self.list_competitions()}
        if original_name.casefold() not in existing:
            return original_name
        suffix = "_importada"
        base = original_name[: self.MAX_NAME_LENGTH - len(suffix)] + suffix
        if base.casefold() not in existing:
            return base
        number = 2
        while True:
            numbered_suffix = f"_importada_{number}"
            candidate = (
                original_name[: self.MAX_NAME_LENGTH - len(numbered_suffix)]
                + numbered_suffix
            )
            if candidate.casefold() not in existing:
                return candidate
            number += 1

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

    # Cambia el estado explicito de un participante en un tramo.
    def set_result_status(self, competition_name, participant, stage, status, time_str=None):
        competition, participant, error = self._validate_stage_context(
            competition_name, stage, participant
        )
        if error:
            return False, error
        status = self.STATUS_VALUES.get(status, status)
        if status not in self.STATUS_LABELS:
            return False, "Estado de tramo no valido."

        time_ms = None
        if status == "finished":
            if not isinstance(time_str, str) or not time_str.strip():
                return False, "Un resultado finalizado necesita un tiempo."
            try:
                time_ms = tiempo_a_milisegundos(time_str.strip())
            except (TypeError, ValueError):
                return False, "Formato de tiempo invalido. Use m:ss.xxx."

        ok = set_stage_status(
            competition[1], stage, participant, status, time_ms=time_ms
        )
        if not ok:
            if status == "stage_dnf":
                return False, "No hay un tiempo base para calcular la penalizacion."
            return False, "No se pudo cambiar el estado del tramo."
        return True, f"Estado actualizado: {self.STATUS_LABELS[status]}."

    # Retira al participante del rally despues o durante el tramo indicado.
    def retire_from_rally(self, competition_name, participant, stage, completed_stage):
        competition, participant, error = self._validate_stage_context(
            competition_name, stage, participant
        )
        if error:
            return False, error
        if not isinstance(completed_stage, bool):
            return False, "Debe indicar como termino el tramo."
        ok = retire_participant(
            competition[1], stage, participant, completed_stage
        )
        if not ok:
            if completed_stage:
                return False, "Registre primero el tiempo final del tramo."
            return False, "No hay un tiempo base para registrar el abandono."
        return True, "Participante retirado del rally."

    # Devuelve un participante retirado al estado activo.
    def reactivate(self, competition_name, participant):
        if not isinstance(competition_name, str) or not isinstance(participant, str):
            return False, "Participante no valido."
        if not reactivate_participant(competition_name, participant):
            return False, "El participante no esta retirado."
        return True, "Participante reactivado."

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
    def _build_leaderboard(
        self, competition_id, stages, participant_records, results=None
    ):
        del competition_id
        results = results or []
        started_stages = {
            result["stage_number"]
            for result in results
            if result["time_ms"] is not None
        }
        by_participant = {}
        for result in results:
            by_participant.setdefault(result["participant_name"], {})[
                result["stage_number"]
            ] = result

        rows = []
        for participant in participant_records:
            name = participant["participant_name"]
            stage_map = by_participant.get(name, {})
            stage_results = []
            stage_times = []
            for stage in range(1, stages + 1):
                result = dict(
                    stage_map.get(stage)
                    or {
                        "stage_number": stage,
                        "status": "pending",
                        "time_ms": None,
                        "revision_count": 0,
                        "previous_time_ms": None,
                    }
                )
                if participant["rally_status"] == "disqualified":
                    if (
                        result["status"] == "dsq"
                        and result["time_ms"] is None
                        and result.get("previous_time_ms") is not None
                    ):
                        result["status"] = "finished"
                        result["time_ms"] = result["previous_time_ms"]
                    elif result["time_ms"] is None:
                        result["status"] = "dsq"
                result["stage_started"] = stage in started_stages
                stage_results.append(result)
                stage_times.append(result["time_ms"])
            completed = sum(time is not None for time in stage_times)
            total = sum(time for time in stage_times if time is not None)
            statuses = {result["status"] for result in stage_results}
            if participant["rally_status"] == "disqualified":
                group = 2
                classification_status = "Descalificado"
            elif participant["rally_status"] == "retired":
                group = 1
                classification_status = "Retirado"
            elif "pending" in statuses:
                group = 0
                classification_status = "Pendiente"
            elif "dns" in statuses:
                group = 0
                classification_status = "No presentado"
            else:
                group = 0
                classification_status = "Clasificado"
            rows.append(
                {
                    "participant": name,
                    "stage_results": stage_results,
                    "stage_times": stage_times,
                    "total": total,
                    "diff": None,
                    "completed_stages": completed,
                    "classification_status": classification_status,
                    "rally_status": participant["rally_status"],
                    "_group": group,
                }
            )

        rows.sort(
            key=lambda row: (
                row["_group"],
                -row["completed_stages"],
                row["total"],
                row["participant"].casefold(),
            )
        )
        best_time_by_progress = {}
        for row in rows:
            if row["_group"] == 2 or row["completed_stages"] <= 0:
                continue
            progress_key = (row["_group"], row["completed_stages"])
            best_time_by_progress[progress_key] = min(
                row["total"],
                best_time_by_progress.get(progress_key, row["total"]),
            )
        rank = 1
        for row in rows:
            if row["_group"] == 2:
                row["rank"] = "DSQ"
            else:
                row["rank"] = rank
                rank += 1
            if row["_group"] != 2 and row["completed_stages"] > 0:
                progress_key = (row["_group"], row["completed_stages"])
                row["diff"] = (
                    row["total"]
                    - best_time_by_progress[progress_key]
                )
            row.pop("_group")
        return rows

    # Determina la etapa con tiempos faltantes mas cercana.
    def get_default_stage(self, competition_id, stages, participants):
        if not participants or stages <= 0:
            return 1
        records = get_participant_records(competition_id)
        results = get_stage_results(competition_id)
        status_by_key = {
            (row["participant_name"], row["stage_number"]): row["status"]
            for row in results
        }
        for stage in range(1, stages + 1):
            relevant = [
                row
                for row in records
                if row["rally_status"] == "active"
                or (
                    row["rally_status"] == "retired"
                    and row["retired_after_stage"] >= stage
                )
            ]
            if any(
                status_by_key.get((row["participant_name"], stage), "pending")
                == "pending"
                for row in relevant
            ):
                return stage
        return stages

    def format_stage_result(self, result):
        status = result["status"]
        if status == "finished":
            return self.format_time(result["time_ms"])
        if status == "stage_dnf":
            return f"NF {self.format_time(result['time_ms'])}"
        if status == "dns":
            return "NP"
        if status == "dsq":
            return "DSQ"
        return "Pendiente" if result.get("stage_started", False) else "-"

    @staticmethod
    # Formatea milisegundos a string o placeholder.
    def format_time(ms):
        if ms is None:
            return "--:--.---"
        return milisegundos_a_tiempo(ms)
