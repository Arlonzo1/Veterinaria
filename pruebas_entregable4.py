"""
pruebas_entregable4.py - Pruebas de estrés y manejo de contradicciones (Entregable 4).

Objetivo: comprobar que TriaVet detecta hechos lógicamente incompatibles y
BLOQUEA el diagnóstico antes de emitir uno erróneo, que no inventa
contradicciones en casos legítimos y que resiste entradas hostiles como las
que usará la otra pareja en la auditoría cruzada.

Grupos de pruebas:
  E4-1  Hallazgos incompatibles (cada par de incompatibilidad/3)
  E4-2  Datos del paciente imposibles (macho gestante, hembra muy joven)
  E4-3  Contradicciones en el texto libre (DCG)
  E4-4  Flujo completo: texto -> discretización -> Prolog
  E4-5  Lo que se afirma o se mide contra lo que se niega
  E4-6  La regla de corte de dictamen/4 deja una sola respuesta
  E4-7  Sin falsos positivos: los casos legítimos se siguen diagnosticando
  E4-8  Entradas hostiles y ambiguas (auditoría cruzada)
  E4-9  Estrés combinatorio: todos los pares de hallazgos
  E4-10 Estrés aleatorio: 400 casos con invariantes

Uso:
  python pruebas_entregable4.py            todas
  python pruebas_entregable4.py 1 3 9      solo esas
La salida se guarda en evidencia/entregable4/.
"""

from __future__ import annotations

import itertools
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from motor import MotorTriaVet
from preprocesamiento import Discretizador

PROYECTO = Path(__file__).resolve().parent
CARPETA_EVIDENCIA = PROYECTO / "evidencia" / "entregable4"
ANCHO = 78
PRIORIDADES = {"critico", "alto", "medio", "bajo", "indeterminado", "datos_invalidos", "inconsistente"}

# Casos legítimos (los ejemplos de la interfaz): no deben marcarse como contradictorios.
CASOS_LEGITIMOS = [
    ("Mi perrito de 4 meses vomita, está muy decaído, no quiere comer y tiene diarrea con sangre. "
     "Le faltan vacunas.", "parvovirosis"),
    ("Mi gato macho de 3 años hace fuerza para orinar, no le sale orina y llora de dolor.",
     "obstruccion_uretral"),
    ("Mi perro de 4 años estuvo encerrado en el carro al sol, jadea mucho, está decaído.",
     "golpe_de_calor"),
    ("Mi pastor alemán de 4 años tiene la barriga hinchada y dura, hace arcadas, babea mucho y "
     "está inquieto.", "dilatacion_torsion_gastrica"),
    ("Mi perra de 5 años está gestante, vomita y tiene diarrea.", None),
    ("Mi perro de 3 años no tiene fiebre ni tos, pero vomita.", None),
]

ENTRADAS_HOSTILES = [
    "",
    "     ",
    "asdf qwer zxcv",
    "'), halt. %",
    "X",
    "_",
    "fiebre(X) :- true.",
    "🐶🐱🔥🤒",
    "1234567890",
    "no no no no no",
    "no tiene ni ni ni o o",
    "tiene fiebre fiebre fiebre fiebre",
    "Mi perro tiene 999999999999999999999 grados",
    "Mi perro tiene -5 grados",
    "Mi perro tiene 40,5 grados y 41,2 grados",
    "Mi perro de -3 años vomita",
    "Mi perro de 900 años vomita",
    "mi perro esta bien",
    "MI PERRO TIENE FIEBRE Y VOMITA",
    "mi perro tiene fiebre." * 300,
]


@dataclass
class Prueba:
    numero: str
    titulo: str
    objetivo: str
    ejecutar: Callable[[MotorTriaVet, list[str], list[str]], None]


def comprobar(fallos: list[str], condicion: bool, mensaje: str) -> None:
    if not condicion:
        fallos.append(mensaje)


def todos_los_hallazgos(motor: MotorTriaVet) -> list[str]:
    return sorted(h for _, _, hs in motor.catalogo() for h in hs)


def incompatibilidades(motor: MotorTriaVet) -> list[tuple[str, str, str]]:
    return [(str(s["A"]), str(s["B"]), s["M"].decode() if isinstance(s["M"], bytes) else str(s["M"]))
            for s in motor.consultar("incompatibilidad(A, B, M)")]


