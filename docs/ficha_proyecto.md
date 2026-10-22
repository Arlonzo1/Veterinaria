# Ficha de definición del proyecto y de la pareja

## 1. Integrantes de la pareja

| Integrante | Código estudiantil | Correo institucional | Rol preliminar |
|---|---|---|---|
| [Nombre completo del integrante 1] | [Código] | [correo@universidad.edu.co] | Líder de Ingeniería del Conocimiento y Modelado Lógico (Prolog) |
| [Nombre completo del integrante 2] | [Código] | [correo@universidad.edu.co] | Líder de Arquitectura de Integración e Interfaz (Python) |

Ambos integrantes dominan Prolog y Python. Los roles indican quién lidera cada frente.

## 2. Tema seleccionado

**Título:** *TriaVet: Sistema Experto Basado en Reglas para el Triage y la Orientación Diagnóstica Preliminar de Urgencias en Perros y Gatos*.

### 2.1 Descripción del problema

En Colombia, el 49 % de los hogares tiene perro y el 38 % tiene gato (Forbes Colombia, 2024). Además, la Ley 1774 de 2016 reconoce a los animales como seres sintientes. Cuando una mascota enferma, su tutor debe decidir si esperar, pedir una cita o ir a urgencias. Lo hace sin formación clínica, con un paciente que no puede describir lo que siente y con signos que suelen ser inespecíficos. Un vómito, por ejemplo, puede ser una indiscreción alimentaria o una intoxicación, una obstrucción o una parvovirosis.

Esa decisión intuitiva produce dos errores:

- **Subestimar:** esperar ante un cuadro crítico, como la dilatación-torsión gástrica, la obstrucción uretral felina o el golpe de calor.
- **Sobreestimar:** ir a urgencias por un cuadro que podía esperar a una consulta programada, lo que eleva costos y congestiona el servicio.

Una lista de triage estructurada clasifica la urgencia mucho mejor que la intuición. En los casos más críticos coincidió con un equipo experto en el 95,5 % de los pacientes, frente al 44,8 % del triage intuitivo (Ruys et al., 2012).

**Usuarios finales:**

- **Usuario principal:** tutores de perros y gatos.
- **Usuarios secundarios:** personal auxiliar de clínicas veterinarias (pretriage), refugios y fundaciones, y estudiantes de medicina veterinaria.
- **Rol de los médicos veterinarios:** no son usuarios del sistema, sino la fuente y los validadores del conocimiento.

### 2.2 Justificación como sistema basado en reglas

| Característica del problema | Cómo la resuelve el sistema experto |
|---|---|
| El conocimiento clínico es heurístico y se expresa como reglas SI‑ENTONCES. | Base de conocimiento declarativa en Prolog, separada del motor y de la interfaz. |
| Las entradas no llevan directo a la conclusión. | Encadenamiento en tres niveles: signos → estados intermedios (deshidratación, abdomen agudo, shock, retención urinaria…) → diagnóstico. |
| Un mismo signo es compatible con varias enfermedades. | Varias hipótesis con un factor de certeza (Shortliffe y Buchanan, 1975) y exclusiones entre diagnósticos. |
| La urgencia no depende solo del diagnóstico. | Reglas de prioridad: los signos de alarma prevalecen y la vulnerabilidad del paciente o la deshidratación suben el nivel. |
| El usuario necesita confiar en la respuesta. | Cada conclusión trae los hallazgos que la sustentan y sus agravantes. |

Un formulario condicional (CRUD) tendría que anticipar cada combinación de respuestas con `if/else`. No podría inferir estados intermedios, manejar información incompleta ni explicar su razonamiento (Giarratano y Riley, 2005).

## 3. Listado de diagnósticos y resultados esperados

| # | Identificador en Prolog | Diagnóstico | Especie | Curso | Severidad base |
|---:|---|---|---|---|---|
| 1 | `parvovirosis` | Parvovirosis canina | Perro | Agudo | Alto |
| 2 | `moquillo` | Moquillo canino (distemper) | Perro | Agudo | Alto |
| 3 | `dilatacion_torsion_gastrica` | Dilatación-torsión gástrica | Perro | Agudo | Crítico |
| 4 | `obstruccion_uretral` | Obstrucción uretral felina | Gato (macho) | Agudo | Crítico |
| 5 | `cistitis` | Cistitis / infección urinaria baja | Perro y gato | Agudo | Medio |
| 6 | `intoxicacion` | Intoxicación | Perro y gato | Agudo | Según la sustancia |
| 7 | `golpe_de_calor` | Golpe de calor | Perro y gato | Agudo | Crítico |
| 8 | `obstruccion_intestinal` | Obstrucción intestinal por cuerpo extraño | Perro y gato | Agudo | Alto |
| 9 | `enfermedad_renal_cronica` | Enfermedad renal crónica | Perro y gato | Crónico | Medio |
| 10 | `gastroenteritis_aguda` | Gastroenteritis aguda inespecífica | Perro y gato | Agudo | Bajo |
| — | `sin_diagnostico_concluyente` | Valor por defecto cuando ningún perfil se cumple | — | — | Bajo |

Para cada caso, el sistema entrega además:

