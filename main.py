"""
main.py - Interfaz web de TriaVet (Entregables 2 y 3).

Uso:
    streamlit run main.py
    python main.py            (equivalente: se relanza con Streamlit)

Capa imperativa de la arquitectura híbrida. Este archivo solo:
  1. captura y limpia las entradas del usuario: la descripción en lenguaje
     natural, las mediciones, los datos del paciente, las respuestas a las
     preguntas sugeridas y, en Modo Experto, el conocimiento nuevo;
  2. llama a motor.py, que consulta base_conocimiento.pl mediante PySwip;
  3. presenta los resultados.
No hay lógica de inferencia en Python: la interpretación del texto (DCG), el
diagnóstico, la traza, las hipótesis descartadas, el peso de cada pregunta y
la validación del conocimiento nuevo se resuelven en Prolog. La única
transformación numérica en Python es la opcional del Entregable 3
(preprocesamiento.py), que convierte mediciones continuas en hechos.

Paneles y predicados de Prolog que los alimentan:
  Consulta      interpretar_texto/10 (DCG) y analizar_caso/10
  ¿Por qué?     explicar_caso/5 e hipotesis_descartadas/5
  ¿Qué falta?   que_falta/8 y pregunta_desempate/6
  Modo experto  vista_previa_diagnostico/3, aprender_diagnostico/3,
                aprender_hallazgo/3, aprender_expresion/5, olvidar/4,
                conocimiento_aprendido/3 y texto_aprendido/1
  Consultas     texto exacto de cada consulta enviada a Prolog
"""

from __future__ import annotations

import html
import itertools
import os
import re
import subprocess
import sys
import textwrap
import unicodedata
from pathlib import Path

if __name__ == "__main__":
    from streamlit.runtime.scriptrunner import get_script_run_ctx

    if get_script_run_ctx(suppress_warning=True) is None:
        # `python main.py`: se relanza este mismo archivo con `streamlit run`.
        raise SystemExit(subprocess.call(
            [sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve()), *sys.argv[1:]]
        ))

import streamlit as st

from motor import (
    ETIQUETA_NIVEL,
    ErrorMotor,
    Explicacion,
    HipotesisDescartada,
    Interpretacion,
    MotorTriaVet,
    NodoTraza,
    Recomendacion,
    Sugerencia,
    legible,
)
from preprocesamiento import VARIABLES, Discretizador

AVISO = (
    "TriaVet es una herramienta académica de orientación. "
    "No reemplaza la valoración de un médico veterinario."
)

# Clave del Modo Experto. Se puede cambiar con la variable de entorno
# TRIAVET_CLAVE_EXPERTO (ver README).
CLAVE_EXPERTO = os.environ.get("TRIAVET_CLAVE_EXPERTO", "experto2026")

# Casos de demostración: ahora se escriben como lo diría un tutor.
CASOS_DEMO = {
    "1": ("Cachorro con diarrea con sangre",
          "Mi perrito de 4 meses vomita, está muy decaído, no quiere comer y tiene "
          "diarrea con sangre. Le faltan vacunas."),
    "2": ("Gato que hace fuerza para orinar",
          "Mi gato macho de 3 años hace fuerza para orinar y llora de dolor."),
    "2b": ("Perra decaída que no come",
           "Mi perra de 4 años está decaída y no come desde ayer."),
    "2c": ("Calor y chicles",
           "Mi perro de 4 años estuvo encerrado en el carro al sol, jadea mucho, "
           "está decaído y se comió unos chicles."),
    "extra": ("Pastor alemán con la barriga hinchada",
              "Mi pastor alemán de 4 años tiene la barriga hinchada y dura, hace arcadas, "
              "babea mucho y está inquieto."),
    "3": ("Ojos amarillos (regla del Modo Experto)",
          "Mi perro de 3 años tiene los ojos amarillos, fiebre y está decaído."),
}

PESTANAS = {"consulta": "🐾 Consulta", "porque": "🔍 ¿Por qué?",
            "quefalta": "🧭 ¿Qué falta?", "experto": "🧠 Modo experto",
            "consultas": "🧾 Consultas Prolog"}

# -- Presentación (solo formato: los valores vienen de Prolog) --------------

COLOR_NIVEL = {"critico": "red", "alto": "orange", "medio": "blue", "bajo": "green"}
ESTILO_PRIORIDAD = {
    "critico": ("#b91c1c", "#fef2f2", "🚨"),
    "alto": ("#c2410c", "#fff7ed", "⚠️"),
    "medio": ("#1d4ed8", "#eff6ff", "🩺"),
    "bajo": ("#15803d", "#f0fdf4", "✅"),
    "indeterminado": ("#475569", "#f8fafc", "💬"),
    "datos_invalidos": ("#7f1d1d", "#fef2f2", "⛔"),
}
ESTILO_FRAGMENTO = {
    "hallazgo": ("frag-ok", "hallazgo"),
    "negado": ("frag-no", "lo niega"),
    "paciente": ("frag-pac", "paciente"),
    "sexo": ("frag-pac", "sexo"),
    "edad": ("frag-pac", "edad"),
    "medicion": ("frag-med", "medición"),
    "desconocida": ("frag-desc", "no reconocida"),
}

TIPO_DESCARTE = {
    "exclusion": ("⚖️", "excluida por un diagnóstico dominante"),
    "condicion_excluyente": ("⛔", "condición excluyente (\\+)"),
    "dato_paciente": ("🚫", "no aplica a este paciente"),
    "evidencia_insuficiente": ("🧩", "falta evidencia crítica"),
    "regla": ("✖", "la regla no se cumple"),
}
ESTADO_COMPETIDORA = {
    "confirmada": "✔ Confirmada",
    "parcial": "◐ Parcial",
    "refutada_usuario": "✖ Descartada por su respuesta",
}
CATEGORIA = {"sintoma": "🩺 Síntoma", "prueba": "🧪 Prueba sencilla", "antecedente": "📋 Antecedente"}
OCULTABLES = {"hecho", "condicion"}

ICONO_NODO = {
    "regla": "▶", "verificacion": "≡", "hallazgo": "●", "negacion": "¬", "dato": "◆",
    "hecho": "·", "condicion": "·",
    "no_regla": "✖", "alternativa": "⎇", "falta": "○", "falta_uno": "○",
    "apoyo_insuficiente": "○", "excluyente": "⛔", "dato_incompatible": "⛔",
    "no_hecho": "✖", "condicion_falsa": "✖",
}

