from __future__ import annotations

import os
import re
import threading
from datetime import date
from pathlib import Path
from queue import Empty, SimpleQueue
import tkinter as tk
from tkinter import messagebox, ttk

from .pipeline import build_pipeline, render_editorial_report, render_markdown, write_run_artifacts
from .settings import current_openai_api_key, default_env_path, save_openai_api_key


class ForecastApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Future News Forecaster")
        self.root.geometry("1240x800")
        self.root.minsize(1080, 720)

        self.colors = {
            "bg": "#F3EFE8",
            "panel": "#FBF8F2",
            "paper": "#FFFDFC",
            "border": "#D6CEC2",
            "accent": "#0F766E",
            "accent_dark": "#115E59",
            "accent_soft": "#D7EFE8",
            "text": "#1F2933",
            "muted": "#6B7280",
            "success_bg": "#DCFCE7",
            "success_fg": "#166534",
            "running_bg": "#DBEAFE",
            "running_fg": "#1D4ED8",
            "error_bg": "#FEE2E2",
            "error_fg": "#B91C1C",
            "idle_bg": "#E7E5E4",
            "idle_fg": "#44403C",
        }

        key = current_openai_api_key() or ""
        self.queue: SimpleQueue[tuple[object, ...]] = SimpleQueue()
        self.worker: threading.Thread | None = None
        self.api_key_var = tk.StringVar(value=key)
        self.provider_var = tk.StringVar(value="auto")
        self.model_var = tk.StringVar(value="gpt-5-mini")
        self.date_var = tk.StringVar(value="2026-04-02")
        self.outlet_var = tk.StringVar(value="Reuters")
        self.limit_var = tk.StringVar(value="5")
        self.out_dir_var = tk.StringVar(value="results/gui-run")
        self.offline_var = tk.BooleanVar(value=False)
        self.web_search_var = tk.BooleanVar(value=True)
        self.show_key_var = tk.BooleanVar(value=False)
        self.status_badge_var = tk.StringVar(value="ГОТОВО")
        self.status_var = tk.StringVar(
            value=f"Ключ хранится в {default_env_path()}. Вставьте его через Ctrl+V и сохраните."
        )
        self.provider_hint_var = tk.StringVar()
        self.outlet_hint_var = tk.StringVar()

        self.key_entry: ttk.Entry | None = None
        self.run_button: ttk.Button | None = None
        self.status_badge: tk.Label | None = None
        self.preview_notebook: ttk.Notebook | None = None
        self.results_tab: tk.Frame | None = None
        self.filter_tab: tk.Frame | None = None
        self.log_tab: tk.Frame | None = None
        self.idea_tab: tk.Frame | None = None
        self.results_widget: tk.Text | None = None
        self.filter_widget: tk.Text | None = None
        self.log_widget: tk.Text | None = None
        self.idea_widget: tk.Text | None = None
        self.sidebar_canvas: tk.Canvas | None = None
        self.sidebar_window_id: int | None = None

        self._configure_root()
        self._configure_styles()
        self._build_layout()
        self._sync_provider_hint()
        self.outlet_var.trace_add("write", self._sync_outlet_hint)
        self._sync_outlet_hint()
        self.root.bind("<Control-Return>", lambda _e: self._start_run())
        self.root.bind("<Control-KP_Enter>", lambda _e: self._start_run())
        self.root.after(150, self._poll_queue)

    def _configure_root(self) -> None:
        self.root.configure(bg=self.colors["bg"])

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=self.colors["panel"], foreground=self.colors["text"])
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 10), padding=(18, 11))
        style.map("Primary.TButton", background=[("active", self.colors["accent_dark"])])
        style.configure("Secondary.TButton", font=("Segoe UI Semibold", 9), padding=(14, 9))
        style.configure("Workspace.TNotebook.Tab", font=("Segoe UI Semibold", 10), padding=(16, 10))

    def _build_layout(self) -> None:
        shell = tk.Frame(self.root, bg=self.colors["bg"], padx=18, pady=18)
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        self._build_header(shell).grid(row=0, column=0, sticky="ew")
        body = tk.Frame(shell, bg=self.colors["bg"])
        body.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        body.grid_columnconfigure(0, minsize=370)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self._build_sidebar(body).grid(row=0, column=0, sticky="nsew")
        self._build_workspace(body).grid(row=0, column=1, sticky="nsew", padx=(16, 0))

    def _build_header(self, parent: tk.Widget) -> tk.Frame:
        card, inner = self._card(parent, padding=(22, 20))
        inner.grid_columnconfigure(0, weight=1)
        tk.Label(inner, text="Future News Forecaster", bg=self.colors["panel"], fg=self.colors["text"], font=("Segoe UI Semibold", 23)).grid(row=0, column=0, sticky="w")
        tk.Label(inner, text="Прогнозирует, как конкретное издание оформит ожидаемый инфоповод, и сразу показывает результат.", bg=self.colors["panel"], fg=self.colors["muted"], font=("Segoe UI", 10), wraplength=700, justify="left").grid(row=1, column=0, sticky="w", pady=(6, 0))
        pill = tk.Frame(inner, bg=self.colors["accent_soft"], padx=14, pady=12)
        pill.grid(row=0, column=1, rowspan=2, sticky="e")
        tk.Label(pill, text="Pipeline", bg=self.colors["accent_soft"], fg=self.colors["accent_dark"], font=("Segoe UI Semibold", 10)).pack(anchor="w")
        tk.Label(pill, text="collect -> score -> retrieve -> draft -> rerank", bg=self.colors["accent_soft"], fg=self.colors["text"], font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))
        return card

    def _build_sidebar(self, parent: tk.Widget) -> tk.Frame:
        shell = tk.Frame(parent, bg=self.colors["bg"])
        shell.grid_rowconfigure(0, weight=1)
        shell.grid_columnconfigure(0, weight=1)
        self.sidebar_canvas = tk.Canvas(shell, bg=self.colors["bg"], borderwidth=0, highlightthickness=0, width=380)
        scroll = ttk.Scrollbar(shell, orient="vertical", command=self.sidebar_canvas.yview)
        self.sidebar_canvas.configure(yscrollcommand=scroll.set)
        self.sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        content = tk.Frame(self.sidebar_canvas, bg=self.colors["bg"])
        self.sidebar_window_id = self.sidebar_canvas.create_window((0, 0), window=content, anchor="nw", width=380)
        content.bind("<Configure>", lambda _e: self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all")))
        self.sidebar_canvas.bind("<Configure>", lambda e: self.sidebar_canvas.itemconfigure(self.sidebar_window_id, width=e.width))
        self.sidebar_canvas.bind("<Enter>", lambda _e: self.root.bind_all("<MouseWheel>", self._on_sidebar_mousewheel))
        self.sidebar_canvas.bind("<Leave>", lambda _e: self.root.unbind_all("<MouseWheel>"))

        key_card, key_inner = self._card(content)
        key_card.pack(fill="x")
        self._title(key_inner, "Ключ OpenAI").pack(anchor="w")
        self._hint(key_inner, "Вставка: Ctrl+V, Shift+Insert или правый клик. Ключ сохраняется в `.env`.").pack(anchor="w", pady=(6, 12))
        self.key_entry = ttk.Entry(key_inner, textvariable=self.api_key_var, show="*")
        self.key_entry.pack(fill="x")
        self._install_key_bindings()
        row = tk.Frame(key_inner, bg=self.colors["panel"])
        row.pack(fill="x", pady=(12, 0))
        row.grid_columnconfigure(0, weight=1)
        ttk.Checkbutton(row, text="Показать ключ", variable=self.show_key_var, command=lambda: self.key_entry.configure(show="" if self.show_key_var.get() else "*")).grid(row=0, column=0, sticky="w")
        ttk.Button(row, text="Сохранить ключ", style="Secondary.TButton", command=self._save_key).grid(row=0, column=1, sticky="e")

        settings_card, settings_inner = self._card(content)
        settings_card.pack(fill="x", pady=(14, 0))
        self._title(settings_inner, "Параметры запуска").pack(anchor="w")
        self._hint(settings_inner, "Если тем для издания не окажется, смотри вкладку «Отбор тем».").pack(anchor="w", pady=(6, 12))
        self._field(settings_inner, "Провайдер"); box = ttk.Combobox(settings_inner, textvariable=self.provider_var, state="readonly", values=["auto", "openai", "mock"]); box.pack(fill="x"); box.bind("<<ComboboxSelected>>", self._sync_provider_hint)
        tk.Label(settings_inner, textvariable=self.provider_hint_var, bg=self.colors["panel"], fg=self.colors["muted"], font=("Segoe UI", 9), wraplength=300, justify="left").pack(anchor="w", pady=(8, 12))
        ttk.Checkbutton(settings_inner, text="Веб-поиск для OpenAI", variable=self.web_search_var).pack(anchor="w")
        self._field(settings_inner, "Модель"); ttk.Entry(settings_inner, textvariable=self.model_var).pack(fill="x")
        duo = tk.Frame(settings_inner, bg=self.colors["panel"]); duo.pack(fill="x", pady=(12, 0)); duo.grid_columnconfigure(0, weight=1); duo.grid_columnconfigure(1, weight=1)
        left = tk.Frame(duo, bg=self.colors["panel"]); left.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        right = tk.Frame(duo, bg=self.colors["panel"]); right.grid(row=0, column=1, sticky="ew")
        self._field(left, "Дата"); ttk.Entry(left, textvariable=self.date_var).pack(fill="x")
        self._field(right, "Количество прогнозов"); ttk.Spinbox(right, from_=1, to=10, textvariable=self.limit_var).pack(fill="x")
        self._field(settings_inner, "Издание"); ttk.Entry(settings_inner, textvariable=self.outlet_var).pack(fill="x")
        tk.Label(
            settings_inner,
            textvariable=self.outlet_hint_var,
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
            wraplength=300,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))
        self._field(settings_inner, "Папка результатов"); ttk.Entry(settings_inner, textvariable=self.out_dir_var).pack(fill="x")
        ttk.Checkbutton(settings_inner, text="Offline режим без live-коллекторов", variable=self.offline_var).pack(anchor="w", pady=(12, 0))

        actions_card, actions_inner = self._card(content)
        actions_card.pack(fill="x", pady=(14, 0))
        self._title(actions_inner, "Действия").pack(anchor="w")
        self._hint(actions_inner, "Ctrl+Enter запускает прогноз.").pack(anchor="w", pady=(6, 12))
        self.run_button = ttk.Button(actions_inner, text="Запустить прогноз", style="Primary.TButton", command=self._start_run)
        self.run_button.pack(fill="x")
        ttk.Button(actions_inner, text="Открыть папку результатов", style="Secondary.TButton", command=self._open_results_dir).pack(fill="x", pady=(10, 0))
        ttk.Button(actions_inner, text="Открыть пояснения проекта", command=self._open_concept_dir).pack(fill="x", pady=(8, 0))
        return shell

    def _build_workspace(self, parent: tk.Widget) -> tk.Frame:
        workspace = tk.Frame(parent, bg=self.colors["bg"])
        workspace.grid_rowconfigure(1, weight=1)
        workspace.grid_columnconfigure(0, weight=1)
        status_card, status_inner = self._card(workspace, padding=(18, 16))
        status_card.grid(row=0, column=0, sticky="ew")
        status_inner.grid_columnconfigure(1, weight=1)
        self.status_badge = tk.Label(status_inner, textvariable=self.status_badge_var, bg=self.colors["idle_bg"], fg=self.colors["idle_fg"], font=("Segoe UI Semibold", 9), padx=12, pady=6)
        self.status_badge.grid(row=0, column=0, sticky="nw")
        tk.Label(status_inner, textvariable=self.status_var, bg=self.colors["panel"], fg=self.colors["text"], font=("Segoe UI", 10), wraplength=700, justify="left").grid(row=0, column=1, sticky="w", padx=(14, 0))
        box, inner = self._card(workspace, padding=(0, 0))
        box.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        inner.grid_rowconfigure(0, weight=1); inner.grid_columnconfigure(0, weight=1)
        self.preview_notebook = ttk.Notebook(inner, style="Workspace.TNotebook"); self.preview_notebook.grid(row=0, column=0, sticky="nsew")
        self.results_tab = tk.Frame(self.preview_notebook, bg=self.colors["paper"])
        self.filter_tab = tk.Frame(self.preview_notebook, bg=self.colors["paper"])
        self.log_tab = tk.Frame(self.preview_notebook, bg=self.colors["paper"])
        self.idea_tab = tk.Frame(self.preview_notebook, bg=self.colors["paper"])
        self.preview_notebook.add(self.results_tab, text="Прогнозы")
        self.preview_notebook.add(self.filter_tab, text="Отбор тем")
        self.preview_notebook.add(self.log_tab, text="Лог")
        self.preview_notebook.add(self.idea_tab, text="Идея проекта")
        self.results_widget = self._text_surface(self.results_tab, "После запуска здесь появятся прогнозы.")
        self.filter_widget = self._text_surface(self.filter_tab, "Здесь появится объяснение, почему темы прошли или не прошли фильтр издания.")
        self.log_widget = self._text_surface(self.log_tab, "Лог запуска появится здесь.", mono=True)
        self.idea_widget = self._text_surface(self.idea_tab, self._load_project_concept())
        return workspace

    def _card(self, parent: tk.Widget, *, padding: tuple[int, int] = (18, 18)) -> tuple[tk.Frame, tk.Frame]:
        border = tk.Frame(parent, bg=self.colors["border"], bd=0, highlightthickness=0)
        inner = tk.Frame(border, bg=self.colors["panel"], padx=padding[0], pady=padding[1])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        return border, inner

    def _title(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=self.colors["panel"], fg=self.colors["text"], font=("Segoe UI Semibold", 12))

    def _hint(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=self.colors["panel"], fg=self.colors["muted"], font=("Segoe UI", 9), wraplength=300, justify="left")

    def _field(self, parent: tk.Widget, text: str) -> None:
        tk.Label(parent, text=text, bg=self.colors["panel"], fg=self.colors["text"], font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(12, 6))

    def _text_surface(self, parent: tk.Widget, initial: str, *, mono: bool = False) -> tk.Text:
        parent.grid_rowconfigure(0, weight=1); parent.grid_columnconfigure(0, weight=1)
        shell = tk.Frame(parent, bg=self.colors["paper"], padx=16, pady=16); shell.grid(row=0, column=0, sticky="nsew")
        shell.grid_rowconfigure(0, weight=1); shell.grid_columnconfigure(0, weight=1)
        widget = tk.Text(shell, wrap="word", relief="flat", borderwidth=0, background=self.colors["paper"], foreground=self.colors["text"], selectbackground=self.colors["accent_soft"], insertbackground=self.colors["text"], font=("Consolas", 10) if mono else ("Segoe UI", 11))
        scroll = ttk.Scrollbar(shell, orient="vertical", command=widget.yview); widget.configure(yscrollcommand=scroll.set)
        widget.grid(row=0, column=0, sticky="nsew"); scroll.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        self._set_text(widget, initial)
        return widget

    def _install_key_bindings(self) -> None:
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Вставить", command=self._paste_from_clipboard)
        menu.add_command(label="Очистить", command=self._clear_api_key)
        self.key_menu = menu
        if self.key_entry is None:
            return
        self.key_entry.bind("<Control-v>", lambda _e: self._paste_from_clipboard() or "break")
        self.key_entry.bind("<Control-V>", lambda _e: self._paste_from_clipboard() or "break")
        self.key_entry.bind("<Shift-Insert>", lambda _e: self._paste_from_clipboard() or "break")
        self.key_entry.bind("<Button-3>", self._show_key_menu)

    def _show_key_menu(self, event: tk.Event) -> str:
        self.key_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _paste_from_clipboard(self) -> None:
        try:
            value = self.root.clipboard_get().strip()
        except tk.TclError:
            messagebox.showwarning("Буфер пуст", "Не удалось получить текст из буфера обмена.")
            return
        if not value:
            messagebox.showwarning("Буфер пуст", "В буфере обмена нет текста для вставки.")
            return
        self.api_key_var.set(value)
        if self.key_entry is not None:
            self.key_entry.focus_set()
            self.key_entry.icursor("end")
        self._set_status("idle", "Ключ вставлен в поле. Теперь сохраните его в .env.")

    def _save_key(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Ключ не введен", "Введите OpenAI API key перед сохранением.")
            return
        path = save_openai_api_key(api_key)
        self._set_status("success", f"Ключ сохранен в {path}")
        self._append_log(f"OPENAI_API_KEY сохранен в {path}")

    def _clear_api_key(self) -> None:
        self.api_key_var.set("")

    def _sync_provider_hint(self, _event: tk.Event | None = None) -> None:
        hints = {
            "auto": "Сначала попробует OpenAI, а если ключа нет или API недоступен, перейдет на mock.",
            "openai": "Использует API OpenAI. Для этого режима нужен сохраненный ключ.",
            "mock": "Полностью локальный режим для проверки pipeline.",
        }
        self.provider_hint_var.set(hints.get(self.provider_var.get().strip(), ""))

    def _sync_outlet_hint(self, *_args) -> None:
        outlet = self.outlet_var.get().strip().lower()
        if outlet in {"reuters", "bloomberg", "financial times", "ft", "associated press", "ap"}:
            text = (
                "Лучше всего текущая версия работает для деловых агентств и экономических редакций. "
                "Подключенные календари хорошо подходят для такого типа СМИ."
            )
        elif outlet in {"медуза", "meduza"}:
            text = (
                "Для selective-изданий вроде Медузы рутинные UK/US релизы часто будут отсеяны. "
                "На некоторых датах мало тем или 0 кандидатов — это нормальный результат."
            )
        else:
            text = (
                "Сейчас продукт лучше всего подходит для деловых и экономических СМИ, например Reuters, Bloomberg или FT. "
                "Для general news, локальных, lifestyle и части политических редакций тем может не быть."
            )
        self.outlet_hint_var.set(text)

    def _start_run(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Запуск уже идет", "Дождитесь завершения текущего запуска.")
            return
        provider = self.provider_var.get().strip()
        key = self.api_key_var.get().strip()
        if provider == "openai" and not key:
            messagebox.showerror("Нужен ключ", "Для режима openai сначала введите ключ и сохраните его.")
            return
        if key:
            save_openai_api_key(key)
        try:
            target_date = date.fromisoformat(self.date_var.get().strip())
            limit = int(self.limit_var.get().strip())
        except ValueError as exc:
            messagebox.showerror("Неверные параметры", f"Проверьте дату и количество: {exc}")
            return
        payload = {
            "target_date": target_date,
            "limit": limit,
            "provider": provider,
            "model": self.model_var.get().strip() or "gpt-5-mini",
            "outlet": self.outlet_var.get().strip() or "Reuters",
            "out_dir": Path(self.out_dir_var.get().strip() or "results/gui-run"),
            "offline": self.offline_var.get(),
            "web_search": self.web_search_var.get(),
        }
        self._set_run_state(True)
        self._set_status("running", "Строю прогноз: собираю события, считаю fit и готовлю результат.")
        self._append_log("Старт прогноза")
        self.worker = threading.Thread(target=self._run_pipeline, args=(payload,), daemon=True)
        self.worker.start()

    def _run_pipeline(self, payload: dict[str, object]) -> None:
        try:
            pipeline = build_pipeline(outlet=str(payload["outlet"]), provider=str(payload["provider"]), model=str(payload["model"]), archive_dir=Path("data/archives"), web_search_enabled=bool(payload["web_search"]))
            run = pipeline.run(target_date=payload["target_date"], limit=int(payload["limit"]), offline=bool(payload["offline"]))
            out_dir = Path(payload["out_dir"]); write_run_artifacts(run, out_dir)
            self.queue.put(("success", run, out_dir))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, *payload = self.queue.get_nowait()
                if str(kind) == "success":
                    self._handle_success(payload[0], payload[1])
                else:
                    self._set_status("error", "Запуск завершился ошибкой. Подробности см. на вкладке «Лог».")
                    self._append_log(f"Ошибка: {payload[0]}")
                    if self.preview_notebook and self.log_tab:
                        self.preview_notebook.select(self.log_tab)
                    self._set_run_state(False)
        except Empty:
            pass
        finally:
            self.root.after(150, self._poll_queue)

    def _handle_success(self, run, out_dir: Path) -> None:
        status = (
            f"Готово: {len(run.candidates)} кандидатов, провайдер={run.provider}, результаты: {out_dir}"
            if run.candidates
            else f"Готово: подходящих тем для издания не найдено. Смотрите вкладку «Отбор тем». Результаты: {out_dir}"
        )
        self._set_status("success", status)
        if self.results_widget:
            self._set_text(self.results_widget, render_markdown(run))
        if self.filter_widget:
            self._set_text(self.filter_widget, render_editorial_report(run))
        if self.preview_notebook:
            self.preview_notebook.select(self.results_tab if run.candidates else self.filter_tab)
        self._append_log(f"Готово. Собрано событий: {len(run.collected_events)}. Финальных кандидатов: {len(run.candidates)}.")
        for warning in run.warnings:
            self._append_log(f"Предупреждение: {warning}")
        self._set_run_state(False)

    def _set_status(self, kind: str, text: str) -> None:
        self.status_var.set(text)
        badges = {
            "idle": ("ГОТОВО", self.colors["idle_bg"], self.colors["idle_fg"]),
            "running": ("РАБОТАЕТ", self.colors["running_bg"], self.colors["running_fg"]),
            "success": ("ГОТОВО", self.colors["success_bg"], self.colors["success_fg"]),
            "error": ("ОШИБКА", self.colors["error_bg"], self.colors["error_fg"]),
        }
        label, bg, fg = badges[kind]
        self.status_badge_var.set(label)
        if self.status_badge:
            self.status_badge.configure(bg=bg, fg=fg)

    def _set_run_state(self, running: bool) -> None:
        if self.run_button:
            self.run_button.configure(state="disabled" if running else "normal", text="Прогноз строится..." if running else "Запустить прогноз")

    def _append_log(self, text: str) -> None:
        if self.log_widget:
            self.log_widget.configure(state="normal")
            self.log_widget.insert("end", text + "\n")
            self.log_widget.see("end")
            self.log_widget.configure(state="disabled")

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", self._plain(text))
        widget.configure(state="disabled")

    def _plain(self, text: str) -> str:
        lines = []
        for raw in text.splitlines():
            line = re.sub(r"^#{1,6}\s*", "", raw.rstrip())
            line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            line = re.sub(r"\*(.*?)\*", r"\1", line)
            line = re.sub(r"`([^`]*)`", r"\1", line)
            lines.append(line)
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"

    def _on_sidebar_mousewheel(self, event: tk.Event) -> str:
        if self.sidebar_canvas:
            self.sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _open_results_dir(self) -> None:
        out_dir = Path(self.out_dir_var.get().strip() or "results/gui-run").resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(out_dir)

    def _open_concept_dir(self) -> None:
        path = Path(__file__).resolve().parents[2] / "docs" / "project-concept"
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)

    def _load_project_concept(self) -> str:
        base = Path(__file__).resolve().parents[2] / "docs" / "project-concept"
        parts = []
        for name in ["README.md", "principles.md"]:
            file_path = base / name
            if file_path.exists():
                parts.append(file_path.read_text(encoding="utf-8").strip())
        return "\n\n".join(parts) + "\n" if parts else "Пояснения о проекте пока не найдены."


def launch_gui() -> None:
    root = tk.Tk()
    ForecastApp(root)
    root.mainloop()
