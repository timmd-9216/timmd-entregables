#!/usr/bin/env python3
"""
build.py — dataset + README de los entregables de TIMMD.

Subcomandos:

  dataset   Lee data/input/*.xlsx, cruza alumnos con mails, consulta la API de
            GitHub para completar titulo/descripcion/tags de los proyectos que
            falten y actualiza data/entregables.yaml.

            Reglas de merge (clave: URL del repositorio):
              - alumnos (nombre, mail, padrón): dueño son los excels, se regenera siempre.
              - titulo / descripcion / tags: dueño es el YAML; solo se completan
                si están vacíos, así las ediciones manuales nunca se pisan.
              - proyectos que dejan de aparecer en el excel: se conservan con
                aviso (o se eliminan con --prune).

            Flags:
              --dry-run     muestra el reporte sin escribir el YAML
              --prune       elimina proyectos que ya no figuran en el excel
              --no-github   no consulta la API de GitHub
              --force       regenera todo desde cero (pisa ediciones manuales)

  readme    Renderiza README.md desde data/entregables.yaml (no toca excels ni red).

Uso:
    uv run scripts/build.py dataset
    uv run scripts/build.py readme
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
import unicodedata
from pathlib import Path

import requests
import yaml
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
YAML_PATH = DATA_DIR / "entregables.yaml"
README_PATH = ROOT / "README.md"
LINKS_XLSX = INPUT_DIR / "links_entregas.xlsx"
MAILS_XLSX = INPUT_DIR / "mails.xlsx"

GITHUB_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
CONECTORES = {"del", "de", "la", "las", "los", "y", "e", "da", "do", "das", "dos"}


# ---------------------------------------------------------------- utilidades

def norm(texto):
    """Normaliza un nombre: sin acentos, minúsculas, espacios colapsados."""
    if texto is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).lower().strip()


def pretty_name(texto):
    """Capitaliza un nombre respetando conectores (del, de, la...)."""
    palabras = re.sub(r"\s+", " ", str(texto)).strip().split()
    partes = []
    for i, palabra in enumerate(palabras):
        if palabra.lower() in CONECTORES and i > 0:
            partes.append(palabra.lower())
        else:
            partes.append(palabra[:1].upper() + palabra[1:])
    return " ".join(partes)


def repo_canonico(url):
    """Devuelve (url_canonica, clave) para una URL de repositorio."""
    url = str(url or "").strip()
    m = GITHUB_RE.search(url)
    if m:
        url_canonica = f"https://github.com/{m.group(1)}/{m.group(2)}"
        return url_canonica, url_canonica.lower()
    return url.rstrip("/"), url.lower()


def titulo_desde_repo(repo_url):
    """Título de fallback humanizando el nombre del repo."""
    nombre = repo_url.rstrip("/").split("/")[-1]
    tokens = [t for t in re.split(r"[-_\s]+", nombre) if t]
    partes = []
    for i, token in enumerate(tokens):
        if token.isupper() and len(token) <= 6:
            partes.append(token)
        elif token.lower() in CONECTORES and i > 0:
            partes.append(token.lower())
        else:
            partes.append(token[:1].upper() + token[1:].lower())
    return " ".join(partes)


def campo_manual(previo, clave):
    """Devuelve (valor, falta). falta=True solo si la clave no existe en el YAML.

    Si la clave existe (aunque esté vacía) es edición manual y no se pisa;
    borrar la línea del YAML para que el script vuelva a sembrarla.
    """
    if previo and clave in previo:
        return previo[clave], False
    return None, True


def esc(valor):
    """Escapa el contenido de una celda de tabla markdown."""
    texto = str(valor or "").strip()
    texto = texto.replace("|", "\\|").replace("\n", " ")
    return texto or "—"


# ------------------------------------------------------------------- lectura

def leer_links():
    """Agrupa las filas del excel de entregas por repositorio.

    Los alumnos de un mismo grupo comparten fila de repo (bloques consecutivos).
    Devuelve [{repo_url, repo_key, integrantes: [(nombre, mail_fila), ...]}].
    """
    wb = load_workbook(LINKS_XLSX, data_only=True)
    ws = wb.worksheets[0]
    grupos = []
    por_key = {}
    for fila in ws.iter_rows(min_row=2, values_only=True):
        valores = list(fila) + [None] * 3
        alumno, mail, link = valores[0], valores[1], valores[2]
        if not alumno or not link:
            continue
        repo_url, repo_key = repo_canonico(link)
        if repo_key not in por_key:
            grupo = {"repo_url": repo_url, "repo_key": repo_key, "integrantes": []}
            por_key[repo_key] = grupo
            grupos.append(grupo)
        grupo["integrantes"].append(
            (str(alumno).strip(), str(mail).strip() if mail else None)
        )
    return grupos


def leer_mails():
    """Lee el formulario de mails. Devuelve ({nombre_normalizado: registro}, duplicados)."""
    wb = load_workbook(MAILS_XLSX, data_only=True)
    ws = wb.worksheets[0]
    alumnos = {}
    duplicados = []
    for fila in ws.iter_rows(min_row=2, values_only=True):
        valores = list(fila) + [None] * 4
        _ts, mail, nombre, padron = valores[0], valores[1], valores[2], valores[3]
        if not nombre or not mail:
            continue
        clave = norm(nombre)
        registro = {
            "nombre": str(nombre).strip(),
            "mail": str(mail).strip(),
            "padron": int(padron) if padron is not None else None,
        }
        if clave in alumnos:
            duplicados.append(registro["nombre"])
            continue
        alumnos[clave] = registro
    return alumnos, duplicados


def buscar_mail(nombre, mails_map):
    """Busca el registro de mail de un alumno con matcheo tolerante.

    1) nombre completo normalizado exacto
    2) primer + último token ("delfina ansaldo")
    3) apellido único en el formulario
    Devuelve (clave, registro) o (None, None).
    """
    clave = norm(nombre)
    if clave in mails_map:
        return clave, mails_map[clave]
    tokens = clave.split()
    if len(tokens) >= 2:
        primero_ultimo = f"{tokens[0]} {tokens[-1]}"
        if primero_ultimo in mails_map:
            return primero_ultimo, mails_map[primero_ultimo]
    if tokens:
        ultimos = [k for k in mails_map if k.split()[-1] == tokens[-1]]
        if len(ultimos) == 1:
            return ultimos[0], mails_map[ultimos[0]]
    return None, None


# ------------------------------------------------------------- github (seed)

def extraer_readme(texto):
    """Del README: primer H1 y primer párrafo "real" (sin badges ni HTML)."""
    h1 = None
    parrafo = None
    for linea in texto.splitlines():
        l = linea.strip()
        if not l:
            continue
        if l.startswith("#"):
            if h1 is None and l.startswith("# "):
                h1 = l[2:].strip().strip("*_`")
            continue
        if l.startswith(("![", "[!", "<")):
            continue
        limpio = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", l)
        limpio = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", limpio)
        limpio = re.sub(r"[`*_]", "", limpio).strip()
        if not limpio or limpio.startswith(("#", "|")):
            continue
        if parrafo is None and len(limpio) >= 30:
            parrafo = limpio
        if h1 and parrafo:
            break
    return h1, parrafo


def github_seed(repo_url):
    """Consulta la API de GitHub: descripción, topics y README del repo."""
    m = GITHUB_RE.search(repo_url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    headers = {"Accept": "application/vnd.github+json"}
    seed = {}
    try:
        r = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}", headers=headers, timeout=10
        )
        if r.ok:
            data = r.json()
            seed["descripcion"] = (data.get("description") or "").strip()
            topics = [str(t) for t in (data.get("topics") or [])]
            if not topics and data.get("language"):
                topics = [str(data["language"]).lower()]
            seed["tags"] = topics[:8]
        else:
            print(f"  [aviso] GitHub API {r.status_code} en {owner}/{repo}")
    except requests.RequestException as e:
        print(f"  [aviso] no se pudo consultar {owner}/{repo}: {e}")
        return None
    try:
        r = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/readme", headers=headers, timeout=10
        )
        if r.ok:
            contenido = base64.b64decode(r.json().get("content", "")).decode("utf-8", "replace")
            h1, parrafo = extraer_readme(contenido)
            seed["titulo"] = h1 or ""
            if not seed.get("descripcion") and parrafo:
                seed["descripcion"] = parrafo
    except requests.RequestException:
        pass
    return seed


# ---------------------------------------------------------------- dataset

def construir_fresh(grupos, mails_map):
    """Arma la estructura cruda desde los excels (sin merge ni GitHub)."""
    proyectos = []
    sin_formulario = []
    usados = set()
    for grupo in grupos:
        alumnos = []
        for nombre, mail_fila in grupo["integrantes"]:
            clave_form, registro = buscar_mail(nombre, mails_map)
            if registro:
                alumnos.append(
                    {
                        "nombre": pretty_name(nombre),
                        "mail": registro["mail"],
                        "padron": registro["padron"],
                    }
                )
                usados.add(clave_form)
            elif mail_fila:
                alumnos.append({"nombre": pretty_name(nombre), "mail": mail_fila, "padron": None})
            else:
                alumnos.append({"nombre": pretty_name(nombre), "mail": None, "padron": None})
                sin_formulario.append(pretty_name(nombre))
        proyectos.append(
            {"repo": grupo["repo_url"], "repo_key": grupo["repo_key"], "alumnos": alumnos}
        )
    pendientes = [
        {**m, "nombre": pretty_name(m["nombre"])}
        for k, m in mails_map.items()
        if k not in usados
    ]
    pendientes.sort(key=lambda a: a["nombre"].lower())
    return proyectos, pendientes, sin_formulario


def mezclar(doc_actual, fresh, args):
    """Aplica las reglas de merge sobre el YAML existente."""
    previos = {}
    orden_previo = []
    for p in ((doc_actual or {}).get("proyectos") or []):
        _, clave = repo_canonico(p.get("repo", ""))
        previos[clave] = p
        orden_previo.append(clave)

    default_cuatrimestre = str((doc_actual or {}).get("cuatrimestre") or "2026 1C")

    proyectos = []
    alumnos_cambiados = []
    for fp in fresh:
        previo = previos.get(fp["repo_key"])
        extras = {
            k: v
            for k, v in (previo or {}).items()
            if k not in {"repo", "titulo", "descripcion", "tags", "alumnos", "cuatrimestre"}
        }

        # Dueño de cada campo: si la clave existe en el YAML (aunque esté vacía)
        # es edición manual y no se pisa. Borrar la línea para que el script
        # vuelva a sembrarla desde la API de GitHub.
        titulo, falta_titulo = campo_manual(previo, "titulo")
        descripcion, falta_desc = campo_manual(previo, "descripcion")
        tags, falta_tags = campo_manual(previo, "tags")
        cuatrimestre, _ = campo_manual(previo, "cuatrimestre")
        if cuatrimestre is None:
            cuatrimestre = default_cuatrimestre

        seed = {}
        if (falta_titulo or falta_desc or falta_tags) and not args.no_github:
            seed = github_seed(fp["repo"]) or {}

        if falta_titulo:
            titulo = seed.get("titulo") or titulo_desde_repo(fp["repo"])
        if falta_desc:
            descripcion = seed.get("descripcion") or ""
        if falta_tags:
            tags = seed.get("tags") or []

        entry = {
            "repo": fp["repo"],
            "titulo": titulo,
            "cuatrimestre": cuatrimestre,
            "descripcion": descripcion,
            "tags": tags,
            "alumnos": fp["alumnos"],
            **extras,
        }
        proyectos.append(entry)

        nombres_previos = {norm(a.get("nombre")) for a in (previo or {}).get("alumnos", [])}
        nombres_fresh = {norm(a.get("nombre")) for a in fp["alumnos"]}
        if previo and nombres_previos != nombres_fresh:
            alumnos_cambiados.append(fp["repo"])

    usados_keys = {fp["repo_key"] for fp in fresh}
    huerfanos = [previos[k] for k in orden_previo if k not in usados_keys]
    if huerfanos:
        nombres = [p.get("repo") for p in huerfanos]
        if args.prune:
            print(f"  [aviso] {len(huerfanos)} proyecto(s) fuera del excel, eliminado(s): {nombres}")
        else:
            print(f"  [aviso] {len(huerfanos)} proyecto(s) fuera del excel, conservado(s): {nombres}")
            proyectos.extend(huerfanos)

    extras = {
        k: v
        for k, v in (doc_actual or {}).items()
        if k not in {"materia", "cuatrimestre", "proyectos", "pendientes"}
    }
    doc = {
        "materia": (doc_actual or {}).get("materia") or "TIMMD",
        "cuatrimestre": default_cuatrimestre,
        "intro": (doc_actual or {}).get("intro") or "",
        "proyectos": proyectos,
        **extras,
    }
    return doc, alumnos_cambiados, huerfanos


def escribir_yaml(doc):
    YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    encabezado = (
        "# Dataset de entregables — fuente de verdad del README.\n"
        "# Editar a mano: intro, titulo, descripcion, tags, cuatrimestre y notas.\n"
        "# Regenerar el README con: uv run scripts/build.py readme\n"
        "# Reglas de 'dataset': alumnos se regenera desde los excels;\n"
        "#   titulo/descripcion/tags son de edición manual y nunca se pisan\n"
        "#   (borrar la línea para que el script los vuelva a sembrar desde GitHub).\n"
        "# cuatrimestre: en proyectos nuevos se siembra del default (nivel superior).\n"
    )
    texto = encabezado + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=110)
    YAML_PATH.write_text(texto, encoding="utf-8")


def cmd_dataset(args):
    doc_actual = None if args.force else cargar_yaml()
    grupos = leer_links()
    mails_map, duplicados = leer_mails()
    fresh, pendientes, sin_formulario = construir_fresh(grupos, mails_map)
    doc, alumnos_cambiados, huerfanos = mezclar(doc_actual, fresh, args)

    total_alumnos = sum(len(p["alumnos"]) for p in doc["proyectos"])
    con_mail = sum(1 for p in doc["proyectos"] for a in p["alumnos"] if a.get("mail"))
    nuevos = sum(1 for fp in fresh if not doc_actual)

    print("Reporte:")
    print(f"  proyectos: {len(doc['proyectos'])} (nuevos: {nuevos}, conservados: {len(fresh) - nuevos}, huérfanos: {len(huerfanos)})")
    print(f"  alumnos: {total_alumnos} (con mail: {con_mail}, sin formulario: {len(sin_formulario)})")
    if sin_formulario:
        print(f"    sin formulario: {', '.join(sin_formulario)}")
    if alumnos_cambiados:
        print(f"    alumnos actualizados en: {alumnos_cambiados}")
    if duplicados:
        print(f"  respuestas duplicadas en formulario: {len(duplicados)} ({', '.join(duplicados)})")
    print(f"  pendientes de entrega: {len(pendientes)}")
    if pendientes:
        print(f"    {', '.join(a['nombre'] for a in pendientes)}")

    if args.dry_run:
        print("(dry-run: no se escribió el YAML)")
        return
    escribir_yaml(doc)
    print(f"  escrito: {YAML_PATH}")
    print("  siguiente paso: uv run scripts/build.py readme")


# ------------------------------------------------------------------ readme

def render_readme(doc):
    materia = str(doc.get("materia") or "TIMMD").strip()
    cuatrimestre = str(doc.get("cuatrimestre") or "").strip()
    proyectos = doc.get("proyectos") or []

    lineas = [f"# Entregables — {materia}", ""]

    intro = str(doc.get("intro") or "").strip()
    if not intro:
        intro = f"Listado de proyectos de la materia **{materia}**"
        if cuatrimestre:
            intro += f" · {cuatrimestre}"
        intro += "."
    lineas += [intro, ""]

    total_alumnos = sum(len(p.get("alumnos") or []) for p in proyectos)
    lineas += [f"**{len(proyectos)} proyectos** · {total_alumnos} integrantes", ""]

    lineas += [
        "| Proyecto | Cuatrimestre | Descripción | Alumnos | Contacto | Repositorio | Tags |",
        "|:---------|:-------------|:------------|:--------|:---------|:------------|:-----|",
    ]
    for p in proyectos:
        repo = str(p.get("repo") or "").strip()
        etiqueta_repo = repo.replace("https://github.com/", "") if repo else ""
        celda_repo = f"[{etiqueta_repo}]({repo})" if repo else "—"

        alumnos = p.get("alumnos") or []
        celda_alumnos = "<br>".join(str(a.get("nombre") or "—") for a in alumnos)
        contactos = []
        for a in alumnos:
            mail = str(a.get("mail") or "").strip()
            contactos.append(f"[{mail}](mailto:{mail})" if mail else "—")
        celda_contacto = "<br>".join(contactos)

        tags = p.get("tags") or []
        celda_tags = " ".join(f"`{t}`" for t in tags)

        lineas.append(
            "| {} | {} | {} | {} | {} | {} | {} |".format(
                f"**{esc(p.get('titulo'))}**",
                esc(p.get("cuatrimestre")),
                esc(p.get("descripcion")),
                esc(celda_alumnos),
                esc(celda_contacto),
                esc(celda_repo),
                esc(celda_tags),
            )
        )

    lineas += [
        "",
        "## Sumá tu proyecto",
        "",
        "¿Aprobaste el taller? Tu proyecto puede quedar en esta tabla para que los próximos cuatrimestres lo retomen, lo unifiquen con otros o construyan sobre él.",
        "",
        "→ [CONTRIBUTING.md](CONTRIBUTING.md) explica cómo sumarlo con un pull request: pasos manuales y un prompt listo para hacerlo con tu agente de código.",
    ]

    lineas += [
        "",
        "---",
        "",
        "_README generado automáticamente desde "
        "[`data/entregables.yaml`](data/entregables.yaml) — no editar a mano. "
        "Correr `uv run scripts/build.py readme`._",
        "",
    ]
    return "\n".join(lineas)


def cmd_readme(args):
    doc = cargar_yaml(obligatorio=True)
    README_PATH.write_text(render_readme(doc), encoding="utf-8")
    print(f"README actualizado ({len(doc.get('proyectos') or [])} proyectos): {README_PATH}")


# ------------------------------------------------------------------- main

def cargar_yaml(obligatorio=False):
    if not YAML_PATH.exists():
        if obligatorio:
            sys.exit(f"ERROR: no existe {YAML_PATH}. Corré primero: uv run scripts/build.py dataset")
        return None
    with YAML_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main():
    parser = argparse.ArgumentParser(
        description="Dataset y README de los entregables de TIMMD"
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    d = sub.add_parser("dataset", help="actualiza data/entregables.yaml desde los excels")
    d.add_argument("--dry-run", action="store_true", help="muestra el reporte sin escribir")
    d.add_argument("--prune", action="store_true", help="elimina proyectos fuera del excel")
    d.add_argument("--no-github", action="store_true", help="no consulta la API de GitHub")
    d.add_argument("--force", action="store_true", help="ignora el YAML actual y regenera todo")

    r = sub.add_parser("readme", help="renderiza README.md desde el YAML")

    args = parser.parse_args()
    if args.comando == "dataset":
        cmd_dataset(args)
    else:
        cmd_readme(args)


if __name__ == "__main__":
    main()