_TEXTO = 'fontcolor="#0f172a"'
_FALTA = f'shape=ellipse, style="filled,dashed", fillcolor="#fff1f2", color="#be123c", {_TEXTO}'
ESTILO_NODO = {
    "regla": f'shape=box, style="rounded,filled", fillcolor="#dbeafe", color="#1d4ed8", {_TEXTO}',
    "verificacion": f'shape=note, style=filled, fillcolor="#f1f5f9", color="#64748b", {_TEXTO}',
    "hallazgo": f'shape=ellipse, style=filled, fillcolor="#dcfce7", color="#15803d", {_TEXTO}',
    "negacion": f'shape=box, style="rounded,filled,dashed", fillcolor="#fef9c3", color="#a16207", {_TEXTO}',
    "dato": f'shape=box, style=filled, fillcolor="#ede9fe", color="#6d28d9", {_TEXTO}',
    "hecho": 'shape=plaintext, fontcolor="#64748b"',
    "condicion": 'shape=plaintext, fontcolor="#64748b"',
    "no_regla": f'shape=box, style="rounded,filled", fillcolor="#fee2e2", color="#b91c1c", {_TEXTO}',
    "alternativa": 'shape=box, style="rounded,dashed", color="#b91c1c", fontcolor="#b91c1c"',
    "falta": _FALTA,
    "falta_uno": _FALTA,
    "apoyo_insuficiente": _FALTA,
    "excluyente": f'shape=octagon, style=filled, fillcolor="#fecaca", color="#991b1b", {_TEXTO}',
    "dato_incompatible": f'shape=box, style=filled, fillcolor="#fecaca", color="#991b1b", {_TEXTO}',
    "no_hecho": 'shape=plaintext, fontcolor="#b91c1c"',
    "condicion_falsa": 'shape=plaintext, fontcolor="#b91c1c"',
}

CSS = """
<style>
.block-container {padding-top: 1.6rem; max-width: 1250px;}
.tv-hero {background: linear-gradient(120deg, #0f766e 0%, #0e7490 55%, #1e3a8a 100%);
  color: #fff; border-radius: 18px; padding: 22px 28px; margin-bottom: 14px;
  box-shadow: 0 6px 22px rgba(15, 118, 110, .22);}
.tv-hero h1 {color: #fff; margin: 0; font-size: 2.1rem; line-height: 1.15;}
.tv-hero p {margin: 6px 0 0; opacity: .92; font-size: 1.02rem;}
.tv-hero .tv-tags span {display: inline-block; background: rgba(255,255,255,.16);
  border: 1px solid rgba(255,255,255,.28); border-radius: 999px; padding: 2px 11px;
  margin: 10px 6px 0 0; font-size: .82rem;}
.tv-card {background: #fff; border: 1px solid #e2e8f0; border-radius: 14px;
  padding: 16px 18px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(15,23,42,.05);}
.tv-step {display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 50%; background: #0f766e; color: #fff;
  font-weight: 700; font-size: .9rem; margin-right: 8px;}
.tv-titulo {font-weight: 700; font-size: 1.08rem; color: #0f172a;}
.tv-prioridad {border-radius: 16px; padding: 18px 22px; margin: 6px 0 14px;
  border-left: 8px solid; display: flex; gap: 18px; align-items: center;}
.tv-prioridad .icono {font-size: 2.6rem; line-height: 1;}
.tv-prioridad .nivel {font-size: .8rem; letter-spacing: .08em; font-weight: 700;
  text-transform: uppercase; opacity: .85;}
.tv-prioridad .grande {font-size: 1.55rem; font-weight: 800; line-height: 1.2;}
.tv-prioridad .texto {font-size: 1rem; margin-top: 4px; color: #1e293b;}
.tv-diag {background: #fff; border: 1px solid #e2e8f0; border-radius: 14px;
  padding: 14px 18px; margin-bottom: 10px; border-top: 5px solid;}
.tv-diag .cab {display: flex; justify-content: space-between; align-items: baseline; gap: 10px;}
.tv-diag .nombre {font-size: 1.15rem; font-weight: 750; color: #0f172a;}
.tv-pill {display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: .78rem;
  font-weight: 700; color: #fff; white-space: nowrap;}
.tv-barra {height: 9px; background: #e2e8f0; border-radius: 99px; overflow: hidden; margin: 8px 0 4px;}
.tv-barra > div {height: 100%; border-radius: 99px;}
.tv-chip {display: inline-block; border-radius: 999px; padding: 2px 10px; margin: 3px 4px 0 0;
  font-size: .82rem; border: 1px solid;}
.chip-ok {background: #dcfce7; border-color: #86efac; color: #14532d;}
.chip-no {background: #f1f5f9; border-color: #cbd5e1; color: #475569; text-decoration: line-through;}
.chip-med {background: #e0f2fe; border-color: #7dd3fc; color: #0c4a6e;}
.chip-desc {background: #fef3c7; border-color: #fcd34d; color: #78350f;}
.tv-oracion {font-size: 1.05rem; line-height: 2.05; color: #334155;}
.tv-oracion mark {border-radius: 6px; padding: 1px 5px; position: relative;}
.frag-ok {background: #bbf7d0; color: #14532d;}
.frag-no {background: #e2e8f0; color: #475569; text-decoration: line-through;}
.frag-pac {background: #ddd6fe; color: #4c1d95;}
.frag-med {background: #bae6fd; color: #0c4a6e;}
.frag-desc {background: #fde68a; color: #78350f;}
.tv-leyenda span {margin-right: 10px; font-size: .8rem;}
.tv-resumen {background: #f0fdfa; border: 1px dashed #5eead4; border-radius: 12px;
  padding: 10px 14px; color: #134e4a; margin-top: 8px;}
.tv-experto {background: linear-gradient(120deg, #312e81, #6d28d9); color: #fff;
  border-radius: 14px; padding: 14px 20px; margin-bottom: 12px;}
.tv-experto b {color: #fff;}
</style>
"""


# ---------------------------------------------------------------------------
# Recursos (se crean una sola vez por servidor)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Cargando la base de conocimiento en SWI-Prolog…")
def obtener_motor() -> MotorTriaVet:
    return MotorTriaVet()


@st.cache_resource(show_spinner="Entrenando el clasificador de mediciones…")
def obtener_discretizador() -> Discretizador:
    return Discretizador()


# ---------------------------------------------------------------------------
# Estado y entradas
# ---------------------------------------------------------------------------

def clave_grupo(grupo: str) -> str:
    return f"grupo_{grupo}"


def clave_medicion(variable: str) -> str:
    return f"med_{variable}"


