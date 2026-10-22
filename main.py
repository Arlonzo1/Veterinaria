"""
main.py - Interfaz web de TriaVet con módulo de auditoría ("caja blanca").

Uso:
    streamlit run main.py
    python main.py            (equivalente: se relanza con Streamlit)

Capa imperativa de la arquitectura híbrida (Entregable 2). Este archivo solo:
  1. captura y limpia las entradas del usuario (datos del paciente, hallazgos
     y respuestas a las preguntas sugeridas);
  2. llama a motor.py, que consulta base_conocimiento.pl mediante PySwip;
  3. presenta los resultados.
No hay lógica de inferencia en Python: el diagnóstico, la traza, las
hipótesis descartadas, el estado de la evidencia y el peso de cada pregunta
se calculan en Prolog. Prolog nunca lee del teclado (no se usa read/1): las
entradas viajan como argumentos de cada consulta.

Paneles y predicados de Prolog que los alimentan:
  Dictamen      analizar_caso/10
  ¿Por qué?     explicar_caso/5 e hipotesis_descartadas/5
  ¿Qué falta?   que_falta/8 y pregunta_desempate/6
  Consultas     texto exacto de cada consulta enviada a Prolog
"""

from __future__ import annotations

import itertools
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
    MotorTriaVet,
    NodoTraza,
    Recomendacion,
    Sugerencia,
    legible,
)

AVISO = (
    "TriaVet es una herramienta académica de orientación. "
    "No reemplaza la valoración de un médico veterinario."
)

# Casos precargados para la demostración en clase o en el video.
CASOS_DEMO = {
    "Caso 1 · Inferencia completa: cachorro con diarrea con sangre": {
        "especie": "perro", "edad": 4, "sexo": "macho",
        "hallazgos": ["vomito", "diarrea_con_sangre", "letargo", "anorexia",
                      "vacunacion_incompleta"],
    },
    "Caso 2 · Desempate: gato macho que hace esfuerzo para orinar": {
        "especie": "gato", "edad": 36, "sexo": "macho",
        "hallazgos": ["esfuerzo_para_orinar", "vocalizacion_dolor"],
    },
    "Caso 2b · Evidencia insuficiente: perro decaído que no come": {
        "especie": "perro", "edad": 48, "sexo": "hembra",
        "hallazgos": ["letargo", "anorexia"],
    },
    "Caso 2c · Empate: golpe de calor frente a intoxicación por xilitol": {
        "especie": "perro", "edad": 48, "sexo": "macho",
        "hallazgos": ["exposicion_calor", "jadeo_excesivo", "letargo", "ingesta_xilitol"],
    },
    "Caso extra · Dilatación-torsión gástrica (Entregable 1)": {
        "especie": "perro", "edad": 48, "sexo": "macho",
        "hallazgos": ["raza_torax_profundo", "abdomen_distendido",
                      "arcadas_improductivas", "salivacion_excesiva", "inquietud"],
    },
}
SIN_CASO = "(elegir un caso)"

# -- Presentación (solo formato: los valores vienen de Prolog) --------------

AVISO_NIVEL = {
    "critico": (st.error, "🚨"),
    "alto": (st.warning, "⚠️"),
    "medio": (st.info, "🩺"),
    "bajo": (st.success, "✅"),
    "indeterminado": (st.info, "❔"),
    "datos_invalidos": (st.error, "⛔"),
}
COLOR_NIVEL = {"critico": "red", "alto": "orange", "medio": "blue", "bajo": "green"}

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

# Nodos que solo detallan hechos de la base y comparaciones (se pueden ocultar).
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
    # demostración ("¿Por qué?")
    "regla": f'shape=box, style="rounded,filled", fillcolor="#dbeafe", color="#1d4ed8", {_TEXTO}',
    "verificacion": f'shape=note, style=filled, fillcolor="#f1f5f9", color="#64748b", {_TEXTO}',
    "hallazgo": f'shape=ellipse, style=filled, fillcolor="#dcfce7", color="#15803d", {_TEXTO}',
    "negacion": f'shape=box, style="rounded,filled,dashed", fillcolor="#fef9c3", color="#a16207", {_TEXTO}',
    "dato": f'shape=box, style=filled, fillcolor="#ede9fe", color="#6d28d9", {_TEXTO}',
    "hecho": 'shape=plaintext, fontcolor="#64748b"',
    "condicion": 'shape=plaintext, fontcolor="#64748b"',
    # refutación ("¿por qué no?")
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