# ---------------------------------------------------------------------------
# Pruebas
# ---------------------------------------------------------------------------

def prueba_incompatibles(motor, salida, fallos) -> None:
    for a, b, motivo in incompatibilidades(motor):
        r = motor.analizar_caso("perro", 24, "hembra", [a, b, "letargo"])
        salida.append(f"[{a} + {b}] -> {r.prioridad} · diagnósticos={[d.id for d in r.diagnosticos]}")
        salida.append(f"    motivo: {motivo}")
        comprobar(fallos, r.prioridad == "inconsistente", f"{a}+{b} debe bloquearse")
        comprobar(fallos, r.diagnosticos == [], f"{a}+{b} no debe diagnosticar")
        comprobar(fallos, motor.explicar("perro", 24, "hembra", [a, b]) == [],
                  f"{a}+{b}: ¿Por qué? debe quedar vacío")
        comprobar(fallos, motor.diagnosticar_todos("perro", 24, "hembra", [a, b]) == [],
                  f"{a}+{b}: diagnosticar_todos debe devolver []")
    r = motor.analizar_caso("perro", 24, "macho", ["fiebre", "hipotermia", "convulsiones"])
    salida.append(f"Con signo de alarma -> alarmas={r.alarmas}")
    salida.append(f"    {r.recomendacion}")
    comprobar(fallos, r.alarmas == ["convulsiones"] and "signos de alarma" in r.recomendacion,
              "aunque se bloquee el diagnóstico, las alarmas deben seguir avisándose")


def prueba_paciente(motor, salida, fallos) -> None:
    casos = [
        (("perro", 24, "macho", ["gestante", "vomito"]), True),
        (("gato", 3, "hembra", ["gestante"]), True),
        (("perro", 24, "hembra", ["gestante", "vomito"]), False),
        (("gato", 6, "hembra", ["gestante"]), False),
    ]
    for caso, esperado in casos:
        c = motor.verificar_consistencia(*caso)
        r = motor.analizar_caso(*caso)
        salida.append(f"{caso} -> {r.prioridad} · {[x.motivo for x in c.contradicciones] or 'consistente'}")
        comprobar(fallos, (r.prioridad == "inconsistente") == esperado, f"{caso}: esperado bloqueo={esperado}")


def prueba_texto(motor, salida, fallos) -> None:
    casos = [
        ("Mi perro tiene fiebre y no tiene fiebre.", "afirmado_y_negado"),
        ("Mi gato tiene temperatura de 40 y temperatura de 36.", "medicion_repetida"),
        ("Mi perro tiene 55 grados de temperatura.", "medicion_imposible"),
        ("Mi perro vomitó 80 veces.", "medicion_imposible"),
        ("Mi perra tiene fiebre de 4 días.", None),
        ("Mi perro tiene 40 grados y vomita.", None),
    ]
    for texto, tipo in casos:
        i = motor.interpretar(texto)
        tipos = [c.tipo for c in i.contradicciones]
        salida.append(f"«{texto}»")
        salida.append(f"    hallazgos={i.hallazgos} negados={i.negados} mediciones={i.mediciones}")
        salida.append(f"    contradicciones={[c.motivo for c in i.contradicciones] or 'ninguna'}")
        if tipo:
            comprobar(fallos, tipo in tipos, f"«{texto}» debe detectar {tipo}")
        else:
            comprobar(fallos, not tipos, f"«{texto}» no debe marcar contradicciones")


def prueba_flujo_completo(motor, salida, fallos) -> None:
    discretizador = Discretizador()
    texto = "Mi perro de 5 años tiene hipotermia, está frío al tacto y tiene 40 grados. Está decaído."
    i = motor.interpretar(texto)
    especie = i.especie or "perro"
    medidos = [h.hallazgo for h in discretizador.discretizar(dict(i.mediciones), especie) if h.hallazgo]
    hallazgos = sorted(set(i.hallazgos + medidos))
    r = motor.analizar_caso(especie, i.edad or 24, i.sexo or "macho", hallazgos)
    salida.append(f"«{texto}»")
    salida.append(f"  DCG: hallazgos={i.hallazgos} mediciones={i.mediciones}")
    salida.append(f"  Discretización (Python): {medidos}")
    salida.append(f"  Prolog: {r.prioridad} · diagnósticos={[d.id for d in r.diagnosticos]}")
    salida.append(f"  {r.recomendacion}")
    comprobar(fallos, "fiebre" in medidos, "40 °C debe discretizarse como fiebre")
    comprobar(fallos, r.prioridad == "inconsistente" and not r.diagnosticos,
              "hipotermia + 40 °C debe bloquear el diagnóstico")