def slug(texto: str) -> str:
    """'Leptospirosis canina' -> 'leptospirosis_canina' (solo formato)."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", texto)
                         if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", sin_tildes.lower()).strip("_")


def inicializar_estado(grupos: list[str]) -> None:
    valores = {"especie": "perro", "edad": 24, "sexo": "macho", "descripcion": "",
               "negados": [], "interpretacion": None, "mostrar_hechos": False,
               "rol": "Tutor", "experto_ok": False, "autor": ""}
    for clave, valor in valores.items():
        st.session_state.setdefault(clave, valor)
    for grupo in grupos:
        st.session_state.setdefault(clave_grupo(grupo), [])
    for variable in VARIABLES:
        st.session_state.setdefault(clave_medicion(variable), None)


def hallazgos_marcados(grupos: list[str]) -> list[str]:
    return [h for g in grupos for h in (st.session_state.get(clave_grupo(g)) or [])]


def mediciones_actuales() -> dict[str, float | None]:
    return {v: st.session_state.get(clave_medicion(v)) for v in VARIABLES}


# -- Callbacks (se ejecutan antes de volver a dibujar) ----------------------

def interpretar_descripcion(grupo_de: dict[str, str], grupos: list[str]) -> None:
    """Envía el texto a la DCG y vuelca lo que Prolog entendió en el formulario."""
    texto = st.session_state.descripcion.strip()
    if not texto:
        st.session_state.interpretacion = None
        return
    try:
        inter = obtener_motor().interpretar(texto)
    except ErrorMotor as exc:
        st.session_state.error_interpretacion = str(exc)
        return
    st.session_state.interpretacion = inter
    if inter.especie:
        st.session_state.especie = inter.especie
    if inter.edad is not None:
        st.session_state.edad = min(inter.edad, 400)
    if inter.sexo:
        st.session_state.sexo = inter.sexo
    for grupo in grupos:
        st.session_state[clave_grupo(grupo)] = [h for h in inter.hallazgos if grupo_de.get(h) == grupo]
    st.session_state.negados = list(inter.negados)
    for variable in VARIABLES:
        st.session_state[clave_medicion(variable)] = None
    for variable, valor in inter.mediciones:
        if variable in VARIABLES:
            st.session_state[clave_medicion(variable)] = valor


def cargar_ejemplo(grupo_de: dict[str, str], grupos: list[str]) -> None:
    codigo = st.session_state.get("ejemplo")
    if codigo in CASOS_DEMO:
        st.session_state.descripcion = CASOS_DEMO[codigo][1]
        interpretar_descripcion(grupo_de, grupos)
    st.session_state.ejemplo = None


def limpiar_caso(grupos: list[str]) -> None:
    for grupo in grupos:
        st.session_state[clave_grupo(grupo)] = []
    for variable in VARIABLES:
        st.session_state[clave_medicion(variable)] = None
    st.session_state.descripcion = ""
    st.session_state.negados = []
    st.session_state.interpretacion = None


def agregar_hallazgos(hallazgos: list[str], grupo_de: dict[str, str]) -> None:
    """El usuario respondió que SÍ presenta los hallazgos."""
    for h in hallazgos:
        clave = clave_grupo(grupo_de[h])
        actuales = list(st.session_state.get(clave) or [])
        if h not in actuales:
            actuales.append(h)
        st.session_state[clave] = actuales
    st.session_state.negados = [n for n in st.session_state.negados if n not in hallazgos]


def agregar_desde(clave_opciones: str, grupo_de: dict[str, str]) -> None:
    agregar_hallazgos(list(st.session_state.get(clave_opciones) or []), grupo_de)


def negar_hallazgos(hallazgos: list[str]) -> None:
    st.session_state.negados = sorted(set(st.session_state.negados) | set(hallazgos))


def olvidar_negados() -> None:
    st.session_state.negados = []


def recargar_base() -> None:
    obtener_motor().recargar()
    st.session_state.aviso_recarga = True


def entrar_experto() -> None:
    if st.session_state.get("clave_ingresada", "") == CLAVE_EXPERTO:
        st.session_state.experto_ok = True
        st.session_state.error_clave = False
    else:
        st.session_state.error_clave = True
    st.session_state.clave_ingresada = ""


def salir_experto() -> None:
    st.session_state.experto_ok = False
    st.session_state.rol = "Tutor"


def aplicar_parametros_url(grupo_de: dict[str, str], grupos: list[str]) -> str | None:
    """?caso=1|2|2b|2c|extra|3 carga un ejemplo y ?panel=... elige la pestaña."""
    if st.session_state.get("url_aplicada"):
        return None
    st.session_state.url_aplicada = True
    codigo = st.query_params.get("caso", "").lower()
    if codigo in CASOS_DEMO:
        st.session_state.ejemplo = codigo
        cargar_ejemplo(grupo_de, grupos)
    if st.query_params.get("rol") == "experto" and st.query_params.get("clave") == CLAVE_EXPERTO:
        st.session_state.rol, st.session_state.experto_ok = "Experto", True
    return PESTANAS.get(st.query_params.get("panel", ""))


# ---------------------------------------------------------------------------
# Piezas visuales
# ---------------------------------------------------------------------------

def nombre(h: str, nombres: dict[str, str]) -> str:
    return nombres.get(h, legible(h))


def chips(hallazgos, nombres, clase: str) -> str:
    return "".join(f'<span class="tv-chip {clase}">{html.escape(nombre(h, nombres))}</span>'
                   for h in hallazgos)


def tarjeta(titulo: str, paso: int | None = None) -> None:
    numero = f'<span class="tv-step">{paso}</span>' if paso else ""
    st.markdown(f'<div class="tv-titulo">{numero}{titulo}</div>', unsafe_allow_html=True)


def oracion_resaltada(inter: Interpretacion, nombres) -> str:
    """La oración del usuario con cada fragmento coloreado según lo que entendió Prolog."""
    piezas = []
    for f in inter.fragmentos:
        texto = html.escape(f.texto)
        if f.tipo not in ESTILO_FRAGMENTO:
            piezas.append(texto)
            continue
        clase, tipo = ESTILO_FRAGMENTO[f.tipo]
        if f.tipo == "hallazgo":
            ayuda = nombre(str(f.valor), nombres)
        elif f.tipo == "negado":
            ayuda = "no presenta: " + ", ".join(nombre(str(h), nombres) for h in f.valor)
        elif f.tipo == "medicion":
            ayuda = f"{VARIABLES[f.valor[0]].nombre if f.valor[0] in VARIABLES else f.valor[0]}: {f.valor[1]:g}"
        elif f.tipo == "paciente":
            ayuda = " ".join(v for v in f.valor if v != "no_indicado")
        else:
            ayuda = f"{tipo}: {f.valor}"
        piezas.append(f'<mark class="{clase}" title="{html.escape(ayuda)}">{texto}</mark>')
    return " ".join(piezas)


def banner_prioridad(prioridad: str, recomendacion: str) -> None:
    borde, fondo, icono = ESTILO_PRIORIDAD.get(prioridad, ("#475569", "#f8fafc", "ℹ️"))
    etiqueta = ETIQUETA_NIVEL.get(prioridad, prioridad)
    partes = recomendacion.split(":", 1)
    titulo, texto = (partes[0], partes[1].strip()) if len(partes) == 2 else (etiqueta, recomendacion)
    texto = texto[:1].upper() + texto[1:]
    st.markdown(
        f'<div class="tv-prioridad" style="background:{fondo}; border-color:{borde};">'
        f'<div class="icono">{icono}</div><div>'
        f'<div class="nivel" style="color:{borde}">Prioridad {html.escape(etiqueta)}</div>'
        f'<div class="grande" style="color:{borde}">{html.escape(titulo.capitalize())}</div>'
        f'<div class="texto">{html.escape(texto)}</div></div></div>',
        unsafe_allow_html=True,
    )


def tarjeta_diagnostico(i: int, d, nombres) -> None:
    borde = ESTILO_PRIORIDAD.get(d.severidad, ("#64748b", "", ""))[0]
    sustento = chips(d.sustento, nombres, "chip-ok") if d.sustento else ""
    agravantes = (f'<div style="margin-top:6px;font-size:.88rem;color:#9a3412">⬆ Agravantes: '
                  f'{html.escape(", ".join(legible(a) for a in d.agravantes))}</div>'
                  if d.agravantes else "")
    st.markdown(
        f'<div class="tv-diag" style="border-top-color:{borde}">'
        f'<div class="cab"><span class="nombre">{i}. {html.escape(d.nombre)}</span>'
        f'<span class="tv-pill" style="background:{borde}">'
        f'{html.escape(ETIQUETA_NIVEL.get(d.severidad, d.severidad))}</span></div>'
        f'<div class="tv-barra"><div style="width:{d.certeza}%;background:{borde}"></div></div>'
        f'<div style="font-size:.85rem;color:#475569">Certeza {d.certeza} %</div>'
        f'<div style="margin-top:6px">{sustento}</div>{agravantes}'
        f'<div style="margin-top:10px;color:#1e293b">💡 <b>Mientras tanto:</b> '
        f'{html.escape(d.indicacion)}</div></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Árbol de inferencia: Graphviz y texto
# ---------------------------------------------------------------------------

def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace('"', '\\"')


def _lineas_nodo(nodo: NodoTraza) -> list[str]:
    if nodo.tipo == "hallazgo":
        return [nodo.descripcion]
    if nodo.tipo in ("hecho", "condicion", "no_hecho", "condicion_falsa"):
        return textwrap.wrap(nodo.etiqueta, 60)
    if nodo.tipo in ("regla", "no_regla"):
        return [f"[Nivel {nodo.nivel}] {nodo.etiqueta}", *textwrap.wrap(nodo.descripcion, 44)]
    return [*textwrap.wrap(nodo.etiqueta, 52), *textwrap.wrap(nodo.descripcion, 44)]


def arbol_dot(nodos: list[NodoTraza], mostrar_hechos: bool) -> str:
    lineas = [
        "digraph traza {",
        'rankdir=LR; bgcolor="transparent"; nodesep=0.12; ranksep=0.3;',
        'node [fontname="Helvetica", fontsize=12, margin="0.12,0.05"];',
        'edge [color="#94a3b8", arrowsize=0.6];',
    ]
    contador = itertools.count()

    def agregar(nodo: NodoTraza, padre: str | None) -> None:
        if not mostrar_hechos and nodo.tipo in OCULTABLES:
            return
        ident = f"n{next(contador)}"
        etiqueta = "\\n".join(_escapar(t) for t in _lineas_nodo(nodo))
        lineas.append(f'{ident} [label="{etiqueta}", {ESTILO_NODO.get(nodo.tipo, "")}];')
        if padre:
            lineas.append(f"{padre} -> {ident};")
        for hijo in nodo.hijos:
            agregar(hijo, ident)

    for nodo in nodos:
        agregar(nodo, None)
    lineas.append("}")
    return "\n".join(lineas)


def _linea_texto(nodo: NodoTraza) -> str:
    icono = ICONO_NODO.get(nodo.tipo, "•")
    if nodo.tipo in ("regla", "no_regla"):
        return f"{icono} [Nivel {nodo.nivel}] {nodo.etiqueta}  —  {nodo.descripcion}"
    if nodo.tipo == "hallazgo":
        return f"{icono} {nodo.descripcion} ({nodo.etiqueta})"
    if nodo.tipo in OCULTABLES:
        return f"{icono} {nodo.etiqueta}"
    return f"{icono} {nodo.etiqueta}  —  {nodo.descripcion}"


def traza_texto(nodos: list[NodoTraza], mostrar_hechos: bool) -> str:
    lineas: list[str] = []

    def recorrer(hijos: list[NodoTraza], prefijo: str) -> None:
        visibles = [n for n in hijos if mostrar_hechos or n.tipo not in OCULTABLES]
        for i, nodo in enumerate(visibles):
            ultimo = i == len(visibles) - 1
            lineas.append(f"{prefijo}{'└─ ' if ultimo else '├─ '}{_linea_texto(nodo)}")
            recorrer(nodo.hijos, prefijo + ("   " if ultimo else "│  "))

    for raiz in nodos:
        lineas.append(_linea_texto(raiz))
        recorrer(raiz.hijos, "")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------

def barra_lateral(especies, sexos, grupo_de, grupos) -> None:
    with st.sidebar:
        st.markdown("## 🐾 TriaVet")
        st.segmented_control("¿Quién usa el sistema?", ["Tutor", "Experto"], key="rol",
                             help="El Modo Experto permite enseñar reglas nuevas al sistema.")
        if st.session_state.rol == "Experto":
            if st.session_state.experto_ok:
                st.success("🔓 Modo experto activo", icon="🧠")
                st.text_input("Su nombre (queda registrado en cada regla)", key="autor",
                              placeholder="p. ej.: Dra. Ospina")
                st.button("Cerrar sesión de experto", on_click=salir_experto, width="stretch")
            else:
                st.text_input("Clave de experto", type="password", key="clave_ingresada")
                st.button("Entrar", on_click=entrar_experto, type="primary", width="stretch")
                if st.session_state.get("error_clave"):
                    st.error("Clave incorrecta.")

        st.divider()
        st.markdown("#### Paciente")
        st.caption("Se completa solo a partir de la descripción; puede corregirlo aquí.")
        st.radio("Especie", list(especies), format_func=especies.get, key="especie", horizontal=True)
        st.number_input("Edad (meses)", min_value=0, max_value=400, step=1, key="edad",
                        help="La base admite de 0 a 300 meses.")
        st.radio("Sexo", list(sexos), format_func=sexos.get, key="sexo", horizontal=True)

        st.divider()
        if st.session_state.negados:
            st.caption("Respondió que **no** presenta: "
                       + ", ".join(legible(h) for h in st.session_state.negados))
            st.button("Olvidar respuestas negativas", on_click=olvidar_negados, width="stretch")
        st.button("🧹 Nuevo caso", on_click=limpiar_caso, args=(grupos,), width="stretch")
        st.button("🔄 Recargar base de conocimiento", on_click=recargar_base, width="stretch",
                  help="Vuelve a leer base_conocimiento.pl, como al reiniciar la aplicación.")
        st.caption(f"⚠️ {AVISO}")


# ---------------------------------------------------------------------------
# Pestaña Consulta
# ---------------------------------------------------------------------------

def panel_consulta(resultado, catalogo, nombres, grupo_de, grupos, derivados, negados) -> None:
    izquierda, derecha = st.columns([1.05, 1], gap="large")

    with izquierda:
        with st.container(border=True):
            tarjeta("Cuéntenos qué le pasa a su mascota", 1)
            st.text_area(
                "Descripción", key="descripcion", height=130, label_visibility="collapsed",
                placeholder="Ejemplo: mi perrita de 4 meses vomita mucho, tiene diarrea con "
                            "sangre y está decaída. No tiene fiebre. Nunca la vacunaron.",
            )
            st.pills("O pruebe con un ejemplo", list(CASOS_DEMO), key="ejemplo",
                     format_func=lambda c: CASOS_DEMO[c][0],
                     on_change=cargar_ejemplo, args=(grupo_de, grupos))
            st.button("🔎 Interpretar y analizar", type="primary", width="stretch",
                      on_click=interpretar_descripcion, args=(grupo_de, grupos))

        inter: Interpretacion | None = st.session_state.interpretacion
        if inter:
            with st.container(border=True):
                tarjeta("Lo que entendió el sistema (gramática DCG en Prolog)", 2)
                st.markdown(f'<div class="tv-oracion">{oracion_resaltada(inter, nombres)}</div>',
                            unsafe_allow_html=True)
                st.markdown(
                    '<div class="tv-leyenda"><span class="frag-ok">■ hallazgo</span>'
                    '<span class="frag-no">■ negado</span><span class="frag-pac">■ paciente</span>'
                    '<span class="frag-med">■ medición</span><span class="frag-desc">■ no reconocido</span></div>',
                    unsafe_allow_html=True)
                st.markdown(f'<div class="tv-resumen">🗨️ {html.escape(inter.resumen)}</div>',
                            unsafe_allow_html=True)
                if inter.desconocidas:
                    st.caption("Palabras que el léxico aún no conoce: "
                               + ", ".join(f"«{p}»" for p in inter.desconocidas)
                               + ". Un experto puede enseñarlas en el Modo Experto.")

        with st.expander("📏 Mediciones (opcional) · se convierten en hechos para Prolog",
                         expanded=any(v is not None for v in mediciones_actuales().values())):
            columnas = st.columns(2)
            for i, (clave, var) in enumerate(VARIABLES.items()):
                columnas[i % 2].number_input(
                    f"{var.nombre} ({var.unidad})", min_value=float(var.minimo),
                    max_value=float(var.maximo), step=float(var.paso), value=None,
                    key=clave_medicion(clave), placeholder="sin medir",
                )
            if derivados:
                st.markdown(" ".join(
                    f'<span class="tv-chip chip-med">{html.escape(h.nombre)} {h.valor:g} {h.unidad}'
                    f' → {html.escape(nombre(h.hallazgo, nombres) if h.hallazgo else "normal")}</span>'
                    for h in derivados), unsafe_allow_html=True)
                st.caption(f"Clasificación con {derivados[0].metodo}.")

        with st.expander("✏️ Revisar o completar los hallazgos manualmente"):
            for grupo, nombre_grupo, opciones in catalogo:
                st.pills(nombre_grupo, opciones, selection_mode="multi", key=clave_grupo(grupo),
                         format_func=lambda h: nombre(h, nombres))

    with derecha:
        tarjeta("Resultado del triage", 3)
        banner_prioridad(resultado.prioridad, resultado.recomendacion)
        if resultado.alarmas:
            st.error("**Signos de alarma:** " + ", ".join(nombre(a, nombres) for a in resultado.alarmas),
                     icon="🚨")
        if resultado.validos:
            st.markdown("**Hechos enviados al motor:** " + chips(resultado.validos, nombres, "chip-ok")
                        + chips(negados, nombres, "chip-no"),
                        unsafe_allow_html=True)
        if resultado.ignorados:
            st.warning("Prolog ignoró: " + ", ".join(f"«{t}»" for t in resultado.ignorados))
        diagnosticos = [d for d in resultado.diagnosticos]
        if not diagnosticos:
            st.info("Describa el caso o marque algún hallazgo para obtener una orientación.", icon="💬")
        for i, d in enumerate(diagnosticos, start=1):
            tarjeta_diagnostico(i, d, nombres)
        if diagnosticos:
            st.caption("¿Por qué este resultado? Abra la pestaña 🔍 ¿Por qué?. "
                       "¿Falta información? Abra 🧭 ¿Qué falta?.")


# ---------------------------------------------------------------------------
# Pestañas ¿Por qué? y ¿Qué falta? (Entregable 2)
# ---------------------------------------------------------------------------

def panel_por_que(explicaciones: list[Explicacion], descartadas: list[HipotesisDescartada],
                  nombres) -> None:
    if not explicaciones:
        st.info("No hay conclusiones que auditar todavía: describa el caso en la pestaña Consulta.")
        return

    por_id = {e.id: e for e in explicaciones}
    if st.session_state.get("explicacion_elegida") not in por_id:
        st.session_state.explicacion_elegida = explicaciones[0].id
    if len(explicaciones) > 1:
        st.segmented_control("Conclusión a auditar", list(por_id), key="explicacion_elegida",
                             format_func=lambda i: por_id[i].nombre)
    e = por_id[st.session_state.explicacion_elegida or explicaciones[0].id]

    st.subheader(f"Traza de «{e.nombre}»")
    severidad, certeza = st.columns(2)
    with severidad.container(border=True):
        st.markdown("**📈 Cómo se calculó la severidad**")
        st.markdown("\n".join(f"{i}. {paso}" for i, paso in enumerate(e.severidad, start=1)))
    with certeza.container(border=True):
        st.markdown("**🎯 Cómo se calculó la certeza**")
        st.markdown(e.certeza)

    st.markdown("#### 🌳 Árbol de inferencia")
    st.caption("Prolog vuelve a demostrar la conclusión con sus propias cláusulas "
               "(metaintérprete con clause/2). Azul: reglas · verde: hallazgos · amarillo: "
               "negaciones por fallo (\\+) · violeta: datos del paciente.")
    mostrar = st.toggle("Mostrar hechos de la base y comparaciones", key="mostrar_hechos")
    st.graphviz_chart(arbol_dot(e.arbol, mostrar))
    with st.expander("Traza textual"):
        st.code(traza_texto(e.arbol, mostrar), language=None)

    hechos, datos = st.columns([3, 2])
    with hechos:
        st.markdown("#### ✅ Hechos comprobados como verdaderos")
        if e.hechos:
            st.markdown(chips(e.hechos, nombres, "chip-ok"), unsafe_allow_html=True)
        else:
            st.caption("Ningún hallazgo intervino en esta conclusión.")
    with datos:
        st.markdown("#### 🐾 Datos del paciente validados")
        st.markdown(" ".join(f":violet-badge[{a.replace('_', ' ')}: {v}]" for a, v in e.datos))

    st.markdown("#### ⚙️ Reglas disparadas")
    if e.reglas:
        st.dataframe(
            [{"Nivel": r.nivel, "Regla": r.etiqueta, "Qué establece": r.descripcion} for r in e.reglas],
            hide_index=True,
            column_config={"Nivel": st.column_config.NumberColumn(width="small"),
                           "Regla": st.column_config.TextColumn(width="medium"),
                           "Qué establece": st.column_config.TextColumn(width="large")},
        )
    else:
        st.caption("Ninguna regla de diagnóstico se disparó; se aplicó el valor por defecto.")

    st.divider()
    st.markdown("#### 🚫 Hipótesis alternativas descartadas")
    st.caption("Diagnósticos que comparten hallazgos con el caso pero no se concluyeron. "
               "El árbol rojo es la refutación («¿por qué no?») que construye Prolog.")
    if not descartadas:
        st.info("Ninguna otra hipótesis comparte hallazgos con el caso.")
    for d in descartadas:
        icono, tipo = TIPO_DESCARTE.get(d.tipo, ("•", d.tipo))
        with st.expander(f"{icono} {d.nombre} — {tipo}"):
            st.markdown(d.resumen)
            st.markdown("**Comparte con el caso:** " + chips(d.compartidos, nombres, "chip-med"),
                        unsafe_allow_html=True)
            if d.arbol:
                st.graphviz_chart(arbol_dot(d.arbol, False))
                st.code(traza_texto(d.arbol, False), language=None)


def botones_respuesta(s: Sugerencia, nombres, grupo_de, clave: str) -> None:
    si, no = st.columns(2)
    if s.tipo == "hallazgo":
        si.button("✅ Sí, lo presenta", key=f"si_{clave}", width="stretch",
                  on_click=agregar_hallazgos, args=(s.hallazgos, grupo_de))
        no.button("❌ No lo presenta", key=f"no_{clave}", width="stretch",
                  on_click=negar_hallazgos, args=(s.hallazgos,))
        return
    opciones = f"opc_{clave}"
    st.pills("¿Cuál?", s.hallazgos, selection_mode="multi", key=opciones,
             format_func=lambda h: nombre(h, nombres))
    si.button("✅ Agregar los seleccionados", key=f"si_{clave}", width="stretch",
              disabled=not st.session_state.get(opciones),
              on_click=agregar_desde, args=(opciones, grupo_de))
    no.button("❌ Ninguno de ellos", key=f"no_{clave}", width="stretch",
              on_click=negar_hallazgos, args=(s.hallazgos,))


def tarjeta_sugerencia(s: Sugerencia, nombres, grupo_de, clave: str) -> None:
    st.markdown(f"### {s.pregunta}")
    etiquetas = [f":blue-badge[{CATEGORIA.get(s.categoria, s.categoria)}]",
                 f":orange-badge[Peso {s.peso:g}]"]
    if s.desempata:
        etiquetas.append(":violet-badge[Desempata]")
    st.markdown(" ".join(etiquetas))
    st.markdown("**Por qué preguntarlo:**\n" + "\n".join(f"- {m}" for m in s.motivos))
    st.markdown(f"**Qué pasaría:** {s.efecto}")
    if s.verificar:
        st.caption(f"🧪 Cómo verificarlo: {s.verificar}")
    botones_respuesta(s, nombres, grupo_de, clave)


def panel_que_falta(reco: Recomendacion, desempate: Sugerencia | None, nombres, grupo_de) -> None:
    if reco.activo:
        st.warning(f"**Módulo de recomendación activado.** {reco.mensaje}", icon="🧭")
    elif reco.estado == "definitivo":
        st.success(reco.mensaje, icon="✅")
    else:
        st.info(reco.mensaje)

    if desempate:
        clave = "principal_" + "_".join(desempate.hallazgos)
        if reco.activo:
            with st.container(border=True):
                st.caption("🎯 PREGUNTA DE MAYOR PESO · consulta pregunta_desempate/6")
                tarjeta_sugerencia(desempate, nombres, grupo_de, clave)
        else:
            with st.expander("Preguntas opcionales (el dictamen no las necesita)"):
                tarjeta_sugerencia(desempate, nombres, grupo_de, clave)

    if reco.competidoras:
        st.markdown("#### ⚔️ Hipótesis en competencia")
        st.dataframe(
            [{"Diagnóstico": c.nombre,
              "Estado": ESTADO_COMPETIDORA.get(c.estado, c.estado),
              "Activación": c.activacion,
              "Gravedad": ETIQUETA_NIVEL.get(c.gravedad, c.gravedad),
              "Ya presenta": ", ".join(nombre(h, nombres) for h in c.coincidencias),
              "Le falta": "; ".join(c.falta) or "—",
              "Si se confirma, excluiría": ", ".join(c.excluiria) or "—"}
             for c in reco.competidoras],
            hide_index=True,
            column_config={"Activación": st.column_config.ProgressColumn(
                "Activación", min_value=0, max_value=100, format="%d %%",
                help="Porcentaje del perfil que ya cubren los hallazgos (calculado en Prolog).")},
        )

    otras = reco.sugerencias[1:6]
    if otras:
        st.markdown("#### 🔎 Otras preguntas útiles")
        for s in otras:
            clave = "otra_" + "_".join(s.hallazgos)
            with st.expander(f"{s.pregunta} · peso {s.peso:g}"):
                tarjeta_sugerencia(s, nombres, grupo_de, clave)
    if reco.sugerencias:
        with st.expander(f"Ranking completo calculado por Prolog ({len(reco.sugerencias)} preguntas)"):
            st.dataframe(
                [{"#": i, "Pregunta": s.pregunta, "Peso": s.peso,
                  "Desempata": "sí" if s.desempata else "no",
                  "Tipo": CATEGORIA.get(s.categoria, s.categoria)}
                 for i, s in enumerate(reco.sugerencias, start=1)],
                hide_index=True,
            )


# ---------------------------------------------------------------------------
# Pestaña Modo experto (Entregable 3)
# ---------------------------------------------------------------------------

def _mostrar_resultado(r) -> None:
    if r.ok:
        st.session_state.aviso_experto = ("ok", r.mensajes)
    else:
        st.session_state.aviso_experto = ("error", r.mensajes)
    st.session_state.consulta_experto = r.consulta


def datos_diagnostico_formulario() -> dict:
    estado = st.session_state
    return {
        "id": estado.get("nd_id") or slug(estado.get("nd_nombre", "")),
        "nombre": estado.get("nd_nombre", ""),
        "especies": estado.get("nd_especies") or [],
        "curso": estado.get("nd_curso", "agudo"),
        "requisitos": estado.get("nd_requisitos") or [],
        "apoyo": estado.get("nd_apoyo") or [],
        "minimo": estado.get("nd_minimo", 1),
        "severidad": estado.get("nd_severidad", "medio"),
        "certeza": estado.get("nd_certeza", 60),
        "indicacion": estado.get("nd_indicacion", ""),
        "excluye": estado.get("nd_excluye") or [],
        "excluido_por": estado.get("nd_excluido_por") or [],
        "autor": estado.get("autor") or "",
    }


def guardar_diagnostico() -> None:
    r = obtener_motor().aprender_diagnostico(datos_diagnostico_formulario())
    _mostrar_resultado(r)
    if r.ok:
        for clave in ("nd_id", "nd_nombre", "nd_indicacion"):
            st.session_state[clave] = ""
        for clave in ("nd_requisitos", "nd_apoyo", "nd_excluye", "nd_excluido_por"):
            st.session_state[clave] = []


def guardar_hallazgo() -> None:
    e = st.session_state
    expresiones = [x.strip() for x in re.split(r"[\n;,]", e.get("nh_expresiones", "")) if x.strip()]
    r = obtener_motor().aprender_hallazgo(
        e.get("nh_id") or slug(e.get("nh_nombre", "")), e.get("nh_nombre", ""),
        e.get("nh_grupo", "general"), e.get("nh_pregunta", ""), expresiones, e.get("autor") or "")
    _mostrar_resultado(r)
    if r.ok:
        for clave in ("nh_id", "nh_nombre", "nh_pregunta", "nh_expresiones"):
            e[clave] = ""


def guardar_expresion() -> None:
    e = st.session_state
    r = obtener_motor().aprender_expresion(e.get("ne_texto", ""), e.get("ne_hallazgo") or "",
                                           e.get("autor") or "")
    _mostrar_resultado(r)
    if r.ok:
        e.ne_texto = ""


def olvidar(tipo: str, id_: str) -> None:
    _mostrar_resultado(obtener_motor().olvidar(tipo, id_))


def panel_experto(motor: MotorTriaVet, catalogo, nombres, especies) -> None:
    if not st.session_state.experto_ok:
        st.info("Este panel es exclusivo del rol **Experto**. Elija «Experto» en la barra lateral "
                "e ingrese la clave.", icon="🔒")
        return

    st.markdown(
        '<div class="tv-experto">🧠 <b>Modo experto · adquisición de conocimiento en caliente.</b> '
        'Lo que enseñe aquí entra a la memoria de Prolog con <code>assertz/1</code> y se escribe en '
        'la Sección 13 de <code>base_conocimiento.pl</code>: el sistema lo usa de inmediato y lo '
        'conserva al reiniciar.</div>', unsafe_allow_html=True)
    if not st.session_state.autor:
        st.warning("Escriba su nombre en la barra lateral: queda registrado en cada regla.")

    aviso = st.session_state.pop("aviso_experto", None)
    if aviso:
        tipo, mensajes = aviso
        if tipo == "ok":
            st.success("\n\n".join(mensajes), icon="💾")
            st.toast("Conocimiento guardado en base_conocimiento.pl", icon="💾")
        else:
            st.error("No se guardó nada:\n\n" + "\n".join(f"- {m}" for m in mensajes))

    hallazgos_todos = [h for _, _, hs in catalogo for h in hs]
    diagnosticos = motor.nombres_diagnosticos()
    grupos = {g: n for g, n, _ in catalogo}

    nuevo_diag, nuevo_hallazgo, expresion, aprendido = st.tabs(
        ["➕ Nuevo diagnóstico", "🏷️ Nuevo hallazgo", "💬 Enseñar una expresión",
         "📚 Lo aprendido y su persistencia"])

    with nuevo_diag:
        st.caption("Defina el perfil clínico. Prolog lo concluirá cuando un caso tenga todos los "
                   "hallazgos obligatorios y al menos el mínimo de signos de apoyo.")
        a, b = st.columns(2)
        a.text_input("Nombre del diagnóstico", key="nd_nombre", placeholder="p. ej.: Leptospirosis")
        b.text_input("Identificador en Prolog", key="nd_id",
                     placeholder=slug(st.session_state.get("nd_nombre", "")) or "se genera del nombre",
                     help="Átomo en minúscula. Si lo deja vacío se genera a partir del nombre.")
        a, b, c = st.columns(3)
        a.multiselect("Especies", list(especies), default=list(especies), key="nd_especies",
                      format_func=especies.get)
        b.segmented_control("Curso", ["agudo", "cronico"], default="agudo", key="nd_curso",
                            format_func=lambda c: {"agudo": "Agudo", "cronico": "Crónico"}[c])
        c.selectbox("Severidad base", ["bajo", "medio", "alto", "critico"], index=2,
                    key="nd_severidad", format_func=lambda n: ETIQUETA_NIVEL[n])
        st.multiselect("Hallazgos obligatorios (todos deben estar presentes)", hallazgos_todos,
                       key="nd_requisitos", format_func=lambda h: nombre(h, nombres))
        st.multiselect("Hallazgos de apoyo (refuerzan la hipótesis)", hallazgos_todos,
                       key="nd_apoyo", format_func=lambda h: nombre(h, nombres))
        a, b = st.columns(2)
        a.number_input("Mínimo de signos de apoyo", min_value=0, max_value=10, value=1, key="nd_minimo")
        b.slider("Certeza base (%)", 10, 90, 60, step=5, key="nd_certeza",
                 help="Certeza inicial; Prolog suma 10 puntos por cada signo de apoyo presente.")
        st.text_area("Indicación para el tutor mientras consigue atención", key="nd_indicacion",
                     height=70)
        a, b = st.columns(2)
        a.multiselect("Si se concluye, excluye a…", list(diagnosticos), key="nd_excluye",
                      format_func=diagnosticos.get)
        b.multiselect("Queda excluido por…", list(diagnosticos), key="nd_excluido_por",
                      format_func=diagnosticos.get)

        datos = datos_diagnostico_formulario()
        errores, texto = motor.vista_previa_diagnostico(datos)
        st.markdown("**Vista previa: cláusulas que se inyectarán con `assertz/1` y se escribirán en el `.pl`**")
        st.code(texto or "% complete el formulario", language="prolog")
        if errores:
            st.caption("Validación de Prolog: " + " · ".join(errores))
        st.button("💾 Aprender diagnóstico", type="primary", disabled=bool(errores),
                  on_click=guardar_diagnostico, width="stretch")

    with nuevo_hallazgo:
        st.caption("Agregue un signo o antecedente que la base aún no conoce. Las expresiones "
                   "enseñan a la gramática DCG a reconocerlo en el texto del tutor.")
        a, b = st.columns(2)
        a.text_input("Nombre del hallazgo", key="nh_nombre", placeholder="p. ej.: Piel u ojos amarillos")
        b.text_input("Identificador en Prolog", key="nh_id",
                     placeholder=slug(st.session_state.get("nh_nombre", "")) or "se genera del nombre")
        st.selectbox("Grupo", list(grupos), key="nh_grupo", format_func=grupos.get,
                     index=list(grupos).index("general") if "general" in grupos else 0)
        st.text_input("Pregunta para el tutor (módulo ¿Qué falta?)", key="nh_pregunta",
                      placeholder="¿Tiene la piel o los ojos amarillos?")
        st.text_area("Expresiones del tutor (una por línea; use * para una raíz: amarill*)",
                     key="nh_expresiones", height=90, placeholder="ojos amarillos\npiel amarilla\namarill*")
        st.button("💾 Aprender hallazgo", type="primary", on_click=guardar_hallazgo, width="stretch")

    with expresion:
        st.caption("Enseñe un sinónimo de un hallazgo que ya existe. Desde ese momento la DCG lo reconoce.")
        a, b = st.columns(2)
        a.text_input("Cómo lo dice el tutor", key="ne_texto", placeholder="p. ej.: hace popo con sangre")
        b.selectbox("Significa", hallazgos_todos, key="ne_hallazgo",
                    format_func=lambda h: nombre(h, nombres))
        if st.session_state.get("ne_texto"):
            prueba = motor.interpretar(st.session_state.ne_texto)
            st.caption("Hoy el sistema entiende: " + (", ".join(nombre(h, nombres) for h in prueba.hallazgos)
                                                     or "nada"))
        st.button("💾 Aprender expresión", type="primary", on_click=guardar_expresion, width="stretch")

    with aprendido:
        diags, hallazgos, expresiones = motor.conocimiento_aprendido()
        m1, m2, m3 = st.columns(3)
        m1.metric("Diagnósticos aprendidos", len(diags))
        m2.metric("Hallazgos aprendidos", len(hallazgos))
        m3.metric("Expresiones aprendidas", len(expresiones))
        for d in diags:
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                c1.markdown(f"**{d.nombre}** · `{d.id}` · {ETIQUETA_NIVEL.get(d.severidad, d.severidad)}  \n"
                            f"Obligatorios: {', '.join(nombre(h, nombres) for h in d.requisitos) or '—'} · "
                            f"Apoyo (mín. {d.minimo}): {', '.join(nombre(h, nombres) for h in d.apoyo) or '—'}  \n"
                            f":gray[Enseñado por {d.autor} · {d.fecha}]")
                c2.button("🗑️ Olvidar", key=f"olv_d_{d.id}", on_click=olvidar, args=("diagnostico", d.id))
        for h_id, h_nombre, grupo, autor, fecha in hallazgos:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"🏷️ **{h_nombre}** · `{h_id}` · {grupos.get(grupo, grupo)} · :gray[{autor} · {fecha}]")
            c2.button("🗑️", key=f"olv_h_{h_id}", on_click=olvidar, args=("hallazgo", h_id))
        for texto, h, autor, fecha in expresiones:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"💬 «{texto}» → {nombre(h, nombres)} · :gray[{autor} · {fecha}]")
            c2.button("🗑️", key=f"olv_e_{texto}", on_click=olvidar, args=("expresion", texto))

        st.divider()
        st.markdown("#### 💾 Prueba de persistencia")
        st.caption("Izquierda: lo que Prolog tiene en memoria. Derecha: lo que está escrito ahora en la "
                   "Sección 13 de base_conocimiento.pl. «Recargar» borra la memoria y vuelve a leer el "
                   "archivo, igual que un reinicio: lo aprendido debe seguir apareciendo.")
        st.button("🔄 Simular reinicio: recargar base_conocimiento.pl", on_click=recargar_base)
        if st.session_state.pop("aviso_recarga", False):
            st.success("Se volvió a cargar el archivo .pl. Lo aprendido sigue disponible.", icon="🔄")
        izquierda, derecha = st.columns(2)
        izquierda.markdown("**En memoria** · `texto_aprendido/1`")
        izquierda.code(motor.texto_aprendido().strip() or "% (vacío)", language="prolog")
        derecha.markdown("**En el archivo** · Sección 13 de `base_conocimiento.pl`")
        derecha.code(motor.seccion_aprendida_en_archivo() or "% (vacío)", language="prolog")

    consulta = st.session_state.get("consulta_experto")
    if consulta:
        with st.expander("Última consulta del Modo Experto enviada a Prolog"):
            st.code(f"?- {consulta}.", language="prolog")


# ---------------------------------------------------------------------------
# Pestaña Consultas
# ---------------------------------------------------------------------------

def panel_consultas(consultas: list[tuple[str, str]]) -> None:
    st.markdown(
        "Python no razona: arma estas consultas con los datos de la interfaz y muestra lo que "
        "Prolog responde. El texto libre viaja como un átomo entre comillas y lo interpreta la "
        "gramática DCG; los hallazgos viajan como átomos y Prolog los valida con `ground/1`."
    )
    for titulo, consulta in consultas:
        st.markdown(f"**{titulo}**")
        st.code(f"?- {consulta}.", language="prolog")


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="TriaVet", page_icon="🐾", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        motor = obtener_motor()
        catalogo = motor.catalogo()
        nombres = motor.nombres_hallazgos()
        especies, sexos = motor.opciones_paciente()
    except ErrorMotor as exc:
        st.error(f"No se pudo iniciar el motor de inferencia: {exc}")
        st.stop()
    discretizador = obtener_discretizador()

    grupos = [g for g, _, _ in catalogo]
    grupo_de = {h: g for g, _, hallazgos in catalogo for h in hallazgos}
    inicializar_estado(grupos)
    pestana_inicial = aplicar_parametros_url(grupo_de, grupos)
    barra_lateral(especies, sexos, grupo_de, grupos)

    especie = st.session_state.especie
    edad = st.session_state.edad
    sexo = st.session_state.sexo
    derivados = discretizador.discretizar(mediciones_actuales(), especie)
    medidos = [h.hallazgo for h in derivados if h.hallazgo]
    hallazgos = list(dict.fromkeys(hallazgos_marcados(grupos) + medidos))
    # Una medición objetiva prevalece sobre una negación del texto.
    negados = [n for n in st.session_state.negados if n not in hallazgos]

    try:
        resultado = motor.analizar_caso(especie, edad, sexo, hallazgos)
        explicaciones = motor.explicar(especie, edad, sexo, hallazgos)
        descartadas = motor.descartadas(especie, edad, sexo, hallazgos)
        reco = motor.que_falta(especie, edad, sexo, hallazgos, negados)
        desempate = motor.pregunta_desempate(especie, edad, sexo, hallazgos, negados)
    except ErrorMotor as exc:
        st.error(f"Error al consultar el motor de inferencia: {exc}")
        st.stop()

    st.markdown(
        '<div class="tv-hero"><h1>🐾 TriaVet</h1>'
        '<p>Describa con sus palabras lo que le pasa a su perro o gato y el sistema experto le '
        'dirá qué tan urgente es, qué podría tener y por qué.</p>'
        '<div class="tv-tags"><span>Lenguaje natural · DCG</span><span>Caja blanca · ¿Por qué?</span>'
        '<span>¿Qué falta?</span><span>Aprendizaje en caliente</span><span>SWI-Prolog + PySwip</span>'
        '</div></div>', unsafe_allow_html=True)

    # Etiquetas fijas: si cambiaran entre interacciones, Streamlit volvería a la
    # primera pestaña.
    consulta_tab, por_que, que_falta, experto, consultas = st.tabs(
        list(PESTANAS.values()), default=pestana_inicial,
    )
    with consulta_tab:
        panel_consulta(resultado, catalogo, nombres, grupo_de, grupos, derivados, negados)
    with por_que:
        panel_por_que(explicaciones, descartadas, nombres)
    with que_falta:
        panel_que_falta(reco, desempate, nombres, grupo_de)
    with experto:
        panel_experto(motor, catalogo, nombres, especies)
    with consultas:
        lista = []
        inter = st.session_state.interpretacion
        if inter:
            lista.append(("Lenguaje natural · interpretar_texto/10 (DCG)", inter.consulta))
        lista += [
            ("Dictamen · analizar_caso/10", resultado.consulta),
            ("¿Por qué? · explicar_caso/5", motor.consulta_explicacion(especie, edad, sexo, hallazgos)),
            ("¿Por qué? · hipotesis_descartadas/5", motor.consulta_descartadas(especie, edad, sexo, hallazgos)),
            ("¿Qué falta? · que_falta/8", motor.consulta_que_falta(especie, edad, sexo, hallazgos, negados)),
            ("¿Qué falta? · pregunta_desempate/6",
             motor.consulta_pregunta_desempate(especie, edad, sexo, hallazgos, negados)),
        ]
        if st.session_state.get("consulta_experto"):
            lista.append(("Modo experto · última consulta", st.session_state.consulta_experto))
        panel_consultas(lista)


main()
