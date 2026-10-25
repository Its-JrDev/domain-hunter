"""Generador de nombres y variaciones de dominios.
Genera combinaciones con prefijos, sufijos y palabras clave de la industria.
"""

from __future__ import annotations

import re

COMMON_PREFIXES = [
    "get",
    "try",
    "use",
    "the",
    "my",
    "go",
    "join",
    "run",
    "open",
    "hey",
    "we",
    "just",
    "real",
    "super",
]

COMMON_SUFFIXES = [
    "app",
    "hq",
    "lab",
    "labs",
    "io",
    "ai",
    "box",
    "tech",
    "dev",
    "ly",
    "hub",
    "kit",
    "flow",
    "space",
    "base",
    "cloud",
    "stack",
    "forge",
    "sync",
    "pay",
    "co",
]


def sanitize_keyword(keyword: str) -> str:
    """Limpia la palabra clave eliminando caracteres especiales o TLD."""
    keyword = keyword.strip().lower()
    # Si viene con TLD, extraer la parte principal
    if "." in keyword:
        keyword = keyword.split(".")[0]
    # Reemplazar espacios y caracteres inválidos por guiones
    keyword = re.sub(r"[^a-z0-9\-]", "", keyword)
    return keyword.strip("-")


def generate_variations(
    keyword: str,
    include_prefixes: bool = True,
    include_suffixes: bool = True,
    use_hyphens: bool = False,
    max_count: int = 40,
) -> list[str]:
    """Genera una lista de variaciones creativas para la palabra clave dada."""
    clean = sanitize_keyword(keyword)
    if not clean:
        return []

    variations: list[str] = [clean]
    sep = "-" if use_hyphens else ""

    if include_prefixes:
        for p in COMMON_PREFIXES:
            variations.append(f"{p}{sep}{clean}")

    if include_suffixes:
        for s in COMMON_SUFFIXES:
            variations.append(f"{clean}{sep}{s}")

    # Variaciones combinadas cortas
    if include_prefixes and include_suffixes:
        for p in ("get", "the", "my"):
            for s in ("app", "hq"):
                variations.append(f"{p}{sep}{clean}{sep}{s}")

    # Deduplicar manteniendo orden
    seen = set()
    result = []
    for v in variations:
        if v not in seen:
            seen.add(v)
            result.append(v)
        if len(result) >= max_count:
            break

    return result
