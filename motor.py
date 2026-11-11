"""
motor.py - Puente entre Python y la base de conocimiento de TriaVet.

Este módulo carga ``base_conocimiento.pl`` en SWI-Prolog mediante PySwip y
expone funciones que invocan los predicados públicos de Prolog.

Responsabilidad estricta: aquí NO hay lógica de inferencia. Validar los
hallazgos, descartar diagnósticos, calcular la severidad y ordenar los
resultados ocurre en Prolog. Python solo:
  1. convierte los datos de entrada en términos de Prolog,
  2. invoca el predicado,
  3. convierte la respuesta en objetos de Python para mostrarlos.

Predicados de Prolog invocados (ver docs/diccionario_predicados.md):
  analizar_caso/10         -> MotorTriaVet.analizar_caso()
  diagnosticar_todos/5     -> MotorTriaVet.diagnosticar_todos()
  catalogo_hallazgos/2     -> MotorTriaVet.catalogo()
  nombre_grupo/2           -> MotorTriaVet.catalogo()
  nombre_diagnostico/2     -> MotorTriaVet.nombre_diagnostico()
  Entregable 2:
  explicar_caso/5          -> MotorTriaVet.explicar()            "¿Por qué?"
  hipotesis_descartadas/5  -> MotorTriaVet.descartadas()         "¿Por qué?"
  que_falta/8              -> MotorTriaVet.que_falta()           "¿Qué falta?"
  pregunta_desempate/6     -> MotorTriaVet.pregunta_desempate()  "¿Qué falta?"
  nombre_hallazgo/2        -> MotorTriaVet.nombres_hallazgos()
  especie_paciente/2, sexo_paciente/2 -> MotorTriaVet.opciones_paciente()
  Entregable 3:
  interpretar_texto/11     -> MotorTriaVet.interpretar()          lenguaje natural (DCG)
  vista_previa_diagnostico/3 -> MotorTriaVet.vista_previa_diagnostico()  Modo Experto
  aprender_diagnostico/3   -> MotorTriaVet.aprender_diagnostico()  assertz + .pl
  aprender_hallazgo/3      -> MotorTriaVet.aprender_hallazgo()     assertz + .pl
  aprender_expresion/5     -> MotorTriaVet.aprender_expresion()    assertz + .pl
  olvidar/4                -> MotorTriaVet.olvidar()               retract + .pl
  conocimiento_aprendido/3 -> MotorTriaVet.conocimiento_aprendido()
  editar_diagnostico/3     -> MotorTriaVet.editar_diagnostico()    retract + assertz + .pl
  editar_hallazgo/3        -> MotorTriaVet.editar_hallazgo()       retract + assertz + .pl
  catalogo_diagnosticos/1  -> MotorTriaVet.catalogo_diagnosticos() originales y aprendidos
  catalogo_hallazgos_completo/1 -> MotorTriaVet.catalogo_hallazgos()
  texto_aprendido/1        -> MotorTriaVet.texto_aprendido()
  Entregable 4:
  verificar_consistencia/7 -> MotorTriaVet.verificar_consistencia()  contradicciones
"""

from __future__ import annotations

import atexit
import queue
import re
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, TypeVar

from pyswip import Prolog

RUTA_BASE = Path(__file__).resolve().with_name("base_conocimiento.pl")


class ErrorMotor(RuntimeError):
    """Error al cargar la base de conocimiento o al consultar a Prolog."""


T = TypeVar("T")


class _HiloProlog:
    """Hilo único que ejecuta todas las llamadas a SWI-Prolog.

    SWI-Prolog asocia un motor a cada hilo que consulta, y una interfaz como
    Streamlit atiende cada interacción en un hilo nuevo; con un único hilo se
    usa siempre el mismo motor. Es daemon para que siga disponible durante
    atexit y pueda liberar su motor antes de que PySwip cierre Prolog.
    """

    def __init__(self) -> None:
        self._tareas: queue.Queue = queue.Queue()
        threading.Thread(target=self._atender, name="prolog", daemon=True).start()

    def _atender(self) -> None:
        while True:
            funcion, resultado = self._tareas.get()
            try:
                resultado.set_result(funcion())
            except BaseException as exc:
                resultado.set_exception(exc)

    def ejecutar(self, funcion: Callable[[], T]) -> T:
        resultado: Future = Future()
        self._tareas.put((funcion, resultado))
        return resultado.result()


@dataclass
class Diagnostico:
    """Un diagnóstico presuntivo tal como lo devuelve analizar_caso/10."""

    id: str
    nombre: str
    severidad: str
    certeza: int
    indicacion: str
    sustento: list[str] = field(default_factory=list)
    agravantes: list[str] = field(default_factory=list)


@dataclass
class ResultadoCaso:
    """Respuesta completa de analizar_caso/10."""

    consulta: str
    validos: list[str]
    ignorados: list[str]
    alarmas: list[str]
    diagnosticos: list[Diagnostico]
    prioridad: str
    recomendacion: str

    @property
    def ids(self) -> list[str]:
        """Identificadores de los diagnósticos en el orden entregado por Prolog."""
        return [d.id for d in self.diagnosticos]


