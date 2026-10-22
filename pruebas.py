"""
pruebas.py - Casos de prueba por consola de TriaVet.

Uso:
    python pruebas.py            ejecuta todos los casos
    python pruebas.py 1 3        ejecuta solo los casos indicados

Ejecuta los casos de prueba contra base_conocimiento.pl a través de
motor.py. Para cada caso muestra: objetivo, entrada, consulta en Prolog,
resultado esperado, resultado obtenido y veredicto. La salida también se
guarda en evidencia/salida_pruebas.txt (o en evidencia/prueba_<n>.txt
cuando se ejecutan casos sueltos).

Código de salida: 0 si todas las pruebas pasan, 1 si alguna falla.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from motor import ETIQUETA_NIVEL, MotorTriaVet, ResultadoCaso, formatear_resultado

CARPETA_EVIDENCIA = Path(__file__).resolve().with_name("evidencia")
ANCHO = 78


@dataclass
class CasoPrueba:
    numero: str
    categoria: str
    titulo: str
    objetivo: str
    especie: object
    edad: object
    sexo: object
    hallazgos: list
    esperado_diagnosticos: list[str]
    esperado_prioridad: str
    # Comprobaciones opcionales
    primero: str | None = None              # diagnóstico que debe ir primero
    no_incluye: list[str] = field(default_factory=list)
    esperado_ignorados: list[str] | None = None
    esperado_alarmas: list[str] | None = None
    severidades: dict[str, str] = field(default_factory=dict)
    indicacion_contiene: dict[str, str] = field(default_factory=dict)
    verificar_diagnosticar_todos: bool = False


CASOS: list[CasoPrueba] = [
    # 1 --------------------------------------------------------------------
    CasoPrueba(
        numero="1",
        categoria="Caso normal 1",
        titulo="Diagnóstico único claro",
        objetivo=(
            "Comprobar el encadenamiento de 3 niveles: los signos activan el "
            "estado intermedio abdomen_agudo (Nivel 2), que junto con el perfil "
            "lleva a una única conclusión de severidad crítica (Nivel 3)."
        ),
        especie="perro", edad=48, sexo="macho",
        hallazgos=["raza_torax_profundo", "abdomen_distendido",
                   "arcadas_improductivas", "salivacion_excesiva", "inquietud"],
        esperado_diagnosticos=["dilatacion_torsion_gastrica"],
        esperado_prioridad="critico",
        severidades={"dilatacion_torsion_gastrica": "critico"},
    ),
    # 2 --------------------------------------------------------------------
    CasoPrueba(
        numero="2",
        categoria="Caso normal 2",
        titulo="Múltiples diagnósticos y recolección",
        objetivo=(
            "Comprobar que setof/3 reúne varias conclusiones en una sola lista "
            "sin duplicados (la entrada repite 'vomito'), que cada una tiene "
            "su propia severidad y que el resultado se ordena de mayor a "
            "menor urgencia. También verifica diagnosticar_todos/5."
        ),
        especie="perro", edad=30, sexo="hembra",
        hallazgos=["vacunacion_completa", "ingesta_xilitol", "vomito", "vomito",
                   "temblores", "poliuria", "polidipsia", "perdida_de_peso"],
        esperado_diagnosticos=["enfermedad_renal_cronica", "intoxicacion"],
        esperado_prioridad="critico",
        primero="intoxicacion",
        severidades={"intoxicacion": "critico", "enfermedad_renal_cronica": "medio"},
        no_incluye=["gastroenteritis_aguda"],
        verificar_diagnosticar_todos=True,
    ),
    # 3 --------------------------------------------------------------------
    CasoPrueba(
        numero="3",
        categoria="Caso de exclusión",
        titulo="Negación por fallo (\\+) y corte (!)",
        objetivo=(
            "Un cachorro con diarrea con sangre sería candidato a parvovirosis, "
            "pero la vacunación completa la descarta con \\+. Queda la "
            "gastroenteritis aguda, cuya severidad base (bajo) sube a medio "
            "por ser cachorro: el corte en etapa_vida/3 y en severidad/3 "
            "elige una sola rama."
        ),
        especie="perro", edad=5, sexo="macho",
        hallazgos=["vacunacion_completa", "vomito", "diarrea_con_sangre", "anorexia"],
        esperado_diagnosticos=["gastroenteritis_aguda"],
        esperado_prioridad="medio",
        no_incluye=["parvovirosis"],
        severidades={"gastroenteritis_aguda": "medio"},
    ),
    # 4 --------------------------------------------------------------------
    CasoPrueba(
        numero="4",
        categoria="Caso borde 1",
        titulo="Datos insuficientes / lista parcial",
        objetivo=(
            "La lista cumple solo parte del perfil del moquillo (falta 'fiebre', "
            "requisito obligatorio verificado con contiene_todos/2) e incluye "
            "un hallazgo inexistente que particionar/3 debe ignorar. setof/3 "
            "no encuentra soluciones y se aplica el valor por defecto."
        ),
        especie="perro", edad=60, sexo="hembra",
        hallazgos=["secrecion_nasal", "tos", "vacunacion_incompleta", "estornudo_raro"],
        esperado_diagnosticos=["sin_diagnostico_concluyente"],
        esperado_prioridad="bajo",
        no_incluye=["moquillo"],
        esperado_ignorados=["estornudo_raro"],
    ),
    # 5 --------------------------------------------------------------------
    CasoPrueba(
        numero="5",
        categoria="Caso borde 2",
        titulo="Lista vacía sin errores en Python",
        objetivo=(
            "Con una lista vacía, Prolog debe responder con la cláusula por "
            "defecto (prioridad indeterminado y ningún diagnóstico) y Python "
            "debe mostrarlo sin lanzar excepciones."
        ),
        especie="gato", edad=24, sexo="hembra",
        hallazgos=[],
        esperado_diagnosticos=[],
        esperado_prioridad="indeterminado",
        esperado_alarmas=[],
    ),
    # Complementarios --------------------------------------------------------
    CasoPrueba(
        numero="6",
        categoria="Complementario",
        titulo="Contraste del caso 3 sin vacunación",
        objetivo=(
            "Con los mismos signos del caso 3 pero sin vacunación completa, la "
            "parvovirosis sí se concluye y excluye a la gastroenteritis "
            "(excluye/2). Su severidad base (alto) sube a crítico por ser "
            "cachorro."
        ),
        especie="perro", edad=5, sexo="macho",
        hallazgos=["vomito", "diarrea_con_sangre", "anorexia"],
        esperado_diagnosticos=["parvovirosis"],
        esperado_prioridad="critico",
        no_incluye=["gastroenteritis_aguda"],
        severidades={"parvovirosis": "critico"},
    ),
    CasoPrueba(
        numero="7",
        categoria="Complementario",
        titulo="Exclusión entre diagnósticos (gato macho)",
        objetivo=(
            "El caso cumple el perfil de cistitis, pero la retención urinaria "
            "en un gato macho concluye obstrucción uretral, que la excluye "
            "mediante \\+ excluido/2."
        ),
        especie="gato", edad=36, sexo="macho",
        hallazgos=["esfuerzo_para_orinar", "ausencia_de_orina",
                   "sangre_en_orina", "vocalizacion_dolor"],
        esperado_diagnosticos=["obstruccion_uretral"],
        esperado_prioridad="critico",
        no_incluye=["cistitis"],
    ),
    CasoPrueba(
        numero="8",
        categoria="Complementario",
        titulo="Mismo gato sin retención urinaria",
        objetivo=(
            "Sin 'ausencia_de_orina' no hay retención, la obstrucción no es "
            "candidata y la cistitis deja de estar excluida."
        ),
        especie="gato", edad=36, sexo="macho",
        hallazgos=["esfuerzo_para_orinar", "miccion_frecuente",
                   "sangre_en_orina", "vocalizacion_dolor"],
        esperado_diagnosticos=["cistitis"],
        esperado_prioridad="medio",
        no_incluye=["obstruccion_uretral"],
    ),
    CasoPrueba(
        numero="9",
        categoria="Complementario",
        titulo="Signo de alarma sin diagnóstico",
        objetivo=(
            "Las convulsiones no completan ningún perfil, pero son un signo de "
            "alarma: la primera cláusula de prioridad_caso/3 (con corte) fija "
            "la prioridad en crítico y indicacion_para/3 cambia la indicación "
            "por defecto por la de urgencias."
        ),
        especie="perro", edad=24, sexo="macho",
        hallazgos=["convulsiones"],
        esperado_diagnosticos=["sin_diagnostico_concluyente"],
        esperado_prioridad="critico",
        esperado_alarmas=["convulsiones"],
        indicacion_contiene={"sin_diagnostico_concluyente": "urgencias"},
    ),
    CasoPrueba(
        numero="10",
        categoria="Complementario",
        titulo="Datos del paciente no válidos",
        objetivo=(
            "Especie y edad fuera del dominio: datos_paciente_validos/1 falla y "
            "la cláusula por defecto de analizar_caso/10 responde "
            "datos_invalidos sin error en Python."
        ),
        especie="conejo", edad="abc", sexo="macho",
        hallazgos=["vomito"],
        esperado_diagnosticos=[],
        esperado_prioridad="datos_invalidos",
    ),
]


class Tee:
    """Escribe simultáneamente en la consola y en un archivo."""

    def __init__(self, *destinos):
        self.destinos = destinos

    def write(self, texto):
        for d in self.destinos:
            d.write(texto)

    def flush(self):
        for d in self.destinos:
            d.flush()


def comprobar(caso: CasoPrueba, r: ResultadoCaso, todos: list[str] | None) -> list[str]:
    """Devuelve la lista de discrepancias entre lo esperado y lo obtenido."""
    fallos = []
    if sorted(r.ids) != sorted(caso.esperado_diagnosticos):
        fallos.append(f"diagnósticos {sorted(r.ids)} != {sorted(caso.esperado_diagnosticos)}")
    if r.prioridad != caso.esperado_prioridad:
        fallos.append(f"prioridad {r.prioridad} != {caso.esperado_prioridad}")
    if len(r.ids) != len(set(r.ids)):
        fallos.append("la lista de diagnósticos contiene duplicados")
    if caso.primero and (not r.ids or r.ids[0] != caso.primero):
        fallos.append(f"el primer diagnóstico debería ser {caso.primero}")
    for excluido in caso.no_incluye:
        if excluido in r.ids:
            fallos.append(f"{excluido} debería estar excluido")
    if caso.esperado_ignorados is not None and r.ignorados != caso.esperado_ignorados:
        fallos.append(f"ignorados {r.ignorados} != {caso.esperado_ignorados}")
    if caso.esperado_alarmas is not None and r.alarmas != caso.esperado_alarmas:
        fallos.append(f"alarmas {r.alarmas} != {caso.esperado_alarmas}")
    severidad_obtenida = {d.id: d.severidad for d in r.diagnosticos}
    for diag, nivel in caso.severidades.items():
        if severidad_obtenida.get(diag) != nivel:
            fallos.append(f"severidad de {diag}: {severidad_obtenida.get(diag)} != {nivel}")
    indicaciones = {d.id: d.indicacion for d in r.diagnosticos}
    for diag, texto in caso.indicacion_contiene.items():
        if texto not in indicaciones.get(diag, ""):
            fallos.append(f"la indicación de {diag} debería mencionar «{texto}»")
    if todos is not None and todos != sorted(set(caso.esperado_diagnosticos)):
        fallos.append(f"diagnosticar_todos/5 devolvió {todos}")
    return fallos


def describir_esperado(caso: CasoPrueba) -> list[str]:
    diags = ", ".join(caso.esperado_diagnosticos) or "(ninguno)"
    lineas = [f"diagnósticos = [{diags}]",
              f"prioridad = {ETIQUETA_NIVEL.get(caso.esperado_prioridad, caso.esperado_prioridad)}"]
    if caso.primero:
        lineas.append(f"primero en la lista = {caso.primero}")
    if caso.severidades:
        lineas.append("severidades: " + ", ".join(f"{d}={n}" for d, n in caso.severidades.items()))
    if caso.no_incluye:
        lineas.append("no debe incluir: " + ", ".join(caso.no_incluye))
    if caso.esperado_ignorados is not None:
        lineas.append(f"ignorados = {caso.esperado_ignorados}")
    if caso.esperado_alarmas is not None:
        lineas.append(f"alarmas = {caso.esperado_alarmas}")
    for diag, texto in caso.indicacion_contiene.items():
        lineas.append(f"la indicación de {diag} menciona «{texto}»")
    return lineas


def ejecutar(caso: CasoPrueba, motor: MotorTriaVet) -> bool:
    print("─" * ANCHO)
    print(f"PRUEBA {caso.numero} · {caso.categoria}: {caso.titulo}")
    print("─" * ANCHO)
    print(f"Objetivo : {caso.objetivo}")
    print(f"Entrada  : especie={caso.especie}, edad={caso.edad} meses, sexo={caso.sexo}")
    print(f"           hallazgos={caso.hallazgos}")

    resultado = motor.analizar_caso(caso.especie, caso.edad, caso.sexo, caso.hallazgos)
    print(f"Consulta : ?- {resultado.consulta}.")

    todos = None
    if caso.verificar_diagnosticar_todos:
        todos = motor.diagnosticar_todos(caso.especie, caso.edad, caso.sexo, caso.hallazgos)
        consulta = motor.consulta_diagnosticar_todos(caso.especie, caso.edad, caso.sexo,
                                                     caso.hallazgos)
        print(f"           ?- {consulta}.")

    esperado = describir_esperado(caso)
    print(f"Esperado : {esperado[0]}")
    for linea in esperado[1:]:
        print(f"           {linea}")

    print(f"Obtenido : diagnósticos = [{', '.join(resultado.ids) or '(ninguno)'}]"
          f" · prioridad = {ETIQUETA_NIVEL.get(resultado.prioridad, resultado.prioridad)}")
    if todos is not None:
        print(f"           diagnosticar_todos/5 -> {todos}")
    print(formatear_resultado(resultado, sangria="           "))

    fallos = comprobar(caso, resultado, todos)
    if fallos:
        print("Veredicto: ✘ FALLÓ")
        for f in fallos:
            print(f"           - {f}")
    else:
        print("Veredicto: ✔ PASÓ")
    print()
    return not fallos


def seleccionar_casos(argumentos: list[str]) -> list[CasoPrueba]:
    """Sin argumentos: todos los casos. Con números: solo esos casos."""
    if not argumentos:
        return CASOS
    pedidos = set(argumentos)
    desconocidos = pedidos - {c.numero for c in CASOS}
    if desconocidos:
        raise SystemExit(f"Casos inexistentes: {', '.join(sorted(desconocidos))}. "
                         f"Disponibles: 1 a {len(CASOS)}.")
    return [c for c in CASOS if c.numero in pedidos]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    casos = seleccionar_casos(sys.argv[1:])
    CARPETA_EVIDENCIA.mkdir(exist_ok=True)
    nombre = ("salida_pruebas.txt" if casos is CASOS
              else "prueba_" + "_".join(c.numero for c in casos) + ".txt")
    ruta_evidencia = CARPETA_EVIDENCIA / nombre
    resultados: list[tuple[CasoPrueba, bool]] = []
    aprobadas = 0

    with open(ruta_evidencia, "w", encoding="utf-8") as archivo:
        consola = sys.stdout
        sys.stdout = Tee(consola, archivo)
        try:
            print("=" * ANCHO)
            print(" TriaVet · Script de pruebas por consola (Python + SWI-Prolog vía PySwip)")
            print(f" Ejecutado: {datetime.now():%Y-%m-%d %H:%M:%S}")
            print("=" * ANCHO)
            motor = MotorTriaVet()
            print(f"Base de conocimiento cargada: {motor.ruta_base.name}\n")

            resultados = [(c, ejecutar(c, motor)) for c in casos]

            aprobadas = sum(ok for _, ok in resultados)
            print("=" * ANCHO)
            print(" RESUMEN")
            print("=" * ANCHO)
            for caso, ok in resultados:
                marca = "✔" if ok else "✘"
                print(f" {marca} Prueba {caso.numero:>2} · {caso.categoria}: {caso.titulo}")
            print(f"\n {aprobadas} de {len(resultados)} pruebas aprobadas.")
        finally:
            sys.stdout = consola

    print(f"Evidencia guardada en: {ruta_evidencia}")
    return 0 if aprobadas == len(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