# ---------------------------------------------------------------------------
# Motor de inferencia (se carga una sola vez por servidor)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Cargando la base de conocimiento en SWI-Prolog…")
def obtener_motor() -> MotorTriaVet:
    return MotorTriaVet()


# ---------------------------------------------------------------------------
# Captura y limpieza de entradas
# ---------------------------------------------------------------------------

def clave_grupo(grupo: str) -> str:
    return f"grupo_{grupo}"


def limpiar_texto_libre(texto: str) -> list[str]:
    """'Vómito, tos;  Fiebre' -> ['vomito', 'tos', 'fiebre'].

    Solo limpieza: quita tildes y espacios sobrantes y separa por comas o
    punto y coma. Decidir si cada término es un hallazgo válido le
    corresponde a Prolog, que informa como ignorados los que no reconoce.
    """
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return [t.strip() for t in re.split(r"[,;]", sin_tildes) if t.strip()]


def inicializar_estado(grupos: list[str]) -> None:
    valores = {"especie": "perro", "edad": 24, "sexo": "macho", "otros": "",
               "negados": [], "caso_demo": SIN_CASO, "mostrar_hechos": False}
    for clave, valor in valores.items():
        st.session_state.setdefault(clave, valor)
    for grupo in grupos:
        st.session_state.setdefault(clave_grupo(grupo), [])


PESTANAS = {"dictamen": "🩺 Dictamen", "porque": "🔍 ¿Por qué?",
            "quefalta": "🧭 ¿Qué falta?", "consultas": "🧾 Consultas Prolog"}


def aplicar_parametros_url(grupo_de: dict[str, str], grupos: list[str]) -> str | None:
    """?caso=1|2|2b|extra precarga un caso de demostración y ?panel=porque|
    quefalta|consultas elige la pestaña inicial (solo al abrir la página)."""
    if st.session_state.get("url_aplicada"):
        return None
    st.session_state.url_aplicada = True
    codigo = st.query_params.get("caso", "").lower()
    for nombre in CASOS_DEMO:
        if nombre.split(" · ")[0].lower().removeprefix("caso ") == codigo:
            st.session_state.caso_demo = nombre
            cargar_caso_demo(grupo_de, grupos)
    return PESTANAS.get(st.query_params.get("panel", ""))


def hallazgos_seleccionados(grupos: list[str]) -> list[str]:
    seleccion = [h for g in grupos for h in (st.session_state.get(clave_grupo(g)) or [])]
    return seleccion + limpiar_texto_libre(st.session_state.otros)


# -- Callbacks de los botones (se ejecutan antes de volver a dibujar) -------

def cargar_caso_demo(grupo_de: dict[str, str], grupos: list[str]) -> None:
    caso = CASOS_DEMO.get(st.session_state.caso_demo)
    if not caso:
        return
    st.session_state.especie = caso["especie"]
    st.session_state.edad = caso["edad"]
    st.session_state.sexo = caso["sexo"]
    for grupo in grupos:
        st.session_state[clave_grupo(grupo)] = [
            h for h in caso["hallazgos"] if grupo_de.get(h) == grupo
        ]
    st.session_state.otros = ""
    st.session_state.negados = []


def limpiar_caso(grupos: list[str]) -> None:
    for grupo in grupos:
        st.session_state[clave_grupo(grupo)] = []
    st.session_state.otros = ""
    st.session_state.negados = []
    st.session_state.caso_demo = SIN_CASO


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
    """El usuario respondió que NO presenta los hallazgos."""
    st.session_state.negados = sorted(set(st.session_state.negados) | set(hallazgos))


