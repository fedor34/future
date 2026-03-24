from __future__ import annotations

import os
import re
import threading
from datetime import date
from pathlib import Path
from queue import Empty, SimpleQueue
import tkinter as tk
from tkinter import messagebox, ttk

from .pipeline import build_pipeline, render_markdown, write_run_artifacts
from .settings import current_openai_api_key, default_env_path, save_openai_api_key


class ForecastApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Future News Forecaster")
        self.root.geometry("1260x820")
        self.root.minsize(1080, 720)

        self.palette = {
            "bg": "#F3EFE8",
            "panel": "#FBF8F2",
            "paper": "#FFFDFC",
            "accent": "#0F766E",
            "accent_dark": "#115E59",
            "accent_soft": "#D7EFE8",
            "border": "#D6CEC2",
            "text": "#1F2933",
            "muted": "#6B7280",
            "log_bg": "#F9F6F0",
            "success_bg": "#DCFCE7",
            "success_fg": "#166534",
            "running_bg": "#DBEAFE",
            "running_fg": "#1D4ED8",
            "error_bg": "#FEE2E2",
            "error_fg": "#B91C1C",
            "idle_bg": "#E7E5E4",
            "idle_fg": "#44403C",
        }

        self.queue: SimpleQueue[tuple[object, ...]] = SimpleQueue()
        self.worker: threading.Thread | None = None

        saved_key = current_openai_api_key() or ""
        if saved_key:
            initial_status = (
                f"Ключ уже найден в {default_env_path()}. "
                "Можно сразу запускать прогноз или обновить ключ в поле слева."
            )
        else:
            initial_status = (
                f"Ключ хранится в {default_env_path()}. "
                "Вставьте его через Ctrl+V, Shift+Insert или правый клик и сохраните."
            )

        self.api_key_var = tk.StringVar(value=saved_key)
        self.provider_var = tk.StringVar(value="auto")
        self.model_var = tk.StringVar(value="gpt-5-mini")
        self.date_var = tk.StringVar(value="2026-04-02")
        self.outlet_var = tk.StringVar(value="Reuters")
        self.limit_var = tk.StringVar(value="5")
        self.out_dir_var = tk.StringVar(value="results/gui-run")
        self.offline_var = tk.BooleanVar(value=False)
        self.web_search_var = tk.BooleanVar(value=True)
        self.show_key_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value=initial_status)
        self.status_badge_var = tk.StringVar(value="ГОТОВО")
        self.provider_hint_var = tk.StringVar()

        self.status_badge: tk.Label | None = None
        self.run_button: ttk.Button | None = None
        self.key_entry: ttk.Entry | None = None
        self.log_widget: tk.Text | None = None
        self.results_widget: tk.Text | None = None
        self.idea_widget: tk.Text | None = None
        self.sidebar_canvas: tk.Canvas | None = None
        self.sidebar_content: tk.Frame | None = None
        self._sidebar_window_id: int | None = None

        self._configure_root()
        self._configure_styles()
        self._build_layout()
        self._install_global_bindings()
        self._sync_provider_hint()
        self._set_status("idle", initial_status)
        self.root.after(150, self._poll_queue)

    def _configure_root(self) -> None:
        self.root.configure(bg=self.palette["bg"])

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(
            ".",
            font=("Segoe UI", 10),
            background=self.palette["panel"],
            foreground=self.palette["text"],
        )
        style.configure(
            "Primary.TButton",
            font=("Segoe UI Semibold", 10),
            padding=(18, 11),
            background=self.palette["accent"],
            foreground="#FFFFFF",
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Primary.TButton",
            background=[
                ("active", self.palette["accent_dark"]),
                ("pressed", self.palette["accent_dark"]),
                ("disabled", self.palette["border"]),
            ],
            foreground=[("disabled", "#F8FAFC")],
        )
        style.configure(
            "Secondary.TButton",
            font=("Segoe UI Semibold", 9),
            padding=(14, 9),
            background=self.palette["accent_soft"],
            foreground=self.palette["text"],
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("active", "#C7E6DD"),
                ("pressed", "#C7E6DD"),
                ("disabled", self.palette["border"]),
            ]
        )
        style.configure(
            "Muted.TButton",
            font=("Segoe UI", 9),
            padding=(12, 8),
            background=self.palette["panel"],
            foreground=self.palette["text"],
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "Muted.TButton",
            background=[
                ("active", self.palette["paper"]),
                ("pressed", self.palette["paper"]),
            ]
        )
        style.configure("TCheckbutton", background=self.palette["panel"], foreground=self.palette["text"])
        style.map("TCheckbutton", background=[("active", self.palette["panel"])])
        style.configure(
            "Workspace.TNotebook",
            background=self.palette["panel"],
            borderwidth=0,
            tabmargins=(0, 0, 0, 0),
        )
        style.configure(
            "Workspace.TNotebook.Tab",
            font=("Segoe UI Semibold", 10),
            padding=(18, 10),
            background=self.palette["bg"],
            foreground=self.palette["muted"],
            borderwidth=0,
        )
        style.map(
            "Workspace.TNotebook.Tab",
            background=[
                ("selected", self.palette["paper"]),
                ("active", self.palette["accent_soft"]),
            ],
            foreground=[
                ("selected", self.palette["text"]),
                ("active", self.palette["text"]),
            ],
        )

    def _build_layout(self) -> None:
        container = tk.Frame(self.root, bg=self.palette["bg"], padx=18, pady=18)
        container.pack(fill="both", expand=True)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        self._build_header(container).grid(row=0, column=0, sticky="ew")

        body = tk.Frame(container, bg=self.palette["bg"])
        body.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        body.grid_columnconfigure(0, minsize=360)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_sidebar_shell(body).grid(row=0, column=0, sticky="nsew")
        self._build_workspace(body).grid(row=0, column=1, sticky="nsew", padx=(16, 0))

    def _build_header(self, parent: tk.Widget) -> tk.Frame:
        card, content = self._make_card(parent, padding=(22, 20))
        content.grid_columnconfigure(0, weight=1)

        title = tk.Label(
            content,
            text="Future News Forecaster",
            bg=self.palette["panel"],
            fg=self.palette["text"],
            font=("Segoe UI Semibold", 23),
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = tk.Label(
            content,
            text=(
                "Сервис не угадывает новости «из воздуха», а строит аккуратный прогноз для заранее "
                "известных событий и сразу показывает результат в приложении."
            ),
            bg=self.palette["panel"],
            fg=self.palette["muted"],
            font=("Segoe UI", 10),
            justify="left",
            wraplength=700,
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(6, 0))

        highlight = tk.Frame(content, bg=self.palette["accent_soft"], padx=14, pady=12)
        highlight.grid(row=0, column=1, rowspan=2, sticky="e")

        highlight_title = tk.Label(
            highlight,
            text="Pipeline",
            bg=self.palette["accent_soft"],
            fg=self.palette["accent_dark"],
            font=("Segoe UI Semibold", 10),
        )
        highlight_title.pack(anchor="w")

        highlight_text = tk.Label(
            highlight,
            text="collect -> score -> retrieve -> draft -> rerank",
            bg=self.palette["accent_soft"],
            fg=self.palette["text"],
            font=("Segoe UI", 10),
        )
        highlight_text.pack(anchor="w", pady=(4, 0))

        return card

    def _build_sidebar_shell(self, parent: tk.Widget) -> tk.Frame:
        shell = tk.Frame(parent, bg=self.palette["bg"])
        shell.grid_rowconfigure(0, weight=1)
        shell.grid_columnconfigure(0, weight=1)

        self.sidebar_canvas = tk.Canvas(
            shell,
            background=self.palette["bg"],
            highlightthickness=0,
            borderwidth=0,
            width=372,
        )
        sidebar_scrollbar = ttk.Scrollbar(shell, orient="vertical", command=self.sidebar_canvas.yview)
        self.sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)

        self.sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        sidebar_scrollbar.grid(row=0, column=1, sticky="ns", padx=(10, 0))

        self.sidebar_content = tk.Frame(self.sidebar_canvas, bg=self.palette["bg"])
        self._sidebar_window_id = self.sidebar_canvas.create_window(
            (0, 0),
            window=self.sidebar_content,
            anchor="nw",
            width=372,
        )

        self.sidebar_content.bind("<Configure>", self._sync_sidebar_scrollregion)
        self.sidebar_canvas.bind("<Configure>", self._resize_sidebar_content)
        self.sidebar_canvas.bind("<Enter>", self._bind_sidebar_mousewheel)
        self.sidebar_canvas.bind("<Leave>", self._unbind_sidebar_mousewheel)

        self._build_sidebar(self.sidebar_content)
        return shell

    def _build_sidebar(self, parent: tk.Widget) -> tk.Frame:
        sidebar = tk.Frame(parent, bg=self.palette["bg"])
        sidebar.pack(fill="both", expand=True)

        key_card, key_content = self._make_card(sidebar)
        key_card.pack(fill="x", anchor="n")
        self._section_title(key_content, "Ключ OpenAI").pack(anchor="w")
        self._section_hint(
            key_content,
            "Вставка работает через Ctrl+V, Shift+Insert и правый клик. Ключ сохраняется в `.env`.",
        ).pack(anchor="w", pady=(6, 12))

        self.key_entry = ttk.Entry(key_content, textvariable=self.api_key_var, show="*")
        self.key_entry.pack(fill="x")
        self._install_key_entry_bindings()

        key_actions = tk.Frame(key_content, bg=self.palette["panel"])
        key_actions.pack(fill="x", pady=(12, 0))
        key_actions.grid_columnconfigure(0, weight=1)

        ttk.Checkbutton(
            key_actions,
            text="Показать ключ",
            variable=self.show_key_var,
            command=self._toggle_key_visibility,
        ).grid(row=0, column=0, sticky="w")

        ttk.Button(
            key_actions,
            text="Сохранить ключ",
            style="Secondary.TButton",
            command=self._save_key,
        ).grid(row=0, column=1, sticky="e")

        env_label = tk.Label(
            key_content,
            text=f"Файл ключа: {default_env_path()}",
            bg=self.palette["panel"],
            fg=self.palette["muted"],
            font=("Segoe UI", 9),
            justify="left",
            wraplength=290,
        )
        env_label.pack(anchor="w", pady=(10, 0))

        settings_card, settings_content = self._make_card(sidebar)
        settings_card.pack(fill="x", anchor="n", pady=(14, 0))
        self._section_title(settings_content, "Параметры запуска").pack(anchor="w")
        self._section_hint(
            settings_content,
            "Все результаты сохраняются в папку, но справа ты сразу видишь сгенерированный прогноз.",
        ).pack(anchor="w", pady=(6, 14))

        self._field(settings_content, "Провайдер")
        provider_box = ttk.Combobox(
            settings_content,
            textvariable=self.provider_var,
            state="readonly",
            values=["auto", "openai", "mock"],
        )
        provider_box.pack(fill="x")
        provider_box.bind("<<ComboboxSelected>>", self._sync_provider_hint)

        provider_hint = tk.Label(
            settings_content,
            textvariable=self.provider_hint_var,
            bg=self.palette["panel"],
            fg=self.palette["muted"],
            font=("Segoe UI", 9),
            justify="left",
            wraplength=290,
        )
        provider_hint.pack(anchor="w", pady=(8, 12))

        ttk.Checkbutton(
            settings_content,
            text="Веб-поиск для OpenAI",
            variable=self.web_search_var,
        ).pack(anchor="w")

        web_search_hint = tk.Label(
            settings_content,
            text="Работает только для OpenAI и auto. Для mock-режима эта опция игнорируется.",
            bg=self.palette["panel"],
            fg=self.palette["muted"],
            font=("Segoe UI", 9),
            justify="left",
            wraplength=290,
        )
        web_search_hint.pack(anchor="w", pady=(6, 0))

        self._field(settings_content, "Модель")
        ttk.Entry(settings_content, textvariable=self.model_var).pack(fill="x")

        compact_row = tk.Frame(settings_content, bg=self.palette["panel"])
        compact_row.pack(fill="x", pady=(12, 0))
        compact_row.grid_columnconfigure(0, weight=1)
        compact_row.grid_columnconfigure(1, weight=1)

        date_wrap = tk.Frame(compact_row, bg=self.palette["panel"])
        date_wrap.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._field(date_wrap, "Дата").pack(anchor="w")
        ttk.Entry(date_wrap, textvariable=self.date_var).pack(fill="x")

        limit_wrap = tk.Frame(compact_row, bg=self.palette["panel"])
        limit_wrap.grid(row=0, column=1, sticky="ew")
        self._field(limit_wrap, "Количество прогнозов").pack(anchor="w")
        ttk.Spinbox(limit_wrap, from_=1, to=10, textvariable=self.limit_var, width=8).pack(fill="x")

        self._field(settings_content, "Издание")
        ttk.Entry(settings_content, textvariable=self.outlet_var).pack(fill="x")

        self._field(settings_content, "Папка результатов")
        ttk.Entry(settings_content, textvariable=self.out_dir_var).pack(fill="x")

        ttk.Checkbutton(
            settings_content,
            text="Offline режим без live-коллекторов",
            variable=self.offline_var,
        ).pack(anchor="w", pady=(14, 0))

        actions_card, actions_content = self._make_card(sidebar)
        actions_card.pack(fill="x", anchor="n", pady=(14, 0))
        self._section_title(actions_content, "Действия").pack(anchor="w")
        self._section_hint(
            actions_content,
            "Ctrl+Enter запускает прогноз. После генерации приложение само переключится на вкладку с результатом.",
        ).pack(anchor="w", pady=(6, 14))

        self.run_button = ttk.Button(
            actions_content,
            text="Запустить прогноз",
            style="Primary.TButton",
            command=self._start_run,
        )
        self.run_button.pack(fill="x")

        ttk.Button(
            actions_content,
            text="Открыть папку результатов",
            style="Secondary.TButton",
            command=self._open_results_dir,
        ).pack(fill="x", pady=(10, 0))

        ttk.Button(
            actions_content,
            text="Открыть пояснения проекта",
            style="Muted.TButton",
            command=self._open_concept_dir,
        ).pack(fill="x", pady=(8, 0))

        return sidebar

    def _build_workspace(self, parent: tk.Widget) -> tk.Frame:
        workspace = tk.Frame(parent, bg=self.palette["bg"])
        workspace.grid_rowconfigure(1, weight=1)
        workspace.grid_columnconfigure(0, weight=1)

        status_card, status_content = self._make_card(workspace, padding=(18, 16))
        status_card.grid(row=0, column=0, sticky="ew")
        status_content.grid_columnconfigure(1, weight=1)

        self.status_badge = tk.Label(
            status_content,
            textvariable=self.status_badge_var,
            bg=self.palette["idle_bg"],
            fg=self.palette["idle_fg"],
            font=("Segoe UI Semibold", 9),
            padx=12,
            pady=6,
        )
        self.status_badge.grid(row=0, column=0, sticky="nw")

        status_text = tk.Label(
            status_content,
            textvariable=self.status_var,
            bg=self.palette["panel"],
            fg=self.palette["text"],
            font=("Segoe UI", 10),
            justify="left",
            wraplength=700,
        )
        status_text.grid(row=0, column=1, sticky="w", padx=(14, 0))

        notebook_shell, notebook_content = self._make_card(workspace, padding=(0, 0), bg_key="panel")
        notebook_shell.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        notebook_content.grid_rowconfigure(0, weight=1)
        notebook_content.grid_columnconfigure(0, weight=1)

        self.preview_notebook = ttk.Notebook(notebook_content, style="Workspace.TNotebook")
        self.preview_notebook.grid(row=0, column=0, sticky="nsew")

        self.results_tab = tk.Frame(self.preview_notebook, bg=self.palette["paper"])
        self.log_tab = tk.Frame(self.preview_notebook, bg=self.palette["paper"])
        self.idea_tab = tk.Frame(self.preview_notebook, bg=self.palette["paper"])

        self.preview_notebook.add(self.results_tab, text="Прогнозы")
        self.preview_notebook.add(self.log_tab, text="Лог")
        self.preview_notebook.add(self.idea_tab, text="Идея проекта")

        self.results_widget = self._build_text_surface(
            self.results_tab,
            "После запуска здесь появятся headline, lead и краткая логика по каждому прогнозу.",
        )
        self.log_widget = self._build_text_surface(
            self.log_tab,
            "Лог запуска появится здесь. Пока приложение готово к работе.",
            mono=True,
        )
        self.idea_widget = self._build_text_surface(
            self.idea_tab,
            self._load_project_concept(),
        )

        return workspace

    def _make_card(
        self,
        parent: tk.Widget,
        *,
        padding: tuple[int, int] = (18, 18),
        bg_key: str = "panel",
    ) -> tuple[tk.Frame, tk.Frame]:
        border = tk.Frame(parent, bg=self.palette["border"], bd=0, highlightthickness=0)
        inner = tk.Frame(border, bg=self.palette[bg_key], padx=padding[0], pady=padding[1])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        return border, inner

    def _section_title(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=self.palette["panel"],
            fg=self.palette["text"],
            font=("Segoe UI Semibold", 12),
        )

    def _section_hint(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=self.palette["panel"],
            fg=self.palette["muted"],
            font=("Segoe UI", 9),
            justify="left",
            wraplength=290,
        )

    def _field(self, parent: tk.Widget, text: str) -> tk.Label:
        label = tk.Label(
            parent,
            text=text,
            bg=self.palette["panel"],
            fg=self.palette["text"],
            font=("Segoe UI Semibold", 9),
        )
        label.pack(anchor="w", pady=(12, 6))
        return label

    def _build_text_surface(self, parent: tk.Widget, initial_text: str, *, mono: bool = False) -> tk.Text:
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        shell = tk.Frame(parent, bg=self.palette["paper"], padx=16, pady=16)
        shell.grid(row=0, column=0, sticky="nsew")
        shell.grid_rowconfigure(0, weight=1)
        shell.grid_columnconfigure(0, weight=1)

        text = tk.Text(
            shell,
            wrap="word",
            relief="flat",
            borderwidth=0,
            background=self.palette["paper"],
            foreground=self.palette["text"],
            selectbackground=self.palette["accent_soft"],
            insertbackground=self.palette["text"],
            padx=4,
            pady=4,
            spacing1=2,
            spacing3=3,
            font=("Consolas", 10) if mono else ("Segoe UI", 11),
        )
        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(10, 0))

        self._set_text_widget(text, initial_text)
        return text

    def _sync_sidebar_scrollregion(self, _event: tk.Event | None = None) -> None:
        if self.sidebar_canvas is not None:
            self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

    def _resize_sidebar_content(self, event: tk.Event) -> None:
        if self.sidebar_canvas is not None and self._sidebar_window_id is not None:
            self.sidebar_canvas.itemconfigure(self._sidebar_window_id, width=event.width)

    def _bind_sidebar_mousewheel(self, _event: tk.Event | None = None) -> None:
        self.root.bind_all("<MouseWheel>", self._on_sidebar_mousewheel)

    def _unbind_sidebar_mousewheel(self, _event: tk.Event | None = None) -> None:
        self.root.unbind_all("<MouseWheel>")

    def _on_sidebar_mousewheel(self, event: tk.Event) -> str:
        if self.sidebar_canvas is not None:
            self.sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _install_global_bindings(self) -> None:
        self.root.bind("<Control-Return>", self._start_run_event)
        self.root.bind("<Control-KP_Enter>", self._start_run_event)

    def _toggle_key_visibility(self) -> None:
        if self.key_entry is not None:
            self.key_entry.configure(show="" if self.show_key_var.get() else "*")

    def _install_key_entry_bindings(self) -> None:
        self.key_menu = tk.Menu(self.root, tearoff=False)
        self.key_menu.add_command(label="Вставить", command=self._paste_api_key_from_clipboard)
        self.key_menu.add_command(label="Очистить", command=self._clear_api_key)

        if self.key_entry is None:
            return

        self.key_entry.bind("<Control-v>", self._paste_api_key)
        self.key_entry.bind("<Control-V>", self._paste_api_key)
        self.key_entry.bind("<Shift-Insert>", self._paste_api_key)
        self.key_entry.bind("<Button-3>", self._show_key_context_menu)

    def _show_key_context_menu(self, event: tk.Event) -> str:
        if self.key_entry is not None:
            self.key_entry.focus_set()
        self.key_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _paste_api_key(self, _event: tk.Event | None = None) -> str:
        self._paste_api_key_from_clipboard()
        return "break"

    def _paste_api_key_from_clipboard(self) -> None:
        try:
            clipboard_text = self.root.clipboard_get()
        except tk.TclError:
            messagebox.showwarning("Буфер пуст", "Не удалось получить текст из буфера обмена.")
            return

        value = clipboard_text.strip()
        if not value:
            messagebox.showwarning("Буфер пуст", "В буфере обмена нет текста для вставки.")
            return

        self.api_key_var.set(value)
        if self.key_entry is not None:
            self.key_entry.focus_set()
            self.key_entry.icursor("end")
        self._set_status("idle", "Ключ вставлен в поле. Нажмите «Сохранить ключ», чтобы записать его в .env.")
        self._append_log("Ключ вставлен из буфера обмена")

    def _clear_api_key(self) -> None:
        self.api_key_var.set("")
        if self.key_entry is not None:
            self.key_entry.focus_set()
        self._set_status("idle", "Поле API key очищено.")

    def _save_key(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Ключ не введен", "Введите OpenAI API key перед сохранением.")
            return
        env_path = save_openai_api_key(api_key)
        self._set_status("success", f"Ключ сохранен в {env_path}")
        self._append_log(f"OPENAI_API_KEY сохранен в {env_path}")

    def _sync_provider_hint(self, _event: tk.Event | None = None) -> None:
        hints = {
            "auto": "Сначала попробует OpenAI, а если ключа нет или API недоступен, перейдет на mock.",
            "openai": "Использует API OpenAI. Для этого режима нужен сохраненный ключ.",
            "mock": "Полностью локальный детерминированный режим для быстрого теста интерфейса и pipeline.",
        }
        self.provider_hint_var.set(hints.get(self.provider_var.get().strip(), ""))

    def _start_run_event(self, _event: tk.Event | None = None) -> str:
        self._start_run()
        return "break"

    def _start_run(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Запуск уже идет", "Дождитесь завершения текущего запуска.")
            return

        provider = self.provider_var.get().strip()
        api_key = self.api_key_var.get().strip()
        if provider == "openai" and not api_key:
            messagebox.showerror(
                "Нужен ключ",
                "Для режима openai сначала введите ключ и нажмите «Сохранить ключ».",
            )
            return

        if api_key:
            save_openai_api_key(api_key)

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
        self._set_status("running", "Строю прогноз: собираю события, считаю кандидатов и готовлю текст.")
        self._append_log("Старт прогноза")
        self.worker = threading.Thread(target=self._run_pipeline, args=(payload,), daemon=True)
        self.worker.start()

    def _set_run_state(self, is_running: bool) -> None:
        if self.run_button is None:
            return
        self.run_button.configure(
            state="disabled" if is_running else "normal",
            text="Прогноз строится..." if is_running else "Запустить прогноз",
        )

    def _run_pipeline(self, payload: dict[str, object]) -> None:
        try:
            pipeline = build_pipeline(
                outlet=str(payload["outlet"]),
                provider=str(payload["provider"]),
                model=str(payload["model"]),
                archive_dir=Path("data/archives"),
                web_search_enabled=bool(payload["web_search"]),
            )
            run = pipeline.run(
                target_date=payload["target_date"],
                limit=int(payload["limit"]),
                offline=bool(payload["offline"]),
            )
            out_dir = Path(payload["out_dir"])
            write_run_artifacts(run, out_dir)
            self.queue.put(("success", run, out_dir))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                message = self.queue.get_nowait()
                kind = str(message[0])
                if kind == "success":
                    run = message[1]
                    out_dir = message[2]
                    self._set_status(
                        "success",
                        (
                            f"Готово: {len(run.candidates)} кандидатов, провайдер={run.provider}, "
                            f"результаты записаны в {out_dir}"
                        ),
                    )
                    if self.results_widget is not None:
                        self._set_text_widget(self.results_widget, render_markdown(run))
                    self.preview_notebook.select(self.results_tab)
                    self._append_log(
                        f"Готово. Собрано событий: {len(run.collected_events)}. "
                        f"Финальных кандидатов: {len(run.candidates)}. "
                        f"Результаты: {out_dir}"
                    )
                    for warning in run.warnings:
                        self._append_log(f"Предупреждение: {warning}")
                    self._set_run_state(False)
                elif kind == "error":
                    self._set_status("error", "Запуск завершился ошибкой. Подробности см. на вкладке «Лог».")
                    self._append_log(f"Ошибка: {message[1]}")
                    self.preview_notebook.select(self.log_tab)
                    self._set_run_state(False)
        except Empty:
            pass
        finally:
            self.root.after(150, self._poll_queue)

    def _set_status(self, kind: str, message: str) -> None:
        self.status_var.set(message)
        badge_tokens = {
            "idle": ("ГОТОВО", self.palette["idle_bg"], self.palette["idle_fg"]),
            "running": ("РАБОТАЕТ", self.palette["running_bg"], self.palette["running_fg"]),
            "success": ("ГОТОВО", self.palette["success_bg"], self.palette["success_fg"]),
            "error": ("ОШИБКА", self.palette["error_bg"], self.palette["error_fg"]),
        }
        text, bg, fg = badge_tokens.get(kind, badge_tokens["idle"])
        self.status_badge_var.set(text)
        if self.status_badge is not None:
            self.status_badge.configure(bg=bg, fg=fg)

    def _append_log(self, message: str) -> None:
        if self.log_widget is None:
            return
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", message + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def _set_text_widget(self, widget: tk.Text, text: str) -> None:
        display_text = self._render_plain_text(text)
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", display_text)
        widget.configure(state="disabled")

    def _render_plain_text(self, text: str) -> str:
        cleaned_lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            line = re.sub(r"^#{1,6}\s*", "", line)
            line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            line = re.sub(r"\*(.*?)\*", r"\1", line)
            line = re.sub(r"`([^`]*)`", r"\1", line)

            if line.startswith("- "):
                line = f"• {line[2:]}"

            cleaned_lines.append(line)

        rendered = "\n".join(cleaned_lines)
        rendered = re.sub(r"\n{3,}", "\n\n", rendered)
        return rendered.strip() + "\n"

    def _open_results_dir(self) -> None:
        out_dir = Path(self.out_dir_var.get().strip() or "results/gui-run").resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(out_dir)

    def _open_concept_dir(self) -> None:
        concept_dir = Path(__file__).resolve().parents[2] / "docs" / "project-concept"
        concept_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(concept_dir)

    def _load_project_concept(self) -> str:
        concept_dir = Path(__file__).resolve().parents[2] / "docs" / "project-concept"
        files = [concept_dir / "README.md", concept_dir / "principles.md"]
        parts: list[str] = []
        for file_path in files:
            if file_path.exists():
                parts.append(file_path.read_text(encoding="utf-8").strip())
        if parts:
            return "\n\n".join(parts) + "\n"
        return "Пояснения о задумке проекта пока не найдены."


def launch_gui() -> None:
    root = tk.Tk()
    ForecastApp(root)
    root.mainloop()
