# TriaVet — Sistema experto de triage para urgencias en perros y gatos

TriaVet es un sistema experto basado en reglas. La base de conocimiento y todo el razonamiento están en **SWI-Prolog**. La interfaz web está en **Python** con **Streamlit** y se conecta a Prolog mediante **PySwip**. El tutor describe con sus palabras lo que le pasa a su mascota y el sistema:

- **entiende el texto libre** con una gramática DCG en Prolog y extrae los hechos: especie, edad, sexo, hallazgos, negaciones y mediciones (Entregable 3);
- infiere los diagnósticos presuntivos, descarta los que no aplican y calcula la severidad, la certeza y la prioridad del caso;
- **explica su razonamiento** («caja blanca»): árbol de reglas disparadas, hechos comprobados e hipótesis descartadas (módulo **«¿Por qué?»**, Entregable 2);
- **orienta cuando la evidencia no alcanza**: qué hipótesis compiten y qué conviene preguntar (módulo **«¿Qué falta?»**, Entregable 2);
- **aprende en caliente**: un usuario con rol **Experto** enseña diagnósticos, hallazgos y expresiones nuevas desde la interfaz; entran a la memoria con `assertz/1` y se escriben en `base_conocimiento.pl`, así que sobreviven a los reinicios (Entregable 3).

> Herramienta académica de orientación. No reemplaza la valoración de un médico veterinario.

## Instalación

