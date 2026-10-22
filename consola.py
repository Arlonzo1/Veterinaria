"""
consola.py - Consola interactiva de TriaVet (Entregable 1).

Uso:
    python consola.py

La interfaz gráfica con el módulo de auditoría del Entregable 2 está en
main.py (streamlit run main.py).

Pide los datos del paciente y los hallazgos observados, los envía a Prolog
(analizar_caso/10) y muestra el resultado. Toda la validación y la
inferencia ocurren en base_conocimiento.pl; este archivo solo lee del
teclado e imprime.
"""

from __future__ import annotations

import sys

from motor import ErrorMotor, MotorTriaVet, formatear_resultado, legible

AVISO = (
    "Aviso: TriaVet es una herramienta académica de orientación. "
    "No reemplaza la valoración de un médico veterinario."
)


def leer(mensaje: str) -> str:
    """input() que trata Ctrl+Z / Ctrl+D como salida limpia."""
    try:
        return input(mensaje).strip()
    except EOFError:
        print()
        raise SystemExit(0)


def mostrar_catalogo(catalogo) -> list[str]:
    """Imprime el menú numerado de hallazgos y devuelve la lista en ese orden."""
    numerados: list[str] = []
    for _, nombre_grupo, hallazgos in catalogo:
        print(f"\n  {nombre_grupo}")
        for hallazgo in hallazgos:
            numerados.append(hallazgo)
            print(f"    {len(numerados):>2}. {legible(hallazgo)}")
    return numerados


def interpretar_seleccion(texto: str, numerados: list[str]) -> list[str]:
    """Traduce '1, 5, fiebre' a nombres de hallazgos.

    Un número del menú se reemplaza por su hallazgo; cualquier otro texto se
    envía tal cual y Prolog decide si es válido (si no, lo reporta como
    ignorado).
    """
    seleccion = []
    for token in (t.strip() for t in texto.split(",")):
        if not token:
            continue
        if token.isdigit() and 1 <= int(token) <= len(numerados):
            seleccion.append(numerados[int(token) - 1])
        else:
            seleccion.append(token)
    return seleccion


def evaluar_caso(motor: MotorTriaVet, numerados: list[str]) -> None:
    print("\n--- Datos del paciente ---")
    especie = leer("Especie (perro/gato): ")
    edad = leer("Edad en meses: ")
    sexo = leer("Sexo (macho/hembra): ")

    print("\n--- Hallazgos observados ---")
    print("Escriba los números del menú o los nombres, separados por comas.")
    print("Deje la línea vacía si no observó ningún signo.")
    hallazgos = interpretar_seleccion(leer("> "), numerados)

    resultado = motor.analizar_caso(especie, edad, sexo, hallazgos)
    print("\n=== Resultado de TriaVet ===")
    print(formatear_resultado(resultado))
    print(f"\n{AVISO}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 72)
    print(" TriaVet - Sistema experto de triage para urgencias en perros y gatos")
    print("=" * 72)
    try:
        motor = MotorTriaVet()
    except ErrorMotor as exc:
        print(f"Error: {exc}")
        return 1

    print("\nHallazgos que reconoce la base de conocimiento:")
    numerados = mostrar_catalogo(motor.catalogo())

    while True:
        try:
            evaluar_caso(motor, numerados)
        except ErrorMotor as exc:
            print(f"\nError al consultar el motor de inferencia: {exc}")
        if leer("\n¿Evaluar otro caso? (s/n): ").lower() not in ("s", "si", "sí"):
            print("Hasta luego.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