# -- Entregable 2: módulos de explicabilidad y de recomendación -------------

@dataclass
class NodoTraza:
    """Nodo del árbol de inferencia: [Tipo, Nivel, Etiqueta, Descripcion, Hijos].

    Tipos de la demostración ("¿Por qué?"): regla, verificacion, hallazgo,
    negacion, dato, hecho, condicion. Tipos de la refutación ("¿por qué
    no?"): no_regla, alternativa, falta, falta_uno, apoyo_insuficiente,
    excluyente, dato_incompatible, no_hecho, condicion_falsa.
    """

    tipo: str
    nivel: int
    etiqueta: str
    descripcion: str
    hijos: list["NodoTraza"] = field(default_factory=list)


@dataclass
class ReglaDisparada:
    nivel: int
    etiqueta: str
    descripcion: str


@dataclass
class Explicacion:
    """Respuesta de explicar_caso/5 para un diagnóstico."""

    id: str
    nombre: str
    arbol: list[NodoTraza]
    reglas: list[ReglaDisparada]
    hechos: list[str]
    datos: list[tuple[str, str]]
    severidad: list[str]
    certeza: str


@dataclass
class HipotesisDescartada:
    """Respuesta de hipotesis_descartadas/5.

    tipo: exclusion | condicion_excluyente | dato_paciente |
          evidencia_insuficiente | regla
    """

    id: str
    nombre: str
    tipo: str
    resumen: str
    compartidos: list[str]
    arbol: list[NodoTraza]


@dataclass
class Competidora:
    """Hipótesis en competencia (que_falta/8)."""

    id: str
    nombre: str
    estado: str          # confirmada | parcial | refutada_usuario
    activacion: int      # % del perfil cubierto
    gravedad: str        # severidad base
    coincidencias: list[str]
    falta: list[str]
    excluiria: list[str]


@dataclass
class Sugerencia:
    """Pregunta sugerida por el módulo "¿Qué falta?"."""

    tipo: str            # hallazgo | grupo (basta uno de los hallazgos)
    categoria: str       # sintoma | prueba | antecedente
    hallazgos: list[str]
    pregunta: str
    peso: float
    desempata: bool
    motivos: list[str]
    efecto: str
    verificar: str


@dataclass
class Recomendacion:
    """Respuesta completa de que_falta/8."""

    estado: str          # sin_hallazgos | insuficiente | empate | certeza_baja |
                         # definitivo | datos_invalidos
    activo: bool         # Prolog decidió activar el módulo de recomendación
    mensaje: str
    competidoras: list[Competidora]
    sugerencias: list[Sugerencia]


# -- Entregable 3: lenguaje natural y Modo Experto --------------------------

@dataclass
class Fragmento:
    """Trozo de la oración reconocido por la DCG.

    tipo: hallazgo | negado | paciente | sexo | edad | medicion | vacia | desconocida
    """

    tipo: str
    valor: object
    texto: str


@dataclass
class Interpretacion:
    """Respuesta de interpretar_texto/11 (gramática DCG de la Sección 11)."""

    consulta: str
    especie: str | None
    edad: int | None
    sexo: str | None
    hallazgos: list[str]
    negados: list[str]
    mediciones: list[tuple[str, float]]
    desconocidas: list[str]
    fragmentos: list[Fragmento]
    resumen: str
    # Entregable 4: contradicciones encontradas en el propio texto
    contradicciones: list[Contradiccion] = field(default_factory=list)


@dataclass
class Contradiccion:
    """Hechos incompatibles detectados por la Sección 14 del .pl (Entregable 4).

    tipo: hallazgos_incompatibles | dato_paciente | afirmado_y_negado |
          medicion_repetida | medicion_imposible
    """

    tipo: str
    elementos: list[str]
    motivo: str


@dataclass
class Consistencia:
    """Respuesta de verificar_consistencia/7."""

    consulta: str
    contradicciones: list[Contradiccion]
    recomendacion: str

    @property
    def ok(self) -> bool:
        return not self.contradicciones


@dataclass
class DiagnosticoAprendido:
    id: str
    nombre: str
    autor: str
    fecha: str
    requisitos: list[str]
    apoyo: list[str]
    minimo: int
    severidad: str
    especies: list[str]


@dataclass
class DiagnosticoCatalogo:
    """Un diagnóstico de la base (original o aprendido) para el Modo Experto."""

    id: str
    nombre: str
    origen: str          # original | aprendido
    severidad: str
    curso: str
    requisitos: list[str]
    apoyo: list[str]
    minimo: int
    especies: list[str]
    autor: str
    fecha: str

    @property
    def aprendido(self) -> bool:
        return self.origen == "aprendido"


@dataclass
class HallazgoCatalogo:
    """Un hallazgo de la base (original o aprendido) para el Modo Experto."""

    id: str
    nombre: str
    grupo: str
    origen: str          # original | aprendido
    autor: str
    fecha: str
    usado_por: list[str]
    expresiones: int

    @property
    def aprendido(self) -> bool:
        return self.origen == "aprendido"


@dataclass
class ResultadoAprendizaje:
    """Respuesta de los predicados del Modo Experto: ok | error y mensajes."""

    consulta: str
    ok: bool
    mensajes: list[str]