1. Instale [SWI-Prolog](https://www.swi-prolog.org/download/stable) 9.x o 10.x. En Windows, marque la opción de agregarlo al `PATH`.
2. Instale Python 3.10 o superior.
3. Instale las dependencias de Python:

```bash
pip install -r requirements.txt
```

`requirements.txt` equivale a `pip install pyswip streamlit scikit-learn`. scikit-learn solo lo usa el preprocesamiento numérico opcional; si no está instalado, el sistema aplica los mismos umbrales clínicos sin el árbol de decisión.

## Ejecución

```bash
streamlit run main.py
```

`python main.py` hace lo mismo. Se abre en `http://localhost:8501`. En VS Code, **Terminal > Run Task…** ofrece las tareas `TriaVet: …`.

| Pestaña | Qué muestra | Predicados de Prolog |
|---|---|---|
| 🐾 Consulta | Cuadro de texto libre, lo que entendió la DCG (texto resaltado y oración de confirmación), mediciones opcionales, prioridad y diagnósticos. | `interpretar_texto/10`, `analizar_caso/10` |
| 🔍 ¿Por qué? | Árbol de inferencia, reglas disparadas, hechos comprobados, cálculo de severidad y certeza, e hipótesis descartadas. | `explicar_caso/5`, `hipotesis_descartadas/5` |
| 🧭 ¿Qué falta? | Estado de la evidencia, hipótesis en competencia y la pregunta de mayor peso con botones «Sí» y «No». | `que_falta/8`, `pregunta_desempate/6` |
| 🧠 Modo experto | Formularios para enseñar diagnósticos, hallazgos y expresiones; lo aprendido; comparación memoria ↔ archivo y recarga del `.pl`. | `vista_previa_diagnostico/3`, `aprender_diagnostico/3`, `aprender_hallazgo/3`, `aprender_expresion/5`, `olvidar/4`, `conocimiento_aprendido/3`, `texto_aprendido/1` |
| 🧾 Consultas Prolog | Texto exacto de cada consulta que Python envió a Prolog. | — |

**Rol Experto.** En la barra lateral elija «Experto» e ingrese la clave. La clave por defecto es `experto2026`; cámbiela con la variable de entorno `TRIAVET_CLAVE_EXPERTO` antes de iniciar la aplicación.

**Atajos de URL:** `?caso=1` (también `2`, `2b`, `2c`, `extra` y `3`) carga un ejemplo; `?panel=porque`, `quefalta`, `experto` o `consultas` abre una pestaña.

**Otras formas de ejecutar:**

```bash
python pruebas_entregable3.py      # 10 pruebas del Entregable 3 → evidencia/entregable3/salida_pruebas.txt
python pruebas_explicabilidad.py   # 10 pruebas del Entregable 2
python pruebas.py                  # 10 pruebas del Entregable 1
python consola.py                  # consola del Entregable 1
python preprocesamiento.py         # cortes que aprende el clasificador numérico
swipl base_conocimiento.pl         # consultas directas en Prolog
```

```prolog
?- interpretar_texto('mi perrita de 4 meses vomita mucho y no tiene fiebre',
                     E, Edad, S, Hallazgos, Negados, M, D, F, Resumen).
E = perro, Edad = 4, S = hembra, Hallazgos = [vomito_persistente], Negados = [fiebre],
Resumen = 'Entendí que se trata de un perro hembra de 4 meses que presenta vómito persistente, y que no presenta fiebre.'
```

## Entregable 3: lenguaje natural y aprendizaje en caliente

### Entrada en lenguaje natural con DCG (Sección 11 del `.pl`)

1. `texto_a_palabras/2` normaliza el texto en Prolog: minúsculas, sin tildes ni signos, y los números quedan como números.
2. La gramática `descripcion//1` recorre las palabras y reconoce fragmentos:
   - **hallazgos:** «vomita mucho», «diarrea con sangre»;
   - **negaciones:** «no tiene fiebre ni tos», «sin vómito»;
   - **paciente:** «mi perrita», «el gato»; la raza también revela la especie («mi bulldog»);
   - **sexo** y **edad:** «de 4 meses», «dos años»;
   - **mediciones:** «temperatura de 40.2», «vomitó 5 veces».

   Las palabras que no conoce se informan.
3. `expresion_larga//1` elige la expresión **más larga** del léxico, por eso «no come» se entiende como anorexia y no como la negación de «come».
4. El léxico es declarativo (`expresion/2`, unas 300 expresiones). Una palabra terminada en `*` es una raíz: «vomit*» reconoce vomita, vomitó, vomitando…
5. **Comunicación bidireccional:** Python envía el texto y recibe los hechos (`interpretar_texto/10`). Otra DCG, `resumen//5`, hace el camino inverso y **genera** la oración con la que el sistema confirma lo que entendió. La interfaz además resalta en colores cada fragmento reconocido.

### Adquisición dinámica de conocimiento — Modo Experto (Sección 12)

- **Nuevo diagnóstico:** nombre, especies, curso, hallazgos obligatorios, hallazgos de apoyo y mínimo, severidad, certeza base, indicación y exclusiones. La interfaz muestra una **vista previa** de las cláusulas exactas que se van a escribir (`vista_previa_diagnostico/3`).
- **Nuevo hallazgo:** signo o antecedente que la base no conocía, con su pregunta para «¿Qué falta?» y las expresiones con que la DCG lo reconocerá.
- **Enseñar una expresión:** sinónimo para un hallazgo existente.

Cada uno sigue los mismos pasos:

1. **Prolog valida:** identificador nuevo y en minúscula, hallazgos existentes, perfil que exija evidencia, severidad y certeza válidas. Con errores no se toca nada.
2. Las cláusulas entran a la memoria con **`assertz/1`**. El diagnóstico aprendido no necesita una regla propia: la cláusula genérica `candidato(Caso, D) :- diagnostico_aprendido(D, _, _), cumple_perfil(Caso, D)` lo concluye. «¿Por qué?» y «¿Qué falta?» lo tratan igual que a los originales porque leen los mismos hechos.
3. **`persistir_conocimiento/0` reescribe la Sección 13 de `base_conocimiento.pl`** con `portray_clause/2`, bajo la línea marca `%% >>> CONOCIMIENTO APRENDIDO EN CALIENTE >>>`. Antes guarda una copia en `base_conocimiento.pl.bak`.

**Persistencia:** al reiniciar la aplicación, `consult/1` vuelve a cargar el archivo completo, con la Sección 13, y lo aprendido sigue disponible. En el panel, «Simular reinicio» recarga el `.pl` y compara lo que hay en memoria con lo que está escrito en el archivo. `olvidar/4` retira lo aprendido con `retract/1` y vuelve a escribir el archivo. El conocimiento original no se puede olvidar.

**Evidencia en el `.pl` entregado.** El archivo conserva lo que se enseñó desde la interfaz:

- el hallazgo `ictericia`, con sus expresiones «ojos amarillos», «piel amarilla» y «amarill*»;
- el diagnóstico `leptospirosis`.

El caso de ejemplo `?caso=3` los usa. Para repetir la demostración desde cero, olvídelos en «📚 Lo aprendido y su persistencia».

### Preprocesamiento numérico (opcional, `preprocesamiento.py`)

Convierte mediciones continuas en hechos discretos antes de enviarlas a Prolog. Para cada variable se entrena un **árbol de decisión de scikit-learn** con valores de referencia etiquetados por especie; el árbol aprende los puntos de corte:

| Variable | Categorías → hecho de Prolog |
|---|---|
| Temperatura rectal (°C) | hipotermia → `hipotermia` · normal · fiebre → `fiebre` |
| Llenado capilar (s) | normal · lento → `llenado_capilar_lento` |
| Vómitos en 24 h | ninguno · ocasional → `vomito` · persistente → `vomito_persistente` |
| Días sin defecar | normal · retenido → `sin_defecar` |
| Pérdida de peso (%) | estable · pérdida → `perdida_de_peso` |

Las mediciones se escriben en la interfaz o se dicen en el texto: la DCG las extrae («temperatura de 40,2») y Python las clasifica. Una medición objetiva prevalece sobre una negación del texto.

## Matriz de cumplimiento del Entregable 3

| Requisito | Dónde se cumple |
|---|---|
| DCG que analiza la oración del usuario y extrae hechos simbólicos | `base_conocimiento.pl`, Sección 11: `descripcion//1`, `fragmento//2`, `negacion//1`, `edad//1`, `medicion//2`, `expresion_larga//1` e `interpretar_texto/10`. Pruebas E3-1, E3-2 y E3-6. |
| Comunicación bidireccional DCG ↔ Python | Python → Prolog: el texto (`MotorTriaVet.interpretar`). Prolog → Python: hechos, fragmentos y la oración generada por `resumen//5`. Prueba E3-3. |
| Los hechos alimentan al motor de inferencia | La pestaña Consulta envía lo interpretado a `analizar_caso/10` y a los módulos del Entregable 2. Prueba E3-5. |
| Panel «Modo Experto» exclusivo del rol Experto, integrado en la interfaz principal | Pestaña 🧠 Modo experto de `main.py` (clave en la barra lateral). |
| Inyección con `assertz/1` a través de PySwip | `aprender_diagnostico/3`, `aprender_hallazgo/3` y `aprender_expresion/5`, invocados por `motor.py`. Prueba E3-8. |
| Escritura persistente en el `.pl` | `persistir_conocimiento/0` reescribe la Sección 13 de `base_conocimiento.pl`. |
| Prueba de persistencia tras reiniciar | Prueba E3-9: un proceso nuevo de Python carga el `.pl` y concluye la regla aprendida. También el panel «Lo aprendido y su persistencia» y el guion del video en [`docs/guion_demo_entregable3.md`](docs/guion_demo_entregable3.md). |
| (Opcional) Preprocesamiento numérico con scikit-learn | `preprocesamiento.py` (árboles de decisión) y el expansor «Mediciones» de la interfaz. Prueba E3-4. |

## Arquitectura híbrida

```
┌──────────────────────── Python (capa imperativa) ────────────────────────┐
│ main.py              interfaz Streamlit: captura texto, mediciones y     │
│                      formularios; dibuja resultados                      │
│ motor.py             puente PySwip: arma las consultas, las ejecuta en   │
│                      un único hilo de Prolog y convierte las respuestas  │
│ preprocesamiento.py  mediciones continuas → hechos discretos (sklearn)   │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ consultas con átomos entre comillas
┌────────────────────────────────▼──────── Prolog (capa simbólica) ────────┐
│ base_conocimiento.pl                                                     │
│  Secc. 1-7   hechos, reglas de 3 niveles, severidad, recolección (E1)    │
│  Secc. 8-10  «¿Por qué?» y «¿Qué falta?» (E2)                            │
│  Secc. 11    lenguaje natural: DCG de análisis y de generación (E3)      │
│  Secc. 12    Modo Experto: validación, assertz/1, retract/1 y escritura  │
│  Secc. 13    conocimiento aprendido en caliente (lo escribe la Secc. 12) │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Python no razona.** No interpreta el texto, no valida hallazgos, no descarta diagnósticos ni calcula pesos. Solo arma consultas, convierte las respuestas y las dibuja. Su limpieza de entradas se limita al formato (decimales con punto, comillas escapadas). La única transformación numérica es la opcional de `preprocesamiento.py`.
- **Prolog no lee del teclado.** No se usa `read/1`: toda entrada llega como argumento de una consulta. `entrada_segura/4` la verifica con `ground/1` y exige átomos en minúscula antes de razonar, así una variable libre enviada desde Python no puede unificar con cualquier hecho.
- **La traza no se escribe a mano.** Un metaintérprete (`demostrar/3`) vuelve a probar cada conclusión con las mismas cláusulas de la base (`clause/2`) y respeta sus cortes. Por eso la explicación coincide exactamente con el razonamiento.

### Módulo «¿Por qué?» (Entregable 2)

- **Reglas disparadas:** árbol (Graphviz y texto) y tabla de las reglas de los niveles 3, 2 y 1 que se cumplieron.
- **Hechos comprobados como verdaderos:** hallazgos que unificaron durante la demostración y datos del paciente validados.
- **Hipótesis alternativas descartadas:** un segundo metaintérprete (`refutar/3`) explica por qué falló la regla `candidato/2` de cada hipótesis que comparte hallazgos con el caso. Clasifica el motivo como **exclusión** por un diagnóstico dominante, **condición excluyente** (`\+`), **dato del paciente** (especie, sexo o edad) o **falta de evidencia crítica**.

### Módulo «¿Qué falta?» (Entregable 2)

1. `estado_evidencia/3` decide si el dictamen es definitivo o si hay **evidencia insuficiente**, **empate** (misma severidad y certezas a no más de 5 puntos) o **certeza baja** (menos de 80 %). En esos tres casos se activa el módulo.
2. `hipotesis_en_competencia/3` reúne las hipótesis confirmadas y las **parcialmente activas**: comparten hallazgos y su fallo se corrige agregando hallazgos. Para cada una calcula su activación y lo que le falta.
3. `sugerencias/5` pondera cada hallazgo no ingresado:
   **peso = Σ peso_rol × gravedad × activación / 100**, con `peso_rol` de 3 (obligatorio), 2 (falta para el mínimo de apoyo) o 1 (refuerzo). El peso se multiplica por 3 si la pregunta favorece a una sola hipótesis, es decir, si **desempata**. En un empate solo se ponderan las dos hipótesis empatadas.
4. `efecto/3` **simula** la respuesta «sí»: vuelve a inferir el caso y dice qué se concluiría o descartaría y cómo cambiarían la certeza y la prioridad.
5. Las respuestas «no» se envían como `Negados`. Prolog deja de sugerirlas y refuta las hipótesis que las necesitaban.

## Estructura

```
.
├── base_conocimiento.pl          Hechos y reglas (toda la lógica, Secciones 1 a 13)
├── motor.py                      Puente Python ↔ Prolog (PySwip)
├── main.py                       Interfaz web Streamlit
├── preprocesamiento.py           Preprocesamiento numérico (Entregable 3, opcional)
├── consola.py                    Consola interactiva (Entregable 1)
├── pruebas.py                    Pruebas del Entregable 1
├── pruebas_explicabilidad.py     Pruebas del Entregable 2
├── pruebas_entregable3.py        Pruebas del Entregable 3
├── requirements.txt
├── .streamlit/config.toml        Tema y opciones de Streamlit
├── .vscode/tasks.json            Tareas para ejecutar desde VS Code
├── evidencia/
│   ├── salida_pruebas.txt        Pruebas del Entregable 1
│   ├── entregable2/              Pruebas y capturas del Entregable 2
│   └── entregable3/              Pruebas del Entregable 3
└── docs/
    ├── ficha_proyecto.md         Ficha del proyecto (Entregable 1)
    ├── diccionario_predicados.md Diccionario de predicados (secciones 15 a 17: Entregable 3)
    ├── guion_demo.md             Guion del video del Entregable 2
    └── guion_demo_entregable3.md Guion del video del Entregable 3
```

## Casos de demostración del Entregable 2

| Caso | Paciente y hallazgos | Qué se observa |
|---|---|---|
| **1 · Inferencia completa** | Perro de 4 meses, macho: vómito, diarrea con sangre, decaimiento, no come y vacunación incompleta | Parvovirosis, **CRÍTICO** (base ALTO + cachorro), certeza 95 %. Árbol con reglas de los niveles 3, 2 y 1, y dos negaciones por fallo. Siete hipótesis descartadas: gastroenteritis (excluida por la parvovirosis), enfermedad renal crónica (`\+` cachorro), obstrucción uretral (solo gatos) y otras por falta de evidencia crítica. |
| **2 · Desempate** | Gato de 36 meses, macho: esfuerzo para orinar y se queja de dolor | Cistitis con certeza de 75 %, por debajo del umbral de 80 %: **se activa «¿Qué falta?»**. Compite con la obstrucción uretral (parcial, CRÍTICA). Pregunta de mayor peso: «¿Al intentar orinar no sale orina…?». Si la respuesta es «sí», se concluye la obstrucción, se descarta la cistitis y la prioridad pasa de MEDIO a CRÍTICO. |
| **2b · Evidencia insuficiente** | Perro de 48 meses, hembra: decaimiento y no come | Ningún perfil se completa. Siete hipótesis parcialmente activas; la primera pregunta es el vómito persistente. |
| **2c · Empate** | Perro de 48 meses, macho: exposición al calor, jadeo, decaimiento e ingesta de xilitol | Golpe de calor e intoxicación empatan (CRÍTICO, 75 %). Solo se ponderan las dos hipótesis empatadas y se sugieren signos que separan una de la otra. |
| **extra** | Dilatación-torsión gástrica (caso 1 del Entregable 1) | Encadenamiento de tres niveles con abdomen agudo. |

En [`docs/guion_demo.md`](docs/guion_demo.md) hay un guion para el video de 3 a 5 minutos.

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