def prueba_afirmado_negado(motor, salida, fallos) -> None:
    c = motor.verificar_consistencia("perro", 24, "macho", ["fiebre", "vomito"], ["fiebre"])
    q = motor.que_falta("perro", 24, "macho", ["fiebre", "vomito"], ["fiebre"])
    salida.append(f"?- {c.consulta}.")
    salida.append(f"    {[x.motivo for x in c.contradicciones]}")
    salida.append(f"¿Qué falta? -> estado={q.estado} sugerencias={len(q.sugerencias)}")
    comprobar(fallos, [x.tipo for x in c.contradicciones] == ["afirmado_y_negado"],
              "fiebre medida y negada debe ser contradicción")
    comprobar(fallos, q.estado == "inconsistente" and not q.sugerencias,
              "¿Qué falta? no debe sugerir preguntas con datos contradictorios")
    ok = motor.verificar_consistencia("perro", 24, "macho", ["vomito"], ["fiebre"])
    salida.append(f"Vomita y no tiene fiebre -> {'consistente' if ok.ok else ok.contradicciones}")
    comprobar(fallos, ok.ok, "negar lo que no se afirmó es consistente")


def prueba_corte(motor, salida, fallos) -> None:
    consulta = ("Caso = caso(perro, 24, macho, [fiebre, hipotermia, vomito]), "
                "contradicciones_caso(Caso, C), findall(P, dictamen(Caso, C, _, P), L)")
    s = motor.consultar(consulta, max_resultados=1)[0]
    soluciones = [str(x) for x in s["L"]]
    salida.append(f"?- {consulta}.")
    salida.append(f"    L = {soluciones}")
    comprobar(fallos, soluciones == ["inconsistente"],
              "el corte de dictamen/4 debe dejar una sola respuesta (inconsistente)")
    consulta2 = ("Caso = caso(perro, 4, macho, [diarrea_con_sangre, vomito, letargo, vacunacion_incompleta]), "
                 "contradicciones_caso(Caso, C), findall(P, dictamen(Caso, C, _, P), L)")
    s2 = motor.consultar(consulta2, max_resultados=1)[0]
    salida.append(f"Caso consistente -> L = {[str(x) for x in s2['L']]}")
    comprobar(fallos, [str(x) for x in s2["L"]] == ["critico"], "un caso consistente se diagnostica normal")


def prueba_legitimos(motor, salida, fallos) -> None:
    for texto, esperado in CASOS_LEGITIMOS:
        i = motor.interpretar(texto)
        r = motor.analizar_caso(i.especie or "perro", i.edad if i.edad is not None else 24,
                                i.sexo or "hembra", i.hallazgos)
        c = motor.verificar_consistencia(i.especie or "perro", i.edad if i.edad is not None else 24,
                                         i.sexo or "hembra", i.hallazgos, i.negados)
        salida.append(f"«{texto[:70]}…» -> {r.prioridad} · {[d.id for d in r.diagnosticos][:2]}")
        comprobar(fallos, c.ok and not i.contradicciones and r.prioridad != "inconsistente",
                  f"falso positivo en «{texto[:40]}»")
        if esperado:
            comprobar(fallos, r.ids[:1] == [esperado], f"«{texto[:40]}» debe concluir {esperado}")


