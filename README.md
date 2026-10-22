# TriaVet — Sistema experto auditable de triage para urgencias en perros y gatos

TriaVet es un sistema experto basado en reglas. La base de conocimiento y todo el razonamiento están en **SWI-Prolog**. La interfaz web está en **Python** con **Streamlit** y se conecta a Prolog mediante **PySwip**. A partir de la especie, la edad, el sexo y los hallazgos que observa el tutor, el sistema:

- infiere los diagnósticos presuntivos de urgencia y descarta los que no aplican;
- asigna a cada uno una severidad y una certeza, y calcula la prioridad del caso;
- **explica su razonamiento** («caja blanca»): muestra el árbol de reglas disparadas, los hechos comprobados y por qué se descartó cada hipótesis alternativa (módulo **«¿Por qué?»**);
- **orienta cuando la evidencia no alcanza**: indica qué hipótesis compiten y qué síntoma, prueba o antecedente conviene preguntar para confirmar o desempatar (módulo **«¿Qué falta?»**).

> Herramienta académica de orientación. No reemplaza la valoración de un médico veterinario.

## Instalación

1. Instale [SWI-Prolog](https://www.swi-prolog.org/download/stable) 9.x o 10.x. En Windows, marque la opción de agregarlo al `PATH`.
2. Instale Python 3.10 o superior.
3. Instale las dependencias de Python:

```bash
pip install -r requirements.txt
```

`requirements.txt` contiene `pyswip` y `streamlit`, es decir, equivale a `pip install pyswip streamlit`.

## Ejecución

**Interfaz web (Entregable 2):**

```bash
streamlit run main.py
```

`python main.py` hace lo mismo: se relanza con Streamlit. Se abre en `http://localhost:8501`.

En la barra lateral se eligen los datos del paciente y los hallazgos. También se puede cargar un **caso de demostración**. La página tiene cuatro pestañas:

| Pestaña | Qué muestra | Predicados de Prolog |
|---|---|---|
| 🩺 Dictamen | Prioridad, diagnósticos, severidad, certeza e indicaciones. | `analizar_caso/10` |
| 🔍 ¿Por qué? | Árbol de inferencia, reglas disparadas, hechos comprobados, cálculo de severidad y certeza, e hipótesis descartadas con su árbol de refutación. | `explicar_caso/5`, `hipotesis_descartadas/5` |
| 🧭 ¿Qué falta? | Estado de la evidencia, hipótesis en competencia, pregunta de mayor peso con los botones «Sí, lo presenta» y «No lo presenta», y el ranking completo. | `que_falta/8`, `pregunta_desempate/6` |
| 🧾 Consultas Prolog | Texto exacto de cada consulta que Python envió a Prolog. | — |

Los parámetros de la URL abren directamente un caso y una pestaña, por ejemplo `http://localhost:8501/?caso=1&panel=porque` o `?caso=2&panel=quefalta`. Valores de `caso`: `1`, `2`, `2b`, `2c`, `extra`. Valores de `panel`: `dictamen`, `porque`, `quefalta`, `consultas`.

**Otras formas de ejecutar:**

```bash
python consola.py                  # consola interactiva del Entregable 1
python pruebas.py                  # 10 pruebas del Entregable 1 → evidencia/salida_pruebas.txt
python pruebas_explicabilidad.py   # 10 pruebas del Entregable 2 → evidencia/entregable2/salida_pruebas.txt
swipl base_conocimiento.pl         # consultas directas en Prolog
```

```prolog
?- pregunta_desempate(gato, 36, macho, [esfuerzo_para_orinar, vocalizacion_dolor], [], P).
```

En Visual Studio Code, **Terminal > Run Task…** ofrece las tareas `TriaVet: …`, entre ellas la interfaz web y las pruebas del Entregable 2.

## Casos de demostración

| Caso | Paciente y hallazgos | Qué se observa |
|---|---|---|
| **1 · Inferencia completa** | Perro de 4 meses, macho: vómito, diarrea con sangre, decaimiento, no come y vacunación incompleta | Parvovirosis, **CRÍTICO** (base ALTO + cachorro), certeza 95 %. Árbol con reglas de los niveles 3, 2 y 1, y dos negaciones por fallo. Siete hipótesis descartadas: gastroenteritis (excluida por la parvovirosis), enfermedad renal crónica (`\+` cachorro), obstrucción uretral (solo gatos) y otras por falta de evidencia crítica. |
| **2 · Desempate** | Gato de 36 meses, macho: esfuerzo para orinar y se queja de dolor | Cistitis con certeza de 75 %, por debajo del umbral de 80 %: **se activa «¿Qué falta?»**. Compite con la obstrucción uretral (parcial, CRÍTICA). Pregunta de mayor peso: «¿Al intentar orinar no sale orina…?». Si la respuesta es «sí», se concluye la obstrucción, se descarta la cistitis y la prioridad pasa de MEDIO a CRÍTICO. |
| **2b · Evidencia insuficiente** | Perro de 48 meses, hembra: decaimiento y no come | Ningún perfil se completa. Siete hipótesis parcialmente activas; la primera pregunta es el vómito persistente. |
| **2c · Empate** | Perro de 48 meses, macho: exposición al calor, jadeo, decaimiento e ingesta de xilitol | Golpe de calor e intoxicación empatan (CRÍTICO, 75 %). Solo se ponderan las dos hipótesis empatadas y se sugieren signos que separan una de la otra. |
| **extra** | Dilatación-torsión gástrica (caso 1 del Entregable 1) | Encadenamiento de tres niveles con abdomen agudo. |

En [`docs/guion_demo.md`](docs/guion_demo.md) hay un guion para el video de 3 a 5 minutos.

## Arquitectura híbrida

```
┌──────────────────────── Python (capa imperativa) ────────────────────────┐
│ main.py    interfaz Streamlit: captura y limpia entradas, dibuja         │
│            resultados (el árbol se convierte a Graphviz)                 │
│ motor.py   puente PySwip: arma las consultas, las ejecuta en un único    │
│            hilo de Prolog y convierte las listas de Prolog en objetos    │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ consultas con átomos entre comillas
┌────────────────────────────────▼──────── Prolog (capa simbólica) ────────┐
│ base_conocimiento.pl                                                     │
│  Secc. 1-7  hechos, reglas de 3 niveles, severidad, recolección (E1)     │
│  Secc. 8    «¿Por qué?»: metaintérpretes de demostración y refutación    │
│  Secc. 9    «¿Qué falta?»: competencia, ponderación y simulación         │
│  Secc. 10   API: explicar_caso/5, hipotesis_descartadas/5, que_falta/8,  │
│             pregunta_desempate/6                                         │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Python no razona.** No valida hallazgos, no descarta diagnósticos ni calcula pesos. Solo arma consultas, convierte las respuestas y las dibuja. Su limpieza de entradas se limita a quitar tildes, espacios y separadores.
- **Prolog no lee del teclado.** No se usa `read/1`: toda entrada llega como argumento de una consulta. `entrada_segura/4` la verifica con `ground/1` y exige átomos en minúscula antes de razonar, así una variable libre enviada desde Python no puede unificar con cualquier hecho.
- **La traza no se escribe a mano.** Un metaintérprete (`demostrar/3`) vuelve a probar cada conclusión con las mismas cláusulas de la base (`clause/2`) y respeta sus cortes. Por eso la explicación coincide exactamente con el razonamiento.

### Módulo «¿Por qué?»

- **Reglas disparadas:** árbol (Graphviz y texto) y tabla de las reglas de los niveles 3, 2 y 1 que se cumplieron.
- **Hechos comprobados como verdaderos:** hallazgos que unificaron durante la demostración y datos del paciente validados.
- **Hipótesis alternativas descartadas:** un segundo metaintérprete (`refutar/3`) explica por qué falló la regla `candidato/2` de cada hipótesis que comparte hallazgos con el caso. Clasifica el motivo como **exclusión** por un diagnóstico dominante, **condición excluyente** (`\+`), **dato del paciente** (especie, sexo o edad) o **falta de evidencia crítica**.

### Módulo «¿Qué falta?»

1. `estado_evidencia/3` decide si el dictamen es definitivo o si hay **evidencia insuficiente**, **empate** (misma severidad y certezas a no más de 5 puntos) o **certeza baja** (menos de 80 %). En esos tres casos se activa el módulo.
2. `hipotesis_en_competencia/3` reúne las hipótesis confirmadas y las **parcialmente activas**: comparten hallazgos y su fallo se corrige agregando hallazgos. Para cada una calcula su activación y lo que le falta.
3. `sugerencias/5` pondera cada hallazgo no ingresado:
   **peso = Σ peso_rol × gravedad × activación / 100**, con `peso_rol` de 3 (obligatorio), 2 (falta para el mínimo de apoyo) o 1 (refuerzo). El peso se multiplica por 3 si la pregunta favorece a una sola hipótesis, es decir, si **desempata**. En un empate solo se ponderan las dos hipótesis empatadas.
4. `efecto/3` **simula** la respuesta «sí»: vuelve a inferir el caso y dice qué se concluiría o descartaría y cómo cambiarían la certeza y la prioridad.
5. Las respuestas «no» se envían como `Negados`. Prolog deja de sugerirlas y refuta las hipótesis que las necesitaban.

## Estructura

```
.
├── base_conocimiento.pl          Hechos y reglas (toda la lógica, Secciones 1 a 10)
├── motor.py                      Puente Python ↔ Prolog (PySwip)
├── main.py                       Interfaz web Streamlit (Entregable 2)
├── consola.py                    Consola interactiva (Entregable 1)
├── pruebas.py                    Pruebas del Entregable 1
├── pruebas_explicabilidad.py     Pruebas del Entregable 2
├── requirements.txt
├── .streamlit/config.toml        Tema y opciones de Streamlit
├── .vscode/tasks.json            Tareas para ejecutar desde VS Code
├── evidencia/
│   ├── salida_pruebas.txt        Pruebas del Entregable 1
│   ├── capturas/                 Capturas del Entregable 1
│   └── entregable2/
│       ├── salida_pruebas.txt    Pruebas del Entregable 2
│       └── capturas/             Capturas de la interfaz
└── docs/
    ├── ficha_proyecto.md         Ficha del proyecto (Entregable 1)
    ├── diccionario_predicados.md Diccionario de predicados (actualizado: secciones 10 a 14)
    └── guion_demo.md             Guion del video de demostración
```

## Roles en la pareja (Entregable 2)

| Rol | Responsabilidad | Dónde está |
|---|---|---|
| **Integrante A** · Ingeniería del conocimiento y motor simbólico | Predicados de traza, hipótesis descartadas y reglas de desempate | `base_conocimiento.pl`, Secciones 8, 9 y 10, más `entrada_segura/4` y `diferencia/3` |
| **Integrante B** · Integración y explicabilidad | Puente PySwip, interfaz y visualización de la auditoría | `motor.py`, `main.py`, `pruebas_explicabilidad.py` |

## Matriz de cumplimiento del Entregable 2

| Requisito | Dónde se cumple |
|---|---|
| **3.1** Interfaz funcional conectada en tiempo real con PySwip | `main.py` (Streamlit). Cada interacción consulta `base_conocimiento.pl` a través de `motor.py`. |
| **3.1** Python solo para la interfaz, la captura y limpieza de entradas y la presentación | `main.py` no contiene reglas: arma consultas y dibuja. La pestaña «Consultas Prolog» muestra cada consulta enviada. |
| **3.1** Sin `read/1` en Prolog | Ningún predicado lee del teclado; las entradas son argumentos de consulta. |
| **3.1** Validación de entradas (`ground/1`, átomos en minúscula) | `entrada_segura/4`, `atomo_minuscula/1` y `atomos_seguros/2`, usados por `preparar_caso/6`. La prueba E2-10 lo verifica. |
| **3.2** Reglas disparadas (listado o árbol) | `demostrar/3` y `reglas_disparadas/3`. En la interfaz: árbol Graphviz, traza textual y tabla. |
| **3.2** Hechos comprobados como verdaderos | `hechos_verificados/2` y `datos_del_paciente/2`. |
| **3.2** Hipótesis alternativas descartadas (falta de evidencia o condición `\+`) | `hipotesis_descartadas/5`, `refutar/3`, `analizar_hipotesis/3` y `motivo_descarte/5`. |
| **3.3** No limitarse a «diagnóstico desconocido» | `estado_evidencia/3` y `describir_estado/4` activan el módulo en los estados insuficiente, empate y certeza baja. |
| **3.3** Predicado de desempate en Prolog | `pregunta_desempate/6` y `que_falta/8` (ponderación en `sugerencias/5` y `ponderar/6`). |
| **4.1** `main.py`, `base_conocimiento.pl`, `README.md` | Este repositorio. |
| **4.2** Diccionario de predicados actualizado | `docs/diccionario_predicados.md`, secciones 10 a 14. |
| **4.3** Demostración (Casos 1 y 2) | Casos precargados en la interfaz y guion en `docs/guion_demo.md`. |

## Entregable 1 (resumen)

| Requisito | Dónde se cumple |
|---|---|
| Hechos estructurados y reglas encadenadas en tres niveles | `base_conocimiento.pl`, Secciones 1 a 5 (224 hechos de dominio y 98 cláusulas de reglas en el Entregable 1). |
| Listas, corte y negación por fallo | Secciones 2 a 6; detalle en el diccionario, secciones 2 a 8. |
| Recolección sin duplicados y severidad | `conclusiones/2`, `diagnosticar_todos/5`, `severidad/3` y `prioridad_caso/3`. |
| Integración por consola | `consola.py` y `pruebas.py` (10 casos; evidencia en `evidencia/salida_pruebas.txt`). |
