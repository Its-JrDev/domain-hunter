"""Diálogos modales para Domain Hunter:
- TLDSelectorModal: Configuración rápida y limpia de TLDs seleccionados.
- GeneratorModal: Generador visual de ideas y variaciones.
- ExportModal: Exportación flexible de dominios a CSV, TXT o JSON.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, RadioButton, RadioSet, Static

from domain_hunter.engine import DomainResult
from domain_hunter.generator import generate_variations

ALL_AVAILABLE_TLDS = [
    "com", "net", "org", "io", "ai", "dev", "app", "co",
    "xyz", "es", "me", "tech", "online", "lat", "mx", "cl",
    "info", "cloud", "store", "space", "sh", "pro"
]


class TLDSelectorModal(ModalScreen[list[str] | None]):
    """Modal para seleccionar TLDs de forma ordenada sin saturar la pantalla principal."""

    def __init__(self, current_tlds: list[str]) -> None:
        super().__init__()
        self.current_tlds = set(current_tlds)

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("🌐 Configurar Extensiones (TLDs)", classes="modal-title")
            yield Label("Selecciona las extensiones a consultar:")

            with Grid(id="tld-grid", classes="tld-grid-container"):
                for tld in ALL_AVAILABLE_TLDS:
                    yield Checkbox(
                        f".{tld}",
                        value=(tld in self.current_tlds),
                        id=f"sel-tld-{tld}",
                    )

            with Horizontal(classes="modal-buttons"):
                yield Button("Aplicar", variant="primary", id="btn-apply-tlds", classes="modal-btn")
                yield Button("Cancelar", variant="default", id="btn-cancel-tlds", classes="modal-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-tlds":
            self.dismiss(None)
        elif event.button.id == "btn-apply-tlds":
            selected = []
            for tld in ALL_AVAILABLE_TLDS:
                try:
                    chk = self.query_one(f"#sel-tld-{tld}", Checkbox)
                    if chk.value:
                        selected.append(tld)
                except Exception:
                    pass
            self.dismiss(selected or ["com"])


class GeneratorModal(ModalScreen[list[str] | None]):
    """Modal generador de variaciones creativas."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("⚡ Generador de Variaciones de Nombres", classes="modal-title")
            yield Label("Ingresa tu palabra clave base (ej: cloud, byte, stream):")
            yield Input(placeholder="Palabra clave base...", id="gen-keyword-input")

            with Horizontal():
                yield Checkbox("Prefijos (get, try, use, my...)", value=True, id="chk-prefixes")
                yield Checkbox("Sufijos (app, hq, lab, dev...)", value=True, id="chk-suffixes")

            yield Checkbox("Incluir guión separador (-)", value=False, id="chk-hyphen")

            yield Label("Vista previa de variaciones:", classes="section-label")
            with VerticalScroll(id="gen-preview-scroll"):
                yield Static("Escribe una palabra para ver sugerencias...", id="gen-preview-text")

            with Horizontal(classes="modal-buttons"):
                yield Button("Buscar Todas", variant="success", id="btn-gen-search", classes="modal-btn")
                yield Button("Cancelar", variant="default", id="btn-gen-cancel", classes="modal-btn")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "gen-keyword-input":
            self._update_preview()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._update_preview()

    def _update_preview(self) -> list[str]:
        kw_input = self.query_one("#gen-keyword-input", Input)
        chk_p = self.query_one("#chk-prefixes", Checkbox).value
        chk_s = self.query_one("#chk-suffixes", Checkbox).value
        chk_h = self.query_one("#chk-hyphen", Checkbox).value

        words = generate_variations(
            keyword=kw_input.value,
            include_prefixes=chk_p,
            include_suffixes=chk_s,
            use_hyphens=chk_h,
            max_count=20,
        )
        preview = self.query_one("#gen-preview-text", Static)
        if words:
            preview.update(", ".join(words))
        else:
            preview.update("[dim]Ingresa una palabra para ver variaciones[/dim]")
        return words

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-gen-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-gen-search":
            words = self._update_preview()
            if words:
                self.dismiss(words)
            else:
                self.dismiss(None)


class ExportModal(ModalScreen[None]):
    """Modal para exportar resultados de búsqueda."""

    def __init__(self, results: list[DomainResult]) -> None:
        super().__init__()
        self.results = results

    def compose(self) -> ComposeResult:
        default_path = str(Path.home() / "Development" / "scripts" / "domain-hunter" / "dominios_disponibles.csv")
        with Vertical(classes="modal-dialog"):
            yield Label("💾 Exportar Resultados", classes="modal-title")
            yield Label("Ruta de archivo:")
            yield Input(value=default_path, id="export-path-input")

            yield Label("Formato:")
            with RadioSet(id="export-format-radios"):
                yield RadioButton("CSV (Detallado con estado y fechas)", value=True, id="fmt-csv")
                yield RadioButton("TXT (Lista de dominios disponibles)", id="fmt-txt")
                yield RadioButton("JSON (Estructurado completo)", id="fmt-json")

            yield Checkbox("Exportar únicamente dominios disponibles", value=True, id="chk-export-avail-only")
            yield Static("", id="export-feedback")

            with Horizontal(classes="modal-buttons"):
                yield Button("Guardar", variant="primary", id="btn-do-export", classes="modal-btn")
                yield Button("Cerrar", variant="default", id="btn-cancel-export", classes="modal-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-export":
            self.dismiss()
        elif event.button.id == "btn-do-export":
            self._save_export()

    def _save_export(self) -> None:
        path_str = self.query_one("#export-path-input", Input).value.strip()
        avail_only = self.query_one("#chk-export-avail-only", Checkbox).value
        fmt_radios = self.query_one("#export-format-radios", RadioSet)

        items = [r for r in self.results if (not avail_only or r.is_available)]

        if not items:
            self.query_one("#export-feedback", Static).update("[yellow]No hay dominios que coincidan con el filtro.[/yellow]")
            return

        try:
            target_path = Path(path_str).expanduser().resolve()
            target_path.parent.mkdir(parents=True, exist_ok=True)

            selected_id = fmt_radios.pressed_button.id if fmt_radios.pressed_button else "fmt-csv"

            if selected_id == "fmt-txt":
                with open(target_path, "w", encoding="utf-8") as f:
                    for item in items:
                        f.write(f"{item.domain}\n")

            elif selected_id == "fmt-json":
                data = [
                    {
                        "domain": i.domain,
                        "tld": i.tld,
                        "status": i.status,
                        "registrar": i.registrar,
                        "created_date": i.created_date,
                        "expiry_date": i.expiry_date,
                        "nameservers": i.nameservers,
                        "notes": i.notes,
                    }
                    for i in items
                ]
                with open(target_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

            else:  # CSV default
                with open(target_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Dominio", "TLD", "Estado", "Registrador", "Creación", "Expiración", "Notas"])
                    for i in items:
                        writer.writerow([
                            i.domain,
                            i.tld,
                            i.status,
                            i.registrar or "",
                            i.created_date or "",
                            i.expiry_date or "",
                            i.notes,
                        ])

            self.query_one("#export-feedback", Static).update(
                f"[green]✓ Exportados {len(items)} dominios a:\n{target_path}[/green]"
            )
        except Exception as e:
            self.query_one("#export-feedback", Static).update(f"[red]Error al guardar: {e}[/red]")