def prueba_hostiles(motor, salida, fallos) -> None:
    tiempos = []
    for texto in ENTRADAS_HOSTILES:
        inicio = time.perf_counter()
        try:
            i = motor.interpretar(texto)
            r = motor.analizar_caso(i.especie or "perro", i.edad if i.edad is not None else 24,
                                    i.sexo or "macho", i.hallazgos)
            ms = (time.perf_counter() - inicio) * 1000
            tiempos.append(ms)
            muestra = texto if len(texto) < 50 else texto[:47] + "…"
            salida.append(f"«{muestra}» ({len(texto)} car.) -> {r.prioridad} · {ms:.0f} ms"
                          + (f" · {[c.tipo for c in i.contradicciones]}" if i.contradicciones else ""))
            comprobar(fallos, r.prioridad in PRIORIDADES, f"prioridad desconocida para «{texto[:30]}»")
        except Exception as exc:  # noqa: BLE001 - la prueba registra cualquier fallo
            fallos.append(f"«{texto[:30]}» lanzó {type(exc).__name__}: {exc}")
    # Datos del paciente fuera de dominio, enviados directamente (sin pasar por la DCG).
    for caso in [("dinosaurio", 24, "macho", ["fiebre"]), ("perro", -5, "macho", ["fiebre"]),
                 ("perro", 9999, "macho", ["fiebre"]), ("perro", 24, "otro", ["fiebre"]),
                 ("perro", 24, "macho", ["no_existe", "fiebre", "fiebre", "FIEBRE"]),
                 ("perro", "X", "macho", ["fiebre"])]:
        r = motor.analizar_caso(*caso)
        salida.append(f"{caso} -> {r.prioridad} · ignorados={r.ignorados}")
        comprobar(fallos, r.prioridad in PRIORIDADES, f"{caso} debe responder sin error")
    if tiempos:
        salida.append(f"Tiempo por entrada: promedio {sum(tiempos) / len(tiempos):.0f} ms · "
                      f"máximo {max(tiempos):.0f} ms")


def prueba_pares(motor, salida, fallos) -> None:
    hallazgos = todos_los_hallazgos(motor)
    pares = list(itertools.combinations(hallazgos, 2))
    esperados = {frozenset((a, b)) for a, b, _ in incompatibilidades(motor)}
    bloqueados, inicio = set(), time.perf_counter()
    for a, b in pares:
        r = motor.analizar_caso("perro", 24, "hembra", [a, b])
        if r.prioridad == "inconsistente":
            bloqueados.add(frozenset((a, b)))
            comprobar(fallos, not r.diagnosticos, f"{a}+{b} bloqueado pero con diagnóstico")
    segundos = time.perf_counter() - inicio
    salida.append(f"{len(hallazgos)} hallazgos -> {len(pares)} pares analizados en {segundos:.1f} s "
                  f"({segundos / len(pares) * 1000:.1f} ms por caso)")
    salida.append(f"Pares bloqueados: {len(bloqueados)} · pares incompatibles en la base: {len(esperados)}")
    for par in sorted(sorted(p) for p in bloqueados):
        salida.append(f"    {par[0]} + {par[1]}")
    comprobar(fallos, bloqueados == esperados,
              f"falsos positivos {sorted(map(sorted, bloqueados - esperados))} · "
              f"no detectados {sorted(map(sorted, esperados - bloqueados))}")


def prueba_aleatoria(motor, salida, fallos) -> None:
    rnd = random.Random(2026)
    hallazgos = todos_los_hallazgos(motor)
    n, bloqueados, inicio = 400, 0, time.perf_counter()
    for _ in range(n):
        caso = (rnd.choice(["perro", "gato"]), rnd.randint(0, 200), rnd.choice(["macho", "hembra"]),
                rnd.sample(hallazgos, rnd.randint(1, 8)))
        negados = rnd.sample(hallazgos, rnd.randint(0, 2))
        r = motor.analizar_caso(*caso)
        c = motor.verificar_consistencia(*caso, negados)
        if r.prioridad == "inconsistente":
            bloqueados += 1
            comprobar(fallos, not r.diagnosticos, f"{caso}: bloqueado con diagnóstico")
            comprobar(fallos, not c.ok, f"{caso}: analizar_caso bloquea pero verificar no")
        cruzados = set(caso[3]) & set(negados)
        if cruzados:
            comprobar(fallos, any(x.tipo == "afirmado_y_negado" for x in c.contradicciones),
                      f"{caso} con negados {negados}: debe detectar afirmado_y_negado")
        if c.ok:
            comprobar(fallos, r.prioridad != "inconsistente", f"{caso}: consistente pero bloqueado")
    segundos = time.perf_counter() - inicio
    salida.append(f"{n} casos aleatorios (semilla 2026) en {segundos:.1f} s · bloqueados: {bloqueados}")
    salida.append("Invariantes verificadas en cada caso:")
    salida.append("    bloqueado => sin diagnósticos y verificar_consistencia lo confirma")
    salida.append("    afirmado y negado a la vez => contradicción afirmado_y_negado")
    salida.append("    caso consistente => nunca se bloquea")


