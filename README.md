# 🔍 Domain Hunter

> Buscador interactivo y concurrente de disponibilidad de dominios con interfaz de terminal moderna (**TUI** en Textual) y soporte CLI.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Textual](https://img.shields.io/badge/TUI-Textual_8.x-5D3FD3)
![License](https://img.shields.io/badge/License-MIT-blue)

---

## ⚡ Características

- **Ultra Rápido y Concurrente**: Consulta múltiples dominios y TLDs en paralelo con control de concurrencia asíncrono.
- **Detección Híbrida Inteligente**:
  - **DNS Pre-check**: Identifica dominios activos mediante registros NS/SOA en ~15ms sin saturar servicios de WHOIS.
  - **RDAP Oficial (RFC 7480/9082)**: Consulta a `rdap.org` (HTTP 404 = disponible garantizado, HTTP 200 = ocupado con datos del registrador y fechas).
  - **Socket TCP WHOIS (Puerto 43)**: Fallback directo para TLDs regionales o sin soporte RDAP uniforme.
- **Interfaz TUI Reactiva (Textual)**:
  - Búsqueda en vivo por palabra clave o dominio completo.
  - Presets de TLDs: `Populares`, `Tech/AI`, `Modernos`, `Latam/ES`.
  - Filtro interactivo `Solo Disponibles`.
  - Marcado de favoritos (`⭐`).
  - Modal de detalles con enlaces directos para registrar (Porkbun, Cloudflare, Namecheap).
- **Generador de Variaciones**: Sugiere prefijos (`get-`, `try-`, `use-`, `my-`) y sufijos (`-app`, `-hq`, `-lab`, `-dev`, `-ai`).
- **Exportación Flexible**: Exporta resultados a **CSV**, **JSON** o **TXT**.
- **Doble Modo**: Úsalo interactivamente en la TUI o en consola/scripts con `--cli`.

---

## 🚀 Uso Rápido

### 1. Ejecución con la TUI Interactiva

```bash
# Directamente desde el directorio:
./run.sh

# O con uv:
uv run main.py

# O con una consulta inicial:
./run.sh mitienda
```

### 2. Atajos de Teclado en la TUI

| Tecla | Acción |
|---|---|
| `s` o `/` | Enfocar la barra de búsqueda |
| `d` | Alternar filtro de "Solo disponibles" |
| `g` | Abrir modal del Generador de Variaciones |
| `e` | Exportar resultados a CSV / JSON / TXT |
| `f` | Marcar o desmarcar fila actual como Favorito (⭐) |
| `c` | Limpiar la lista actual de dominios |
| `Enter` | Ver detalles completos de RDAP/WHOIS del dominio seleccionado |
| `q` | Salir de la aplicación |

---

### 3. Modo Consola (CLI) y Scripts

Ideal para automatizaciones, tuberías bash o comprobaciones rápidas sin abrir la TUI:

```bash
# Consultar palabra con TLDs específicos:
./run.sh novastream --cli --tlds com,io,ai,dev

# Consultar dominios directos:
./run.sh google.com midominioquenoexiste123897.com --cli

# Generar variaciones y filtrar solo los disponibles:
./run.sh byte --cli --generate --only-available

# Exportar directamente a CSV desde CLI:
./run.sh startup --cli --tlds com,ai,io --export /tmp/startup_domains.csv
```

---

## 🛠️ Instalación Global

Si deseas ejecutar `domain-hunter` desde cualquier lugar de tu terminal:

```bash
ln -sf "$(pwd)/run.sh" ~/.local/bin/domain-hunter
```

Y luego ejecuta simplemente:
```bash
domain-hunter
```

---

## 📄 Licencia

MIT © jr
