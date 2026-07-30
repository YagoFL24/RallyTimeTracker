from datetime import datetime
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
    export_championship_data as write_championship_export,
    export_championship_pdf as write_championship_pdf,
    export_data as write_export_file,
    export_pdf as write_classification_pdf,
    read_data as read_import_file,
)
from persistencia import (
    add_championship_event,
    add_competition,
    add_driver_alias,
    add_time,
    create_championship as persist_championship,
    delete_championship as persist_delete_championship,
    delete_competition,
    fill_times,
    fill_times_penalitation,
    get_championship,
    get_championship_drivers,
    get_championship_events,
    get_championship_points,
    get_championships,
    get_competition,
    get_competition_championships,
    get_competitions,
    get_participants,
    get_participant_records,
    get_stage_results,
    import_competition_snapshot,
    move_championship_event,
    reactivate_participant,
    remove_championship_event,
    retire_participant,
    set_championship_driver_availability,
    set_stage_status,
    update_championship_settings,
    update_competition_date,
)


class RallyService:
    MAX_NAME_LENGTH = 255
    DEFAULT_CHAMPIONSHIP_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
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

    # Devuelve nombres de campeonatos disponibles.
    def list_championships(self):
        return [row["championship_name"] for row in get_championships()]

    # Crea un campeonato, sus pilotos globales y la tabla de puntuación.
    def create_championship(
        self, name, drivers, position_points=None, stage_win_bonus=5
    ):
        if not isinstance(name, str) or not name.strip():
            return False, "El nombre del campeonato no puede estar vacio."
        name = name.strip()
        if len(name) > self.MAX_NAME_LENGTH:
            return False, f"El nombre no puede superar {self.MAX_NAME_LENGTH} caracteres."
        if get_championship(name) is not None:
            return False, "Ya existe un campeonato con ese nombre."
        normalized_drivers, error = self._normalize_championship_drivers(drivers)
        if error:
            return False, error
        points, error = self._normalize_championship_points(position_points)
        if error:
            return False, error
        if not self._is_strict_int(stage_win_bonus) or stage_win_bonus < 0:
            return False, "La bonificacion por tramos debe ser un entero no negativo."
        if not persist_championship(
            name, normalized_drivers, points, stage_win_bonus
        ):
            return False, "No se pudo crear el campeonato."
        return True, "Campeonato creado."

    def _normalize_championship_drivers(self, drivers):
        if not isinstance(drivers, (list, tuple)) or not drivers:
            return None, "Debe indicar al menos un piloto."
        normalized = []
        keys = set()
        for driver in drivers:
            if not isinstance(driver, str) or not driver.strip():
                return None, "Los pilotos no pueden estar vacios."
            driver = driver.strip()
            if len(driver) > self.MAX_NAME_LENGTH:
                return None, (
                    f"El nombre de un piloto no puede superar "
                    f"{self.MAX_NAME_LENGTH} caracteres."
                )
            if driver.casefold() in keys:
                return None, "Los pilotos del campeonato no pueden repetirse."
            keys.add(driver.casefold())
            normalized.append(driver)
        return normalized, None

    def _normalize_championship_points(self, position_points):
        if position_points is None:
            return list(self.DEFAULT_CHAMPIONSHIP_POINTS), None
        if not isinstance(position_points, (list, tuple)) or not position_points:
            return None, "Debe indicar al menos una posicion puntuable."
        points = []
        for value in position_points:
            if not self._is_strict_int(value) or value < 0:
                return None, "Todos los puntos deben ser enteros no negativos."
            if value > MAX_SQLITE_INTEGER:
                return None, "La tabla de puntos contiene un valor demasiado grande."
            points.append(value)
        return points, None

    # Carga calendario, resultados y clasificación recalculada de un campeonato.
    def get_championship_info(self, championship_name):
        championship = get_championship(championship_name)
        if championship is None:
            return None
        championship_id = championship["id"]
        drivers = get_championship_drivers(championship_id)
        points = get_championship_points(championship_id)
        events = get_championship_events(championship_id)
        for event in events:
            competition = self.get_competition_info(event["competition_name"])
            event["competition"] = competition
            event["status"] = self._championship_event_status(competition)
            event["results"] = self._build_championship_event_results(
                competition,
                event["driver_mappings"],
                drivers,
                points,
                championship["stage_win_bonus"],
                event["status"] == "Finalizada",
            )
        if championship["manually_finalized"]:
            status = "Finalizado"
        elif events and all(event["status"] == "Finalizada" for event in events):
            status = "Finalizado"
        elif any(event["status"] != "Planificada" for event in events):
            status = "En curso"
        else:
            status = "Planificado"
        return {
            **championship,
            "name": championship["championship_name"],
            "status": status,
            "drivers": drivers,
            "points_table": points,
            "events": events,
            "standings": self._build_championship_standings(drivers, events),
        }

    @staticmethod
    def _championship_event_status(competition):
        if competition is None:
            return "Planificada"
        started = any(row["status"] != "pending" for row in competition["results"])
        if not started:
            return "Planificada"
        active_names = {
            row["participant_name"]
            for row in competition["participant_records"]
            if row["rally_status"] == "active"
        }
        has_pending = any(
            row["participant_name"] in active_names and row["status"] == "pending"
            for row in competition["results"]
        )
        return "En curso" if has_pending else "Finalizada"

    def _build_championship_event_results(
        self, competition, mappings, drivers, points, stage_win_bonus, award_points
    ):
        if competition is None:
            return {}
        driver_by_id = {row["id"]: row for row in drivers}
        leaderboard = {
            row["participant"]: row for row in competition["leaderboard"]
        }
        mapped = []
        for mapping in mappings:
            if not mapping["participates"] or mapping["participant_name"] is None:
                continue
            row = leaderboard.get(mapping["participant_name"])
            if row is None or mapping["driver_id"] not in driver_by_id:
                continue
            mapped.append((mapping, row))

        valid = [
            item
            for item in mapped
            if item[1]["rally_status"] != "disqualified"
            and item[1]["classification_status"] != "No presentado"
        ]
        valid.sort(
            key=lambda item: (
                0 if item[1]["rally_status"] == "active" else 1,
                -item[1]["completed_stages"],
                item[1]["total"],
                driver_by_id[item[0]["driver_id"]]["official_name"].casefold(),
            )
        )
        positions = {}
        previous_key = None
        position = None
        for index, (mapping, row) in enumerate(valid, start=1):
            result_key = (
                0 if row["rally_status"] == "active" else 1,
                row["completed_stages"],
                row["total"],
            )
            if result_key != previous_key:
                position = index
                previous_key = result_key
            positions[mapping["driver_id"]] = position

        stage_wins = {mapping["driver_id"]: 0 for mapping, _row in valid}
        for stage_index in range(competition["stages"]):
            finishers = []
            for mapping, row in valid:
                result = row["stage_results"][stage_index]
                if result["status"] == "finished" and result["time_ms"] is not None:
                    finishers.append((mapping["driver_id"], result["time_ms"]))
            if finishers:
                best = min(time_ms for _driver_id, time_ms in finishers)
                for driver_id, time_ms in finishers:
                    if time_ms == best:
                        stage_wins[driver_id] += 1
        maximum_wins = max(stage_wins.values(), default=0)
        bonus_winners = {
            driver_id
            for driver_id, wins in stage_wins.items()
            if maximum_wins > 0 and wins == maximum_wins
        }

        results = {}
        for mapping, row in mapped:
            driver_id = mapping["driver_id"]
            position = positions.get(driver_id)
            base_points = (
                points[position - 1]
                if award_points and position is not None and position <= len(points)
                else 0
            )
            bonus = (
                stage_win_bonus
                if award_points and driver_id in bonus_winners
                else 0
            )
            results[driver_id] = {
                "position": position,
                "points": base_points,
                "bonus": bonus,
                "total_points": base_points + bonus,
                "stage_wins": stage_wins.get(driver_id, 0),
                "rally_status": row["rally_status"],
                "classification_status": row["classification_status"],
                "participant": mapping["participant_name"],
                "awarded": award_points,
            }
        return results

    @staticmethod
    def _build_championship_standings(drivers, events):
        rows = []
        for driver in drivers:
            event_results = []
            position_counts = {}
            total_points = 0
            stage_wins = 0
            retirements = 0
            for event in events:
                result = event["results"].get(driver["id"])
                event_results.append(result)
                if result is None:
                    continue
                total_points += result["total_points"]
                stage_wins += result["stage_wins"]
                if result["position"] is not None:
                    position_counts[result["position"]] = (
                        position_counts.get(result["position"], 0) + 1
                    )
                if result["rally_status"] == "retired":
                    retirements += 1
            recent_results = tuple(
                result["position"] if result and result["position"] is not None else 10**9
                for result in reversed(event_results)
            )
            tie_key = (
                -total_points,
                -position_counts.get(1, 0),
                -position_counts.get(2, 0),
                -position_counts.get(3, 0),
                recent_results,
            )
            rows.append(
                {
                    "driver_id": driver["id"],
                    "driver": driver["official_name"],
                    "status": driver["status"],
                    "points": total_points,
                    "difference": 0,
                    "wins": position_counts.get(1, 0),
                    "seconds": position_counts.get(2, 0),
                    "thirds": position_counts.get(3, 0),
                    "podiums": sum(
                        position_counts.get(position, 0) for position in (1, 2, 3)
                    ),
                    "stage_wins": stage_wins,
                    "retirements": retirements,
                    "event_results": event_results,
                    "_tie_key": tie_key,
                }
            )
        rows.sort(key=lambda row: (row["_tie_key"], row["driver"].casefold()))
        leader_points = rows[0]["points"] if rows else 0
        previous_key = None
        rank = 0
        for index, row in enumerate(rows, start=1):
            if row["_tie_key"] != previous_key:
                rank = index
                previous_key = row["_tie_key"]
            row["rank"] = rank
            row["difference"] = leader_points - row["points"]
            row.pop("_tie_key")
        return rows

    # Asocia una competición existente y recuerda las correspondencias de pilotos.
    def add_competition_to_championship(
        self, championship_name, competition_name, explicit_mappings=None
    ):
        championship = self.get_championship_info(championship_name)
        if championship is None:
            return False, "No existe ese campeonato."
        if championship["manually_finalized"]:
            return False, "El campeonato esta finalizado."
        competition = self.get_competition_info(competition_name)
        if competition is None:
            return False, "No existe esa competicion."
        if any(
            event["competition_name"].casefold() == competition["name"].casefold()
            for event in championship["events"]
        ):
            return False, "La competicion ya pertenece al campeonato."
        mappings, aliases, missing = self._resolve_championship_mappings(
            championship["drivers"], competition, explicit_mappings
        )
        if missing:
            return False, "Falta asociar: " + ", ".join(missing) + "."
        for driver_id, alias in aliases:
            if not add_driver_alias(driver_id, alias):
                return False, f"El alias '{alias}' ya pertenece a otro piloto."
        if not add_championship_event(
            championship["id"], competition["id"], mappings
        ):
            return False, "No se pudo añadir la competicion al campeonato."
        return True, "Competicion añadida al campeonato."

    @staticmethod
    def _resolve_championship_mappings(drivers, competition, explicit_mappings=None):
        explicit_mappings = explicit_mappings or {}
        participant_by_key = {
            row["participant_name"].casefold(): row
            for row in competition["participant_records"]
        }
        mappings = {}
        aliases = []
        missing = []
        used_participants = set()
        for driver in drivers:
            if driver["status"] != "active":
                continue
            requested = explicit_mappings.get(driver["official_name"])
            participant = None
            if isinstance(requested, str) and requested.strip():
                participant = participant_by_key.get(requested.strip().casefold())
            if participant is None:
                for candidate in [driver["official_name"], *driver["aliases"]]:
                    participant = participant_by_key.get(candidate.casefold())
                    if participant is not None:
                        break
            if participant is None or participant["id"] in used_participants:
                missing.append(driver["official_name"])
                continue
            mappings[driver["id"]] = participant["id"]
            used_participants.add(participant["id"])
            if participant["participant_name"].casefold() not in {
                alias.casefold() for alias in driver["aliases"]
            }:
                aliases.append((driver["id"], participant["participant_name"]))
        return mappings, aliases, missing

    # Crea una competición con el roster activo y la incorpora al calendario.
    def create_competition_for_championship(
        self, championship_name, competition_name, stages, event_date=None
    ):
        championship = self.get_championship_info(championship_name)
        if championship is None:
            return False, "No existe ese campeonato."
        if championship["manually_finalized"]:
            return False, "El campeonato esta finalizado."
        active_drivers = [
            row["official_name"]
            for row in championship["drivers"]
            if row["status"] == "active"
        ]
        if not active_drivers:
            return False, "No hay pilotos activos para crear la competicion."
        ok, message = self.create_competition(
            competition_name, stages, active_drivers, event_date
        )
        if not ok:
            return False, message
        ok, message = self.add_competition_to_championship(
            championship_name, competition_name
        )
        if not ok:
            delete_competition(competition_name)
            return False, message
        return True, "Competicion creada y añadida al campeonato."

    # Quita una prueba del calendario sin borrar su competición.
    def remove_competition_from_championship(self, championship_name, event_id):
        championship = self.get_championship_info(championship_name)
        if championship is None:
            return False, "No existe ese campeonato."
        if not self._is_strict_int(event_id):
            return False, "Prueba no valida."
        try:
            create_backup("pre_championship")
        except BackupError as exc:
            return False, f"No se pudo crear la copia previa: {exc}"
        if not remove_championship_event(championship["id"], event_id):
            return False, "No se pudo retirar la prueba del campeonato."
        return True, "Prueba retirada; la competicion original se conserva."

    def move_competition_in_championship(
        self, championship_name, event_id, direction
    ):
        championship = get_championship(championship_name)
        if championship is None:
            return False, "No existe ese campeonato."
        if not move_championship_event(championship["id"], event_id, direction):
            return False, "La prueba ya esta en el limite del calendario."
        return True, "Calendario reordenado."

    # Retira o reincorpora un piloto desde una prueba concreta.
    def set_championship_driver_active(
        self,
        championship_name,
        driver_name,
        from_order,
        active,
        explicit_mappings=None,
    ):
        championship = self.get_championship_info(championship_name)
        if championship is None:
            return False, "No existe ese campeonato."
        driver = next(
            (
                row
                for row in championship["drivers"]
                if row["official_name"].casefold() == str(driver_name).casefold()
            ),
            None,
        )
        if driver is None:
            return False, "El piloto no pertenece al campeonato."
        if not self._is_strict_int(from_order) or from_order <= 0:
            return False, "La prueba inicial no es valida."
        if not isinstance(active, bool):
            return False, "El estado del piloto no es valido."
        event_mappings = {}
        if active:
            explicit_mappings = explicit_mappings or {}
            missing = []
            for event in championship["events"]:
                if event["event_order"] < from_order:
                    continue
                competition = event["competition"]
                requested = explicit_mappings.get(event["competition_name"])
                mappings, aliases, unresolved = self._resolve_championship_mappings(
                    [{**driver, "status": "active"}],
                    competition,
                    {driver["official_name"]: requested} if requested else None,
                )
                if unresolved:
                    missing.append(event["competition_name"])
                    continue
                event_mappings[event["id"]] = mappings[driver["id"]]
                for driver_id, alias in aliases:
                    if not add_driver_alias(driver_id, alias):
                        return False, f"El alias '{alias}' ya pertenece a otro piloto."
            if missing:
                return False, "Falta asociar al piloto en: " + ", ".join(missing) + "."
        if not set_championship_driver_availability(
            championship["id"], driver["id"], from_order, active, event_mappings
        ):
            return False, "No se pudo actualizar la participacion del piloto."
        return (
            True,
            "Piloto reincorporado al campeonato."
            if active
            else "Piloto retirado del campeonato.",
        )

    # Reemplaza tabla de puntos, bonificación y cierre manual.
    def configure_championship(
        self,
        championship_name,
        position_points,
        stage_win_bonus,
        manually_finalized=None,
    ):
        championship = get_championship(championship_name)
        if championship is None:
            return False, "No existe ese campeonato."
        points, error = self._normalize_championship_points(position_points)
        if error:
            return False, error
        if not self._is_strict_int(stage_win_bonus) or stage_win_bonus < 0:
            return False, "La bonificacion por tramos debe ser un entero no negativo."
        if not update_championship_settings(
            championship["id"], points, stage_win_bonus, manually_finalized
        ):
            return False, "No se pudo actualizar el campeonato."
        return True, "Configuracion actualizada y clasificacion recalculada."

    def delete_championship(self, championship_name):
        championship = get_championship(championship_name)
        if championship is None:
            return False, "No existe ese campeonato."
        try:
            create_backup("pre_championship")
        except BackupError as exc:
            return False, f"No se pudo crear la copia previa: {exc}"
        if not persist_delete_championship(championship["id"]):
            return False, "No se pudo borrar el campeonato."
        return True, "Campeonato borrado; sus competiciones se conservan."

    def export_championship(self, championship_name, destination):
        championship = self.get_championship_info(championship_name)
        if championship is None:
            return False, "No existe ese campeonato."
        try:
            write_championship_export(championship, destination)
        except (ExchangeError, OSError) as exc:
            return False, f"No se pudo exportar el campeonato: {exc}"
        return True, "Campeonato exportado correctamente."

    def export_championship_pdf(self, championship_name, destination):
        championship = self.get_championship_info(championship_name)
        if championship is None:
            return False, "No existe ese campeonato."
        try:
            write_championship_pdf(championship, destination)
        except (ExchangeError, OSError) as exc:
            return False, f"No se pudo crear el PDF del campeonato: {exc}"
        return True, "PDF del campeonato guardado correctamente."

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
    def create_competition(self, name, stages, participants, event_date=None):
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
        event_date, error = self._normalize_event_date(event_date)
        if error:
            return False, error

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

        if not add_competition(
            name, stages, normalized_participants, event_date=event_date
        ):
            return False, "No se pudo crear la competicion."
        return True, "Competicion creada."

    @staticmethod
    def _normalize_event_date(event_date):
        if event_date is None or not str(event_date).strip():
            return None, None
        event_date = str(event_date).strip()
        try:
            datetime.strptime(event_date, "%Y-%m-%d")
        except ValueError:
            return None, "La fecha debe usar el formato AAAA-MM-DD."
        return event_date, None

    def set_competition_date(self, competition_name, event_date):
        competition = get_competition(competition_name)
        if competition is None:
            return False, "No existe esa competicion."
        event_date, error = self._normalize_event_date(event_date)
        if error:
            return False, error
        if not update_competition_date(competition[1], event_date):
            return False, "No se pudo actualizar la fecha."
        return True, "Fecha actualizada."

    # Borra una competicion y sus datos asociados.
    def delete_competition(self, name):
        linked = get_competition_championships(name)
        if linked:
            return False, (
                "La competicion pertenece a: "
                + ", ".join(linked)
                + ". Retirela de esos campeonatos antes de borrarla."
            )
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

    # Devuelve el siguiente participante activo pendiente, respetando el orden de alta.
    def get_next_pending_participant(
        self, competition_name, stage, current_participant=None
    ):
        competition = self.get_competition_info(competition_name)
        if competition is None:
            return None
        if (
            not self._is_strict_int(stage)
            or not 1 <= stage <= competition["stages"]
        ):
            return None

        records = {
            row["participant_name"]: row
            for row in competition["participant_records"]
        }
        results = {
            row["participant_name"]: row
            for row in competition["results"]
            if row["stage_number"] == stage
        }
        participants = competition["participants"]
        pending = {
            participant
            for participant in participants
            if records[participant]["rally_status"] == "active"
            and results[participant]["status"] == "pending"
        }
        if not pending:
            return None

        start = 0
        if current_participant in participants:
            start = participants.index(current_participant) + 1
        for offset in range(len(participants)):
            participant = participants[(start + offset) % len(participants)]
            if participant in pending:
                return participant
        return None

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
