# llm-wiki-toolkit

Kit ligero y sin dependencias para mantener una **base de conocimiento en Markdown** que leen y escriben agentes de IA (Claude Code, Codex y otros), **sin base de datos vectorial**.

- **Indice en dos niveles**: un maestro pequeno dirige al agente a sub-indices pequenos.
- **Busqueda de texto completo local** con SQLite FTS5, incremental y sin servidor.
- **Escritura segura**: el log solo se anade al final y `raw/` solo se crea, con verificacion SHA-256.
- **Verificador de integridad**: `wikikit verify` detecta paginas sin frontmatter, enlaces rotos, contadores desfasados y paginas sin indexar.

Python 3.10+, solo libreria estandar en el nucleo. Windows, macOS y Linux.

## Instalacion

**Primera vez:** sigue la [guía de primera ejecución](docs/FIRST_RUN.md) para instalar desde GitHub sin clonar, crear una wiki, añadir una página, buscar y verificar el resultado en Windows, macOS o Linux. La guía está redactada en inglés; los comandos son independientes de la plataforma.

Los siguientes comandos requieren tener una copia local del repositorio; **no** se refieren a PyPI:


```bash
pip install .          # nucleo
pip install .[docs]    # anade extraccion de .docx / .pdf / .pptx
```

## Demo con los archivos del repositorio

```bash
cp -r examples/demo-wiki /tmp/jardin && cd /tmp/jardin
wikikit split-index _meta/INDEX.md --dry-run
wikikit split-index _meta/INDEX.md
wikikit verify --fail-on-broken
wikikit search index
wikikit search query "mulch"
```

Para empezar una wiki propia: `wikikit init mi-wiki`.

## Comandos

| Comando | Funcion |
|---|---|
| `wikikit init [DIR]` | Crea la estructura minima y las plantillas de agente (no sobrescribe). |
| `wikikit split-index INDEX.md [--dry-run]` | Parte un indice monolitico en maestro + sub-indices; el historial va a `_HISTORY.md`; aborta si se perdiera algun enlace. |
| `wikikit search index / query / stats` | Indexa y busca con FTS5 (`--any`, `--fts`, `--source`, `--project`, `--json`). |
| `wikikit log append ENTRY.md` | Anade una entrada al log con cabecera `## [AAAA-MM-DD] TIPO | titulo`, rechazando duplicados y verificando que lo previo no cambia. |
| `wikikit raw save FILE` | Copia a `raw/` solo si el nombre no existe; nunca sobrescribe. |
| `wikikit verify [--fail-on-broken] [--json]` | Comprueba las invariantes (BROKEN / WARN). |

Mas detalle (configuracion, integracion con Claude Code, FAQ y cuando pasar a vectores) en el [README en ingles](README.md).

## Licencia

MIT.
