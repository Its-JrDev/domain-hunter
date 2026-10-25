"""Aplicación TUI principal de Domain Hunter construida con Textual."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
)

from domain_hunter.engine import DomainEngine, DomainResult
from domain_hunter.tui.modals import DomainDetailModal, ExportModal, GeneratorModal

DEFAULT_TLDS = [
    "com",
    "io",
    "ai",
    "dev",
    "app",
    "co",
    "xyz",
    "es",
    "net",
    "org",
    "me",
    "tech",
    "online",
    "lat",
    "mx",
]

PRESETS: dict[str, list[str]] = {
    "preset-pop": ["com", "net", "org", "co"],
    "preset-tech": ["ai", "io", "dev", "app", "tech"],
    "preset-modern": ["xyz", "me", "online", "tech", "lat"],
    "preset-es": ["es", "lat", "mx", "co", "com"],
}

CSS_PATH = Path(__file__).parent / "styles.tcss"


class DomainHunterApp(App[None]):
    """Aplicación TUI para la búsqueda de dominios disponibles."""

    TITLE = "DOMAIN HUNTER"
    SUB_TITLE = "Buscador Asíncrono de Dominios Disponibles"
    CSS_PATH = CSS_PATH

    BINDINGS = [
        Binding("q", "quit", "Salir", show=True),
        Binding("s", "focus_search", "Buscar (/)", show=True),
        Binding("/", "focus_search", "Buscar", show=False),
        Binding("d", "toggle_available_only", "Solo Disponibles", show=True),
        Binding("g", "open_generator", "Generador Ideas", show=True),
        Binding("e", "open_export", "Exportar", show=True),
        Binding("f", "toggle_favorite", "Favorito ⭐", show=True),
        Binding("c", "clear_all", "Limpiar", show=True),
    ]

    def __init__(self, initial_query: str | None = None) -> None:
        super().__init__()
        self.engine = DomainEngine()
        self.initial_query = initial_query
        self.all_results: dict[str, DomainResult] = {}
        self.row_keys: dict[str, str] = {}
        self.search_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="top-panel"):
            with Horizontal(id="search-row"):
                yield Input(
                    placeholder="Escribe palabra o dominio (ej: novatech o novatech.com)...",
                    id="search-input",
                    value=self.initial_query or "",
                )
                yield Button("Buscar", variant="primary", id="btn-search")
                yield Button("⚡ Ideas", variant="default", id="btn-generator")
                yield Button("Limpiar", variant="default", id="btn-clear")

            with Vertical(id="tld-panel"):
                yield Label("Presets rápidos:", classes="section-label")
                with Horizontal(id="preset-buttons"):
                    yield Button("⭐ Populares", id="preset-pop", classes="preset-btn")
                    yield Button("⚡ Tech / AI", id="preset-tech", classes="preset-btn")
                    yield Button("🌐 Modernos", id="preset-modern", classes="preset-btn")
                    yield Button("🌎 Latam/ES", id="preset-es", classes="preset-btn")
                    yield Button("Todos", id="preset-all", classes="preset-btn")
                    yield Button("Ninguno", id="preset-none", classes="preset-btn")

                with Horizontal(id="tld-checkboxes"):
                    for tld in DEFAULT_TLDS:
                        yield Checkbox(f".{tld}", value=True, id=f"tld-{tld}", classes="tld-check")

        with Horizontal(id="filter-stats-bar"):
            yield Checkbox("Solo disponibles", value=False, id="chk-available-only")
            yield Static("Consultados: 0 | Disponibles: 0 | Ocupados: 0", id="stats-label")

        with Container(id="table-container"):
            table = DataTable(id="results-table", cursor_type="row")
            table.add_columns("Fav", "Estado", "Dominio", "TLD", "Registrador", "Expira", "Notas")
            yield table

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()
        if self.initial_query:
            self.action_start_search()

    def _get_active_tlds(self) -> list[str]:
        active: list[str] = []
        for tld in DEFAULT_TLDS:
            try:
                chk = self.query_one(f"#tld-{tld}", Checkbox)
                if chk.value:
                    active.append(tld)
            except Exception:
                pass
        return active or ["com"]

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_toggle_available_only(self) -> None:
        chk = self.query_one("#chk-available-only", Checkbox)
        chk.value = not chk.value
        self._refresh_table()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "chk-available-only":
            self._refresh_table()

    def action_open_generator(self) -> None:
        def _handle_generator_words(words: list[str] | None) -> None:
            if words:
                self._run_bulk_search(words)

        self.push_screen(GeneratorModal(), _handle_generator_words)

    def action_open_export(self) -> None:
        self.push_screen(ExportModal(list(self.all_results.values())))

    def action_clear_all(self) -> None:
        if self.search_task and not self.search_task.done():
            self.search_task.cancel()
        self.all_results.clear()
        self.row_keys.clear()
        table = self.query_one("#results-table", DataTable)
        table.clear()
        self._update_stats()

    def action_toggle_favorite(self) -> None:
        table = self.query_one("#results-table", DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        dom_name = str(row_key.value) if row_key else ""
        if dom_name in self.all_results:
            res = self.all_results[dom_name]
            res.is_favorite = not res.is_favorite
            self._update_row_in_table(res)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        b_id = event.button.id or ""
        if b_id == "btn-search":
            self.action_start_search()
        elif b_id == "btn-generator":
            self.action_open_generator()
        elif b_id == "btn-clear":
            self.action_clear_all()
        elif b_id in PRESETS:
            selected = PRESETS[b_id]
            for tld in DEFAULT_TLDS:
                try:
                    chk = self.query_one(f"#tld-{tld}", Checkbox)
                    chk.value = tld in selected
                except Exception:
                    pass
        elif b_id == "preset-all":
            for tld in DEFAULT_TLDS:
                try:
                    self.query_one(f"#tld-{tld}", Checkbox).value = True
                except Exception:
                    pass
        elif b_id == "preset-none":
            for tld in DEFAULT_TLDS:
                try:
                    self.query_one(f"#tld-{tld}", Checkbox).value = False
                except Exception:
                    pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.action_start_search()

    def action_start_search(self) -> None:
        val = self.query_one("#search-input", Input).value.strip().lower()
        if not val:
            return

        # Si el input tiene punto (ej. "proyecto.com"), buscar ese directamente
        if "." in val:
            domains_to_check = [val]
        else:
            tlds = self._get_active_tlds()
            domains_to_check = [f"{val}.{tld}" for tld in tlds]

        self._run_bulk_search(domains_to_check)

    def _run_bulk_search(self, domains_to_check: list[str]) -> None:
        if self.search_task and not self.search_task.done():
            self.search_task.cancel()

        table = self.query_one("#results-table", DataTable)
        for d in domains_to_check:
            if d not in self.all_results:
                placeholder = DomainResult(domain=d, tld=d.split(".")[-1], status="querying")
                self.all_results[d] = placeholder
                self._add_or_update_row(placeholder)

        self._update_stats()
        self.search_task = asyncio.create_task(self._search_worker(domains_to_check))

    async def _search_worker(self, domains: list[str]) -> None:
        try:
            async for result in self.engine.check_domains_stream(domains, max_concurrency=8):
                self.all_results[result.domain] = result
                self._add_or_update_row(result)
                self._update_stats()
        except asyncio.CancelledError:
            pass

    def _add_or_update_row(self, res: DomainResult) -> None:
        table = self.query_one("#results-table", DataTable)
        avail_only = self.query_one("#chk-available-only", Checkbox).value

        # Si se filtra por solo disponibles y no está disponible ni consultando, no mostrar
        if avail_only and res.status != "available" and res.status != "querying":
            if res.domain in self.row_keys:
                try:
                    table.remove_row(res.domain)
                    del self.row_keys[res.domain]
                except Exception:
                    pass
            return

        fav_str = "⭐" if res.is_favorite else ""
        if res.status == "querying":
            status_str = "[bold yellow]⏳ CONSULTANDO...[/bold yellow]"
        elif res.status == "available":
            status_str = "[bold green]✓ DISPONIBLE[/bold green]"
        elif res.status == "taken":
            status_str = "[bold red]✗ OCUPADO[/bold red]"
        else:
            status_str = "[dim]? INDETERMINADO[/dim]"

        row_data = (
            fav_str,
            status_str,
            f"[bold]{res.domain}[/bold]",
            res.tld,
            res.registrar or "-",
            res.expiry_date or "-",
            res.notes or ("Activo en DNS" if res.dns_active else "-"),
        )

        if res.domain in self.row_keys:
            try:
                for col_idx, val in enumerate(row_data):
                    table.update_cell(res.domain, table.columns[col_idx].key, val)
            except Exception:
                pass
        else:
            table.add_row(*row_data, key=res.domain)
            self.row_keys[res.domain] = res.domain

    def _update_row_in_table(self, res: DomainResult) -> None:
        self._add_or_update_row(res)

    def _refresh_table(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.clear()
        self.row_keys.clear()
        for res in self.all_results.values():
            self._add_or_update_row(res)
        self._update_stats()

    def _update_stats(self) -> None:
        total = len(self.all_results)
        avail = sum(1 for r in self.all_results.values() if r.is_available)
        taken = sum(1 for r in self.all_results.values() if r.is_taken)
        lbl = self.query_one("#stats-label", Static)
        lbl.update(
            f"Total: [bold]{total}[/] | "
            f"Disponibles: [bold green]{avail}[/] | "
            f"Ocupados: [bold red]{taken}[/]"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        dom_name = str(event.row_key.value) if event.row_key else ""
        if dom_name in self.all_results:
            self.push_screen(DomainDetailModal(self.all_results[dom_name]))
