# Guion de la demostración — Entregable 3 (4 a 6 minutos)

Este video es la **prueba de persistencia** que pide el entregable: se crea una regla en caliente y se demuestra que la base de conocimiento la conserva después de reiniciar la aplicación.

**Preparación**

1. Abra `base_conocimiento.pl` en VS Code y ubíquese al final, en la línea `%% >>> CONOCIMIENTO APRENDIDO EN CALIENTE >>>` (Sección 13).
2. Si la Sección 13 ya tiene la leptospirosis de una prueba anterior, olvídela antes de grabar. Use el Modo experto › «📚 Lo aprendido y su persistencia» › 🗑️, primero el diagnóstico y luego el hallazgo.
3. Ejecute `streamlit run main.py` en una terminal visible y abra `http://localhost:8501`.

| Tiempo | Acción en la interfaz | Qué decir |
|---|---|---|
| 0:00–1:00 | **Consulta:** escribir «Mi perrito de 4 meses vomita mucho, tiene diarrea con sangre y está muy decaído. No tiene fiebre ni tos. Nunca lo vacunaron.» y pulsar **Interpretar y analizar**. | El sistema ya no depende de casillas. El texto viaja a Prolog y la gramática DCG (`descripcion//1`) lo analiza. En verde están los hallazgos, en gris tachado lo que el tutor niega y en violeta los datos del paciente. La oración de abajo la genera otra DCG, `resumen//5`, a partir de los hechos: es el camino inverso. Con esos hechos el motor concluye parvovirosis CRÍTICA. |
| 1:00–1:30 | Abrir **📏 Mediciones**, escribir 40.2 °C en temperatura. | (Opcional híbrido) Un árbol de decisión de scikit-learn convierte la medición continua en el hecho discreto `fiebre` antes de enviarlo a Prolog. |
| 1:30–1:50 | Escribir «Mi perro de 3 años tiene los ojos amarillos, fiebre y está decaído.» y analizar. | «Ojos amarillos» aparece en amarillo: la base no lo conoce todavía. |
| 1:50–3:30 | **Barra lateral:** rol Experto, clave `experto2026`, escribir el nombre. **🧠 Modo experto › Nuevo hallazgo:** «Piel u ojos amarillos (ictericia)», identificador `ictericia`, grupo Estado general, una pregunta y las expresiones `ojos amarillos; piel amarilla; amarill*`. Pulsar **Aprender hallazgo**. **Nuevo diagnóstico:** «Leptospirosis», obligatorio *ictericia*; apoyo *fiebre, decaimiento, no come, vómito*; mínimo 1; severidad ALTO; indicación. Mostrar la **vista previa** y pulsar **Aprender diagnóstico**. | El panel solo aparece con el rol Experto. Prolog valida lo que se enseña (pruebe dejar el nombre vacío: el botón se bloquea y aparecen los motivos). Al aprender, las cláusulas entran a la memoria con `assertz/1` a través de PySwip y `persistir_conocimiento/0` las escribe en la Sección 13 del `.pl`. |
| 3:30–3:50 | Cambiar a **VS Code**: la Sección 13 de `base_conocimiento.pl` ya tiene las cláusulas nuevas. | Este es el archivo modificado: el aprendizaje quedó escrito con sintaxis Prolog. |
| 3:50–4:30 | **Reinicio real:** en la terminal, `Ctrl+C` para detener Streamlit y volver a ejecutar `streamlit run main.py`. Recargar la página como **Tutor** y escribir otra vez «Mi perro de 3 años tiene los ojos amarillos, fiebre y está decaído.» | Es un proceso nuevo: SWI-Prolog empieza vacío y vuelve a leer el `.pl`. Ahora «ojos amarillos» aparece en verde y el sistema concluye **Leptospirosis**. El conocimiento sobrevivió al reinicio. |
| 4:30–5:00 | Pestaña **🔍 ¿Por qué?**. | El árbol muestra «regla aprendida en Modo Experto (autor)»: la regla nueva se audita igual que las originales. |
| 5:00–5:30 | (Opcional) **📚 Lo aprendido y su persistencia**: comparar «En memoria» con «En el archivo» y pulsar **Simular reinicio**. Luego **🗑️ Olvidar**. | `olvidar/4` usa `retract/1` y vuelve a escribir el archivo; el conocimiento original no se puede olvidar. |

**Respaldo sin video:** `python pruebas_entregable3.py` ejecuta la misma secuencia de forma automática. En la prueba E3-9, un proceso nuevo de Python carga el `.pl` y concluye la regla aprendida. La salida queda en `evidencia/entregable3/salida_pruebas.txt`.