PRUEBAS = [
    Prueba("1", "Hallazgos incompatibles", "Cada par de incompatibilidad/3 bloquea el diagnóstico.",
           prueba_incompatibles),
    Prueba("2", "Datos del paciente imposibles", "Macho gestante y hembra demasiado joven se bloquean.",
           prueba_paciente),
    Prueba("3", "Contradicciones en el texto libre (DCG)",
           "Afirmar y negar, dos valores de una medición y valores imposibles.", prueba_texto),
    Prueba("4", "Flujo completo texto -> discretización -> Prolog",
           "«hipotermia ... 40 grados» se bloquea aunque la fiebre la produzca Python.",
           prueba_flujo_completo),
    Prueba("5", "Afirmado o medido contra negado",
           "Medir fiebre y responder que no tiene fiebre es una contradicción.", prueba_afirmado_negado),
    Prueba("6", "Regla de corte de dictamen/4", "Con contradicciones hay una sola respuesta posible.",
           prueba_corte),
    Prueba("7", "Sin falsos positivos", "Los casos legítimos se siguen diagnosticando igual.",
           prueba_legitimos),
    Prueba("8", "Entradas hostiles y ambiguas (auditoría cruzada)",
           "Texto vacío, código, emojis, números absurdos y datos fuera de dominio no rompen el sistema.",
           prueba_hostiles),
    Prueba("9", "Estrés combinatorio: todos los pares",
           "Solo los pares de incompatibilidad/3 se bloquean (ni más ni menos).", prueba_pares),
    Prueba("10", "Estrés aleatorio con invariantes", "400 casos al azar cumplen las reglas de bloqueo.",
           prueba_aleatoria),
]


class Tee:
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
    print(f"PRUEBA E4-{prueba.numero} · {prueba.titulo}")
    print("─" * ANCHO)
    print(f"Objetivo : {prueba.objetivo}")
    salida: list[str] = []
    fallos: list[str] = []
    try:
        prueba.ejecutar(motor, salida, fallos)
    except Exception as exc:  # noqa: BLE001
        fallos.append(f"Excepción: {type(exc).__name__}: {exc}")
    for linea in salida:
        print(f"  {linea}")
    for f in fallos:
        print(f"  ✘ {f}")
    print(f"Veredicto: {'✔ PASÓ' if not fallos else '✘ FALLÓ'}\n")
    return not fallos


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    pedidas = set(sys.argv[1:])
    desconocidas = pedidas - {p.numero for p in PRUEBAS}
    if desconocidas:
        raise SystemExit(f"Pruebas inexistentes: {', '.join(sorted(desconocidas))}.")
    pruebas = [p for p in PRUEBAS if not pedidas or p.numero in pedidas]
    CARPETA_EVIDENCIA.mkdir(parents=True, exist_ok=True)
    nombre = ("salida_pruebas.txt" if not pedidas
              else "prueba_" + "_".join(p.numero for p in pruebas) + ".txt")
    ruta = CARPETA_EVIDENCIA / nombre

    with open(ruta, "w", encoding="utf-8") as archivo:
        consola = sys.stdout
        sys.stdout = Tee(consola, archivo)
        try:
            print("=" * ANCHO)
            print(" TriaVet · Pruebas del Entregable 4 (estrés y manejo de contradicciones)")
            print(f" Ejecutado: {datetime.now():%Y-%m-%d %H:%M:%S}")
            print("=" * ANCHO)
            motor = MotorTriaVet()
            inicio = time.perf_counter()
            resultados = [(p, ejecutar(p, motor)) for p in pruebas]
            aprobadas = sum(ok for _, ok in resultados)
            print("=" * ANCHO)
            print(" RESUMEN")
            print("=" * ANCHO)
            for p, ok in resultados:
                print(f" {'✔' if ok else '✘'} Prueba E4-{p.numero} · {p.titulo}")
            print(f"\n {aprobadas} de {len(resultados)} pruebas aprobadas "
                  f"en {time.perf_counter() - inicio:.1f} s.")
        finally:
            sys.stdout = consola

    print(f"Evidencia guardada en: {ruta}")
    return 0 if all(ok for _, ok in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
