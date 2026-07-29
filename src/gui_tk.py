import os
import sqlite3
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog, messagebox, ttk

from database_schema import DatabaseMigrationError
from servicios import RallyService


class RallyApp(tk.Tk):
    # Inicializa la ventana principal y el estado base.
    def __init__(self):
        super().__init__()
        self.ready = False
        self.service = RallyService()
        self.current_competition = None
        self.dark_mode = True
        self.style = ttk.Style(self)
        self.theme_colors = {}
        self._theme_text_widgets = []
        self.dashboard_window = None
        self.dashboard_tree = None
        self.dashboard_competition_name = None
        self._dashboard_rows_by_participant = {}

        self.title("Rally Time Tracker")
        self.geometry("1100x650")
        self.minsize(900, 600)
        self._configure_text_rendering()

        self._build_ui()
        self._set_app_icon()
        self.apply_theme()
        self.current_leaderboard = []
        try:
            self.refresh_competitions()
        except (DatabaseMigrationError, sqlite3.DatabaseError, OSError) as exc:
            messagebox.showerror(
                "Error de base de datos",
                f"No se pudo abrir o migrar la base de datos.\n\n{exc}",
                parent=self,
            )
            self.destroy()
            return
        self.ready = True

    # Construye el layout principal.
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        main = ttk.Frame(self, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)
        main.rowconfigure(1, weight=0)

        self._build_left_panel(main)
        self._build_right_panel(main)
        self._build_status_bar(main)

    # Ajusta escalado y fuente base.
    def _configure_text_rendering(self):
        self._set_dpi_awareness()
        self.tk.call("tk", "scaling", 1.25)

        base_font = tkfont.nametofont("TkDefaultFont")
        base_font.configure(family="Segoe UI", size=15)
        self.option_add("*Font", base_font)

    # Activa DPI awareness en Windows si es posible.
    def _set_dpi_awareness(self):
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

    # Construye el panel de competiciones y botones.
    def _build_left_panel(self, parent):
        panel = ttk.Frame(parent)
        panel.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        panel.rowconfigure(1, weight=1)

        ttk.Label(panel, text="Competiciones").grid(row=0, column=0, sticky="w")

        list_frame = ttk.Frame(panel)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=8)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.competition_list = tk.Listbox(list_frame, height=18)
        self.competition_list.grid(row=0, column=0, sticky="nsew")
        self.competition_list.bind("<<ListboxSelect>>", self.on_select_competition)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.competition_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.competition_list.config(yscrollcommand=scrollbar.set)

        buttons = ttk.Frame(panel)
        buttons.grid(row=2, column=0, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        buttons.columnconfigure(2, weight=1)

        ttk.Button(buttons, text="Nueva", command=self.open_new_competition).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(buttons, text="Borrar", command=self.delete_selected_competition).grid(
            row=0, column=1, sticky="ew", padx=(0, 6)
        )
        ttk.Button(buttons, text="Refrescar", command=self.refresh_competitions).grid(
            row=0, column=2, sticky="ew"
        )

        ttk.Button(buttons, text="Exportar", command=self.export_clicked).grid(
            row=1, column=0, sticky="ew", padx=(0, 6), pady=(6, 0)
        )
        ttk.Button(buttons, text="Importar", command=self.import_clicked).grid(
            row=1, column=1, sticky="ew", padx=(0, 6), pady=(6, 0)
        )
        ttk.Button(buttons, text="Guardar PDF", command=self.export_pdf_clicked).grid(
            row=1, column=2, sticky="ew", pady=(6, 0)
        )

        self.theme_button = ttk.Button(panel, text="Modo oscuro", command=self.toggle_theme)
        self.theme_button.grid(row=3, column=0, sticky="ew", pady=(8, 0))

    # Construye el panel de detalles y tabla.
    def _build_right_panel(self, parent):
        panel = ttk.Frame(parent)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        header = ttk.Frame(panel)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        self.header_label = ttk.Label(
            header,
            text="Selecciona una competicion",
            font=("Segoe UI", 12, "bold"),
        )
        self.header_label.grid(row=0, column=0, sticky="w")
        self.dashboard_button = ttk.Button(
            header,
            text="Panel del tramo",
            command=self.open_stage_dashboard,
            state="disabled",
        )
        self.dashboard_button.grid(row=0, column=1, sticky="e")

        self.table_frame = ttk.Frame(panel)
        self.table_frame.grid(row=1, column=0, sticky="nsew", pady=8)
        self.table_frame.columnconfigure(0, weight=1)
        self.table_frame.rowconfigure(0, weight=1)

        self.tree = None

        self._build_actions(panel)

    # Construye la fila de acciones inferiores.
    def _build_actions(self, parent):
        actions = ttk.Frame(parent)
        actions.grid(row=2, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)

        self._build_add_time(actions)
        self._build_fill_missing(actions)
        self._build_penalize(actions)
        self._build_result_status(actions)

    # Crea controles para estados de tramo y abandono del rally.
    def _build_result_status(self, parent):
        frame = ttk.LabelFrame(parent, text="Estado del participante y tramo", padding=8)
        frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        for column in range(8):
            frame.columnconfigure(column, weight=1)

        ttk.Label(frame, text="Participante").grid(row=0, column=0, sticky="w")
        self.status_participant_var = tk.StringVar()
        self.status_participant_combo = ttk.Combobox(
            frame, textvariable=self.status_participant_var, state="readonly"
        )
        self.status_participant_combo.grid(row=1, column=0, sticky="ew", padx=(0, 6))

        ttk.Label(frame, text="Tramo").grid(row=0, column=1, sticky="w")
        self.status_stage_var = tk.StringVar()
        self.status_stage_combo = ttk.Combobox(
            frame, textvariable=self.status_stage_var, state="readonly", width=7
        )
        self.status_stage_combo.grid(row=1, column=1, sticky="ew", padx=(0, 6))

        ttk.Label(frame, text="Estado").grid(row=0, column=2, sticky="w")
        self.result_status_var = tk.StringVar(value="Pendiente")
        self.result_status_combo = ttk.Combobox(
            frame,
            textvariable=self.result_status_var,
            state="readonly",
            values=list(self.service.STATUS_LABELS.values()),
        )
        self.result_status_combo.grid(row=1, column=2, sticky="ew", padx=(0, 6))

        ttk.Label(frame, text="Tiempo si finaliza").grid(row=0, column=3, sticky="w")
        self.status_time_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.status_time_var).grid(
            row=1, column=3, sticky="ew", padx=(0, 6)
        )
        ttk.Button(frame, text="Aplicar estado", command=self.apply_status_clicked).grid(
            row=1, column=4, sticky="ew", padx=(0, 12)
        )

        ttk.Label(frame, text="Abandono del rally").grid(row=0, column=5, sticky="w")
        self.retirement_mode_var = tk.StringVar(value="Despues de finalizar")
        self.retirement_mode_combo = ttk.Combobox(
            frame,
            textvariable=self.retirement_mode_var,
            state="readonly",
            values=["Despues de finalizar", "Durante el tramo"],
        )
        self.retirement_mode_combo.grid(row=1, column=5, sticky="ew", padx=(0, 6))
        ttk.Button(frame, text="Retirar", command=self.retire_clicked).grid(
            row=1, column=6, sticky="ew", padx=(0, 6)
        )
        ttk.Button(frame, text="Reactivar", command=self.reactivate_clicked).grid(
            row=1, column=7, sticky="ew"
        )

    # Crea el formulario para agregar tiempos.
    def _build_add_time(self, parent):
        frame = ttk.LabelFrame(parent, text="Agregar tiempo", padding=8)
        frame.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Participante").grid(row=0, column=0, sticky="w")
        self.add_participant_var = tk.StringVar()
        self.add_participant_combo = ttk.Combobox(
            frame, textvariable=self.add_participant_var, state="readonly"
        )
        self.add_participant_combo.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(frame, text="Etapa").grid(row=1, column=0, sticky="w")
        self.add_stage_var = tk.StringVar()
        self.add_stage_combo = ttk.Combobox(frame, textvariable=self.add_stage_var, state="readonly")
        self.add_stage_combo.grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(frame, text="Tiempo (m:ss.xxx)").grid(row=2, column=0, sticky="w")
        self.add_time_var = tk.StringVar()
        self.add_time_entry = ttk.Entry(frame, textvariable=self.add_time_var)
        self.add_time_entry.grid(row=2, column=1, sticky="ew", pady=2)

        ttk.Button(frame, text="Guardar", command=self.add_time_clicked).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )

    # Crea el formulario para rellenar abandonos.
    def _build_fill_missing(self, parent):
        frame = ttk.LabelFrame(parent, text="Rellenar abandonos", padding=8)
        frame.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Etapa").grid(row=0, column=0, sticky="w")
        self.fill_stage_var = tk.StringVar()
        self.fill_stage_combo = ttk.Combobox(frame, textvariable=self.fill_stage_var, state="readonly")
        self.fill_stage_combo.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Button(frame, text="Rellenar", command=self.fill_missing_clicked).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )

    # Crea el formulario para aplicar penalizaciones.
    def _build_penalize(self, parent):
        frame = ttk.LabelFrame(parent, text="Penalizar", padding=8)
        frame.grid(row=0, column=2, sticky="ew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Participante").grid(row=0, column=0, sticky="w")
        self.penalize_participant_var = tk.StringVar()
        self.penalize_participant_combo = ttk.Combobox(
            frame, textvariable=self.penalize_participant_var, state="readonly"
        )
        self.penalize_participant_combo.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(frame, text="Etapa").grid(row=1, column=0, sticky="w")
        self.penalize_stage_var = tk.StringVar()
        self.penalize_stage_combo = ttk.Combobox(frame, textvariable=self.penalize_stage_var, state="readonly")
        self.penalize_stage_combo.grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(frame, text="Segundos").grid(row=2, column=0, sticky="w")
        self.penalize_seconds_var = tk.StringVar(value="10")
        ttk.Entry(frame, textvariable=self.penalize_seconds_var).grid(row=2, column=1, sticky="ew", pady=2)

        ttk.Button(frame, text="Aplicar", command=self.penalize_clicked).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )

    # Muestra la barra de estado inferior.
    def _build_status_bar(self, parent):
        self.status_var = tk.StringVar(value="")
        status = ttk.Label(parent, textvariable=self.status_var, anchor="w")
        status.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    # Actualiza el mensaje de estado.
    def set_status(self, message, ok=True):
        prefix = "OK" if ok else "Aviso"
        self.status_var.set(f"{prefix}: {message}")

    # Carga el icono de la aplicacion.
    def _set_app_icon(self):
        self._set_app_user_model_id()
        try:
            self.iconbitmap(self._resource_path("assets", "images", "rally.ico"))
        except Exception:
            pass
        try:
            icon = tk.PhotoImage(file=self._resource_path("assets", "images", "rally.png"))
            self.iconphoto(True, icon)
        except Exception:
            pass

    # Fija el AppUserModelID para el icono en taskbar.
    def _set_app_user_model_id(self):
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "RallyTimeTracker.App"
            )
        except Exception:
            pass

    # Resuelve rutas para recursos empaquetados.
    def _resource_path(self, *parts):
        base_dir = getattr(sys, "_MEIPASS", None) or os.getcwd()
        return os.path.join(base_dir, *parts)

    # Recarga la lista de competiciones.
    def refresh_competitions(self):
        selections = self.competition_list.curselection()
        selected_name = None
        if selections:
            selected_name = self.competition_list.get(selections[0])

        self.competition_list.delete(0, tk.END)
        for name in self.service.list_competitions():
            self.competition_list.insert(tk.END, name)

        if selected_name and self._select_competition_by_name(selected_name):
            return
        self._reset_competition_view()

    @staticmethod
    def _safe_filename(name):
        forbidden = '<>:"/\\|?*'
        safe = "".join("_" if character in forbidden else character for character in name)
        return safe.rstrip(". ") or "competicion"

    # Exporta la competición seleccionada a CSV o Excel.
    def export_clicked(self):
        if not self.current_competition:
            self.set_status("Seleccione una competicion.", ok=False)
            return
        name = self.current_competition["name"]
        destination = filedialog.asksaveasfilename(
            parent=self,
            title="Exportar competición",
            initialfile=f"{self._safe_filename(name)}.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Libro de Excel", "*.xlsx"), ("Archivo CSV", "*.csv")],
        )
        if not destination:
            return
        ok, message = self.service.export_competition(name, destination)
        self.set_status(message, ok=ok)
        if not ok:
            messagebox.showerror("Error de exportación", message, parent=self)

    # Importa una competición desde un archivo CSV o Excel.
    def import_clicked(self):
        source = filedialog.askopenfilename(
            parent=self,
            title="Importar competición",
            filetypes=[
                ("CSV o Excel", "*.csv *.xlsx"),
                ("Libro de Excel", "*.xlsx"),
                ("Archivo CSV", "*.csv"),
            ],
        )
        if not source:
            return
        ok, message, imported_name = self.service.import_competition(source)
        self.set_status(message, ok=ok)
        if not ok:
            messagebox.showerror("Error de importación", message, parent=self)
            return
        self.refresh_competitions()
        self._select_competition_by_name(imported_name)

    # Guarda la clasificación actual como PDF imprimible.
    def export_pdf_clicked(self):
        if not self.current_competition:
            self.set_status("Seleccione una competicion.", ok=False)
            return
        name = self.current_competition["name"]
        destination = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar clasificación PDF",
            initialfile=f"clasificacion_{self._safe_filename(name)}.pdf",
            defaultextension=".pdf",
            filetypes=[("Documento PDF", "*.pdf")],
        )
        if not destination:
            return
        ok, message = self.service.export_classification_pdf(name, destination)
        self.set_status(message, ok=ok)
        if not ok:
            messagebox.showerror("Error al crear PDF", message, parent=self)

    # Limpia el estado y los controles cuando no hay competicion seleccionada.
    def _reset_competition_view(self):
        self.current_competition = None
        self.current_leaderboard = []
        self.header_label.config(text="Selecciona una competicion")
        if hasattr(self, "dashboard_button"):
            self.dashboard_button.config(state="disabled")
        if getattr(self, "dashboard_window", None) is not None:
            self._close_stage_dashboard()
        self._clear_table()
        self._update_action_sources([], 0)

    # Selecciona una competicion por nombre en la lista.
    def _select_competition_by_name(self, name):
        for idx in range(self.competition_list.size()):
            if self.competition_list.get(idx) == name:
                self.competition_list.selection_clear(0, tk.END)
                self.competition_list.selection_set(idx)
                self.competition_list.activate(idx)
                self.on_select_competition()
                return True
        return False

    # Carga datos de la competicion seleccionada.
    def on_select_competition(self, _event=None):
        selection = self.competition_list.curselection()
        if selection:
            name = self.competition_list.get(selection[0])
        elif self.current_competition:
            name = self.current_competition["name"]
        else:
            return
        competition = self.service.get_competition_info(name)
        if competition is None:
            self.set_status("La competicion ya no existe.", ok=False)
            self.refresh_competitions()
            return
        self.current_competition = competition
        self.dashboard_button.config(state="normal")
        header = f"{competition['name']}  |  Etapas: {competition['stages']}"
        self.header_label.config(text=header)
        self._render_table(competition)
        self._update_action_sources(competition["participants"], competition["stages"])
        default_stage = self.service.get_default_stage(
            competition["id"],
            competition["stages"],
            competition["participants"],
        )
        self.add_stage_combo.set(str(default_stage))
        self.status_stage_combo.set(str(default_stage))
        self._refresh_stage_dashboard(
            reset_stage=self.dashboard_competition_name != competition["name"]
        )

    # Abre el panel operativo del tramo actual.
    def open_stage_dashboard(self):
        if not self.current_competition:
            self.set_status("Seleccione una competicion.", ok=False)
            return
        if self.dashboard_window is not None and self.dashboard_window.winfo_exists():
            self.dashboard_window.deiconify()
            self.dashboard_window.lift()
            self._refresh_stage_dashboard()
            return

        window = tk.Toplevel(self)
        window.title("Panel de control del tramo")
        window.geometry("1050x600")
        window.minsize(850, 450)
        window.transient(self)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(2, weight=1)
        window.protocol("WM_DELETE_WINDOW", self._close_stage_dashboard)
        window.bind("<Destroy>", self._on_dashboard_destroy)
        self.dashboard_window = window

        controls = ttk.Frame(window, padding=10)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(5, weight=1)
        ttk.Label(controls, text="Tramo").grid(row=0, column=0, padx=(0, 6))
        self.dashboard_stage_var = tk.StringVar()
        self.dashboard_stage_combo = ttk.Combobox(
            controls,
            textvariable=self.dashboard_stage_var,
            state="readonly",
            width=8,
        )
        self.dashboard_stage_combo.grid(row=0, column=1, padx=(0, 10))
        self.dashboard_stage_combo.bind(
            "<<ComboboxSelected>>", self._dashboard_stage_changed
        )
        self.dashboard_follow_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            controls,
            text="Seguir tramo actual",
            variable=self.dashboard_follow_var,
            command=self._refresh_stage_dashboard,
        ).grid(row=0, column=2, padx=(0, 10))
        ttk.Button(
            controls, text="Ir al actual", command=self._go_to_current_stage
        ).grid(row=0, column=3, padx=(0, 10))
        ttk.Label(
            controls,
            text="Doble clic para cargar el piloto en los formularios",
        ).grid(row=0, column=5, sticky="e")

        summary = ttk.Frame(window, padding=(10, 0, 10, 10))
        summary.grid(row=1, column=0, sticky="ew")
        summary_labels = (
            ("total", "Total"),
            ("pending", "Pendientes"),
            ("finished", "Finalizados"),
            ("stage_dnf", "NF"),
            ("dns", "NP"),
            ("dsq", "DSQ"),
            ("modified", "Modificados"),
        )
        self.dashboard_summary_vars = {}
        for column, (key, label) in enumerate(summary_labels):
            summary.columnconfigure(column, weight=1)
            frame = ttk.LabelFrame(summary, text=label, padding=6)
            frame.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0, 6 if column < len(summary_labels) - 1 else 0),
            )
            value = tk.StringVar(value="0")
            self.dashboard_summary_vars[key] = value
            ttk.Label(frame, textvariable=value, anchor="center").pack(fill="x")

        table_frame = ttk.Frame(window, padding=(10, 0, 10, 10))
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        columns = (
            "participant",
            "rally_status",
            "result_status",
            "time",
            "previous",
            "revisions",
            "alert",
        )
        self.dashboard_tree = ttk.Treeview(
            table_frame, columns=columns, show="headings"
        )
        self.dashboard_tree.grid(row=0, column=0, sticky="nsew")
        headings = (
            "Piloto",
            "Estado rally",
            "Resultado",
            "Tiempo",
            "Anterior",
            "Revisiones",
            "Atención",
        )
        widths = (180, 130, 150, 120, 120, 90, 210)
        for column, heading, width in zip(columns, headings, widths):
            self.dashboard_tree.heading(column, text=heading)
            self.dashboard_tree.column(
                column,
                width=width,
                anchor="w" if column in {"participant", "alert"} else "center",
            )
        self.dashboard_tree.bind("<Double-1>", self._load_dashboard_selection)
        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.dashboard_tree.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.dashboard_tree.configure(yscrollcommand=scrollbar.set)
        ttk.Button(
            table_frame,
            text="Cargar participante seleccionado",
            command=self._load_dashboard_selection,
        ).grid(row=1, column=0, sticky="e", pady=(8, 0))

        self._apply_dashboard_tags()
        self._refresh_stage_dashboard(reset_stage=True)

    def _on_dashboard_destroy(self, event):
        if event.widget is self.dashboard_window:
            self.dashboard_window = None
            self.dashboard_tree = None
            self.dashboard_competition_name = None
            self._dashboard_rows_by_participant = {}

    def _close_stage_dashboard(self):
        window = self.dashboard_window
        self.dashboard_window = None
        self.dashboard_tree = None
        self.dashboard_competition_name = None
        self._dashboard_rows_by_participant = {}
        if window is not None and window.winfo_exists():
            window.destroy()

    def _dashboard_stage_changed(self, _event=None):
        self.dashboard_follow_var.set(False)
        self._refresh_stage_dashboard()

    def _go_to_current_stage(self):
        self.dashboard_follow_var.set(True)
        self._refresh_stage_dashboard(reset_stage=True)

    # Recarga contadores y filas; se invoca también después de cada acción.
    def _refresh_stage_dashboard(self, reset_stage=False):
        if (
            self.dashboard_window is None
            or not self.dashboard_window.winfo_exists()
            or not self.current_competition
        ):
            return
        stages = self.current_competition["stages"]
        self.dashboard_stage_combo["values"] = [
            str(stage) for stage in range(1, stages + 1)
        ]
        selected_stage = None
        if not reset_stage and not self.dashboard_follow_var.get():
            try:
                selected_stage = int(self.dashboard_stage_var.get())
            except (TypeError, ValueError):
                selected_stage = None
        dashboard = self.service.get_stage_dashboard(
            self.current_competition["name"], selected_stage
        )
        if dashboard is None:
            return
        self.dashboard_competition_name = dashboard["competition"]
        self.dashboard_window.title(
            f"Panel del tramo {dashboard['stage']} — {dashboard['competition']}"
        )
        self.dashboard_stage_combo.set(str(dashboard["stage"]))
        for key, variable in self.dashboard_summary_vars.items():
            variable.set(str(dashboard["counts"][key]))
        self.dashboard_tree.delete(*self.dashboard_tree.get_children())
        self._dashboard_rows_by_participant = {
            row["participant"]: row for row in dashboard["rows"]
        }
        for row in dashboard["rows"]:
            tags = []
            if row["pending"]:
                tags.append("pending")
            if row["modified"]:
                tags.append("modified")
            if row["rally_status"] != "active":
                tags.append("inactive")
            if not tags:
                tags.append("resolved")
            self.dashboard_tree.insert(
                "",
                tk.END,
                values=(
                    row["participant"],
                    row["rally_status_label"],
                    row["result_status_label"],
                    self.service.format_time(row["time_ms"])
                    if row["time_ms"] is not None
                    else "-",
                    self.service.format_time(row["previous_time_ms"])
                    if row["previous_time_ms"] is not None
                    else "-",
                    row["revision_count"],
                    row["alert"],
                ),
                tags=tuple(tags),
            )

    # Lleva el piloto y el tramo del panel a los controles de edición.
    def _load_dashboard_selection(self, _event=None):
        if self.dashboard_tree is None:
            return
        selection = self.dashboard_tree.selection()
        if not selection:
            self.set_status("Seleccione un piloto en el panel.", ok=False)
            return
        participant = self.dashboard_tree.item(selection[0], "values")[0]
        stage = self.dashboard_stage_var.get()
        row = self._dashboard_rows_by_participant[participant]
        for combo in (
            self.add_participant_combo,
            self.penalize_participant_combo,
            self.status_participant_combo,
        ):
            combo.set(participant)
        for combo in (
            self.add_stage_combo,
            self.fill_stage_combo,
            self.penalize_stage_combo,
            self.status_stage_combo,
        ):
            combo.set(stage)
        current_time = (
            self.service.format_time(row["time_ms"])
            if row["time_ms"] is not None
            else ""
        )
        self.add_time_var.set(current_time)
        self.status_time_var.set(current_time)
        self.result_status_var.set(
            "Finalizado"
            if row["result_status"] == "pending"
            else self.service.STATUS_LABELS[row["result_status"]]
        )
        self.add_time_entry.focus_set()
        self.lift()
        self.set_status(
            f"{participant} y tramo {stage} cargados en los formularios."
        )

    def _apply_dashboard_tags(self):
        if self.dashboard_tree is None:
            return
        if self.dark_mode:
            colors = {
                "pending": "#6B4E16",
                "modified": "#59406B",
                "inactive": "#454545",
                "resolved": "#234F34",
            }
        else:
            colors = {
                "pending": "#FFF3CD",
                "modified": "#E8D9F6",
                "inactive": "#E2E3E5",
                "resolved": "#D4EDDA",
            }
        for tag, background in colors.items():
            self.dashboard_tree.tag_configure(tag, background=background)

    # Renderiza la tabla de tiempos y ranking.
    def _render_table(self, competition):
        self._build_table(competition["stages"])
        self.current_leaderboard = list(competition["leaderboard"])
        self._populate_table(self.current_leaderboard, competition["stages"])

    # Configura columnas y scrolls de la tabla.
    def _build_table(self, stages):
        self._clear_table()
        columns = ["rank", "participant", "status"] + [f"stage_{i}" for i in range(1, stages + 1)] + ["total", "diff"]
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings", height=16)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<MouseWheel>", self._on_mousewheel)
        self.tree.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self.tree.bind("<Button-4>", self._on_mousewheel)
        self.tree.bind("<Button-5>", self._on_mousewheel)
        self.tree.bind("<Shift-Button-4>", self._on_shift_mousewheel)
        self.tree.bind("<Shift-Button-5>", self._on_shift_mousewheel)

        headings = ["Pos", "Piloto", "Estado"] + [f"Tramo {i}" for i in range(1, stages + 1)] + ["General", "Dif."]
        for col, heading in zip(columns, headings):
            self.tree.heading(col, text=heading, command=lambda c=col: self.sort_by_column(c, stages))
            anchor = "w" if col in ("participant", "status") else "center"
            if col == "participant":
                width = 180
            elif col == "status":
                width = 125
            elif col in ("total", "diff"):
                width = 120
            else:
                width = 110
            self.tree.column(col, width=width, anchor=anchor, stretch=True)

        v_scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        self.tree.config(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Maneja scroll vertical con rueda.
    def _on_mousewheel(self, event):
        if event.num == 4:
            self.tree.yview_scroll(-20, "units")
        elif event.num == 5:
            self.tree.yview_scroll(20, "units")
        else:
            self.tree.yview_scroll(int(-20 * (event.delta / 120)), "units")

    # Maneja scroll horizontal con shift+rueda.
    def _on_shift_mousewheel(self, event):
        if event.num == 4:
            self.tree.xview_scroll(-20, "units")
        elif event.num == 5:
            self.tree.xview_scroll(20, "units")
        else:
            self.tree.xview_scroll(int(-20 * (event.delta / 120)), "units")

    # Inserta filas en la tabla.
    def _populate_table(self, rows, stages):
        if self.tree is None:
            return
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            rank = row["rank"]
            if row["diff"] is None:
                diff_text = "-"
            else:
                diff_text = "-" if row["diff"] == 0 else f"+{self.service.format_time(row['diff'])}"
            values = [
                rank,
                row["participant"],
                row["classification_status"],
                *[
                    self.service.format_stage_result(result)
                    for result in row["stage_results"]
                ],
                self.service.format_time(row["total"]),
                diff_text,
            ]
            self.tree.insert("", tk.END, values=values)

    # Ordena la tabla por columna seleccionada.
    def sort_by_column(self, column, stages):
        if not self.current_leaderboard:
            return

        def missing_last(value):
            return value is None

        if column == "rank":
            key_func = lambda r: (
                r.get("rally_status") == "disqualified",
                r["rank"] if isinstance(r["rank"], int) else 0,
            )
        elif column == "total":
            key_func = lambda r: r["total"]
        elif column == "participant":
            key_func = lambda r: r["participant"].lower()
        elif column == "status":
            key_func = lambda r: r["classification_status"]
        elif column.startswith("stage_"):
            stage_index = int(column.split("_")[1]) - 1
            key_func = lambda r: (missing_last(r["stage_times"][stage_index]), r["stage_times"][stage_index] or 0)
        elif column == "diff":
            key_func = lambda r: (r["diff"] is None, r["diff"] or 0)
        else:
            key_func = lambda r: r["total"]

        sorted_rows = sorted(
            self.current_leaderboard,
            key=lambda row: (
                row.get("rally_status") == "disqualified",
                key_func(row),
            ),
        )
        self._populate_table(sorted_rows, stages)

    # Limpia tabla y scrollbars actuales.
    def _clear_table(self):
        if self.tree is not None:
            self.tree.destroy()
            self.tree = None
        for widget in self.table_frame.grid_slaves():
            if isinstance(widget, ttk.Scrollbar):
                widget.destroy()

    # Actualiza combos de participantes y etapas.
    def _update_action_sources(self, participants, stages):
        stage_values = [str(i) for i in range(1, stages + 1)]

        for combo in (
            self.add_participant_combo,
            self.penalize_participant_combo,
            self.status_participant_combo,
        ):
            combo["values"] = participants
            if participants:
                combo.set(participants[0])
            else:
                combo.set("")

        for combo in (
            self.add_stage_combo,
            self.fill_stage_combo,
            self.penalize_stage_combo,
            self.status_stage_combo,
        ):
            combo["values"] = stage_values
            combo.set(stage_values[0] if stage_values else "")

    # Guarda un tiempo desde el formulario.
    def add_time_clicked(self):
        if not self.current_competition:
            self.set_status("Seleccione una competicion.", ok=False)
            return
        participant = self.add_participant_var.get()
        stage = self.add_stage_var.get()
        time_str = self.add_time_var.get()
        if not participant or not stage:
            self.set_status("Debe seleccionar participante y etapa.", ok=False)
            return
        ok, msg = self.service.add_time_str(self.current_competition["name"], participant, int(stage), time_str)
        self.set_status(msg, ok=ok)
        if ok:
            self.add_time_var.set("")
            self.on_select_competition()
            self.add_stage_combo.set(stage)

    # Rellena abandonos en la etapa seleccionada.
    def fill_missing_clicked(self):
        if not self.current_competition:
            self.set_status("Seleccione una competicion.", ok=False)
            return
        stage = self.fill_stage_var.get()
        if not stage:
            self.set_status("Debe seleccionar la etapa.", ok=False)
            return
        ok, msg = self.service.fill_missing_times(self.current_competition["name"], int(stage))
        self.set_status(msg, ok=ok)
        if ok:
            self.on_select_competition()

    # Aplica penalizacion con segundos indicados.
    def penalize_clicked(self):
        if not self.current_competition:
            self.set_status("Seleccione una competicion.", ok=False)
            return
        participant = self.penalize_participant_var.get()
        stage = self.penalize_stage_var.get()
        seconds_text = (self.penalize_seconds_var.get() or "").strip()
        if not participant or not stage:
            self.set_status("Debe seleccionar participante y etapa.", ok=False)
            return
        if not seconds_text:
            self.set_status("Debe indicar la penalizacion en segundos.", ok=False)
            return
        try:
            penalty_seconds = float(seconds_text)
        except ValueError:
            self.set_status("Segundos invalido.", ok=False)
            return
        ok, msg = self.service.penalize(
            self.current_competition["name"],
            int(stage),
            participant,
            penalty_seconds,
        )
        self.set_status(msg, ok=ok)
        if ok:
            self.on_select_competition()

    # Aplica el estado seleccionado al participante y tramo.
    def apply_status_clicked(self):
        if not self.current_competition:
            self.set_status("Seleccione una competicion.", ok=False)
            return
        participant = self.status_participant_var.get()
        stage = self.status_stage_var.get()
        if not participant or not stage:
            self.set_status("Seleccione participante y tramo.", ok=False)
            return
        ok, message = self.service.set_result_status(
            self.current_competition["name"],
            participant,
            int(stage),
            self.result_status_var.get(),
            self.status_time_var.get(),
        )
        self.set_status(message, ok=ok)
        if ok:
            self.status_time_var.set("")
            self.on_select_competition()

    # Marca el abandono definitivo del rally.
    def retire_clicked(self):
        if not self.current_competition:
            self.set_status("Seleccione una competicion.", ok=False)
            return
        participant = self.status_participant_var.get()
        stage = self.status_stage_var.get()
        if not participant or not stage:
            self.set_status("Seleccione participante y tramo.", ok=False)
            return
        completed = self.retirement_mode_var.get() == "Despues de finalizar"
        ok, message = self.service.retire_from_rally(
            self.current_competition["name"], participant, int(stage), completed
        )
        self.set_status(message, ok=ok)
        if ok:
            self.on_select_competition()

    # Reactiva un participante retirado.
    def reactivate_clicked(self):
        if not self.current_competition:
            self.set_status("Seleccione una competicion.", ok=False)
            return
        participant = self.status_participant_var.get()
        ok, message = self.service.reactivate(
            self.current_competition["name"], participant
        )
        self.set_status(message, ok=ok)
        if ok:
            self.on_select_competition()

    # Abre dialogo para crear competicion.
    def open_new_competition(self):
        dialog = tk.Toplevel(self)
        dialog.title("Nueva competicion")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=self.theme_colors.get("bg"))

        dialog.columnconfigure(1, weight=1)

        ttk.Label(dialog, text="Nombre").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var).grid(row=0, column=1, sticky="ew", padx=8, pady=(8, 2))

        ttk.Label(dialog, text="Etapas").grid(row=1, column=0, sticky="w", padx=8, pady=2)
        stages_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=stages_var).grid(row=1, column=1, sticky="ew", padx=8, pady=2)

        ttk.Label(dialog, text="Participantes (uno por linea)").grid(
            row=2, column=0, sticky="w", padx=8, pady=2
        )
        participants_text = tk.Text(dialog, height=6, width=30)
        participants_text.grid(row=2, column=1, sticky="ew", padx=8, pady=2)
        self._register_text_widget(participants_text)

        # Valida datos y crea la competicion desde el dialogo.
        def create():
            name = name_var.get().strip()
            try:
                stages = int(stages_var.get())
            except ValueError:
                self.set_status("Etapas debe ser un numero.", ok=False)
                return

            raw = participants_text.get("1.0", tk.END)
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            if len(lines) == 1 and "," in lines[0]:
                participants = [p.strip() for p in lines[0].split(",") if p.strip()]
            else:
                participants = lines

            ok, msg = self.service.create_competition(name, stages, participants)
            self.set_status(msg, ok=ok)
            if ok:
                dialog.destroy()
                self.refresh_competitions()
                self._select_competition_by_name(name)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 8))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)

        ttk.Button(buttons, text="Crear", command=create).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="Cancelar", command=dialog.destroy).grid(row=0, column=1, sticky="ew")

    # Elimina la competicion actual previa confirmacion.
    def delete_selected_competition(self):
        if not self.current_competition:
            self.set_status("Seleccione una competicion.", ok=False)
            return
        name = self.current_competition["name"]
        if not messagebox.askyesno("Confirmar", f"¿Borrar la competicion '{name}'?"):
            return
        ok, msg = self.service.delete_competition(name)
        self.set_status(msg, ok=ok)
        if ok:
            self.refresh_competitions()

    # Registra widgets Text para aplicar tema.
    def _register_text_widget(self, widget):
        self._theme_text_widgets.append(widget)
        widget.bind("<Destroy>", lambda _event, w=widget: self._unregister_text_widget(w))
        self._apply_text_widget_theme(widget)

    # Elimina un widget Text de la lista de temas.
    def _unregister_text_widget(self, widget):
        self._theme_text_widgets = [w for w in self._theme_text_widgets if w is not widget]

    # Aplica colores del tema a widgets Text.
    def _apply_text_widget_theme(self, widget):
        colors = self.theme_colors
        if not colors:
            return
        widget.configure(
            bg=colors["entry_bg"],
            fg=colors["fg"],
            insertbackground=colors["fg"],
            highlightbackground=colors["bg"],
            highlightcolor=colors["accent"],
        )

    # Aplica el tema visual a toda la UI.
    def apply_theme(self):
        if self.dark_mode:
            colors = {
                "bg": "#1e1e1e",
                "panel": "#252526",
                "entry_bg": "#3c3c3c",
                "fg": "#d4d4d4",
                "accent": "#0e639c",
            }
        else:
            colors = {
                "bg": "#d9d9d9",
                "panel": "#d9d9d9",
                "entry_bg": "#e3e3e3",
                "fg": "#1e1e1e",
                "accent": "#0e639c",
            }

        self.theme_colors = colors
        self.configure(bg=colors["bg"])
        self.style.theme_use("clam")

        self.style.configure("TFrame", background=colors["bg"])
        self.style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
        self.style.configure(
            "TButton",
            background=colors["panel"],
            foreground=colors["fg"],
            bordercolor=colors["accent"],
            lightcolor=colors["accent"],
            darkcolor=colors["accent"],
        )
        self.style.map("TButton", background=[("active", colors["accent"])], foreground=[("active", "#ffffff")])
        self.style.configure(
            "TEntry",
            fieldbackground=colors["entry_bg"],
            foreground=colors["fg"],
            bordercolor=colors["accent"],
            lightcolor=colors["accent"],
            darkcolor=colors["accent"],
        )
        self.style.configure("TCombobox", fieldbackground=colors["entry_bg"], foreground=colors["fg"])
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", colors["entry_bg"])],
            bordercolor=[("readonly", colors["accent"])],
            lightcolor=[("readonly", colors["accent"])],
            darkcolor=[("readonly", colors["accent"])],
            arrowcolor=[("readonly", colors["accent"])],
        )
        self.style.configure(
            "TLabelframe",
            background=colors["bg"],
            foreground=colors["fg"],
            bordercolor=colors["accent"],
            lightcolor=colors["accent"],
            darkcolor=colors["accent"],
        )
        self.style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["fg"])

        self.style.configure(
            "Treeview",
            background=colors["panel"],
            fieldbackground=colors["panel"],
            foreground=colors["fg"],
            rowheight=36,
            font=("Segoe UI", 15),
        )
        self.style.configure(
            "Treeview.Heading",
            background=colors["bg"],
            foreground=colors["fg"],
            font=("Segoe UI", 15, "bold"),
        )
        self.style.map(
            "Treeview",
            background=[("selected", colors["accent"])],
            foreground=[("selected", "#ffffff")],
        )
        self.style.configure(
            "TScrollbar",
            background=colors["accent"],
            troughcolor=colors["panel"],
            bordercolor=colors["accent"],
            lightcolor=colors["accent"],
            darkcolor=colors["accent"],
            arrowcolor=colors["accent"],
        )

        if self.tree is not None:
            self.tree.configure(
                background=colors["panel"],
                foreground=colors["fg"],
                fieldbackground=colors["panel"],
            )

        list_bg = colors["bg"]
        self.competition_list.configure(
            bg=list_bg,
            fg=colors["fg"],
            selectbackground=colors["accent"],
            selectforeground="#ffffff",
            highlightbackground=colors["bg"],
            highlightcolor=colors["bg"],
        )
        selected = self.competition_list.curselection()
        if selected:
            self.competition_list.selection_clear(0, tk.END)
            for idx in selected:
                self.competition_list.selection_set(idx)

        for widget in list(self._theme_text_widgets):
            if widget.winfo_exists():
                self._apply_text_widget_theme(widget)
            else:
                self._unregister_text_widget(widget)

        self._apply_dashboard_tags()

        self.theme_button.config(text="Modo oscuro" if self.dark_mode else "Modo claro")

    # Alterna entre modo claro y oscuro.
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()


# Arranca la aplicacion.
def main():
    app = RallyApp()
    if app.ready:
        app.mainloop()


if __name__ == "__main__":
    main()
