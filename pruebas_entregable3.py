"""
pruebas_entregable3.py - Pruebas del Entregable 3 (lenguaje natural y Modo Experto).

Uso:
    python pruebas_entregable3.py          ejecuta todas las pruebas
    python pruebas_entregable3.py 1 9      ejecuta solo las indicadas

Verifica contra base_conocimiento.pl, a través de motor.py:
  - la gramática DCG (interpretar_texto/10): extracción de hechos,
    negaciones, datos del paciente, mediciones y la oración generada;
  - el preprocesamiento numérico (preprocesamiento.py);
  - el Modo Experto: validación, assertz/1, escritura en el .pl,
    persistencia tras reiniciar (un proceso nuevo de Python) y olvido.

Las pruebas de aprendizaje trabajan sobre una COPIA temporal de
base_conocimiento.pl, así el archivo del proyecto no cambia. Para que la DCG
y el motor usen el mismo archivo, todas las pruebas cargan esa copia.

La salida se guarda en evidencia/entregable3/salida_pruebas.txt.
Código de salida: 0 si todas las pruebas pasan, 1 si alguna falla.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from motor import ETIQUETA_NIVEL, MotorTriaVet
from preprocesamiento import Discretizador

PROYECTO = Path(__file__).resolve().parent
CARPETA_EVIDENCIA = PROYECTO / "evidencia" / "entregable3"
ANCHO = 78

TEXTO_CACHORRO = ("Mi perrito de 4 meses vomita mucho, tiene diarrea con sangre y está muy "
                  "decaído. No tiene fiebre ni tos. Nunca lo vacunaron.")
TEXTO_LEPTO = "Mi perro de 3 años tiene los ojos amarillos, fiebre y está decaído."

HALLAZGO_NUEVO = dict(
    id_="ictericia", nombre="Piel u ojos amarillos (ictericia)", grupo="general",
    pregunta="¿Tiene la piel, las encías o el blanco de los ojos amarillos?",
    expresiones=["ojos amarillos", "piel amarilla", "amarill*"], autor="Dra. Prueba",
)
DIAGNOSTICO_NUEVO = dict(
    id="leptospirosis", nombre="Leptospirosis", especies=["perro"], curso="agudo",
    requisitos=["ictericia"], apoyo=["fiebre", "vomito", "letargo", "anorexia"], minimo=1,
    severidad="alto", certeza=60,
    indicacion="Use guantes al manipular la orina y acuda hoy al veterinario.",
    excluye=[], excluido_por=[], autor="Dra. Prueba",
)

# Estado compartido entre pruebas (la copia del .pl y su huella original).
ESTADO: dict[str, object] = {}


@dataclass
class Prueba:
    numero: str
    titulo: str
    objetivo: str
    ejecutar: Callable[[MotorTriaVet, list[str], list[str]], None]


def comprobar(fallos: list[str], condicion: bool, mensaje: str) -> None:
    if not condicion:
        fallos.append(mensaje)


def huella(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:16]


def seccion_13(ruta: Path) -> str:
    marca = "%% >>> CONOCIMIENTO APRENDIDO EN CALIENTE >>>"
    return ruta.read_text(encoding="utf-8").split(marca, 1)[1].strip()


# ---------------------------------------------------------------------------
# Lenguaje natural (DCG)
# ---------------------------------------------------------------------------

def prueba_extraccion(motor, salida, fallos) -> None:
    salida.append(f"Texto: «{TEXTO_CACHORRO}»")
    i = motor.interpretar(TEXTO_CACHORRO)
    salida.append(f"?- {i.consulta}.")
    salida.append(f"Especie={i.especie} · Edad={i.edad} meses · Sexo={i.sexo}")
    salida.append(f"Hallazgos={i.hallazgos}")
    comprobar(fallos, i.especie == "perro", f"especie {i.especie}")
    comprobar(fallos, i.edad == 4, f"edad {i.edad}")
    esperados = ["diarrea_con_sangre", "letargo", "vacunacion_incompleta", "vomito_persistente"]
    comprobar(fallos, i.hallazgos == esperados, f"hallazgos {i.hallazgos} != {esperados}")


def prueba_negacion(motor, salida, fallos) -> None:
    i = motor.interpretar(TEXTO_CACHORRO)
    salida.append(f"Negados={i.negados}")
    comprobar(fallos, i.negados == ["fiebre", "tos"], f"negados {i.negados}")
    texto = "El gato no come, no orina y no tiene fiebre"
    j = motor.interpretar(texto)
    salida.append(f"Texto: «{texto}» -> hallazgos={j.hallazgos} · negados={j.negados}")
    comprobar(fallos, j.hallazgos == ["anorexia", "ausencia_de_orina"],
              "«no come» y «no orina» son hallazgos (expresión más larga del léxico)")
    comprobar(fallos, j.negados == ["fiebre"], f"negados {j.negados}")
    fragmentos = [(f.tipo, f.texto) for f in i.fragmentos if f.tipo in ("hallazgo", "negado")]
    salida.append(f"Fragmentos reconocidos: {fragmentos}")


def prueba_generacion(motor, salida, fallos) -> None:
    i = motor.interpretar(TEXTO_CACHORRO)
    salida.append(f"Oración generada por resumen//5: «{i.resumen}»")
    comprobar(fallos, i.resumen.startswith("Entendí que se trata de un perro de 4 meses"),
              "la oración debe describir al paciente")
    comprobar(fallos, "no presenta fiebre ni tos" in i.resumen, "debe decir «no presenta fiebre ni tos»")
    raza = motor.interpretar("Mi bulldog estuvo al sol en un carro cerrado y se desmayó")
    salida.append(f"«Mi bulldog…» -> especie={raza.especie} · {raza.hallazgos}")
    comprobar(fallos, raza.especie == "perro", "la raza bulldog revela la especie perro")


def prueba_mediciones(motor, salida, fallos) -> None:
    texto = "Mi gata de 2 años vomitó 5 veces y tiene temperatura de 40,2"
    i = motor.interpretar(texto)
    salida.append(f"Texto: «{texto}» -> mediciones={i.mediciones}")
    comprobar(fallos, ("vomitos_24h", 5.0) in i.mediciones, "debe extraer 5 vómitos")
    comprobar(fallos, ("temperatura", 40.2) in i.mediciones, "debe extraer 40.2 °C")
    d = Discretizador()
    hechos = d.discretizar(dict(i.mediciones), i.especie or "perro")
    for h in hechos:
        salida.append(f"  {h.nombre} {h.valor:g} {h.unidad} -> {h.categoria} -> {h.hallazgo} ({h.metodo})")
    comprobar(fallos, {h.hallazgo for h in hechos} == {"vomito_persistente", "fiebre"},
              f"hechos discretos {[h.hallazgo for h in hechos]}")
    salida.append(f"Cortes aprendidos para la temperatura (gato): {d.umbrales_aprendidos('temperatura', 'gato')}")
    normal = d.clasificar("temperatura", 38.6, "perro")
    comprobar(fallos, normal.hallazgo is None, "38.6 °C es normal: no genera hecho")


def prueba_texto_a_dictamen(motor, salida, fallos) -> None:
    i = motor.interpretar(TEXTO_CACHORRO)
    r = motor.analizar_caso(i.especie, i.edad, "macho", i.hallazgos)
    salida.append(f"?- {r.consulta}.")
    salida.append(f"Dictamen: {[(d.id, d.severidad, d.certeza) for d in r.diagnosticos]} · "
                  f"prioridad {ETIQUETA_NIVEL.get(r.prioridad)}")
    comprobar(fallos, r.ids and r.ids[0] == "parvovirosis", "debe concluir parvovirosis")
    comprobar(fallos, r.prioridad == "critico", "la prioridad debe ser CRÍTICO")


def prueba_entrada_rara(motor, salida, fallos) -> None:
    vacia = motor.interpretar("")
    salida.append(f"Texto vacío -> hallazgos={vacia.hallazgos} · «{vacia.resumen}»")
    comprobar(fallos, vacia.hallazgos == [] and vacia.especie is None, "texto vacío sin hechos")
    rara = motor.interpretar("X') :- halt. % mi perro tiene estornudos raros y tos")
    salida.append(f"Texto con código Prolog -> hallazgos={rara.hallazgos} · desconocidas={rara.desconocidas}")
    comprobar(fallos, rara.hallazgos == ["tos"], "el texto se trata como datos, no como código")
    comprobar(fallos, "estornudos" in rara.desconocidas, "debe informar las palabras que no conoce")


# ---------------------------------------------------------------------------
# Modo Experto
# ---------------------------------------------------------------------------

def prueba_validacion(motor, salida, fallos) -> None:
    ruta = Path(ESTADO["copia"])
    antes = huella(ruta)
    malo = dict(DIAGNOSTICO_NUEVO, id="Lepto Spirosis", nombre="", especies=[], requisitos=[],
                minimo=0, severidad="grave", certeza=5, excluye=["no_existe"])
    r = motor.aprender_diagnostico(malo)
    salida.append(f"?- {r.consulta}.")
    salida += [f"  ✘ {m}" for m in r.mensajes]
    comprobar(fallos, not r.ok, "un diagnóstico inválido no debe aprenderse")
    comprobar(fallos, len(r.mensajes) >= 6, f"debe listar los errores ({len(r.mensajes)})")
    comprobar(fallos, huella(ruta) == antes, "el archivo .pl no debe cambiar")


def prueba_aprender(motor, salida, fallos) -> None:
    ruta = Path(ESTADO["copia"])
    antes = motor.interpretar(TEXTO_LEPTO)
    salida.append(f"Antes de aprender, «ojos amarillos» -> {antes.hallazgos} · no reconocidas {antes.desconocidas}")
    h = motor.aprender_hallazgo(**HALLAZGO_NUEVO)
    salida.append(f"?- {h.consulta}.")
    salida += [f"  {m}" for m in h.mensajes]
    d = motor.aprender_diagnostico(DIAGNOSTICO_NUEVO)
    salida.append(f"?- {d.consulta}.")
    salida += [f"  {m}" for m in d.mensajes]
    comprobar(fallos, h.ok and d.ok, "el hallazgo y el diagnóstico deben aprenderse")
    despues = motor.interpretar(TEXTO_LEPTO)
    salida.append(f"Sin reiniciar, la DCG ya entiende: {despues.hallazgos}")
    comprobar(fallos, "ictericia" in despues.hallazgos, "la DCG debe reconocer «ojos amarillos»")
    r = motor.analizar_caso("perro", 36, "macho", despues.hallazgos)
    salida.append(f"Dictamen en caliente: {[(x.id, x.severidad, x.certeza) for x in r.diagnosticos]}")
    comprobar(fallos, r.ids[:1] == ["leptospirosis"], "debe concluir la regla aprendida")
    e = motor.explicar("perro", 36, "macho", despues.hallazgos)
    reglas = [x.descripcion for x in e[0].reglas] if e else []
    salida.append(f"Traza: {next((x for x in reglas if 'Modo Experto' in x), '—')}")
    comprobar(fallos, any("regla aprendida en Modo Experto" in x for x in reglas),
              "la traza «¿Por qué?» debe mostrar la regla aprendida")
    texto = seccion_13(ruta)
    salida.append("Sección 13 del .pl:")
    salida += [f"  {linea}" for linea in texto.splitlines()]
    comprobar(fallos, "requisito(leptospirosis, [ictericia])." in texto, "la regla debe estar en el .pl")


def prueba_persistencia(motor, salida, fallos) -> None:
    """Reinicio real: un proceso nuevo de Python carga el .pl desde cero."""
    codigo = (
        "import json, sys; sys.path.insert(0, sys.argv[2]);"
        "from motor import MotorTriaVet;"
        "m = MotorTriaVet(sys.argv[1]);"
        "i = m.interpretar(sys.argv[3]);"
        "r = m.analizar_caso('perro', 36, 'macho', i.hallazgos);"
        "d, h, e = m.conocimiento_aprendido();"
        "print(json.dumps({'aprendidos': [x.id for x in d], 'hallazgos': i.hallazgos,"
        " 'dictamen': r.ids}))"
    )
    proceso = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", codigo, str(ESTADO["copia"]), str(PROYECTO), TEXTO_LEPTO],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    linea = next((l for l in proceso.stdout.splitlines() if l.startswith("{")), "{}")
    datos = json.loads(linea)
    salida.append(f"Proceso nuevo (PID distinto) cargó la copia del .pl y respondió: {datos}")
    comprobar(fallos, datos.get("aprendidos") == ["leptospirosis"], "tras reiniciar debe seguir aprendida")
    comprobar(fallos, "ictericia" in datos.get("hallazgos", []), "tras reiniciar la DCG debe reconocerla")
    comprobar(fallos, datos.get("dictamen", [])[:1] == ["leptospirosis"], "tras reiniciar debe concluirla")
    motor.recargar()
    diags, _, _ = motor.conocimiento_aprendido()
    salida.append(f"Recarga (consult/1) en este proceso: aprendidos={[x.id for x in diags]} "
                  "(sin duplicados)")
    comprobar(fallos, [x.id for x in diags] == ["leptospirosis"], "la recarga no debe duplicar")


def prueba_olvidar(motor, salida, fallos) -> None:
    ruta = Path(ESTADO["copia"])
    bloqueado = motor.olvidar("hallazgo", "ictericia")
    salida.append(f"Olvidar ictericia mientras la usa la leptospirosis -> {bloqueado.mensajes}")
    comprobar(fallos, not bloqueado.ok, "no se puede olvidar un hallazgo en uso")
    for tipo, id_ in [("diagnostico", "leptospirosis"), ("hallazgo", "ictericia")]:
        r = motor.olvidar(tipo, id_)
        salida.append(f"?- {r.consulta}. -> {r.mensajes}")
        comprobar(fallos, r.ok, f"debe olvidar {id_}")
    original = motor.olvidar("diagnostico", "parvovirosis")
    salida.append(f"Olvidar un diagnóstico original -> {original.mensajes}")
    comprobar(fallos, not original.ok, "el conocimiento original no se puede olvidar")
    comprobar(fallos, huella(ruta) == ESTADO["huella_original"],
              "el .pl debe volver a ser idéntico al original")
    salida.append(f"Huella del .pl: {huella(ruta)} (original {ESTADO['huella_original']})")


PRUEBAS = [
    Prueba("1", "DCG: extracción de hechos del texto libre",
           "La gramática extrae especie, edad y hallazgos de una oración del tutor.", prueba_extraccion),
    Prueba("2", "DCG: negaciones y expresiones más largas",
           "«no tiene fiebre ni tos» niega; «no come» y «no orina» son hallazgos.", prueba_negacion),
    Prueba("3", "DCG en sentido inverso: oración de confirmación",
           "resumen//5 genera el texto a partir de los hechos (comunicación bidireccional).",
           prueba_generacion),
    Prueba("4", "Mediciones y preprocesamiento numérico",
           "La DCG extrae números y el clasificador los convierte en hechos discretos.", prueba_mediciones),
    Prueba("5", "Del texto al dictamen",
           "El texto libre alimenta analizar_caso/10 sin formulario.", prueba_texto_a_dictamen),
    Prueba("6", "Entradas vacías, extrañas o con código",
           "El texto viaja como dato y las palabras desconocidas se informan.", prueba_entrada_rara),
    Prueba("7", "Modo Experto: validación en Prolog",
           "Un diagnóstico mal definido se rechaza con sus motivos y el .pl no cambia.", prueba_validacion),
    Prueba("8", "Modo Experto: aprendizaje en caliente (assertz/1 + .pl)",
           "El hallazgo y el diagnóstico nuevos se usan de inmediato y quedan escritos en el .pl.",
           prueba_aprender),
    Prueba("9", "Persistencia tras reiniciar",
           "Un proceso nuevo carga el .pl y conserva la regla aprendida.", prueba_persistencia),
    Prueba("10", "Olvidar lo aprendido (retract/1 + .pl)",
           "Se retira lo aprendido y el archivo vuelve a su estado original.", prueba_olvidar),
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
    print(f"PRUEBA E3-{prueba.numero} · {prueba.titulo}")
    print("─" * ANCHO)
    print(f"Objetivo : {prueba.objetivo}")
    salida: list[str] = []
    fallos: list[str] = []
    try:
        prueba.ejecutar(motor, salida, fallos)
    except Exception as exc:  # una prueba que lanza una excepción falla
        fallos.append(f"excepción: {exc!r}")
    for linea in salida:
        print(f"  {linea}")
    print("Veredicto: " + ("✘ FALLÓ" if fallos else "✔ PASÓ"))
    for f in fallos:
        print(f"           - {f}")
    print()
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
    resultados: list[tuple[Prueba, bool]] = []

    carpeta = Path(tempfile.mkdtemp(prefix="triavet_"))
    copia = carpeta / "base_conocimiento.pl"
    # La copia empieza con la Sección 13 vacía: las pruebas no dependen de lo
    # que un experto ya haya enseñado en el archivo del proyecto.
    marca = "%% >>> CONOCIMIENTO APRENDIDO EN CALIENTE >>>"
    original = (PROYECTO / "base_conocimiento.pl").read_text(encoding="utf-8")
    copia.write_text(original.split(marca, 1)[0] + marca + "\n", encoding="utf-8", newline="\n")
    ESTADO.update(copia=copia, huella_original=huella(copia))

    with open(ruta, "w", encoding="utf-8") as archivo:
        consola = sys.stdout
        sys.stdout = Tee(consola, archivo)
        try:
            print("=" * ANCHO)
            print(" TriaVet · Pruebas del Entregable 3 (DCG y aprendizaje en caliente)")
            print(f" Ejecutado: {datetime.now():%Y-%m-%d %H:%M:%S}")
            print("=" * ANCHO)
            motor = MotorTriaVet(copia)
            print(f"Copia de trabajo de la base: {copia}")
            print(f"Huella inicial del .pl: {ESTADO['huella_original']}\n")
            resultados = [(p, ejecutar(p, motor)) for p in pruebas]
            aprobadas = sum(ok for _, ok in resultados)
            print("=" * ANCHO)
            print(" RESUMEN")
            print("=" * ANCHO)
            for p, ok in resultados:
                print(f" {'✔' if ok else '✘'} Prueba E3-{p.numero} · {p.titulo}")
            print(f"\n {aprobadas} de {len(resultados)} pruebas aprobadas.")
        finally:
            sys.stdout = consola
            shutil.rmtree(carpeta, ignore_errors=True)

    print(f"Evidencia guardada en: {ruta}")
    return 0 if all(ok for _, ok in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
