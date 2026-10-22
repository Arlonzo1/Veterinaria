"""
pruebas_explicabilidad.py - Pruebas de los módulos del Entregable 2.

Uso:
    python pruebas_explicabilidad.py          ejecuta todas las pruebas
    python pruebas_explicabilidad.py 1 4      ejecuta solo las indicadas

Verifica contra base_conocimiento.pl, a través de motor.py:
  - el módulo "¿Por qué?" (explicar_caso/5 e hipotesis_descartadas/5);
  - el módulo "¿Qué falta?" (que_falta/8 y pregunta_desempate/6);
  - la validación de entradas con ground/1 (entrada_segura/4).
La salida se guarda en evidencia/entregable2/salida_pruebas.txt (o en
prueba_<n>.txt cuando se ejecutan pruebas sueltas).

Código de salida: 0 si todas las pruebas pasan, 1 si alguna falla.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from motor import ETIQUETA_NIVEL, MotorTriaVet, NodoTraza

CARPETA_EVIDENCIA = Path(__file__).resolve().parent / "evidencia" / "entregable2"
ANCHO = 78

CACHORRO = ("perro", 4, "macho",
            ["vomito", "diarrea_con_sangre", "letargo", "anorexia", "vacunacion_incompleta"])
GATO = ("gato", 36, "macho", ["esfuerzo_para_orinar", "vocalizacion_dolor"])
DECAIDO = ("perro", 48, "hembra", ["letargo", "anorexia"])
EMPATE = ("perro", 48, "macho", ["exposicion_calor", "jadeo_excesivo", "letargo", "ingesta_xilitol"])


@dataclass
class Prueba:
    numero: str
    titulo: str
    objetivo: str
    ejecutar: Callable[[MotorTriaVet, list[str], list[str]], None]


def comprobar(fallos: list[str], condicion: bool, mensaje: str) -> None:
    if not condicion:
        fallos.append(mensaje)


def contar_nodos(nodos: list[NodoTraza], tipo: str) -> int:
    return sum((n.tipo == tipo) + contar_nodos(n.hijos, tipo) for n in nodos)


# ---------------------------------------------------------------------------
# Pruebas
# ---------------------------------------------------------------------------

def prueba_por_que(motor: MotorTriaVet, salida: list[str], fallos: list[str]) -> None:
    salida.append(f"?- {motor.consulta_explicacion(*CACHORRO)}.")
    explicaciones = motor.explicar(*CACHORRO)
    comprobar(fallos, [e.id for e in explicaciones] == ["parvovirosis"],
              f"explicaciones {[e.id for e in explicaciones]} != ['parvovirosis']")
    if not explicaciones:
        return
    e = explicaciones[0]
    reglas = [r.etiqueta for r in e.reglas]
    salida.append(f"Reglas disparadas ({len(reglas)}):")
    salida += [f"  Nivel {r.nivel}: {r.etiqueta}" for r in e.reglas]
    salida.append(f"Hechos comprobados: {e.hechos}")
    salida.append(f"Datos del paciente: {e.datos}")
    salida += [f"Severidad: {p}" for p in e.severidad]
    salida.append(f"Certeza: {e.certeza}")
    for esperada in ["diagnostico_posible(Caso, parvovirosis)", "candidato(Caso, parvovirosis)",
                     "cuadro_digestivo(Caso)", "susceptible_parvovirus(Caso)",
                     "etapa(Caso, cachorro)", "cumple_perfil(Caso, parvovirosis)"]:
        comprobar(fallos, esperada in reglas, f"falta la regla disparada {esperada}")
    comprobar(fallos, {r.nivel for r in e.reglas} == {1, 2, 3},
              "deben aparecer reglas de los niveles 1, 2 y 3")
    comprobar(fallos, e.hechos == sorted(CACHORRO[3]), f"hechos {e.hechos}")
    comprobar(fallos, contar_nodos(e.arbol, "negacion") == 2,
              "el árbol debe registrar las dos negaciones por fallo (\\+)")
    comprobar(fallos, e.severidad[-1] == "Nivel final: CRÍTICO.", "severidad final")
    comprobar(fallos, "95 %" in e.certeza, "certeza 95 %")


def prueba_descartadas(motor: MotorTriaVet, salida: list[str], fallos: list[str]) -> None:
    salida.append(f"?- {motor.consulta_descartadas(*CACHORRO)}.")
    descartadas = {d.id: d for d in motor.descartadas(*CACHORRO)}
    for d in descartadas.values():
        salida.append(f"  {d.nombre} [{d.tipo}] comparte {d.compartidos}")
        salida.append(f"      {d.resumen}")
    esperados = {
        "gastroenteritis_aguda": "exclusion",
        "enfermedad_renal_cronica": "condicion_excluyente",
        "obstruccion_uretral": "dato_paciente",
        "obstruccion_intestinal": "evidencia_insuficiente",
    }
    for diagnostico, tipo in esperados.items():
        obtenido = descartadas.get(diagnostico)
        comprobar(fallos, obtenido is not None and obtenido.tipo == tipo,
                  f"{diagnostico} debería descartarse por {tipo}")
    comprobar(fallos, "parvovirosis" not in descartadas, "la conclusión no es una descartada")
    comprobar(fallos, all(d.compartidos for d in descartadas.values()),
              "toda descartada comparte al menos un hallazgo")


def prueba_exclusion_negacion(motor: MotorTriaVet, salida: list[str], fallos: list[str]) -> None:
    caso = ("perro", 5, "macho", ["vacunacion_completa", "vomito", "diarrea_con_sangre", "anorexia"])
    salida.append(f"?- {motor.consulta_descartadas(*caso)}.")
    descartadas = {d.id: d for d in motor.descartadas(*caso)}
    parvo = descartadas.get("parvovirosis")
    if parvo:
        salida.append(f"  {parvo.nombre} [{parvo.tipo}] {parvo.resumen}")
        salida += ["  " + linea for linea in texto_arbol(parvo.arbol)]
    comprobar(fallos, parvo is not None and parvo.tipo == "condicion_excluyente",
              "parvovirosis debe descartarse por la vacunación completa (\\+)")
    comprobar(fallos, parvo is not None and contar_nodos(parvo.arbol, "excluyente") >= 1,
              "el árbol de refutación debe contener el nodo excluyente")


def prueba_que_falta_desempate(motor: MotorTriaVet, salida: list[str], fallos: list[str]) -> None:
    salida.append(f"?- {motor.consulta_que_falta(*GATO, [])}.")
    reco = motor.que_falta(*GATO, [])
    salida.append(f"Estado: {reco.estado} (activo={reco.activo}) {reco.mensaje}")
    for c in reco.competidoras:
        salida.append(f"  Compite: {c.nombre} [{c.estado}] activación {c.activacion} % "
                      f"falta {c.falta}")
    salida.append(f"?- {motor.consulta_pregunta_desempate(*GATO, [])}.")
    pregunta = motor.pregunta_desempate(*GATO, [])
    if pregunta:
        salida.append(f"Pregunta de mayor peso: {pregunta.pregunta} (peso {pregunta.peso}, "
                      f"desempata={pregunta.desempata})")
        salida.append(f"  {pregunta.efecto}")
    comprobar(fallos, reco.activo and reco.estado == "certeza_baja", "el módulo debe activarse")
    comprobar(fallos, [(c.id, c.estado) for c in reco.competidoras]
              == [("cistitis", "confirmada"), ("obstruccion_uretral", "parcial")],
              "compiten cistitis (confirmada) y obstrucción uretral (parcial)")
    comprobar(fallos, pregunta is not None and pregunta.hallazgos == ["ausencia_de_orina"],
              "la pregunta de desempate debe ser ausencia_de_orina")
    comprobar(fallos, pregunta is not None and pregunta.desempata, "debe marcarse como desempate")
    comprobar(fallos, pregunta is not None and "CRÍTICO" in pregunta.efecto,
              "el efecto simulado debe subir la prioridad a CRÍTICO")
    pesos = [s.peso for s in reco.sugerencias]
    comprobar(fallos, pesos == sorted(pesos, reverse=True), "sugerencias ordenadas por peso")


def prueba_respuesta_si(motor: MotorTriaVet, salida: list[str], fallos: list[str]) -> None:
    especie, edad, sexo, hallazgos = GATO
    hallazgos = hallazgos + ["ausencia_de_orina"]
    salida.append("Respuesta del usuario: «Sí, lo presenta» (ausencia_de_orina)")
    resultado = motor.analizar_caso(especie, edad, sexo, hallazgos)
    reco = motor.que_falta(especie, edad, sexo, hallazgos, [])
    salida.append(f"Diagnósticos: {resultado.ids} · prioridad "
                  f"{ETIQUETA_NIVEL.get(resultado.prioridad)} · estado {reco.estado}")
    comprobar(fallos, resultado.ids == ["obstruccion_uretral"], "debe concluirse obstrucción uretral")
    comprobar(fallos, resultado.prioridad == "critico", "prioridad crítica")
    comprobar(fallos, reco.estado == "definitivo" and not reco.activo, "dictamen definitivo")


def prueba_respuesta_no(motor: MotorTriaVet, salida: list[str], fallos: list[str]) -> None:
    salida.append("Respuesta del usuario: «No lo presenta» (ausencia_de_orina)")
    salida.append(f"?- {motor.consulta_que_falta(*GATO, ['ausencia_de_orina'])}.")
    reco = motor.que_falta(*GATO, ["ausencia_de_orina"])
    estados = {c.id: c.estado for c in reco.competidoras}
    salida.append(f"Competidoras: {estados}")
    pregunta = motor.pregunta_desempate(*GATO, ["ausencia_de_orina"])
    salida.append(f"Nueva pregunta: {pregunta.pregunta if pregunta else '(ninguna)'}")
    comprobar(fallos, estados.get("obstruccion_uretral") == "refutada_usuario",
              "la obstrucción debe quedar refutada por la respuesta")
    comprobar(fallos, pregunta is not None and "ausencia_de_orina" not in pregunta.hallazgos,
              "no debe volver a preguntar lo ya respondido")


def prueba_insuficiente(motor: MotorTriaVet, salida: list[str], fallos: list[str]) -> None:
    salida.append(f"?- {motor.consulta_que_falta(*DECAIDO, [])}.")
    reco = motor.que_falta(*DECAIDO, [])
    salida.append(f"Estado: {reco.estado} (activo={reco.activo}) {reco.mensaje}")
    for c in reco.competidoras:
        salida.append(f"  Compite: {c.nombre} activación {c.activacion} % falta {c.falta}")
    for i, s in enumerate(reco.sugerencias[:5], start=1):
        salida.append(f"  {i}. {s.pregunta} (peso {s.peso})")
    comprobar(fallos, reco.estado == "insuficiente" and reco.activo, "evidencia insuficiente")
    comprobar(fallos, len(reco.competidoras) >= 3, "varias hipótesis parcialmente activas")
    comprobar(fallos, all(c.estado == "parcial" for c in reco.competidoras),
              "ninguna confirmada")
    comprobar(fallos, bool(reco.sugerencias)
              and reco.sugerencias[0].hallazgos == ["vomito_persistente"],
              "la primera pregunta debe ser vomito_persistente")


def prueba_empate(motor: MotorTriaVet, salida: list[str], fallos: list[str]) -> None:
    salida.append(f"?- {motor.consulta_que_falta(*EMPATE, [])}.")
    reco = motor.que_falta(*EMPATE, [])
    salida.append(f"Estado: {reco.estado} (activo={reco.activo}) {reco.mensaje}")
    for i, s in enumerate(reco.sugerencias[:4], start=1):
        salida.append(f"  {i}. {s.pregunta} (peso {s.peso}, desempata={s.desempata})")
        salida.append(f"     {s.efecto}")
    comprobar(fallos, reco.estado == "empate" and reco.activo, "debe detectarse el empate")
    primera = reco.sugerencias[0] if reco.sugerencias else None
    comprobar(fallos, primera is not None and primera.desempata,
              "la primera pregunta debe favorecer a una sola de las hipótesis empatadas")
    comprobar(fallos, primera is not None and ("se rompería el empate" in primera.efecto
                                               or "definitivo" in primera.efecto),
              "responder «sí» a la primera pregunta debe romper el empate")
    no_separan = [s for s in reco.sugerencias if not s.desempata]
    comprobar(fallos, all(s.peso < primera.peso for s in no_separan) if primera else False,
              "una pregunta que refuerza a ambas no debe pesar más que una que las separa")


def prueba_alarma(motor: MotorTriaVet, salida: list[str], fallos: list[str]) -> None:
    caso = ("perro", 24, "macho", ["convulsiones"])
    salida.append(f"?- {motor.consulta_explicacion(*caso)}.")
    e = motor.explicar(*caso)
    if e:
        salida.append(f"{e[0].id}: {e[0].arbol[0].descripcion}")
        salida += [f"Severidad: {p}" for p in e[0].severidad]
    comprobar(fallos, [x.id for x in e] == ["sin_diagnostico_concluyente"], "sin diagnóstico")
    comprobar(fallos, bool(e) and "alarma" in e[0].severidad[0], "la severidad explica la alarma")


def prueba_validacion(motor: MotorTriaVet, salida: list[str], fallos: list[str]) -> None:
    consultas = [
        ("explicar_caso(perro, 48, macho, [vomito, X], E)", "E", []),
        ("hipotesis_descartadas(perro, 48, macho, _, D)", "D", []),
        ("explicar_caso('Perro', 48, macho, [vomito], E)", "E", []),
        ("que_falta(perro, Edad, macho, [vomito], [], Estado, C, S)", "Estado", None),
    ]
    for consulta, variable, esperado in consultas:
        soluciones = motor.consultar(consulta, max_resultados=1)
        valor = soluciones[0][variable] if soluciones else "(falló)"
        salida.append(f"?- {consulta}.  ->  {variable} = {valor}")
        if esperado is not None:
            comprobar(fallos, valor == esperado, f"{consulta} debería dar {esperado}")
        else:
            comprobar(fallos, isinstance(valor, list) and valor[0] == "datos_invalidos",
                      f"{consulta} debería responder datos_invalidos")


PRUEBAS = [
    Prueba("1", "¿Por qué?: traza de una inferencia completa",
           "Cachorro sin vacunación completa con diarrea con sangre: la traza debe mostrar las "
           "reglas de los niveles 3, 2 y 1, las negaciones por fallo, los hechos comprobados "
           "y la justificación de la severidad y la certeza.", prueba_por_que),
    Prueba("2", "¿Por qué?: hipótesis alternativas descartadas",
           "En el mismo caso, cada hipótesis que comparte hallazgos debe descartarse con su "
           "motivo: exclusión, condición excluyente (\\+), dato del paciente o falta de evidencia.",
           prueba_descartadas),
    Prueba("3", "¿Por qué?: refutación por negación (\\+)",
           "Caso 3 del Entregable 1: la vacunación completa descarta la parvovirosis; el árbol "
           "de refutación debe mostrar la condición excluyente.", prueba_exclusion_negacion),
    Prueba("4", "¿Qué falta?: certeza baja y consulta de desempate",
           "Gato macho con esfuerzo para orinar: cistitis con certeza baja frente a obstrucción "
           "uretral parcial. pregunta_desempate/6 debe sugerir ausencia_de_orina.",
           prueba_que_falta_desempate),
    Prueba("5", "¿Qué falta?: el usuario responde «sí»",
           "Al agregar el hallazgo sugerido se confirma la obstrucción uretral y el dictamen "
           "pasa a ser definitivo.", prueba_respuesta_si),
    Prueba("6", "¿Qué falta?: el usuario responde «no»",
           "La respuesta negativa refuta la hipótesis que lo exigía y no se vuelve a preguntar.",
           prueba_respuesta_no),
    Prueba("7", "¿Qué falta?: evidencia insuficiente",
           "Perro decaído que no come: ningún perfil se completa; varias hipótesis compiten y "
           "la pregunta de mayor peso es el vómito persistente.", prueba_insuficiente),
    Prueba("8", "¿Qué falta?: empate entre dos diagnósticos",
           "Golpe de calor e intoxicación por xilitol con la misma severidad y certeza: la "
           "primera pregunta debe separarlas y romper el empate.", prueba_empate),
    Prueba("9", "¿Por qué?: alarma sin diagnóstico",
           "Convulsiones sin perfil completo: la explicación usa el valor por defecto de "
           "conclusiones/2 y la severidad se justifica por la alarma.", prueba_alarma),
    Prueba("10", "Validación de entradas con ground/1",
           "Variables libres, listas abiertas o átomos con mayúscula deben rechazarse con la "
           "cláusula por defecto, sin errores en Python.", prueba_validacion),
]


def texto_arbol(nodos: list[NodoTraza], sangria: str = "") -> list[str]:
    lineas = []
    for n in nodos:
        lineas.append(f"{sangria}[{n.tipo}] {n.etiqueta} — {n.descripcion}")
        lineas += texto_arbol(n.hijos, sangria + "    ")
    return lineas


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


def ejecutar(prueba: Prueba, motor: MotorTriaVet) -> bool:
    print("─" * ANCHO)
    print(f"PRUEBA E2-{prueba.numero} · {prueba.titulo}")
    print("─" * ANCHO)
    print(f"Objetivo : {prueba.objetivo}")
    salida: list[str] = []
    fallos: list[str] = []
    prueba.ejecutar(motor, salida, fallos)
    for linea in salida:
        print(f"  {linea}")
    if fallos:
        print("Veredicto: ✘ FALLÓ")
        for f in fallos:
            print(f"           - {f}")
    else:
        print("Veredicto: ✔ PASÓ")
    print()
    return not fallos


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    pedidas = set(sys.argv[1:])
    desconocidas = pedidas - {p.numero for p in PRUEBAS}
    if desconocidas:
        raise SystemExit(f"Pruebas inexistentes: {', '.join(sorted(desconocidas))}. "
                         f"Disponibles: 1 a {len(PRUEBAS)}.")
    pruebas = [p for p in PRUEBAS if not pedidas or p.numero in pedidas]
    CARPETA_EVIDENCIA.mkdir(parents=True, exist_ok=True)
    nombre = ("salida_pruebas.txt" if not pedidas
              else "prueba_" + "_".join(p.numero for p in pruebas) + ".txt")
    ruta = CARPETA_EVIDENCIA / nombre
    resultados: list[tuple[Prueba, bool]] = []

    with open(ruta, "w", encoding="utf-8") as archivo:
        consola = sys.stdout
        sys.stdout = Tee(consola, archivo)
        try:
            print("=" * ANCHO)
            print(" TriaVet · Pruebas del Entregable 2 (explicabilidad y recomendación)")
            print(f" Ejecutado: {datetime.now():%Y-%m-%d %H:%M:%S}")
            print("=" * ANCHO)
            motor = MotorTriaVet()
            print(f"Base de conocimiento cargada: {motor.ruta_base.name}\n")
            resultados = [(p, ejecutar(p, motor)) for p in pruebas]
            aprobadas = sum(ok for _, ok in resultados)
            print("=" * ANCHO)
            print(" RESUMEN")
            print("=" * ANCHO)
            for p, ok in resultados:
                print(f" {'✔' if ok else '✘'} Prueba E2-{p.numero} · {p.titulo}")
            print(f"\n {aprobadas} de {len(resultados)} pruebas aprobadas.")
        finally:
            sys.stdout = consola

    print(f"Evidencia guardada en: {ruta}")
    return 0 if all(ok for _, ok in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
