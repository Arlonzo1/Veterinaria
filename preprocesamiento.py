"""
preprocesamiento.py - Preprocesamiento numérico híbrido (Entregable 3, opcional).

Las reglas de Prolog razonan con hechos discretos ("fiebre", "llenado
capilar lento"), pero en el mundo real el tutor o el auxiliar miden valores
continuos: 40.3 °C, 3 segundos, 5 vómitos. Este módulo convierte esas
mediciones en hechos discretos ANTES de enviarlos al motor de inferencia.

Clasificador ligero: para cada variable se entrena un árbol de decisión de
scikit-learn (DecisionTreeClassifier) con una tabla de valores de referencia
etiquetados por especie. El árbol aprende los puntos de corte; el resultado
es una categoría (p. ej. "fiebre") que se traduce en un hallazgo de la base
de conocimiento. Si scikit-learn no está instalado, se usan directamente los
umbrales de referencia (mismo resultado, sin aprendizaje).

Valores de referencia (perro y gato adultos en reposo):
  temperatura rectal        normal 38.0-39.2 °C; < 37.5 hipotermia; > 39.2 fiebre
  tiempo de llenado capilar normal < 2 s; >= 2.5 s lento
  vómitos en 24 h           1-2 vómito; >= 3 vómito persistente
  días sin defecar          >= 2 sin defecar
  pérdida de peso           >= 5 % del peso habitual
Estos umbrales coinciden con las preguntas de la Sección 9 del .pl.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from sklearn.tree import DecisionTreeClassifier
except ImportError:  # el módulo es opcional
    DecisionTreeClassifier = None


@dataclass(frozen=True)
class Variable:
    clave: str
    nombre: str
    unidad: str
    minimo: float
    maximo: float
    paso: float
    # (valor, categoría) etiquetados a partir de los rangos de referencia
    referencia: dict[str, list[tuple[float, str]]]
    # categoría -> hallazgo de la base de conocimiento (None = normal)
    hallazgo: dict[str, str | None]
    # umbrales de respaldo si no hay scikit-learn: [(límite superior, categoría)]
    umbrales: dict[str, list[tuple[float, str]]]


def _rejilla(tramos: list[tuple[float, float, str]], paso: float) -> list[tuple[float, str]]:
    """Valores de referencia etiquetados a partir de tramos [desde, hasta)."""
    datos = []
    for desde, hasta, etiqueta in tramos:
        x = desde
        while x < hasta - 1e-9:
            datos.append((round(x, 2), etiqueta))
            x += paso
    return datos


_TEMP = [(34.0, 37.5, "hipotermia"), (37.5, 39.3, "normal"), (39.3, 42.5, "fiebre")]
_TEMP_GATO = [(34.0, 37.7, "hipotermia"), (37.7, 39.3, "normal"), (39.3, 42.5, "fiebre")]

VARIABLES: dict[str, Variable] = {
    "temperatura": Variable(
        "temperatura", "Temperatura rectal", "°C", 34.0, 42.5, 0.1,
        {"perro": _rejilla(_TEMP, 0.1), "gato": _rejilla(_TEMP_GATO, 0.1)},
        {"hipotermia": "hipotermia", "normal": None, "fiebre": "fiebre"},
        {"perro": [(37.5, "hipotermia"), (39.3, "normal"), (99, "fiebre")],
         "gato": [(37.7, "hipotermia"), (39.3, "normal"), (99, "fiebre")]},
    ),
    "llenado_capilar": Variable(
        "llenado_capilar", "Tiempo de llenado capilar", "s", 0.5, 6.0, 0.5,
        {e: _rejilla([(0.5, 2.5, "normal"), (2.5, 6.5, "lento")], 0.25) for e in ("perro", "gato")},
        {"normal": None, "lento": "llenado_capilar_lento"},
        {e: [(2.5, "normal"), (99, "lento")] for e in ("perro", "gato")},
    ),
    "vomitos_24h": Variable(
        "vomitos_24h", "Vómitos en las últimas 24 h", "veces", 0, 20, 1,
        {e: _rejilla([(0, 1, "ninguno"), (1, 3, "ocasional"), (3, 21, "persistente")], 1)
         for e in ("perro", "gato")},
        {"ninguno": None, "ocasional": "vomito", "persistente": "vomito_persistente"},
        {e: [(1, "ninguno"), (3, "ocasional"), (999, "persistente")] for e in ("perro", "gato")},
    ),
    "dias_sin_defecar": Variable(
        "dias_sin_defecar", "Días sin defecar", "días", 0, 10, 1,
        {e: _rejilla([(0, 2, "normal"), (2, 11, "retenido")], 1) for e in ("perro", "gato")},
        {"normal": None, "retenido": "sin_defecar"},
        {e: [(2, "normal"), (999, "retenido")] for e in ("perro", "gato")},
    ),
    "perdida_peso_pct": Variable(
        "perdida_peso_pct", "Pérdida de peso", "%", 0, 40, 1,
        {e: _rejilla([(0, 5, "estable"), (5, 41, "perdida")], 0.5) for e in ("perro", "gato")},
        {"estable": None, "perdida": "perdida_de_peso"},
        {e: [(5, "estable"), (999, "perdida")] for e in ("perro", "gato")},
    ),
}


@dataclass
class HechoDiscreto:
    """Resultado de discretizar una medición."""

    variable: str
    nombre: str
    valor: float
    unidad: str
    categoria: str
    hallazgo: str | None     # hecho que se envía a Prolog (None si es normal)
    metodo: str              # "árbol de decisión" | "umbrales de referencia"


class Discretizador:
    """Convierte mediciones continuas en hechos discretos para Prolog."""

    def __init__(self) -> None:
        self.usa_sklearn = DecisionTreeClassifier is not None
        self._arboles: dict[tuple[str, str], object] = {}
        if self.usa_sklearn:
            for variable in VARIABLES.values():
                for especie, datos in variable.referencia.items():
                    arbol = DecisionTreeClassifier(max_depth=3, random_state=0)
                    arbol.fit([[x] for x, _ in datos], [c for _, c in datos])
                    self._arboles[(variable.clave, especie)] = arbol

    def umbrales_aprendidos(self, clave: str, especie: str) -> list[float]:
        """Puntos de corte que aprendió el árbol (para mostrarlos en la interfaz)."""
        arbol = self._arboles.get((clave, especie))
        if arbol is None:
            return [u for u, _ in VARIABLES[clave].umbrales[especie][:-1]]
        return sorted(round(float(t), 2) for t in arbol.tree_.threshold if t != -2)

    def clasificar(self, clave: str, valor: float, especie: str = "perro") -> HechoDiscreto:
        variable = VARIABLES[clave]
        especie = especie if especie in variable.referencia else "perro"
        arbol = self._arboles.get((clave, especie))
        if arbol is not None:
            categoria = str(arbol.predict([[float(valor)]])[0])
            metodo = "árbol de decisión (scikit-learn)"
        else:
            categoria = next(c for limite, c in variable.umbrales[especie] if valor < limite)
            metodo = "umbrales de referencia"
        return HechoDiscreto(clave, variable.nombre, float(valor), variable.unidad,
                             categoria, variable.hallazgo[categoria], metodo)

    def discretizar(self, mediciones: dict[str, float | None], especie: str = "perro") -> list[HechoDiscreto]:
        """Clasifica todas las mediciones informadas (se ignoran las vacías)."""
        return [
            self.clasificar(clave, valor, especie)
            for clave, valor in mediciones.items()
            if clave in VARIABLES and valor is not None
        ]


if __name__ == "__main__":
    d = Discretizador()
    print("scikit-learn:", d.usa_sklearn)
    for clave in VARIABLES:
        print(clave, "cortes aprendidos (perro):", d.umbrales_aprendidos(clave, "perro"))
    for clave, valor in [("temperatura", 40.2), ("temperatura", 38.5), ("temperatura", 36.9),
                         ("llenado_capilar", 3), ("vomitos_24h", 5), ("vomitos_24h", 1)]:
        h = d.clasificar(clave, valor)
        print(f"{clave}={valor} -> {h.categoria} -> {h.hallazgo}")