# ---------------------------------------------------------------------------
# Conversión de valores de Python a términos de Prolog
# ---------------------------------------------------------------------------

def _normalizar(valor: object) -> str:
    """Formato de texto: minúsculas, '_' entre palabras y solo caracteres de palabra.

    Es solo formato (como pasar a minúsculas): decidir si el hallazgo existe
    le corresponde a Prolog (particionar/3).
    """
    texto = "_".join(str(valor).strip().lower().split())
    return re.sub(r"[^\w]", "", texto)


def termino_atomo(valor: object) -> str:
    """Convierte un valor en un átomo de Prolog entre comillas simples.

    Las comillas evitan que un texto de usuario se interprete como variable
    (p. ej. 'Fiebre') o como código Prolog.
    """
    return f"'{_normalizar(valor)}'"


def termino_edad(valor: object) -> str:
    """La edad viaja como entero si lo es; si no, como átomo.

    Python no decide si la edad es válida: si llega un átomo, Prolog la
    rechaza en datos_paciente_validos/1 y responde con datos_invalidos.
    """
    texto = str(valor).strip()
    return texto if texto.isdigit() else termino_atomo(texto)


def termino_lista(valores: Iterable[object]) -> str:
    """Convierte una secuencia de Python en una lista de átomos de Prolog."""
    return "[" + ", ".join(termino_atomo(v) for v in valores) + "]"


def termino_texto(valor: object, maximo: int = 1500) -> str:
    """Texto libre (oración, nombre, indicación) como átomo entre comillas.

    A diferencia de termino_atomo/1 conserva tildes, espacios y signos: solo
    escapa la barra y la comilla simple, une las líneas y limita el largo.
    Interpretar el texto le corresponde a Prolog.
    """
    texto = " ".join(str(valor).split())[:maximo]
    texto = texto.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{texto}'"


def termino_lista_textos(valores: Iterable[object]) -> str:
    return "[" + ", ".join(termino_texto(v, 200) for v in valores) + "]"


def termino_entero(valor: object) -> str:
    """Entero como texto; cualquier otra cosa viaja como átomo y Prolog la rechaza."""
    texto = str(valor).strip()
    return texto if re.fullmatch(r"-?\d+", texto) else termino_atomo(texto)


# ---------------------------------------------------------------------------
# Conversión de valores de Prolog a Python
# ---------------------------------------------------------------------------

def _texto(valor: object) -> str:
    if isinstance(valor, bytes):
        return valor.decode("utf-8")
    return str(valor)


def _lista_textos(valor: object) -> list[str]:
    return [_texto(v) for v in valor] if isinstance(valor, list) else []


def _a_contradicciones(filas: object) -> list[Contradiccion]:
    """Filas de Prolog: [[Tipo, Elementos, Motivo], ...]."""
    if not isinstance(filas, list):
        return []
    return [Contradiccion(_texto(t), [_texto(e) for e in (es if isinstance(es, list) else [es])],
                          _texto(m))
            for t, es, m in filas]


def _a_diagnostico(fila: list) -> Diagnostico:
    """Fila de Prolog: [Id, Nombre, Severidad, Certeza, Indicacion, Sustento, Agravantes]."""
    id_, nombre, severidad, certeza, indicacion, sustento, agravantes = fila
    return Diagnostico(
        id=_texto(id_),
        nombre=_texto(nombre),
        severidad=_texto(severidad),
        certeza=int(certeza),
        indicacion=_texto(indicacion),
        sustento=_lista_textos(sustento),
        agravantes=_lista_textos(agravantes),
    )


def _a_nodo(fila: list) -> NodoTraza:
    """[Tipo, Nivel, Etiqueta, Descripcion, Hijos] -> NodoTraza (recursivo)."""
    tipo, nivel, etiqueta, descripcion, hijos = fila
    return NodoTraza(
        tipo=_texto(tipo),
        nivel=int(nivel),
        etiqueta=_texto(etiqueta),
        descripcion=_texto(descripcion),
        hijos=[_a_nodo(h) for h in hijos],
    )


def _a_explicacion(fila: list) -> Explicacion:
    """[Id, Nombre, Arbol, Reglas, Hechos, Datos, Severidad, Certeza]."""
    id_, nombre, arbol, reglas, hechos, datos, severidad, certeza = fila
    return Explicacion(
        id=_texto(id_),
        nombre=_texto(nombre),
        arbol=[_a_nodo(n) for n in arbol],
        reglas=[ReglaDisparada(int(n), _texto(e), _texto(d)) for n, e, d in reglas],
        hechos=_lista_textos(hechos),
        datos=[(_texto(a), _texto(v)) for a, v in datos],
        severidad=_lista_textos(severidad),
        certeza=_texto(certeza),
    )


def _a_descartada(fila: list) -> HipotesisDescartada:
    """[Id, Nombre, Tipo, Resumen, Compartidos, Arbol]."""
    id_, nombre, tipo, resumen, compartidos, arbol = fila
    return HipotesisDescartada(
        id=_texto(id_),
        nombre=_texto(nombre),
        tipo=_texto(tipo),
        resumen=_texto(resumen),
        compartidos=_lista_textos(compartidos),
        arbol=[_a_nodo(n) for n in arbol],
    )