def olvidar_negados() -> None:
    st.session_state.negados = []


def recargar_base() -> None:
    obtener_motor().recargar()


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
    """Código DOT del árbol (Streamlit lo dibuja en el navegador)."""
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
    """El mismo árbol como lista con sangría (para copiar al informe)."""
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
# Paneles
# ---------------------------------------------------------------------------

def barra_lateral(catalogo, nombres, especies, sexos, grupo_de, grupos) -> None:
    with st.sidebar:
        st.header("🐾 Paciente")
        st.selectbox(
            "Caso de demostración", [SIN_CASO, *CASOS_DEMO], key="caso_demo",
            on_change=cargar_caso_demo, args=(grupo_de, grupos),
        )
        st.radio("Especie", list(especies), format_func=especies.get, key="especie",
                 horizontal=True)
        st.number_input("Edad (meses)", min_value=0, max_value=400, step=1, key="edad",
                        help="La base de conocimiento admite de 0 a 300 meses; "
                             "fuera de ese rango Prolog responde «datos no válidos».")
        st.radio("Sexo", list(sexos), format_func=sexos.get, key="sexo", horizontal=True)

        st.header("🩺 Hallazgos observados")
        for grupo, nombre_grupo, opciones in catalogo:
            clave = clave_grupo(grupo)
            n = len(st.session_state.get(clave) or [])
            with st.expander(f"{nombre_grupo} · {n}" if n else nombre_grupo, expanded=n > 0):
                st.pills(nombre_grupo, opciones, selection_mode="multi", key=clave,
                         format_func=lambda h: nombres.get(h, legible(h)),
                         label_visibility="collapsed")
        st.text_input("Otros hallazgos (texto libre)", key="otros",
                      placeholder="p. ej.: estornudos, tos",
                      help="Prolog valida cada término; los que no reconoce se informan "
                           "como ignorados.")

        negados = st.session_state.negados
        if negados:
            st.caption("Respondió que **no** presenta: "
                       + ", ".join(nombres.get(h, legible(h)) for h in negados))
            st.button("Olvidar respuestas negativas", on_click=olvidar_negados)
        st.button("Limpiar caso", on_click=limpiar_caso, args=(grupos,))
        st.button("Recargar base de conocimiento", on_click=recargar_base,
                  help="Vuelve a consultar base_conocimiento.pl (útil si se editó).")


def panel_dictamen(resultado, nombres) -> None:
    if resultado.ignorados:
        st.warning("Prolog no reconoce estos términos y los ignoró: "
                   + ", ".join(f"«{t}»" for t in resultado.ignorados))
    if resultado.alarmas:
        st.error("**Signos de alarma:** "
                 + ", ".join(nombres.get(a, legible(a)) for a in resultado.alarmas))
    if not resultado.diagnosticos:
        st.info("Sin diagnósticos que mostrar.")
    for i, d in enumerate(resultado.diagnosticos, start=1):
        with st.container(border=True):
            titulo, nivel = st.columns([4, 1])
            titulo.markdown(f"#### {i}. {d.nombre}")
            with nivel:
                st.badge(ETIQUETA_NIVEL.get(d.severidad, d.severidad),
                         color=COLOR_NIVEL.get(d.severidad, "gray"))
            st.progress(d.certeza / 100, text=f"Certeza: {d.certeza} %")
            if d.sustento:
                st.markdown("**Hallazgos que la sustentan:** "
                            + " · ".join(nombres.get(h, legible(h)) for h in d.sustento))
            if d.agravantes:
                st.markdown("**Agravantes:** " + ", ".join(legible(a) for a in d.agravantes))
            st.markdown(f"**Qué hacer mientras tanto:** {d.indicacion}")