- la **prioridad global**;
- una **recomendación** de cuándo buscar atención;
- una **indicación** de qué hacer y qué evitar mientras tanto;
- el **porcentaje de certeza**;
- los **hallazgos que sustentan** cada diagnóstico.

## 4. Entradas del sistema (53 hallazgos en 9 grupos)

| Grupo | Hallazgos |
|---|---|
| Signos digestivos (10) | vómito, vómito persistente, diarrea, diarrea con sangre, arcadas improductivas, abdomen distendido, dolor abdominal, salivación excesiva, anorexia, sin defecar |
| Signos urinarios (7) | esfuerzo para orinar, ausencia de orina, micción frecuente, sangre en orina, poliuria, polidipsia, lamido genital |
| Signos respiratorios (4) | jadeo excesivo, dificultad respiratoria, secreción nasal, tos |
| Signos neurológicos (4) | convulsiones, temblores, desorientación, mioclonías |
| Estado general (12) | letargo, fiebre, encías pálidas, encías rojo intenso, llenado capilar lento, colapso, pérdida de peso, halitosis urémica, ojos hundidos, piel sin elasticidad, inquietud, vocalización de dolor |
| Vacunación (2) | vacunación completa, vacunación incompleta |
| Condición (2) | gestante, enfermedad crónica previa |
| Raza (2) | raza de tórax profundo, raza braquicéfala |
| Exposiciones (10) | exposición al calor, ingesta de objeto, ingesta de chocolate, xilitol, uvas, cebolla, ibuprofeno, paracetamol, lirio o raticida |

A estos hallazgos se suman los datos del paciente: especie, edad en meses y sexo.

## 5. Escala de severidad y prioridad

| Nivel | Peso | Recomendación |
|---|---:|---|
| **Crítico** | 4 | Urgencia vital: acudir de inmediato a urgencias veterinarias. |
| **Alto** | 3 | Atención veterinaria el mismo día, en las próximas horas. |
| **Medio** | 2 | Consulta en las próximas 24 a 48 horas, vigilando la evolución. |
| **Bajo** | 1 | Vigilar en casa; consultar si los signos persisten o empeoran. |

Además existen dos estados especiales: **Indeterminado**, cuando no se ingresan hallazgos válidos, y **Datos no válidos**, cuando la especie, la edad o el sexo están fuera del dominio.

**Criterios para subir o bajar de nivel** (en este orden de precedencia):

1. **Signos de alarma:** dificultad respiratoria, convulsiones, colapso o signos de shock. Fijan el nivel en **crítico**, sin importar el diagnóstico.
2. **Nivel base:** el de cada diagnóstico. Para las intoxicaciones depende de la sustancia y la especie. Por ejemplo, el paracetamol es crítico en gatos y alto en perros. Las combinaciones sin registro se tratan como alto, por precaución.
3. **Agravantes:** cada uno sube un nivel, hasta un máximo de crítico. Solo se aplican a cuadros agudos:
   - paciente vulnerable (cachorro, geriátrico, gestante o con enfermedad crónica previa);
   - deshidratación inferida;
   - compromiso neurológico.
4. **Prioridad del caso:** el nivel más alto entre sus diagnósticos.

**Criterios de descarte:**

- La vacunación completa descarta la parvovirosis y el moquillo.
- Ser cachorro descarta la enfermedad renal crónica.
- Los signos de alarma descartan la gastroenteritis inespecífica.
- La obstrucción uretral excluye la cistitis.
- La parvovirosis, la intoxicación, la obstrucción intestinal y la dilatación-torsión gástrica excluyen la gastroenteritis inespecífica.

## 6. Alcance y limitaciones

- Se limita a perros y gatos y a los 10 cuadros listados.
- Es una herramienta académica de orientación. No reemplaza el examen físico ni el diagnóstico veterinario.
- Los perfiles y los valores de certeza son preliminares. Deben validarse con al menos un médico veterinario.

## Referencias

- Forbes Colombia. (2024, 28 de diciembre). *Colombia es el segundo país de Latam en el que más creció el mercado de alimentos para mascotas: estudio*. https://forbes.co/2024/12/28/actualidad/colombia-es-el-segundo-pais-de-latam-en-el-que-mas-crecio-el-mercado-de-alimentos-para-mascotas-estudio/
- Giarratano, J. C. y Riley, G. D. (2005). *Expert systems: Principles and programming* (4.ª ed.). Thomson Course Technology.
- Ley 1774 de 2016. Por medio de la cual se modifican el Código Civil, la Ley 84 de 1989, el Código Penal, el Código de Procedimiento Penal y se dictan otras disposiciones. 6 de enero de 2016.
- Ruys, L. J., Gunning, M., Teske, E., Robben, J. H. y Sigrist, N. E. (2012). Evaluation of a veterinary triage list modified from a human five-point triage system in 485 dogs and cats. *Journal of Veterinary Emergency and Critical Care, 22*(3), 303–312. https://doi.org/10.1111/j.1476-4431.2012.00736.x
- Shortliffe, E. H. y Buchanan, B. G. (1975). A model of inexact reasoning in medicine. *Mathematical Biosciences, 23*(3–4), 351–379. https://doi.org/10.1016/0025-5564(75)90047-4