def _a_competidora(fila: list) -> Competidora:
    """[Id, Nombre, Estado, Activacion, Gravedad, Coincidencias, Falta, Excluiria]."""
    id_, nombre, estado, activacion, gravedad, coincidencias, falta, excluiria = fila
    return Competidora(
        id=_texto(id_),
        nombre=_texto(nombre),
        estado=_texto(estado),
        activacion=int(activacion),
        gravedad=_texto(gravedad),
        coincidencias=_lista_textos(coincidencias),
        falta=_lista_textos(falta),
        excluiria=_lista_textos(excluiria),
    )


def _a_sugerencia(fila: list) -> Sugerencia:
    """[Tipo, Categoria, Hallazgos, Pregunta, Peso, Desempata, Motivos, Efecto, Verificar]."""
    tipo, categoria, hallazgos, pregunta, peso, desempata, motivos, efecto, verificar = fila
    return Sugerencia(
        tipo=_texto(tipo),
        categoria=_texto(categoria),
        hallazgos=_lista_textos(hallazgos),
        pregunta=_texto(pregunta),
        peso=float(peso),
        desempata=_texto(desempata) == "si",
        motivos=_lista_textos(motivos),
        efecto=_texto(efecto),
        verificar=_texto(verificar),
    )


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------

class MotorTriaVet:
    """Fachada de Python sobre la base de conocimiento de Prolog."""

    def __init__(self, ruta_base: Path | str = RUTA_BASE) -> None:
        ruta = Path(ruta_base).resolve()
        if not ruta.exists():
            raise ErrorMotor(f"No se encontró la base de conocimiento: {ruta}")
        self._hilo = _HiloProlog()
        self._prolog = Prolog()
        self.ruta_base = ruta
        self.recargar()
        atexit.register(self.cerrar)

    def recargar(self) -> None:
        """(Re)carga base_conocimiento.pl; consult/1 reemplaza las cláusulas."""
        try:
            # as_posix(): Prolog interpreta '\' como escape dentro de un átomo.
            self._hilo.ejecutar(lambda: self._prolog.consult(self.ruta_base.as_posix()))
        except Exception as exc:  # PrologError u otros errores de carga
            raise ErrorMotor(f"No se pudo cargar {self.ruta_base.name}: {exc}") from exc

    def cerrar(self) -> None:
        """Libera el motor de Prolog del hilo de consultas antes de salir.

        Sin esto, SWI-Prolog avisa al terminar que no pudo detener sus hilos.
        PySwip no publica PL_thread_destroy_engine, así que se toma de la
        biblioteca ya cargada; si no estuviera disponible, solo queda el aviso.
        """
        try:
            from pyswip.core import _lib
            self._hilo.ejecutar(_lib.PL_thread_destroy_engine)
        except Exception:
            pass

    # -- consultas genéricas -------------------------------------------------

    def consultar(self, consulta: str, max_resultados: int = -1) -> list[dict]:
        """Ejecuta una consulta y devuelve todas sus soluciones como diccionarios."""
        try:
            return self._hilo.ejecutar(
                lambda: list(self._prolog.query(consulta, maxresult=max_resultados))
            )
        except Exception as exc:
            raise ErrorMotor(f"Error al consultar «{consulta}»: {exc}") from exc

    # -- construcción de consultas (también las usa pruebas.py) --------------

    @staticmethod
    def consulta_analisis(especie, edad, sexo, hallazgos) -> str:
        return (
            f"analizar_caso({termino_atomo(especie)}, {termino_edad(edad)}, "
            f"{termino_atomo(sexo)}, {termino_lista(hallazgos)}, "
            "Validos, Ignorados, Alarmas, Diagnosticos, Prioridad, Recomendacion)"
        )

    @staticmethod
    def consulta_diagnosticar_todos(especie, edad, sexo, hallazgos) -> str:
        return (
            f"diagnosticar_todos({termino_atomo(especie)}, {termino_edad(edad)}, "
            f"{termino_atomo(sexo)}, {termino_lista(hallazgos)}, Diagnosticos)"
        )

    @staticmethod
    def _argumentos_caso(especie, edad, sexo, hallazgos) -> str:
        return (
            f"{termino_atomo(especie)}, {termino_edad(edad)}, "
            f"{termino_atomo(sexo)}, {termino_lista(hallazgos)}"
        )

    @classmethod
    def consulta_explicacion(cls, especie, edad, sexo, hallazgos) -> str:
        return f"explicar_caso({cls._argumentos_caso(especie, edad, sexo, hallazgos)}, Explicaciones)"

    @classmethod
    def consulta_descartadas(cls, especie, edad, sexo, hallazgos) -> str:
        return f"hipotesis_descartadas({cls._argumentos_caso(especie, edad, sexo, hallazgos)}, Descartadas)"

    @classmethod
    def consulta_que_falta(cls, especie, edad, sexo, hallazgos, negados) -> str:
        return (
            f"que_falta({cls._argumentos_caso(especie, edad, sexo, hallazgos)}, "
            f"{termino_lista(negados)}, Estado, Competidoras, Sugerencias)"
        )

    @classmethod
    def consulta_pregunta_desempate(cls, especie, edad, sexo, hallazgos, negados) -> str:
        return (
            f"pregunta_desempate({cls._argumentos_caso(especie, edad, sexo, hallazgos)}, "
            f"{termino_lista(negados)}, Pregunta)"
        )

    # -- API pública ---------------------------------------------------------

    def analizar_caso(self, especie, edad, sexo, hallazgos: Iterable[object]) -> ResultadoCaso:
        """Invoca analizar_caso/10 y devuelve la respuesta completa."""
        consulta = self.consulta_analisis(especie, edad, sexo, list(hallazgos))
        soluciones = self.consultar(consulta, max_resultados=1)
        if not soluciones:
            # analizar_caso/10 tiene una cláusula por defecto, así que esto
            # solo ocurriría si la base de conocimiento estuviera incompleta.
            raise ErrorMotor("Prolog no devolvió respuesta para el caso.")
        s = soluciones[0]
        return ResultadoCaso(
            consulta=consulta,
            validos=_lista_textos(s["Validos"]),
            ignorados=_lista_textos(s["Ignorados"]),
            alarmas=_lista_textos(s["Alarmas"]),
            diagnosticos=[_a_diagnostico(f) for f in s["Diagnosticos"]],
            prioridad=_texto(s["Prioridad"]),
            recomendacion=_texto(s["Recomendacion"]),
        )

    def diagnosticar_todos(self, especie, edad, sexo, hallazgos: Iterable[object]) -> list[str]:
        """Invoca diagnosticar_todos/5: lista única, ordenada y sin duplicados."""
        consulta = self.consulta_diagnosticar_todos(especie, edad, sexo, list(hallazgos))
        soluciones = self.consultar(consulta, max_resultados=1)
        return _lista_textos(soluciones[0]["Diagnosticos"]) if soluciones else []

    def catalogo(self) -> list[tuple[str, str, list[str]]]:
        """Grupos de hallazgos válidos: [(grupo, nombre_legible, [hallazgos...])]."""
        soluciones = self.consultar(
            "nombre_grupo(Grupo, Nombre), catalogo_hallazgos(Grupo, Hallazgos)"
        )
        return [
            (_texto(s["Grupo"]), _texto(s["Nombre"]), _lista_textos(s["Hallazgos"]))
            for s in soluciones
        ]

    def nombre_diagnostico(self, id_diagnostico: str) -> str:
        """Nombre legible de un diagnóstico (nombre_diagnostico/2)."""
        soluciones = self.consultar(
            f"nombre_diagnostico({termino_atomo(id_diagnostico)}, Nombre)", max_resultados=1
        )
        return _texto(soluciones[0]["Nombre"]) if soluciones else id_diagnostico

    # -- API del Entregable 2 ------------------------------------------------

    def explicar(self, especie, edad, sexo, hallazgos: Iterable[object]) -> list[Explicacion]:
        """Módulo "¿Por qué?": traza de cada conclusión (explicar_caso/5)."""
        consulta = self.consulta_explicacion(especie, edad, sexo, list(hallazgos))
        soluciones = self.consultar(consulta, max_resultados=1)
        return [_a_explicacion(f) for f in soluciones[0]["Explicaciones"]] if soluciones else []

    def descartadas(self, especie, edad, sexo, hallazgos: Iterable[object]) -> list[HipotesisDescartada]:
        """Hipótesis alternativas descartadas y su motivo (hipotesis_descartadas/5)."""
        consulta = self.consulta_descartadas(especie, edad, sexo, list(hallazgos))
        soluciones = self.consultar(consulta, max_resultados=1)
        return [_a_descartada(f) for f in soluciones[0]["Descartadas"]] if soluciones else []

    def que_falta(self, especie, edad, sexo, hallazgos: Iterable[object],
                  negados: Iterable[object] = ()) -> Recomendacion:
        """Módulo "¿Qué falta?" (que_falta/8).

        negados: hallazgos que el usuario respondió que NO presenta; Prolog
        los descarta como preguntas y refuta las hipótesis que los exigen.
        """
        consulta = self.consulta_que_falta(especie, edad, sexo, list(hallazgos), list(negados))
        soluciones = self.consultar(consulta, max_resultados=1)
        if not soluciones:
            raise ErrorMotor("Prolog no devolvió respuesta para que_falta/8.")
        s = soluciones[0]
        tipo, activo, mensaje = s["Estado"]
        return Recomendacion(
            estado=_texto(tipo),
            activo=_texto(activo) == "si",
            mensaje=_texto(mensaje),
            competidoras=[_a_competidora(f) for f in s["Competidoras"]],
            sugerencias=[_a_sugerencia(f) for f in s["Sugerencias"]],
        )

    def pregunta_desempate(self, especie, edad, sexo, hallazgos: Iterable[object],
                           negados: Iterable[object] = ()) -> Sugerencia | None:
        """Consulta de desempate: la pregunta de mayor peso (pregunta_desempate/6)."""
        consulta = self.consulta_pregunta_desempate(
            especie, edad, sexo, list(hallazgos), list(negados)
        )
        soluciones = self.consultar(consulta, max_resultados=1)
        return _a_sugerencia(soluciones[0]["Pregunta"]) if soluciones else None

    def nombres_hallazgos(self) -> dict[str, str]:
        """Nombre legible de cada hallazgo (nombre_hallazgo/2)."""
        return {
            _texto(s["H"]): _texto(s["N"])
            for s in self.consultar("nombre_hallazgo(H, N)")
        }

    def opciones_paciente(self) -> tuple[dict[str, str], dict[str, str]]:
        """Especies y sexos admitidos (especie_paciente/2 y sexo_paciente/2)."""
        especies = {_texto(s["E"]): _texto(s["N"]) for s in self.consultar("especie_paciente(E, N)")}
        sexos = {_texto(s["S"]): _texto(s["N"]) for s in self.consultar("sexo_paciente(S, N)")}
        return especies, sexos

    def nombres_diagnosticos(self) -> dict[str, str]:
        """Diagnósticos del catálogo, incluidos los aprendidos (para el Modo Experto)."""
        return {
            _texto(s["D"]): _texto(s["N"])
            for s in self.consultar("diagnostico_del_catalogo(D), nombre_diagnostico(D, N)")
        }

    # -- API del Entregable 3: lenguaje natural (DCG) ------------------------

    @staticmethod
    def consulta_interpretar(texto: str) -> str:
        return (
            f"interpretar_texto({termino_texto(texto)}, Especie, Edad, Sexo, Hallazgos, "
            "Negados, Mediciones, Desconocidas, Fragmentos, Resumen, Contradicciones)"
        )

    def interpretar(self, texto: str) -> Interpretacion:
        """Analiza una oración en lenguaje natural con la DCG (interpretar_texto/10).

        Python solo limpia el formato: une las líneas y escribe con punto los
        decimales ("40,2" -> "40.2") para que la coma siga separando frases.
        """
        limpio = re.sub(r"(\d),(\d)", r"\1.\2", texto)
        consulta = self.consulta_interpretar(limpio)
        soluciones = self.consultar(consulta, max_resultados=1)
        if not soluciones:
            raise ErrorMotor("Prolog no devolvió respuesta para interpretar_texto/11.")
        s = soluciones[0]

        def opcional(valor):
            v = _texto(valor)
            return None if v == "no_indicado" else v

        edad = s["Edad"]
        return Interpretacion(
            consulta=consulta,
            especie=opcional(s["Especie"]),
            edad=int(edad) if isinstance(edad, (int, float)) else None,
            sexo=opcional(s["Sexo"]),
            hallazgos=_lista_textos(s["Hallazgos"]),
            negados=_lista_textos(s["Negados"]),
            mediciones=[(_texto(v), float(x)) for v, x in s["Mediciones"]],
            desconocidas=_lista_textos(s["Desconocidas"]),
            fragmentos=[
                Fragmento(_texto(t), v if isinstance(v, (int, float, list)) else _texto(v), _texto(x))
                for t, v, x in s["Fragmentos"]
            ],
            resumen=_texto(s["Resumen"]),
            contradicciones=_a_contradicciones(s["Contradicciones"]),
        )

    # -- API del Entregable 4: manejo de contradicciones ---------------------

    def recomendacion(self, prioridad: str) -> str:
        """Texto de recomendacion/2 para una prioridad."""
        s = self.consultar(f"recomendacion({termino_atomo(prioridad)}, T)", max_resultados=1)
        return _texto(s[0]["T"]) if s else ""

    @classmethod
    def consulta_consistencia(cls, especie, edad, sexo, hallazgos, negados) -> str:
        return (
            f"verificar_consistencia({cls._argumentos_caso(especie, edad, sexo, hallazgos)}, "
            f"{termino_lista(negados)}, Contradicciones, Recomendacion)"
        )

    def verificar_consistencia(self, especie, edad, sexo, hallazgos: Iterable[object],
                               negados: Iterable[object] = ()) -> Consistencia:
        """Contradicciones del caso (verificar_consistencia/7). Prolog decide qué choca."""
        consulta = self.consulta_consistencia(especie, edad, sexo, list(hallazgos), list(negados))
        s = self.consultar(consulta, max_resultados=1)
        if not s:
            return Consistencia(consulta, [], "")
        return Consistencia(consulta, _a_contradicciones(s[0]["Contradicciones"]),
                            _texto(s[0]["Recomendacion"]))

    # -- API del Entregable 3: Modo Experto ----------------------------------

    @staticmethod
    def termino_diagnostico(d: dict) -> str:
        """diagnostico(Id, Nombre, Especies, Curso, Requisitos, Apoyo, Minimo,
        Severidad, CertezaPct, Indicacion, Excluye, ExcluidoPor, Autor)"""
        return (
            f"diagnostico({termino_atomo(d['id'])}, {termino_texto(d['nombre'], 120)}, "
            f"{termino_lista(d['especies'])}, {termino_atomo(d['curso'])}, "
            f"{termino_lista(d['requisitos'])}, {termino_lista(d['apoyo'])}, "
            f"{termino_entero(d['minimo'])}, {termino_atomo(d['severidad'])}, "
            f"{termino_entero(d['certeza'])}, {termino_texto(d['indicacion'], 400)}, "
            f"{termino_lista(d['excluye'])}, {termino_lista(d['excluido_por'])}, "
            f"{termino_texto(d['autor'], 80)})"
        )

    def _aprendizaje(self, consulta: str) -> ResultadoAprendizaje:
        soluciones = self.consultar(consulta, max_resultados=1)
        if not soluciones:
            raise ErrorMotor(f"Prolog no respondió a «{consulta}».")
        s = soluciones[0]
        return ResultadoAprendizaje(consulta, _texto(s["Estado"]) == "ok", _lista_textos(s["Mensajes"]))

    def vista_previa_diagnostico(self, datos: dict) -> tuple[list[str], str]:
        """Errores de validación y cláusulas que se escribirían (sin aprender)."""
        consulta = f"vista_previa_diagnostico({self.termino_diagnostico(datos)}, Errores, Texto)"
        s = self.consultar(consulta, max_resultados=1)[0]
        return _lista_textos(s["Errores"]), _texto(s["Texto"])

    def aprender_diagnostico(self, datos: dict) -> ResultadoAprendizaje:
        """Valida, inyecta con assertz/1 y escribe en el .pl un diagnóstico nuevo."""
        return self._aprendizaje(
            f"aprender_diagnostico({self.termino_diagnostico(datos)}, Estado, Mensajes)"
        )

    def aprender_hallazgo(self, id_, nombre, grupo, pregunta, expresiones, autor) -> ResultadoAprendizaje:
        """Agrega un signo o antecedente nuevo y las expresiones que lo reconocen."""
        termino = (
            f"hallazgo({termino_atomo(id_)}, {termino_texto(nombre, 120)}, {termino_atomo(grupo)}, "
            f"{termino_texto(pregunta, 300)}, {termino_lista_textos(expresiones)}, "
            f"{termino_texto(autor, 80)})"
        )
        return self._aprendizaje(f"aprender_hallazgo({termino}, Estado, Mensajes)")

    def aprender_expresion(self, texto, hallazgo, autor) -> ResultadoAprendizaje:
        """Enseña a la DCG una forma nueva de decir un hallazgo existente."""
        return self._aprendizaje(
            f"aprender_expresion({termino_texto(texto, 200)}, {termino_atomo(hallazgo)}, "
            f"{termino_texto(autor, 80)}, Estado, Mensajes)"
        )

    def olvidar(self, tipo: str, id_: str) -> ResultadoAprendizaje:
        """Retira de la memoria y del .pl algo aprendido (tipo: diagnostico | hallazgo | expresion)."""
        clave = termino_texto(id_, 200) if tipo == "expresion" else termino_atomo(id_)
        return self._aprendizaje(f"olvidar({termino_atomo(tipo)}, {clave}, Estado, Mensajes)")

    def vista_previa_edicion(self, datos: dict) -> tuple[list[str], str]:
        """Como vista_previa_diagnostico(), pero valida en modo edición."""
        consulta = f"vista_previa_edicion({self.termino_diagnostico(datos)}, Errores, Texto)"
        s = self.consultar(consulta, max_resultados=1)[0]
        return _lista_textos(s["Errores"]), _texto(s["Texto"])

    def editar_diagnostico(self, datos: dict) -> ResultadoAprendizaje:
        """Reemplaza (retract + assertz + .pl) un diagnóstico aprendido."""
        return self._aprendizaje(
            f"editar_diagnostico({self.termino_diagnostico(datos)}, Estado, Mensajes)"
        )

    def editar_hallazgo(self, id_, nombre, grupo, pregunta, expresiones, autor) -> ResultadoAprendizaje:
        """Reemplaza nombre, grupo, pregunta y expresiones de un hallazgo aprendido."""
        termino = (
            f"hallazgo({termino_atomo(id_)}, {termino_texto(nombre, 120)}, {termino_atomo(grupo)}, "
            f"{termino_texto(pregunta, 300)}, {termino_lista_textos(expresiones)}, "
            f"{termino_texto(autor, 80)})"
        )
        return self._aprendizaje(f"editar_hallazgo({termino}, Estado, Mensajes)")

    def datos_diagnostico(self, id_: str) -> dict | None:
        """Valores actuales de un diagnóstico aprendido (para el formulario de edición)."""
        s = self.consultar(f"datos_diagnostico_aprendido({termino_atomo(id_)}, D)", max_resultados=1)
        if not s:
            return None
        (nombre, especies, curso, requisitos, apoyo, minimo, certeza, severidad,
         indicacion, excluye, excluido_por) = s[0]["D"]
        return {
            "id": id_, "nombre": _texto(nombre), "especies": _lista_textos(especies),
            "curso": _texto(curso), "requisitos": _lista_textos(requisitos),
            "apoyo": _lista_textos(apoyo), "minimo": int(minimo), "certeza": int(certeza),
            "severidad": _texto(severidad), "indicacion": _texto(indicacion),
            "excluye": _lista_textos(excluye), "excluido_por": _lista_textos(excluido_por),
        }

    def datos_hallazgo(self, id_: str) -> dict | None:
        """Valores actuales de un hallazgo aprendido (para el formulario de edición)."""
        s = self.consultar(f"datos_hallazgo_aprendido({termino_atomo(id_)}, D)", max_resultados=1)
        if not s:
            return None
        nombre, grupo, pregunta, expresiones = s[0]["D"]
        return {"id": id_, "nombre": _texto(nombre), "grupo": _texto(grupo),
                "pregunta": _texto(pregunta), "expresiones": _lista_textos(expresiones)}

    def catalogo_diagnosticos(self) -> list[DiagnosticoCatalogo]:
        """Todos los diagnósticos, originales y aprendidos (catalogo_diagnosticos/1)."""
        s = self.consultar("catalogo_diagnosticos(F)", max_resultados=1)[0]
        return [
            DiagnosticoCatalogo(_texto(i), _texto(n), _texto(o), _texto(sev), _texto(c),
                                _lista_textos(r), _lista_textos(a), int(m), _lista_textos(es),
                                _texto(au), _texto(fe))
            for i, n, o, sev, c, r, a, m, es, au, fe in s["F"]
        ]

    def catalogo_hallazgos(self) -> list[HallazgoCatalogo]:
        """Todos los hallazgos, originales y aprendidos (catalogo_hallazgos_completo/1)."""
        s = self.consultar("catalogo_hallazgos_completo(F)", max_resultados=1)[0]
        return [
            HallazgoCatalogo(_texto(i), _texto(n), _texto(g), _texto(o), _texto(au), _texto(fe),
                             _lista_textos(u), int(k))
            for i, n, g, o, au, fe, u, k in s["F"]
        ]

    def conocimiento_aprendido(self):
        """(diagnosticos, hallazgos, expresiones) aprendidos en Modo Experto."""
        s = self.consultar("conocimiento_aprendido(D, H, E)", max_resultados=1)[0]
        diagnosticos = [
            DiagnosticoAprendido(_texto(i), _texto(n), _texto(a), _texto(f), _lista_textos(r),
                                 _lista_textos(ap), int(m), _texto(sev), _lista_textos(es))
            for i, n, a, f, r, ap, m, sev, es in s["D"]
        ]
        hallazgos = [tuple(_texto(x) for x in fila) for fila in s["H"]]
        expresiones = [tuple(_texto(x) for x in fila) for fila in s["E"]]
        return diagnosticos, hallazgos, expresiones

    def texto_aprendido(self) -> str:
        """Lo aprendido en memoria, en sintaxis Prolog (texto_aprendido/1)."""
        s = self.consultar("texto_aprendido(T)", max_resultados=1)
        return _texto(s[0]["T"]) if s else ""

    def seccion_aprendida_en_archivo(self) -> str:
        """Lo que hay HOY en la Sección 13 del archivo .pl (para comprobar la persistencia)."""
        contenido = self.ruta_base.read_text(encoding="utf-8")
        marca = "%% >>> CONOCIMIENTO APRENDIDO EN CALIENTE >>>"
        return contenido.split(marca, 1)[1].strip() if marca in contenido else ""


