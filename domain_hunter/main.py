"""Punto de entrada de Domain Hunter.
Soporta ejecución interactiva con Textual TUI o ejecución directa por consola (CLI).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from domain_hunter.engine import DomainEngine, DomainResult
from domain_hunter.generator import generate_variations
from domain_hunter.tui.app import DEFAULT_TLDS, DomainHunterApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="domain-hunter",
        description="Buscador moderno de disponibilidad de dominios con TUI en Python",
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Palabra clave o dominio a consultar (ej: mitienda o mitienda.com)",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Ejecuta en modo consola directa sin abrir la interfaz interactiva TUI",
    )
    parser.add_argument(
        "--tlds",
        type=str,
        default=",".join(DEFAULT_TLDS[:8]),
        help="TLDs a consultar separados por comas (por defecto: com,io,ai,dev,app,co,xyz,es)",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Genera variaciones y prefijos/sufijos a partir de la palabra clave",
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Ruta para exportar los resultados (soporta .csv, .json, .txt)",
    )
    parser.add_argument(
        "--only-available",
        action="store_true",
        help="Muestra o exporta únicamente los dominios disponibles",
    )
    return parser.parse_args()


async def run_cli_mode(
    queries: list[str],
    tlds: list[str],
    only_available: bool = False,
    export_path: str | None = None,
) -> int:
    console = Console()
    engine = DomainEngine()

    domains: list[str] = []
    for q in queries:
        q = q.strip().lower()
        if "." in q:
            domains.append(q)
        else:
            for t in tlds:
                domains.append(f"{q}.{t.strip().lstrip('.')}")

    if not domains:
        console.print("[red]No se especificaron dominios a consultar.[/red]")
        return 1

    console.print(f"[bold cyan]🔍 Domain Hunter[/bold cyan] - Verificando [bold]{len(domains)}[/bold] dominios...\n")

    results: list[DomainResult] = []
    table = Table(title="Resultados de Disponibilidad")
    table.add_column("Estado", style="bold", justify="center")
    table.add_column("Dominio", style="cyan")
    table.add_column("TLD", style="dim")
    table.add_column("Registrador")
    table.add_column("Expiración", style="magenta")
    table.add_column("Notas", style="dim")

    async for res in engine.check_domains_stream(domains, max_concurrency=10):
        results.append(res)
        if only_available and not res.is_available:
            continue

        if res.is_available:
            st = "[green]✓ DISPONIBLE[/green]"
        elif res.is_taken:
            st = "[red]✗ OCUPADO[/red]"
        else:
            st = "[yellow]? INDETERMINADO[/yellow]"

        table.add_row(
            st,
            res.domain,
            res.tld,
            res.registrar or "-",
            res.expiry_date or "-",
            res.notes or ("DNS Activo" if res.dns_active else "-"),
        )

    console.print(table)

    total = len(results)
    avail = sum(1 for r in results if r.is_available)
    taken = sum(1 for r in results if r.is_taken)
    console.print(
        f"\n[bold]Resumen:[/] Total: {total} | [green]Disponibles: {avail}[/] | [red]Ocupados: {taken}[/]\n"
    )

    if export_path:
        _export_cli_results(results, export_path, only_available, console)

    return 0


def _export_cli_results(
    results: list[DomainResult],
    path_str: str,
    only_available: bool,
    console: Console,
) -> None:
    items = [r for r in results if (not only_available or r.is_available)]
    p = Path(path_str).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    ext = p.suffix.lower()
    if ext == ".json":
        data = [
            {
                "domain": i.domain,
                "tld": i.tld,
                "status": i.status,
                "registrar": i.registrar,
                "created_date": i.created_date,
                "expiry_date": i.expiry_date,
                "notes": i.notes,
            }
            for i in items
        ]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    elif ext == ".txt":
        with open(p, "w", encoding="utf-8") as f:
            for i in items:
                f.write(f"{i.domain}\n")
    else:  # csv
        with open(p, "w", newline="", encoding="utf-8") as f:
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

    console.print(f"[bold green]✓ Exportados {len(items)} registros a:[/] {p}")


def main() -> None:
    args = parse_args()

    # Si se solicitan variaciones con la palabra clave
    keywords = [args.query] if args.query else []
    if args.generate and args.query:
        variations = generate_variations(args.query, max_count=15)
        keywords = variations

    # Detectar si se debe ejecutar en CLI o si no hay TTY interactivo
    if args.cli or (not sys.stdin.isatty() and args.query):
        tlds = [t.strip() for t in args.tlds.split(",") if t.strip()]
        sys.exit(
            asyncio.run(
                run_cli_mode(
                    queries=keywords,
                    tlds=tlds,
                    only_available=args.only_available,
                    export_path=args.export,
                )
            )
        )
    else:
        app = DomainHunterApp(initial_query=args.query)
        app.run()


if __name__ == "__main__":
    main()