def panel_por_que(explicaciones: list[Explicacion], descartadas: list[HipotesisDescartada],
                  nombres) -> None:
    if not explicaciones:
        st.info("No hay conclusiones que auditar: revise los datos del paciente.")
        return

    por_id = {e.id: e for e in explicaciones}
    if st.session_state.get("explicacion_elegida") not in por_id:
        st.session_state.explicacion_elegida = explicaciones[0].id
    if len(explicaciones) > 1:
        st.radio("Conclusión a auditar", list(por_id), horizontal=True,
                 format_func=lambda i: por_id[i].nombre, key="explicacion_elegida")
    e = por_id[st.session_state.explicacion_elegida]

    st.subheader(f"Traza de «{e.nombre}»")
    severidad, certeza = st.columns(2)
    with severidad:
        st.markdown("**Cómo se calculó la severidad**")
        st.markdown("\n".join(f"{i}. {paso}" for i, paso in enumerate(e.severidad, start=1)))
    with certeza:
        st.markdown("**Cómo se calculó la certeza**")
        st.markdown(e.certeza)

    st.markdown("#### 🌳 Árbol de inferencia")
    st.caption("Prolog vuelve a demostrar la conclusión con sus propias cláusulas "
               "(metaintérprete con clause/2) y registra cada regla que se disparó y "
               "cada hallazgo que unificó. Azul: reglas · verde: hallazgos · amarillo: "
               "negaciones por fallo (\\+) · violeta: datos del paciente.")
    mostrar = st.toggle("Mostrar hechos de la base y comparaciones", key="mostrar_hechos")
    st.graphviz_chart(arbol_dot(e.arbol, mostrar))
    with st.expander("Traza textual (la misma demostración en forma de lista)"):
        st.code(traza_texto(e.arbol, mostrar), language=None)

    hechos, datos = st.columns([3, 2])
    with hechos:
        st.markdown("#### ✅ Hechos comprobados como verdaderos")
        if e.hechos:
            st.markdown(" ".join(f":green-badge[{nombres.get(h, legible(h))}]" for h in e.hechos))
        else:
            st.caption("Ningún hallazgo intervino en esta conclusión.")
    with datos:
        st.markdown("#### 🐾 Datos del paciente validados")
        st.markdown(" ".join(f":violet-badge[{a.replace('_', ' ')}: {v}]" for a, v in e.datos))

    st.markdown("#### ⚙️ Reglas disparadas")
    if e.reglas:
        st.dataframe(
            [{"Nivel": r.nivel, "Regla": r.etiqueta, "Qué establece": r.descripcion}
             for r in e.reglas],
            hide_index=True,
            column_config={
                "Nivel": st.column_config.NumberColumn(width="small"),
                "Regla": st.column_config.TextColumn(width="medium"),
                "Qué establece": st.column_config.TextColumn(width="large"),
            },
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
            st.markdown("**Comparte con el caso:** "
                        + " ".join(f":gray-badge[{nombres.get(h, legible(h))}]"
                                   for h in d.compartidos))
            if d.arbol:
                st.graphviz_chart(arbol_dot(d.arbol, False))
                st.code(traza_texto(d.arbol, False), language=None)


def botones_respuesta(s: Sugerencia, nombres, grupo_de, clave: str) -> None:
    """Respuestas a una pregunta sugerida; vuelven a consultar a Prolog."""
    si, no = st.columns(2)
    if s.tipo == "hallazgo":
        si.button("✅ Sí, lo presenta", key=f"si_{clave}", width="stretch",
                  on_click=agregar_hallazgos, args=(s.hallazgos, grupo_de))
        no.button("❌ No lo presenta", key=f"no_{clave}", width="stretch",
                  on_click=negar_hallazgos, args=(s.hallazgos,))
        return
    opciones = f"opc_{clave}"
    st.pills("¿Cuál?", s.hallazgos, selection_mode="multi", key=opciones,
             format_func=lambda h: nombres.get(h, legible(h)))
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
              "Ya presenta": ", ".join(nombres.get(h, legible(h)) for h in c.coincidencias),
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
            st.caption("Peso = Σ peso_rol × gravedad × activación / 100 sobre las hipótesis en "
                       "competencia, multiplicado por el factor de desempate (parametro/2) si "
                       "la pregunta favorece a una sola. En un empate solo cuentan las dos "
                       "hipótesis empatadas.")


def panel_consultas(consultas: list[tuple[str, str]]) -> None:
    st.markdown(
        "Python no razona: arma estas consultas con los datos del formulario (cada valor "
        "viaja como átomo entre comillas, así un texto como `Fiebre` no se interpreta como "
        "variable) y muestra lo que Prolog responde. Antes de inferir, Prolog verifica la "
        "entrada con `ground/1` y exige átomos en minúscula (`entrada_segura/4`)."
    )
    for titulo, consulta in consultas:
        st.markdown(f"**{titulo}**")
        st.code(f"?- {consulta}.", language="prolog")


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="TriaVet · Auditoría", page_icon="🐾", layout="wide")
    try:
        motor = obtener_motor()
        catalogo = motor.catalogo()
        nombres = motor.nombres_hallazgos()
        especies, sexos = motor.opciones_paciente()
    except ErrorMotor as exc:
        st.error(f"No se pudo iniciar el motor de inferencia: {exc}")
        st.stop()

    grupos = [g for g, _, _ in catalogo]
    grupo_de = {h: g for g, _, hallazgos in catalogo for h in hallazgos}
    inicializar_estado(grupos)
    pestana_inicial = aplicar_parametros_url(grupo_de, grupos)
    barra_lateral(catalogo, nombres, especies, sexos, grupo_de, grupos)

    especie = st.session_state.especie
    edad = st.session_state.edad
    sexo = st.session_state.sexo
    hallazgos = hallazgos_seleccionados(grupos)
    negados = list(st.session_state.negados)

    try:
        resultado = motor.analizar_caso(especie, edad, sexo, hallazgos)
        explicaciones = motor.explicar(especie, edad, sexo, hallazgos)
        descartadas = motor.descartadas(especie, edad, sexo, hallazgos)
        reco = motor.que_falta(especie, edad, sexo, hallazgos, negados)
        desempate = motor.pregunta_desempate(especie, edad, sexo, hallazgos, negados)
    except ErrorMotor as exc:
        st.error(f"Error al consultar el motor de inferencia: {exc}")
        st.stop()

    st.title("TriaVet")
    st.caption("Sistema experto de triage para urgencias en perros y gatos · "
               "auditoría «caja blanca» con SWI-Prolog y PySwip")

    aviso, icono = AVISO_NIVEL.get(resultado.prioridad, (st.info, "ℹ️"))
    aviso(f"**Prioridad {ETIQUETA_NIVEL.get(resultado.prioridad, resultado.prioridad)}.** "
          f"{resultado.recomendacion}", icon=icono)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Diagnósticos", len([d for d in resultado.ids if d != "sin_diagnostico_concluyente"]))
    m2.metric("Reglas disparadas", sum(len(e.reglas) for e in explicaciones))
    m3.metric("Hipótesis descartadas", len(descartadas))
    m4.metric("Evidencia", "requiere datos" if reco.activo else "suficiente"
              if reco.estado == "definitivo" else "—")

    dictamen, por_que, que_falta, consultas = st.tabs(
        list(PESTANAS.values()), default=pestana_inicial, key="pestana", on_change="rerun",
    )
    with dictamen:
        panel_dictamen(resultado, nombres)
    with por_que:
        panel_por_que(explicaciones, descartadas, nombres)
    with que_falta:
        panel_que_falta(reco, desempate, nombres, grupo_de)
    with consultas:
        panel_consultas([
            ("Dictamen · analizar_caso/10", resultado.consulta),
            ("¿Por qué? · explicar_caso/5",
             motor.consulta_explicacion(especie, edad, sexo, hallazgos)),
            ("¿Por qué? · hipotesis_descartadas/5",
             motor.consulta_descartadas(especie, edad, sexo, hallazgos)),
            ("¿Qué falta? · que_falta/8",
             motor.consulta_que_falta(especie, edad, sexo, hallazgos, negados)),
            ("¿Qué falta? · pregunta_desempate/6",
             motor.consulta_pregunta_desempate(especie, edad, sexo, hallazgos, negados)),
        ])

    st.caption(f"⚠️ {AVISO}")


main()