# ---------------------------------------------------------------------------
# Presentación en consola (compartida por main.py y pruebas.py)
# ---------------------------------------------------------------------------

ETIQUETA_NIVEL = {
    "critico": "CRÍTICO",
    "alto": "ALTO",
    "medio": "MEDIO",
    "bajo": "BAJO",
    "indeterminado": "INDETERMINADO",
    "datos_invalidos": "DATOS NO VÁLIDOS",
    "inconsistente": "DATOS CONTRADICTORIOS",
}


def legible(atomo: str) -> str:
    """'vomito_persistente' -> 'vomito persistente' (solo para mostrar)."""
    return atomo.replace("_", " ")


def formatear_resultado(resultado: ResultadoCaso, sangria: str = "") -> str:
    """Texto listo para imprimir con la respuesta de Prolog."""
    s = sangria
    lineas = [
        f"{s}Prioridad del caso : {ETIQUETA_NIVEL.get(resultado.prioridad, resultado.prioridad)}",
        f"{s}Recomendación      : {resultado.recomendacion}",
        f"{s}Hallazgos válidos  : {', '.join(map(legible, resultado.validos)) or '(ninguno)'}",
    ]
    if resultado.ignorados:
        lineas.append(f"{s}Hallazgos ignorados: {', '.join(resultado.ignorados)}")
    if resultado.alarmas:
        lineas.append(f"{s}Signos de alarma   : {', '.join(map(legible, resultado.alarmas))}")
    if not resultado.diagnosticos:
        lineas.append(f"{s}Diagnósticos       : (ninguno)")
    for i, d in enumerate(resultado.diagnosticos, start=1):
        lineas.append(
            f"{s}  {i}. {d.nombre}  [{ETIQUETA_NIVEL.get(d.severidad, d.severidad)}]"
            f"  certeza {d.certeza} %"
        )
        if d.sustento:
            lineas.append(f"{s}     Sustento   : {', '.join(map(legible, d.sustento))}")
        if d.agravantes:
            lineas.append(f"{s}     Agravantes : {', '.join(map(legible, d.agravantes))}")
        lineas.append(f"{s}     Indicación : {d.indicacion}")
    return "\n".join(lineas)
