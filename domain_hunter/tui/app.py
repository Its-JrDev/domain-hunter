"""Aplicación TUI moderna estilo OpenCode para Domain Hunter.
Disposición en 3 columnas divididas: Historial de Sesiones, Resultados y Live Inspector.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Static,
)
from textual.widgets.option_list import Option

from domain_hunter.engine import DomainEngine, DomainResult
from domain_hunter.tui.modals import ExportModal, GeneratorModal, TLDSelectorModal

PRESET_LISTS: dict[str, list[str]] = {
    "Populares": ["com", "net", "org", "co"],
    "Tech/AI": ["ai", "io", "dev", "app", "tech", "sh"],
    "Globales": ["xyz", "me", "online", "cloud", "store", "info"],
    "Latam/ES": ["es", "lat", "mx", "cl", "co", "com"],
}

CSS_PATH = Path(__file__).parent / "styles.tcss"


@dataclass
class SearchSession:
    """Representa una sesión individual de búsqueda para evitar apilamientos."""
    id: str
    query: str
    created_at: str
    results: dict[str, DomainResult] = field(default_factory=dict)
    tlds: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def available_count(self) -> int:
        return sum(1 for r in self.results.values() if r.is_available)

    @property
    def taken_count(self) -> int:
        return sum(1 for r in self.results.values() if r.is_taken)

    @property
    def label(self) -> str:
        if self.total == 0:
            return f"🔍 {self.query}"
        return f"● {self.query}  [green]{self.available_count}[/]/[dim]{self.total}[/]"


class DomainHunterApp(App[None]):
    """Aplicación TUI para la búsqueda de dominios disponibles."""

    TITLE = "DOMAIN HUNTER"
    SUB_TITLE = "Buscador Asíncrono de Dominios"
    CSS_PATH = CSS_PATH

    BINDINGS = [
        Binding("q", "quit", "Salir", show=True),
        Binding("/", "focus_search", "Buscar (/)", show=True),
        Binding("d", "toggle_filter", "Solo Disponibles", show=True),
        Binding("t", "toggle_presets", "TLDs", show=True),
        Binding("g", "open_generator", "Ideas", show=True),
        Binding("e", "open_export", "Exportar", show=True),
        Binding("c", "copy_domain", "Copiar", show=True),
    ]

    def __init__(self, initial_query: str | None = None) -> None:
        super().__init__()
        self.engine = DomainEngine()
        self.initial_query = initial_query
        self.sessions: dict[str, SearchSession] = {}
        self.active_session_id: str | None = None
        self.selected_domain: str | None = None
        self.available_only: bool = False
        self.current_preset: str = "Populares"
        self.active_tlds: list[str] = list(PRESET_LISTS["Populares"])
        self.search_task: asyncio.Task | None = None
        self.session_counter = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="top-bar"):
            with Horizontal(id="search-box"):
                yield Input(
                    placeholder="🔍 Escribe una palabra o dominio (ej: novatech o novatech.com) y presiona Enter...",
                    id="search-input",
                    value=self.initial_query or "",
                )
                yield Button("Buscar", variant="primary", id="btn-search", classes="action-btn btn-primary")
                yield Button("+ Nueva", id="btn-new", classes="action-btn")

        with Horizontal(id="main-split"):
            # Columna Izquierda: Historial de Sesiones
            with Vertical(id="sidebar-pane", classes="split-pane"):
                yield Label("📂 SESIONES", classes="pane-header")
                yield OptionList(id="sessions-list")
                with Horizontal(id="sidebar-footer"):
                    yield Button("Limpiar Todo", id="btn-clear-all", classes="pill-btn")

            # Columna Central: Lista de Resultados
            with Vertical(id="results-pane", classes="split-pane"):
                yield Label("📋 RESULTADOS", id="results-header", classes="pane-header")
                table = DataTable(id="results-table", cursor_type="row")
                table.add_columns("●", "Dominio", "TLD", "Estado", "Registrador", "Expira")
                yield table

            # Columna Derecha: Inspector en Vivo
            with Vertical(id="inspector-pane", classes="split-pane"):
                yield Label("ℹ INSPECTOR EN VIVO", classes="pane-header")
                with VerticalScroll(id="inspector-content"):
                    yield Static("[dim]Selecciona un dominio para inspeccionar sus detalles...[/dim]", id="inspector-body")

        # Barra de Controles Inferior
        with Horizontal(id="bottom-bar"):
            yield Button("Filtro: Todos", id="btn-toggle-filter", classes="pill-btn")
            yield Button(f"TLDs: {self.current_preset} ▾", id="btn-preset-toggle", classes="pill-btn")
            yield Button("+ Custom TLDs", id="btn-custom-tlds", classes="pill-btn")
            yield Button("⚡ Variaciones", id="btn-generator", classes="pill-btn")
            yield Button("📁 Exportar", id="btn-export", classes="pill-btn")
            yield Static("Total: 0 | Disponibles: 0", id="status-stats")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()
        if self.initial_query:
            self.action_start_search(self.initial_query)

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_toggle_filter(self) -> None:
        self.available_only = not self.available_only
        btn = self.query_one("#btn-toggle-filter", Button)
        if self.available_only:
            btn.label = "Filtro: Solo Disponibles"
            btn.add_class("pill-active")
        else:
            btn.label = "Filtro: Todos"
            btn.remove_class("pill-active")
        self._render_current_session_table()

    def action_toggle_presets(self) -> None:
        preset_names = list(PRESET_LISTS.keys())
        idx = preset_names.index(self.current_preset) if self.current_preset in preset_names else 0
        next_idx = (idx + 1) % len(preset_names)
        self.current_preset = preset_names[next_idx]
        self.active_tlds = list(PRESET_LISTS[self.current_preset])
        self.query_one("#btn-preset-toggle", Button).label = f"TLDs: {self.current_preset} ▾"

    def action_open_generator(self) -> None:
        def _handle_words(words: list[str] | None) -> None:
            if words:
                for w in words[:15]:
                    self.action_start_search(w)

        self.push_screen(GeneratorModal(), _handle_words)

    def action_open_export(self) -> None:
        sess = self._get_active_session()
        items = list(sess.results.values()) if sess else []
        self.push_screen(ExportModal(items))

    def action_copy_domain(self) -> None:
        if self.selected_domain:
            try:
                import subprocess
                # Intentar copiar a portapapeles si xclip/wl-copy está disponible
                subprocess.run(["xclip", "-selection", "clipboard"], input=self.selected_domain.encode(), check=False)
            except Exception:
                pass
            self.notify(f"Copiado: {self.selected_domain}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        b_id = event.button.id
        if b_id == "btn-search":
            query = self.query_one("#search-input", Input).value.strip()
            if query:
                self.action_start_search(query)
        elif b_id == "btn-new":
            inp = self.query_one("#search-input", Input)
            inp.value = ""
            inp.focus()
        elif b_id == "btn-toggle-filter":
            self.action_toggle_filter()
        elif b_id == "btn-preset-toggle":
            self.action_toggle_presets()
        elif b_id == "btn-custom-tlds":
            def _handle_tlds(selected: list[str] | None) -> None:
                if selected:
                    self.active_tlds = selected
                    self.current_preset = "Personalizado"
                    self.query_one("#btn-preset-toggle", Button).label = "TLDs: Personalizado ▾"
            self.push_screen(TLDSelectorModal(self.active_tlds), _handle_tlds)
        elif b_id == "btn-generator":
            self.action_open_generator()
        elif b_id == "btn-export":
            self.action_open_export()
        elif b_id == "btn-clear-all":
            self._clear_all_sessions()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            query = event.input.value.strip()
            if query:
                self.action_start_search(query)

    def action_start_search(self, raw_query: str) -> None:
        clean_query = raw_query.strip().lower()
        if not clean_query:
            return

        self.session_counter += 1
        sess_id = f"sess_{self.session_counter}"
        now_str = datetime.now().strftime("%H:%M:%S")

        # Determinar lista de dominios a verificar
        if "." in clean_query:
            domains = [clean_query]
        else:
            domains = [f"{clean_query}.{tld}" for tld in self.active_tlds]

        session = SearchSession(
            id=sess_id,
            query=clean_query,
            created_at=now_str,
            tlds=list(self.active_tlds),
        )

        for d in domains:
            session.results[d] = DomainResult(domain=d, tld=d.split(".")[-1], status="querying")

        self.sessions[sess_id] = session
        self.active_session_id = sess_id

        # Agregar al OptionList lateral
        ol = self.query_one("#sessions-list", OptionList)
        ol.add_option(Option(session.label, id=sess_id))
        ol.highlighted = ol.option_count - 1

        self._render_current_session_table()

        # Iniciar tarea asíncrona de búsqueda para esta sesión
        if self.search_task and not self.search_task.done():
            self.search_task.cancel()
        self.search_task = asyncio.create_task(self._search_worker(session, domains))

    async def _search_worker(self, session: SearchSession, domains: list[str]) -> None:
        try:
            async for result in self.engine.check_domains_stream(domains, max_concurrency=10):
                session.results[result.domain] = result
                # Si esta sesión es la activa, actualizar la tabla
                if self.active_session_id == session.id:
                    self._update_row_in_table(result)
                    self._update_stats()
                    if self.selected_domain == result.domain:
                        self._render_inspector(result)

                # Actualizar etiqueta en el historial
                try:
                    ol = self.query_one("#sessions-list", OptionList)
                    ol.replace_option_prompt(session.id, session.label)
                except Exception:
                    pass
        except asyncio.CancelledError:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        sess_id = event.option_id
        if sess_id and sess_id in self.sessions:
            self.active_session_id = sess_id
            self._render_current_session_table()

    def _get_active_session(self) -> SearchSession | None:
        if self.active_session_id and self.active_session_id in self.sessions:
            return self.sessions[self.active_session_id]
        return None

    def _render_current_session_table(self) -> None:
        session = self._get_active_session()
        table = self.query_one("#results-table", DataTable)
        table.clear()

        header_lbl = self.query_one("#results-header", Label)
        if not session:
            header_lbl.update("📋 RESULTADOS")
            self._update_stats()
            self._render_inspector(None)
            return

        header_lbl.update(f"📋 RESULTADOS: {session.query.upper()} ({len(session.results)} dominios)")

        for res in session.results.values():
            if self.available_only and not res.is_available and res.status != "querying":
                continue
            self._add_row_to_table(table, res)

        self._update_stats()

        # Seleccionar automáticamente la primera fila para el inspector
        if table.row_count > 0:
            table.move_cursor(row=0)
            first_dom = list(session.results.keys())[0]
            self.selected_domain = first_dom
            self._render_inspector(session.results.get(first_dom))
        else:
            self._render_inspector(None)

    def _add_row_to_table(self, table: DataTable, res: DomainResult) -> None:
        dot = "●"
        if res.status == "available":
            dot_styled = "[bold green]●[/bold green]"
            st_styled = "[bold green]DISPONIBLE[/bold green]"
        elif res.status == "taken":
            dot_styled = "[bold red]●[/bold red]"
            st_styled = "[bold red]OCUPADO[/bold red]"
        else:
            dot_styled = "[bold yellow]⏳[/bold yellow]"
            st_styled = "[bold yellow]CONSULTANDO[/bold yellow]"

        table.add_row(
            dot_styled,
            f"[bold]{res.domain}[/bold]",
            res.tld,
            st_styled,
            res.registrar or "-",
            res.expiry_date or "-",
            key=res.domain,
        )

    def _update_row_in_table(self, res: DomainResult) -> None:
        table = self.query_one("#results-table", DataTable)
        col_keys = list(table.columns.keys())

        if self.available_only and not res.is_available:
            try:
                table.remove_row(res.domain)
            except Exception:
                pass
            return

        if res.status == "available":
            dot_styled = "[bold green]●[/bold green]"
            st_styled = "[bold green]DISPONIBLE[/bold green]"
        elif res.status == "taken":
            dot_styled = "[bold red]●[/bold red]"
            st_styled = "[bold red]OCUPADO[/bold red]"
        else:
            dot_styled = "[bold yellow]⏳[/bold yellow]"
            st_styled = "[bold yellow]CONSULTANDO[/bold yellow]"

        row_vals = [
            dot_styled,
            f"[bold]{res.domain}[/bold]",
            res.tld,
            st_styled,
            res.registrar or "-",
            res.expiry_date or "-",
        ]

        try:
            for idx, val in enumerate(row_vals):
                table.update_cell(res.domain, col_keys[idx], val)
        except Exception:
            try:
                table.add_row(*row_vals, key=res.domain)
            except Exception:
                pass

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        dom_name = str(event.row_key.value) if event.row_key else ""
        session = self._get_active_session()
        if session and dom_name in session.results:
            self.selected_domain = dom_name
            self._render_inspector(session.results[dom_name])

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.on_data_table_row_highlighted(event)

    def _render_inspector(self, res: DomainResult | None) -> None:
        body = self.query_one("#inspector-body", Static)
        if not res:
            body.update("[dim]Selecciona un dominio para inspeccionar sus detalles...[/dim]")
            return

        lines: list[str] = [f"[bold white]{res.domain.upper()}[/bold white]\n"]

        if res.status == "available":
            lines.append("[bold green]● DISPONIBLE PARA REGISTRO[/bold green]\n")
            lines.append("[bold cyan]Enlaces rápidos de compra:[/bold cyan]")
            lines.append(f"• [underline]Cloudflare[/]: https://dash.cloudflare.com/?to=/:account/domains/register/{res.domain}")
            lines.append(f"• [underline]Porkbun[/]:    https://porkbun.com/checkout/search?q={res.domain}")
            lines.append(f"• [underline]Namecheap[/]:  https://www.namecheap.com/domains/registration/results/?domain={res.domain}\n")
            lines.append("[dim]Presiona [b]c[/b] para copiar el dominio[/dim]")
        elif res.status == "taken":
            lines.append("[bold red]● DOMINIO REGISTRADO / OCUPADO[/bold red]\n")
            lines.append(f"[bold cyan]Registrador:[/]  {res.registrar or 'Desconocido'}")
            lines.append(f"[bold cyan]F. Registro:[/]  {res.created_date or 'No disponible'}")
            lines.append(f"[bold cyan]F. Expira:[/]    {res.expiry_date or 'No disponible'}")
            if res.nameservers:
                lines.append(f"[bold cyan]DNS Servers:[/]  {', '.join(res.nameservers)}")
            if res.status_codes:
                lines.append(f"[bold cyan]Estados EPP:[/]  {', '.join(res.status_codes[:3])}")
            if res.notes:
                lines.append(f"[bold cyan]Notas:[/]        {res.notes}")
            lines.append("\n[dim]Presiona [b]c[/b] para copiar el dominio[/dim]")
        else:
            lines.append("[bold yellow]⏳ Consultando disponibilidad en DNS / RDAP...[/bold yellow]")

        body.update("\n".join(lines))

    def _update_stats(self) -> None:
        session = self._get_active_session()
        stats = self.query_one("#status-stats", Static)
        if not session:
            stats.update("Total: 0 | Disponibles: 0")
            return

        total = session.total
        avail = session.available_count
        taken = session.taken_count
        stats.update(
            f"Sesión: [bold]{session.query}[/] | "
            f"Total: [bold]{total}[/] | "
            f"[green]Disponibles: {avail}[/] | "
            f"[red]Ocupados: {taken}[/]"
        )

    def _clear_all_sessions(self) -> None:
        if self.search_task and not self.search_task.done():
            self.search_task.cancel()
        self.sessions.clear()
        self.active_session_id = None
        self.selected_domain = None
        self.query_one("#sessions-list", OptionList).clear_options()
        self._render_current_session_table()
