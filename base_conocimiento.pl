/*  ===========================================================================
    TriaVet - Sistema experto para el triage y la orientación diagnóstica
              preliminar de urgencias en perros y gatos

    Archivo     : base_conocimiento.pl
    Motor       : SWI-Prolog 9.x / 10.x
    Integración : Python mediante PySwip (ver motor.py)

    ESTRUCTURA DEL ARCHIVO
      Sección 1. Hechos de la base de conocimiento
      Sección 2. Utilidades de procesamiento de listas
      Sección 3. Reglas de Nivel 1 - validación preliminar
      Sección 4. Reglas de Nivel 2 - inferencia intermedia
      Sección 5. Reglas de Nivel 3 - conclusión diagnóstica
      Sección 6. Severidad, certeza y prioridad
      Sección 7. Meta-predicados de recolección y API para Python
      Sección 8. Módulo de explicabilidad "¿Por qué?"     (Entregable 2)
      Sección 9. Módulo de recomendación "¿Qué falta?"    (Entregable 2)
      Sección 10. API para Python del Entregable 2
      Sección 11. Lenguaje natural con DCG                (Entregable 3)
      Sección 12. Adquisición dinámica de conocimiento    (Entregable 3)
      Sección 13. Conocimiento aprendido en caliente      (lo escribe el
                  Modo Experto; se conserva al reiniciar la aplicación)

    REPRESENTACIÓN DE UN CASO
      caso(Especie, EdadMeses, Sexo, Hallazgos)
        Especie   : perro | gato
        EdadMeses : entero entre 0 y 300
        Sexo      : macho | hembra
        Hallazgos : lista ordenada y sin duplicados de átomos válidos
                    (signos clínicos y antecedentes del paciente)

    GRAFO DE DEPENDENCIAS (prevención de ciclos)
      Las reglas solo consultan reglas de un nivel igual o inferior y ninguna
      regla se invoca a sí misma por la izquierda:
        Nivel 3 (candidato/2, excluido/2, diagnostico_posible/2)
          -> Nivel 2 (estados intermedios)
            -> Nivel 1 (validación) -> utilidades de listas -> hechos
      excluido/2 llama a candidato/2, nunca a diagnostico_posible/2, por lo
      que aunque existieran exclusiones mutuas no se produciría un bucle.
      Los predicados recursivos sobre listas consumen la cabeza antes de la
      llamada recursiva, de modo que siempre terminan.
      Las Secciones 8 a 10 están por encima de todo lo anterior: sus
      metaintérpretes leen las reglas con clause/2, pero ninguna regla de las
      Secciones 1 a 7 las invoca. demostrar/3 y refutar/3 solo recorren
      cuerpos de cláusulas, que son finitos.

    INTERACCIÓN CON PYTHON
      Prolog nunca lee del teclado (no se usa read/1): toda entrada llega
      como argumento de una consulta y se valida con entrada_segura/4
      (ground/1 y átomos en minúscula) antes de razonar.

    AVISO: herramienta académica de orientación. No reemplaza el examen
    clínico ni el diagnóstico de un médico veterinario.
    =========================================================================== */

:- encoding(utf8).

/*  ---------------------------------------------------------------------------
    PREDICADOS AMPLIABLES EN CALIENTE (Entregable 3)
    El Modo Experto agrega cláusulas a estos predicados con assertz/1 y las
    escribe en la Sección 13 de este mismo archivo. Por eso son dinámicos
    (admiten assertz/retract) y discontiguos (sus cláusulas aprendidas quedan
    al final del archivo, separadas de las originales).
    --------------------------------------------------------------------------- */
:- dynamic
    signo/2, antecedente/2, nombre_hallazgo/2, pregunta/2,
    nombre_diagnostico/2, especie_afectada/2, curso/2,
    requisito/2, apoyo/2, minimo_apoyo/2, certeza_base/2,
    severidad_base/2, indicacion/2, excluye/2,
    diagnostico_aprendido/3, hallazgo_aprendido/3, expresion_aprendida/4.
:- discontiguous
    signo/2, antecedente/2, nombre_hallazgo/2, pregunta/2,
    nombre_diagnostico/2, especie_afectada/2, curso/2,
    requisito/2, apoyo/2, minimo_apoyo/2, certeza_base/2,
    severidad_base/2, indicacion/2, excluye/2.

%   Ruta de este archivo: la usa la Sección 12 para escribir lo aprendido.
:- dynamic archivo_base/1.
:- prolog_load_context(source, Archivo),
   retractall(archivo_base(_)),
   assertz(archivo_base(Archivo)).


/*  ===========================================================================
    SECCIÓN 1. HECHOS DE LA BASE DE CONOCIMIENTO
    =========================================================================== */

/* ---------------------------------------------------------------------------
   1.1 Pacientes admitidos
   especie_paciente(?Especie, ?Nombre)
   sexo_paciente(?Sexo, ?Nombre)
   --------------------------------------------------------------------------- */
especie_paciente(perro, 'Perro').
especie_paciente(gato,  'Gato').

sexo_paciente(macho,  'Macho').
sexo_paciente(hembra, 'Hembra').

/* ---------------------------------------------------------------------------
   1.2 Catálogo de signos clínicos observables por el tutor
   signo(?Signo, ?Sistema)
   --------------------------------------------------------------------------- */
% Sistema digestivo
signo(vomito,                 digestivo).
signo(vomito_persistente,     digestivo).
signo(diarrea,                digestivo).
signo(diarrea_con_sangre,     digestivo).
signo(arcadas_improductivas,  digestivo).
signo(abdomen_distendido,     digestivo).
signo(dolor_abdominal,        digestivo).
signo(salivacion_excesiva,    digestivo).
signo(anorexia,               digestivo).
signo(sin_defecar,            digestivo).
% Sistema urinario
signo(esfuerzo_para_orinar,   urinario).
signo(ausencia_de_orina,      urinario).
signo(miccion_frecuente,      urinario).
signo(sangre_en_orina,        urinario).
signo(poliuria,               urinario).
signo(polidipsia,             urinario).
signo(lamido_genital,         urinario).
% Sistema respiratorio
signo(jadeo_excesivo,         respiratorio).
signo(dificultad_respiratoria, respiratorio).
signo(secrecion_nasal,        respiratorio).
signo(tos,                    respiratorio).
% Sistema nervioso
signo(convulsiones,           neurologico).
signo(temblores,              neurologico).
signo(desorientacion,         neurologico).
signo(mioclonias,             neurologico).
% Estado general
signo(letargo,                general).
signo(fiebre,                 general).
signo(encias_palidas,         general).
signo(encias_rojo_intenso,    general).
signo(llenado_capilar_lento,  general).
signo(colapso,                general).
signo(perdida_de_peso,        general).
signo(halitosis_uremica,      general).
signo(ojos_hundidos,          general).
signo(piel_sin_elasticidad,   general).
signo(inquietud,              general).
signo(vocalizacion_dolor,     general).
signo(hipotermia,             general).

/* ---------------------------------------------------------------------------
   1.3 Antecedentes y factores de riesgo del paciente
   antecedente(?Antecedente, ?Tipo)
   --------------------------------------------------------------------------- */
antecedente(vacunacion_completa,      vacunacion).
antecedente(vacunacion_incompleta,    vacunacion).
antecedente(gestante,                 condicion).
antecedente(enfermedad_cronica_previa, condicion).
antecedente(raza_torax_profundo,      raza).
antecedente(raza_braquicefala,        raza).
antecedente(exposicion_calor,         exposicion).
antecedente(ingesta_objeto,           exposicion).
antecedente(ingesta_chocolate,        exposicion).
antecedente(ingesta_xilitol,          exposicion).
antecedente(ingesta_uvas,             exposicion).
antecedente(ingesta_cebolla,          exposicion).
antecedente(ingesta_ibuprofeno,       exposicion).
antecedente(ingesta_paracetamol,      exposicion).
antecedente(ingesta_lirio,            exposicion).
antecedente(ingesta_raticida,         exposicion).

/* ---------------------------------------------------------------------------
   1.4 Nombres legibles de los grupos de hallazgos (para el menú de consola)
   nombre_grupo(?Grupo, ?Nombre)
   --------------------------------------------------------------------------- */
nombre_grupo(digestivo,    'Signos digestivos').
nombre_grupo(urinario,     'Signos urinarios').
nombre_grupo(respiratorio, 'Signos respiratorios').
nombre_grupo(neurologico,  'Signos neurológicos').
nombre_grupo(general,      'Estado general').
nombre_grupo(vacunacion,   'Vacunación').
nombre_grupo(condicion,    'Condición del paciente').
nombre_grupo(raza,         'Raza').
nombre_grupo(exposicion,   'Exposiciones e ingestas').

/* ---------------------------------------------------------------------------
   1.5 Signos de alarma: elevan la prioridad a crítica sin importar el
   diagnóstico presuntivo
   signo_alarma(?Signo, ?Descripcion)
   --------------------------------------------------------------------------- */
signo_alarma(dificultad_respiratoria, 'dificultad respiratoria').
signo_alarma(convulsiones,            'convulsiones').
signo_alarma(colapso,                 'colapso o incapacidad para levantarse').

/* ---------------------------------------------------------------------------
   1.6 Indicadores que definen los estados intermedios del Nivel 2
   indicadores(?Estado, ?ListaDeHallazgos)
   --------------------------------------------------------------------------- */
indicadores(cuadro_digestivo,         [vomito, vomito_persistente, diarrea, diarrea_con_sangre]).
indicadores(deshidratacion,           [vomito_persistente, diarrea, diarrea_con_sangre,
                                       ojos_hundidos, piel_sin_elasticidad]).
indicadores(compromiso_neurologico,   [convulsiones, temblores, desorientacion, mioclonias]).
indicadores(depresion_estado_general, [letargo, colapso]).
indicadores(perfusion_deficiente,     [encias_palidas, llenado_capilar_lento, hipotermia]).
indicadores(condicion_vulnerable,     [gestante, enfermedad_cronica_previa]).

/* ---------------------------------------------------------------------------
   1.7 Umbrales de edad por especie (en meses)
   umbral_edad(?Especie, ?Etapa, ?Meses)
     cachorro  : edad < Meses        geriatrico : edad >= Meses
   --------------------------------------------------------------------------- */
umbral_edad(perro, cachorro,   12).
umbral_edad(perro, geriatrico, 96).
umbral_edad(gato,  cachorro,   12).
umbral_edad(gato,  geriatrico, 120).

/* ---------------------------------------------------------------------------
   1.8 Sustancias tóxicas
   sustancia(?Ingesta, ?Sustancia)
   toxicidad(?Sustancia, ?Especie, ?Nivel)
   Las combinaciones no registradas se tratan con el nivel por defecto de
   intoxicacion (principio de precaución), ver toxicidad_para/3.
   --------------------------------------------------------------------------- */
sustancia(ingesta_chocolate,   chocolate).
sustancia(ingesta_xilitol,     xilitol).
sustancia(ingesta_uvas,        uvas).
sustancia(ingesta_cebolla,     cebolla).
sustancia(ingesta_ibuprofeno,  ibuprofeno).
sustancia(ingesta_paracetamol, paracetamol).
sustancia(ingesta_lirio,       lirio).
sustancia(ingesta_raticida,    raticida).

toxicidad(chocolate,   perro, alto).
toxicidad(chocolate,   gato,  alto).
toxicidad(xilitol,     perro, critico).
toxicidad(uvas,        perro, alto).
toxicidad(cebolla,     perro, medio).
toxicidad(cebolla,     gato,  alto).
toxicidad(ibuprofeno,  perro, alto).
toxicidad(ibuprofeno,  gato,  critico).
toxicidad(paracetamol, perro, alto).
toxicidad(paracetamol, gato,  critico).
toxicidad(lirio,       gato,  critico).
toxicidad(raticida,    perro, alto).
toxicidad(raticida,    gato,  alto).

/* ---------------------------------------------------------------------------
   1.9 Catálogo de diagnósticos
   nombre_diagnostico(?Diagnostico, ?Nombre)
   especie_afectada(?Diagnostico, ?Especie)
   curso(?Diagnostico, ?Curso)          Curso: agudo | cronico
   --------------------------------------------------------------------------- */
nombre_diagnostico(parvovirosis,                'Parvovirosis canina').
nombre_diagnostico(moquillo,                    'Moquillo canino (distemper)').
nombre_diagnostico(dilatacion_torsion_gastrica, 'Dilatación-torsión gástrica').
nombre_diagnostico(obstruccion_uretral,         'Obstrucción uretral felina').
nombre_diagnostico(cistitis,                    'Cistitis / infección urinaria baja').
nombre_diagnostico(intoxicacion,                'Intoxicación').
nombre_diagnostico(golpe_de_calor,              'Golpe de calor').
nombre_diagnostico(obstruccion_intestinal,      'Obstrucción intestinal por cuerpo extraño').
nombre_diagnostico(enfermedad_renal_cronica,    'Enfermedad renal crónica').
nombre_diagnostico(gastroenteritis_aguda,       'Gastroenteritis aguda inespecífica').
nombre_diagnostico(sin_diagnostico_concluyente, 'Sin diagnóstico concluyente').

especie_afectada(parvovirosis,                perro).
especie_afectada(moquillo,                    perro).
especie_afectada(dilatacion_torsion_gastrica, perro).
especie_afectada(obstruccion_uretral,         gato).
especie_afectada(cistitis,                    perro).
especie_afectada(cistitis,                    gato).
especie_afectada(intoxicacion,                perro).
especie_afectada(intoxicacion,                gato).
especie_afectada(golpe_de_calor,              perro).
especie_afectada(golpe_de_calor,              gato).
especie_afectada(obstruccion_intestinal,      perro).
especie_afectada(obstruccion_intestinal,      gato).
especie_afectada(enfermedad_renal_cronica,    perro).
especie_afectada(enfermedad_renal_cronica,    gato).
especie_afectada(gastroenteritis_aguda,       perro).
especie_afectada(gastroenteritis_aguda,       gato).

curso(parvovirosis,                agudo).
curso(moquillo,                    agudo).
curso(dilatacion_torsion_gastrica, agudo).
curso(obstruccion_uretral,         agudo).
curso(cistitis,                    agudo).
curso(intoxicacion,                agudo).
curso(golpe_de_calor,              agudo).
curso(obstruccion_intestinal,      agudo).
curso(enfermedad_renal_cronica,    cronico).
curso(gastroenteritis_aguda,       agudo).
curso(sin_diagnostico_concluyente, agudo).

/* ---------------------------------------------------------------------------
   1.10 Perfiles clínicos
   requisito(?Diagnostico, ?ListaObligatoria)   todos deben estar presentes
   apoyo(?Diagnostico, ?ListaDeApoyo)           refuerzan la hipótesis
   minimo_apoyo(?Diagnostico, ?N)               cuántos de apoyo se exigen
   certeza_base(?Diagnostico, ?Factor)          certeza inicial (0..1)
   --------------------------------------------------------------------------- */
requisito(parvovirosis,                [diarrea_con_sangre]).
requisito(moquillo,                    [secrecion_nasal, fiebre]).
requisito(dilatacion_torsion_gastrica, [abdomen_distendido, arcadas_improductivas]).
requisito(obstruccion_uretral,         [esfuerzo_para_orinar, ausencia_de_orina]).
requisito(cistitis,                    []).
requisito(intoxicacion,                []).
requisito(golpe_de_calor,              [exposicion_calor, jadeo_excesivo]).
requisito(obstruccion_intestinal,      [vomito_persistente]).
requisito(enfermedad_renal_cronica,    [poliuria, polidipsia]).
requisito(gastroenteritis_aguda,       []).
requisito(sin_diagnostico_concluyente, []).

apoyo(parvovirosis,                [vomito, vomito_persistente, letargo, anorexia, fiebre,
                                    vacunacion_incompleta]).
apoyo(moquillo,                    [tos, mioclonias, convulsiones, letargo, anorexia, diarrea,
                                    vacunacion_incompleta]).
apoyo(dilatacion_torsion_gastrica, [salivacion_excesiva, inquietud, dolor_abdominal,
                                    raza_torax_profundo, colapso]).
apoyo(obstruccion_uretral,         [vocalizacion_dolor, lamido_genital, letargo, vomito,
                                    anorexia]).
apoyo(cistitis,                    [miccion_frecuente, sangre_en_orina, esfuerzo_para_orinar,
                                    lamido_genital, vocalizacion_dolor]).
apoyo(intoxicacion,                [vomito, salivacion_excesiva, temblores, convulsiones,
                                    letargo, diarrea, desorientacion]).
apoyo(golpe_de_calor,              [encias_rojo_intenso, colapso, letargo, vomito,
                                    desorientacion, raza_braquicefala, dificultad_respiratoria]).
apoyo(obstruccion_intestinal,      [ingesta_objeto, sin_defecar, dolor_abdominal, anorexia,
                                    letargo]).
apoyo(enfermedad_renal_cronica,    [perdida_de_peso, halitosis_uremica, vomito, anorexia,
                                    letargo]).
apoyo(gastroenteritis_aguda,       [vomito, diarrea, diarrea_con_sangre, anorexia]).
apoyo(sin_diagnostico_concluyente, []).

minimo_apoyo(parvovirosis,                1).
minimo_apoyo(moquillo,                    1).
minimo_apoyo(dilatacion_torsion_gastrica, 1).
minimo_apoyo(obstruccion_uretral,         0).
minimo_apoyo(cistitis,                    2).
minimo_apoyo(intoxicacion,                0).
minimo_apoyo(golpe_de_calor,              1).
minimo_apoyo(obstruccion_intestinal,      2).
minimo_apoyo(enfermedad_renal_cronica,    1).
minimo_apoyo(gastroenteritis_aguda,       1).
minimo_apoyo(sin_diagnostico_concluyente, 0).

certeza_base(parvovirosis,                0.60).
certeza_base(moquillo,                    0.50).
certeza_base(dilatacion_torsion_gastrica, 0.70).
certeza_base(obstruccion_uretral,         0.75).
certeza_base(cistitis,                    0.55).
certeza_base(intoxicacion,                0.65).
certeza_base(golpe_de_calor,              0.65).
certeza_base(obstruccion_intestinal,      0.50).
certeza_base(enfermedad_renal_cronica,    0.55).
certeza_base(gastroenteritis_aguda,       0.40).
certeza_base(sin_diagnostico_concluyente, 0.00).

/* ---------------------------------------------------------------------------
   1.11 Exclusiones entre diagnósticos
   excluye(?Dominante, ?Excluido)
   Si el diagnóstico Dominante es candidato, el Excluido se descarta porque
   el primero explica mejor (y con mayor urgencia) los mismos hallazgos.
   --------------------------------------------------------------------------- */
excluye(obstruccion_uretral,         cistitis).
excluye(parvovirosis,                gastroenteritis_aguda).
excluye(intoxicacion,                gastroenteritis_aguda).
excluye(obstruccion_intestinal,      gastroenteritis_aguda).
excluye(dilatacion_torsion_gastrica, gastroenteritis_aguda).

/* ---------------------------------------------------------------------------
   1.12 Escala de severidad
   severidad_base(?Diagnostico, ?Nivel)
   nivel_valor(?Nivel, ?Peso)           ponderación numérica para ordenar
   siguiente_nivel(?Nivel, ?NivelSuperior)
   recomendacion(?Prioridad, ?Texto)
   --------------------------------------------------------------------------- */
severidad_base(parvovirosis,                alto).
severidad_base(moquillo,                    alto).
severidad_base(dilatacion_torsion_gastrica, critico).
severidad_base(obstruccion_uretral,         critico).
severidad_base(cistitis,                    medio).
severidad_base(intoxicacion,                alto).
severidad_base(golpe_de_calor,              critico).
severidad_base(obstruccion_intestinal,      alto).
severidad_base(enfermedad_renal_cronica,    medio).
severidad_base(gastroenteritis_aguda,       bajo).
severidad_base(sin_diagnostico_concluyente, bajo).

nivel_valor(bajo,    1).
nivel_valor(medio,   2).
nivel_valor(alto,    3).
nivel_valor(critico, 4).

siguiente_nivel(bajo,    medio).
siguiente_nivel(medio,   alto).
siguiente_nivel(alto,    critico).
siguiente_nivel(critico, critico).

recomendacion(critico,
    'URGENCIA VITAL: acuda de inmediato a un servicio veterinario de urgencias.').
recomendacion(alto,
    'URGENTE: busque atención veterinaria hoy mismo, en las próximas horas.').
recomendacion(medio,
    'PRIORITARIO: programe una consulta veterinaria en las próximas 24 a 48 horas y vigile la evolución.').
recomendacion(bajo,
    'NO URGENTE: vigile al paciente en casa y consulte si los signos persisten o empeoran.').
recomendacion(indeterminado,
    'SIN HALLAZGOS VÁLIDOS: no es posible orientar el caso; revise los signos ingresados.').
recomendacion(datos_invalidos,
    'DATOS DEL PACIENTE NO VÁLIDOS: revise la especie (perro/gato), la edad en meses (0-300) y el sexo (macho/hembra).').

/* ---------------------------------------------------------------------------
   1.13 Indicaciones mientras se consigue atención veterinaria
   indicacion(?Clave, ?Texto)
   Clave es un diagnóstico o la clave especial alarma_sin_diagnostico.
   --------------------------------------------------------------------------- */
indicacion(parvovirosis,
    'Aísle al cachorro de otros perros, no lo obligue a comer y llévelo hoy mismo al veterinario: la deshidratación avanza rápido.').
indicacion(moquillo,
    'Aísle al perro de otros perros y acuda a consulta; si aparecen convulsiones, vaya a urgencias.').
indicacion(dilatacion_torsion_gastrica,
    'No le dé agua ni comida ni intente provocarle el vómito. Trasládelo de inmediato a urgencias.').
indicacion(obstruccion_uretral,
    'No espere a que orine por sí solo ni le presione el abdomen. Trasládelo de inmediato a urgencias.').
indicacion(cistitis,
    'Asegure agua fresca y arenero o paseos frecuentes; programe consulta. Si deja de orinar, acuda a urgencias.').
indicacion(intoxicacion,
    'No induzca el vómito ni dé remedios caseros sin indicación veterinaria. Lleve el empaque o una muestra de la sustancia.').
indicacion(golpe_de_calor,
    'Llévelo a la sombra y refrésquelo con agua a temperatura ambiente (no helada) mientras lo traslada a urgencias.').
indicacion(obstruccion_intestinal,
    'No le dé comida ni laxantes. Acuda hoy al veterinario e informe qué objeto pudo ingerir.').
indicacion(enfermedad_renal_cronica,
    'Mantenga agua fresca disponible siempre y programe consulta para pruebas de función renal.').
indicacion(gastroenteritis_aguda,
    'Ofrezca agua en pequeñas cantidades y vigile; consulte si los signos duran más de 24 horas o empeoran.').
indicacion(sin_diagnostico_concluyente,
    'Los hallazgos no permiten orientar un diagnóstico; observe la evolución y consulte si aparecen nuevos signos.').
indicacion(alarma_sin_diagnostico,
    'Hay signos de alarma aunque no se identifica la causa: acuda de inmediato a urgencias veterinarias.').

/* ---------------------------------------------------------------------------
   1.14 Nombres legibles de los hallazgos (Entregable 2)
   nombre_hallazgo(?Hallazgo, ?Nombre)
   Los usan la interfaz y los textos de la traza y de las recomendaciones.
   --------------------------------------------------------------------------- */
% Signos digestivos
nombre_hallazgo(vomito,                    'Vómito').
nombre_hallazgo(vomito_persistente,        'Vómito persistente').
nombre_hallazgo(diarrea,                   'Diarrea').
nombre_hallazgo(diarrea_con_sangre,        'Diarrea con sangre').
nombre_hallazgo(arcadas_improductivas,     'Arcadas improductivas').
nombre_hallazgo(abdomen_distendido,        'Abdomen distendido').
nombre_hallazgo(dolor_abdominal,           'Dolor abdominal').
nombre_hallazgo(salivacion_excesiva,       'Salivación excesiva').
nombre_hallazgo(anorexia,                  'No come (anorexia)').
nombre_hallazgo(sin_defecar,               'Sin defecar').
% Signos urinarios
nombre_hallazgo(esfuerzo_para_orinar,      'Esfuerzo para orinar').
nombre_hallazgo(ausencia_de_orina,         'No sale orina').
nombre_hallazgo(miccion_frecuente,         'Micción frecuente').
nombre_hallazgo(sangre_en_orina,           'Sangre en la orina').
nombre_hallazgo(poliuria,                  'Orina en exceso (poliuria)').
nombre_hallazgo(polidipsia,                'Bebe en exceso (polidipsia)').
nombre_hallazgo(lamido_genital,            'Lamido genital').
% Signos respiratorios
nombre_hallazgo(jadeo_excesivo,            'Jadeo excesivo').
nombre_hallazgo(dificultad_respiratoria,   'Dificultad respiratoria').
nombre_hallazgo(secrecion_nasal,           'Secreción nasal').
nombre_hallazgo(tos,                       'Tos').
% Signos neurológicos
nombre_hallazgo(convulsiones,              'Convulsiones').
nombre_hallazgo(temblores,                 'Temblores').
nombre_hallazgo(desorientacion,            'Desorientación').
nombre_hallazgo(mioclonias,                'Mioclonías (tics musculares)').
% Estado general
nombre_hallazgo(letargo,                   'Decaimiento (letargo)').
nombre_hallazgo(fiebre,                    'Fiebre').
nombre_hallazgo(encias_palidas,            'Encías pálidas').
nombre_hallazgo(encias_rojo_intenso,       'Encías rojo intenso').
nombre_hallazgo(llenado_capilar_lento,     'Llenado capilar lento').
nombre_hallazgo(colapso,                   'Colapso').
nombre_hallazgo(perdida_de_peso,           'Pérdida de peso').
nombre_hallazgo(halitosis_uremica,         'Aliento a orina (halitosis urémica)').
nombre_hallazgo(ojos_hundidos,             'Ojos hundidos').
nombre_hallazgo(piel_sin_elasticidad,      'Piel sin elasticidad').
nombre_hallazgo(inquietud,                 'Inquietud').
nombre_hallazgo(vocalizacion_dolor,        'Se queja de dolor').
nombre_hallazgo(hipotermia,                'Temperatura baja (hipotermia)').
% Antecedentes
nombre_hallazgo(vacunacion_completa,       'Vacunación completa').
nombre_hallazgo(vacunacion_incompleta,     'Vacunación incompleta o ausente').
nombre_hallazgo(gestante,                  'Gestante').
nombre_hallazgo(enfermedad_cronica_previa, 'Enfermedad crónica previa').
nombre_hallazgo(raza_torax_profundo,       'Raza de tórax profundo').
nombre_hallazgo(raza_braquicefala,         'Raza braquicéfala').
nombre_hallazgo(exposicion_calor,          'Exposición al calor').
nombre_hallazgo(ingesta_objeto,            'Tragó un objeto').
nombre_hallazgo(ingesta_chocolate,         'Ingesta de chocolate').
nombre_hallazgo(ingesta_xilitol,           'Ingesta de xilitol').
nombre_hallazgo(ingesta_uvas,              'Ingesta de uvas o pasas').
nombre_hallazgo(ingesta_cebolla,           'Ingesta de cebolla o ajo').
nombre_hallazgo(ingesta_ibuprofeno,        'Ingesta de ibuprofeno').
nombre_hallazgo(ingesta_paracetamol,       'Ingesta de paracetamol').
nombre_hallazgo(ingesta_lirio,             'Ingesta de lirio').
nombre_hallazgo(ingesta_raticida,          'Ingesta de raticida').


/*  ===========================================================================
    SECCIÓN 2. UTILIDADES DE PROCESAMIENTO DE LISTAS
    Todas recorren la lista consumiendo la cabeza antes de la llamada
    recursiva (recursión por la derecha), por lo que siempre terminan.
    =========================================================================== */

%!  presente(+Hallazgo, +Hallazgos) is semidet.
%   Verdadero si Hallazgo está en la lista. memberchk/2 es determinista:
%   no deja puntos de elección que generen soluciones repetidas.
presente(Hallazgo, Hallazgos) :-
    memberchk(Hallazgo, Hallazgos).

%!  alguno_presente(+Candidatos, +Hallazgos) is semidet.
%   Verdadero si al menos un elemento de Candidatos está en Hallazgos.
%   CORTE: basta el primer elemento encontrado; sin el corte, el
%   backtracking produciría una solución por cada coincidencia.
alguno_presente(Candidatos, Hallazgos) :-
    member(X, Candidatos),
    presente(X, Hallazgos), !.

%!  contiene_todos(+Requeridos, +Hallazgos) is semidet.
%   Verifica que Requeridos sea un subconjunto de Hallazgos.
contiene_todos([], _).
contiene_todos([R|Rs], Hallazgos) :-
    presente(R, Hallazgos),
    contiene_todos(Rs, Hallazgos).

%!  contar_presentes(+Lista, +Hallazgos, -N) is det.
%   Cuenta cuántos elementos de Lista aparecen en Hallazgos.
%   CORTE: la segunda y la tercera cláusula son mutuamente excluyentes
%   (el elemento está o no está); el corte impide que, al retroceder, la
%   tercera cláusula vuelva a contar un elemento que sí estaba presente.
contar_presentes([], _, 0).
contar_presentes([X|Xs], Hallazgos, N) :-
    presente(X, Hallazgos), !,
    contar_presentes(Xs, Hallazgos, N0),
    N is N0 + 1.
contar_presentes([_|Xs], Hallazgos, N) :-
    contar_presentes(Xs, Hallazgos, N).

%!  interseccion(+Lista, +Hallazgos, -Comunes) is det.
%   Filtra los elementos de Lista que están en Hallazgos (conserva el orden).
%   CORTE: mismo criterio de exclusión mutua que contar_presentes/3.
interseccion([], _, []).
interseccion([X|Xs], Hallazgos, [X|Comunes]) :-
    presente(X, Hallazgos), !,
    interseccion(Xs, Hallazgos, Comunes).
interseccion([_|Xs], Hallazgos, Comunes) :-
    interseccion(Xs, Hallazgos, Comunes).

%!  particionar(+Lista, -Validos, -Invalidos) is det.
%   Separa los hallazgos reconocidos por la base de conocimiento de los
%   que no lo son (errores de digitación, signos fuera del dominio).
%   CORTE: un elemento es válido o inválido, nunca ambas cosas.
particionar([], [], []).
particionar([H|T], [H|Validos], Invalidos) :-
    hallazgo_valido(H), !,
    particionar(T, Validos, Invalidos).
particionar([H|T], Validos, [H|Invalidos]) :-
    particionar(T, Validos, Invalidos).

%!  pares_valores(+Pares, -Valores) is det.
%   Extrae los valores de una lista de pares Clave-Valor.
pares_valores([], []).
pares_valores([_-V|Pares], [V|Valores]) :-
    pares_valores(Pares, Valores).

%!  diferencia(+Lista, +Hallazgos, -Ausentes) is det.
%   Elementos de Lista que NO están en Hallazgos (conserva el orden). Es el
%   complemento de interseccion/3; lo usan los módulos del Entregable 2 para
%   saber qué hallazgos faltan.
%   CORTE: mismo criterio de exclusión mutua que interseccion/3.
diferencia([], _, []).
diferencia([X|Xs], Hallazgos, Ausentes) :-
    presente(X, Hallazgos), !,
    diferencia(Xs, Hallazgos, Ausentes).
diferencia([X|Xs], Hallazgos, [X|Ausentes]) :-
    diferencia(Xs, Hallazgos, Ausentes).


/*  ===========================================================================
    SECCIÓN 3. REGLAS DE NIVEL 1 - VALIDACIÓN PRELIMINAR
    Clasifican los datos de entrada y verifican condiciones elementales.
    =========================================================================== */

%!  hallazgo_valido(+Hallazgo) is semidet.
%   Un hallazgo es válido si es un átomo registrado como signo o antecedente.
%   CORTE: si ya es un signo, no se busca además entre los antecedentes.
hallazgo_valido(H) :-
    atom(H),
    signo(H, _), !.
hallazgo_valido(H) :-
    atom(H),
    antecedente(H, _).

%!  grupo_hallazgo(?Hallazgo, ?Grupo) is nondet.
%   Asocia cada hallazgo con su grupo (sistema orgánico o tipo de antecedente).
grupo_hallazgo(H, Grupo) :-
    signo(H, Grupo).
grupo_hallazgo(H, Grupo) :-
    antecedente(H, Grupo).

%!  normalizar_entrada(+Entrada, -Validos, -Ignorados) is det.
%   Ordena la lista recibida desde Python, elimina duplicados (sort/2) y la
%   separa en hallazgos válidos e ignorados.
normalizar_entrada(Entrada, Validos, Ignorados) :-
    sort(Entrada, SinDuplicados),
    particionar(SinDuplicados, Validos, Ignorados).

%!  entrada_segura(+Especie, +Edad, +Sexo, +Entrada) is semidet.
%   Barrera de validación de los datos que llegan desde Python (Entregable 2):
%     - ground/1: ningún argumento puede traer variables libres, que de otro
%       modo unificarían con cualquier hecho y producirían respuestas falsas;
%     - especie y sexo deben ser átomos en minúscula;
%     - la edad debe ser un entero y los hallazgos, una lista cerrada.
entrada_segura(Especie, Edad, Sexo, Entrada) :-
    ground(Especie-Edad-Sexo-Entrada),
    atomo_minuscula(Especie),
    atomo_minuscula(Sexo),
    integer(Edad),
    is_list(Entrada).

%!  atomo_minuscula(+Termino) is semidet.
%   El término es un átomo escrito completamente en minúscula.
atomo_minuscula(Termino) :-
    atom(Termino),
    downcase_atom(Termino, Termino).

%!  atomos_seguros(+Entrada, -Lista) is det.
%   Lista cerrada de átomos en minúscula enviada desde Python.
%   CORTE + FALLBACK: cualquier otra entrada se trata como lista vacía.
atomos_seguros(Entrada, Entrada) :-
    is_list(Entrada),
    ground(Entrada),
    forall(member(X, Entrada), atomo_minuscula(X)), !.
atomos_seguros(_, []).

%!  datos_paciente_validos(+Caso) is semidet.
%   Verifica especie, sexo y edad (entero entre 0 y 300 meses).
datos_paciente_validos(caso(Especie, Edad, Sexo, _)) :-
    especie_paciente(Especie, _),
    sexo_paciente(Sexo, _),
    integer(Edad),
    Edad >= 0,
    Edad =< 300.

%!  etapa_vida(+Especie, +EdadMeses, ?Etapa) is det.
%   Clasifica la edad en cachorro, adulto o geriatrico.
%   CORTE: las tres cláusulas son mutuamente excluyentes y la última es el
%   valor por defecto (fallback). La unificación de Etapa se hace DESPUÉS
%   del corte para que la regla sea correcta también cuando se consulta con
%   Etapa ya instanciada (p. ej. etapa_vida(perro, 5, adulto) debe fallar).
etapa_vida(Especie, Edad, Etapa) :-
    umbral_edad(Especie, cachorro, Meses),
    Edad < Meses, !,
    Etapa = cachorro.
etapa_vida(Especie, Edad, Etapa) :-
    umbral_edad(Especie, geriatrico, Meses),
    Edad >= Meses, !,
    Etapa = geriatrico.
etapa_vida(_, _, adulto).

%!  etapa(+Caso, ?Etapa) is det.
etapa(caso(Especie, Edad, _, _), Etapa) :-
    etapa_vida(Especie, Edad, Etapa).


/*  ===========================================================================
    SECCIÓN 4. REGLAS DE NIVEL 2 - INFERENCIA INTERMEDIA
    Combinan reglas de Nivel 1 y hechos para deducir estados intermedios que
    el usuario no ingresa directamente.
    =========================================================================== */

%!  cuadro_digestivo(+Caso) is semidet.
cuadro_digestivo(caso(_, _, _, H)) :-
    indicadores(cuadro_digestivo, Indicadores),
    alguno_presente(Indicadores, H).

%!  deshidratacion(+Caso) is semidet.
%   Se infiere con al menos dos indicadores de pérdida de líquidos.
deshidratacion(caso(_, _, _, H)) :-
    indicadores(deshidratacion, Indicadores),
    contar_presentes(Indicadores, H, N),
    N >= 2.

%!  compromiso_neurologico(+Caso) is semidet.
compromiso_neurologico(caso(_, _, _, H)) :-
    indicadores(compromiso_neurologico, Indicadores),
    alguno_presente(Indicadores, H).

%!  signos_de_shock(+Caso) is semidet.
%   Depresión del estado general + perfusión deficiente.
signos_de_shock(caso(_, _, _, H)) :-
    indicadores(depresion_estado_general, Depresion),
    alguno_presente(Depresion, H),
    indicadores(perfusion_deficiente, Perfusion),
    alguno_presente(Perfusion, H).

%!  signo_de_alarma(+Caso) is semidet.
%   CORTE: basta un signo de alarma directo; solo si no hay ninguno se
%   evalúa el estado intermedio de shock (segunda cláusula).
signo_de_alarma(caso(_, _, _, H)) :-
    member(S, H),
    signo_alarma(S, _), !.
signo_de_alarma(Caso) :-
    signos_de_shock(Caso).

%!  alarmas_presentes(+Caso, -Alarmas) is det.
%   Lista los signos de alarma directos y, si aplica, el estado de shock.
alarmas_presentes(Caso, Alarmas) :-
    Caso = caso(_, _, _, H),
    findall(S, (member(S, H), signo_alarma(S, _)), Directas),
    alarma_por_shock(Caso, PorShock),
    append(Directas, PorShock, Alarmas).

%   CORTE + FALLBACK: si hay shock se devuelve [signos_de_shock]; en caso
%   contrario la cláusula por defecto devuelve la lista vacía.
alarma_por_shock(Caso, [signos_de_shock]) :-
    signos_de_shock(Caso), !.
alarma_por_shock(_, []).

%!  abdomen_agudo(+Caso) is semidet.
abdomen_agudo(caso(_, _, _, H)) :-
    alguno_presente([dolor_abdominal, abdomen_distendido], H),
    alguno_presente([vomito_persistente, arcadas_improductivas], H).

%!  retencion_urinaria(+Caso) is semidet.
retencion_urinaria(caso(_, _, _, H)) :-
    contiene_todos([esfuerzo_para_orinar, ausencia_de_orina], H).

%!  exposicion_toxica(+Caso, -Sustancia) is nondet.
%   Una solución por cada sustancia tóxica reportada.
exposicion_toxica(caso(_, _, _, H), Sustancia) :-
    member(Ingesta, H),
    sustancia(Ingesta, Sustancia).

%!  hipertermia_probable(+Caso) is semidet.
hipertermia_probable(caso(_, _, _, H)) :-
    contiene_todos([exposicion_calor, jadeo_excesivo], H).

%!  sin_proteccion_vacunal(+Caso) is semidet.
%   NEGACIÓN POR FALLO: el paciente se considera sin protección si NO se
%   reporta vacunación completa. H está instanciada (viene del caso).
sin_proteccion_vacunal(caso(_, _, _, H)) :-
    \+ presente(vacunacion_completa, H).

%!  susceptible_parvovirus(+Caso) is semidet.
%   Sin protección vacunal y, además, cachorro o con esquema incompleto.
%   CORTE: si ya es cachorro no hace falta revisar la segunda cláusula.
susceptible_parvovirus(Caso) :-
    sin_proteccion_vacunal(Caso),
    etapa(Caso, cachorro), !.
susceptible_parvovirus(Caso) :-
    sin_proteccion_vacunal(Caso),
    Caso = caso(_, _, _, H),
    presente(vacunacion_incompleta, H).

%!  paciente_vulnerable(+Caso) is semidet.
%   Cachorro, geriátrico, gestante o con enfermedad crónica previa.
%   CORTE: una sola condición de vulnerabilidad es suficiente.
paciente_vulnerable(Caso) :-
    etapa(Caso, Etapa),
    memberchk(Etapa, [cachorro, geriatrico]), !.
paciente_vulnerable(caso(_, _, _, H)) :-
    indicadores(condicion_vulnerable, Condiciones),
    alguno_presente(Condiciones, H).

%!  cumple_perfil(+Caso, +Diagnostico) is semidet.
%   El caso cumple el perfil si la especie es compatible, están TODOS los
%   requisitos (subconjunto) y hay al menos el mínimo de signos de apoyo.
cumple_perfil(caso(Especie, _, _, H), Diagnostico) :-
    especie_afectada(Diagnostico, Especie),
    requisito(Diagnostico, Requisitos),
    contiene_todos(Requisitos, H),
    apoyo(Diagnostico, Apoyo),
    contar_presentes(Apoyo, H, N),
    minimo_apoyo(Diagnostico, Minimo),
    N >= Minimo.


/*  ===========================================================================
    SECCIÓN 5. REGLAS DE NIVEL 3 - CONCLUSIÓN DIAGNÓSTICA
    candidato/2 integra reglas de Nivel 2 para plantear hipótesis;
    diagnostico_posible/2 aplica los criterios de descarte.
    =========================================================================== */

%!  candidato(+Caso, ?Diagnostico) is nondet.
%   Hipótesis diagnóstica antes de aplicar las exclusiones entre diagnósticos.

% Parvovirosis: cuadro digestivo en un perro susceptible.
% La negación de la vacunación completa está dentro de susceptible_parvovirus/1.
candidato(Caso, parvovirosis) :-
    cuadro_digestivo(Caso),
    susceptible_parvovirus(Caso),
    cumple_perfil(Caso, parvovirosis).

% Moquillo: secreción nasal + fiebre en un perro sin protección vacunal.
candidato(Caso, moquillo) :-
    sin_proteccion_vacunal(Caso),
    cumple_perfil(Caso, moquillo).

% Dilatación-torsión gástrica: abdomen agudo con distensión y arcadas.
candidato(Caso, dilatacion_torsion_gastrica) :-
    abdomen_agudo(Caso),
    cumple_perfil(Caso, dilatacion_torsion_gastrica).

% Obstrucción uretral: retención urinaria en un gato macho.
candidato(Caso, obstruccion_uretral) :-
    Caso = caso(gato, _, macho, _),
    retencion_urinaria(Caso),
    cumple_perfil(Caso, obstruccion_uretral).

% Cistitis: al menos dos signos urinarios bajos (puede quedar excluida por
% la obstrucción uretral, ver excluye/2).
candidato(Caso, cistitis) :-
    cumple_perfil(Caso, cistitis).

% Intoxicación: basta con que se reporte la ingesta de una sustancia tóxica.
% once/1 evita una solución repetida por cada sustancia ingerida.
candidato(Caso, intoxicacion) :-
    once(exposicion_toxica(Caso, _)),
    cumple_perfil(Caso, intoxicacion).

% Golpe de calor: hipertermia probable y al menos un signo de apoyo.
candidato(Caso, golpe_de_calor) :-
    hipertermia_probable(Caso),
    cumple_perfil(Caso, golpe_de_calor).

% Obstrucción intestinal: vómito persistente y dos signos de apoyo.
candidato(Caso, obstruccion_intestinal) :-
    cuadro_digestivo(Caso),
    cumple_perfil(Caso, obstruccion_intestinal).

% Enfermedad renal crónica: poliuria + polidipsia en un paciente que NO es
% cachorro. NEGACIÓN POR FALLO con Especie y Edad ya instanciadas.
candidato(Caso, enfermedad_renal_cronica) :-
    Caso = caso(Especie, Edad, _, _),
    \+ etapa_vida(Especie, Edad, cachorro),
    cumple_perfil(Caso, enfermedad_renal_cronica).

% Gastroenteritis aguda inespecífica: cuadro digestivo SIN signos de alarma.
% NEGACIÓN POR FALLO: si hay cualquier signo de alarma el cuadro no puede
% considerarse una gastroenteritis inespecífica.
candidato(Caso, gastroenteritis_aguda) :-
    cuadro_digestivo(Caso),
    \+ signo_de_alarma(Caso),
    cumple_perfil(Caso, gastroenteritis_aguda).

% Diagnósticos aprendidos en el Modo Experto (Entregable 3): se concluyen
% cuando el caso cumple el perfil que definió el experto. El hecho
% diagnostico_aprendido/3 va primero para que esta cláusula no se aplique a
% los diagnósticos originales del catálogo.
candidato(Caso, Diagnostico) :-
    diagnostico_aprendido(Diagnostico, _, _),
    cumple_perfil(Caso, Diagnostico).

%!  excluido(+Caso, +Diagnostico) is semidet.
%   Un diagnóstico se excluye si otro diagnóstico dominante es candidato.
%   CORTE: basta con encontrar una exclusión.
%   Llama a candidato/2 y no a diagnostico_posible/2: así se evitan ciclos.
excluido(Caso, Diagnostico) :-
    excluye(Dominante, Diagnostico),
    candidato(Caso, Dominante), !.

%!  diagnostico_posible(+Caso, ?Diagnostico) is nondet.
%   NEGACIÓN POR FALLO: Diagnostico ya está instanciado por candidato/2
%   cuando se evalúa \+ excluido/2.
diagnostico_posible(Caso, Diagnostico) :-
    candidato(Caso, Diagnostico),
    \+ excluido(Caso, Diagnostico).


/*  ===========================================================================
    SECCIÓN 6. SEVERIDAD, CERTEZA Y PRIORIDAD
    =========================================================================== */

%!  severidad(+Caso, +Diagnostico, -Nivel) is det.
%   1) Un signo de alarma fija el nivel en critico.
%   2) En otro caso: nivel base del diagnóstico (o de la sustancia tóxica),
%      subido un nivel por cada factor agravante.
%   CORTE: la primera cláusula, cuando aplica, anula la segunda.
severidad(Caso, _, Nivel) :-
    signo_de_alarma(Caso), !,
    Nivel = critico.
severidad(Caso, Diagnostico, Nivel) :-
    nivel_base(Caso, Diagnostico, Base),
    agravantes(Caso, Diagnostico, Agravantes),
    length(Agravantes, K),
    subir_niveles(Base, K, Nivel).

%!  nivel_base(+Caso, +Diagnostico, -Nivel) is det.
%   CORTE: la intoxicación tiene su propio cálculo; las demás usan el hecho
%   severidad_base/2.
nivel_base(Caso, intoxicacion, Nivel) :- !,
    severidad_intoxicacion(Caso, Nivel).
nivel_base(_, Diagnostico, Nivel) :-
    severidad_base(Diagnostico, Nivel).

%!  severidad_intoxicacion(+Caso, -Nivel) is det.
%   Toma el nivel más alto entre todas las sustancias ingeridas.
severidad_intoxicacion(Caso, Nivel) :-
    Caso = caso(Especie, _, _, _),
    findall(Peso-N,
            ( exposicion_toxica(Caso, S),
              toxicidad_para(S, Especie, N),
              nivel_valor(N, Peso) ),
            Pares),
    max_member(_-Nivel, Pares).

%!  toxicidad_para(+Sustancia, +Especie, -Nivel) is det.
%   CORTE + FALLBACK: si la combinación sustancia/especie está registrada se
%   usa ese nivel; si no, se aplica el nivel por defecto de intoxicacion.
toxicidad_para(Sustancia, Especie, Nivel) :-
    toxicidad(Sustancia, Especie, N), !,
    Nivel = N.
toxicidad_para(_, _, Nivel) :-
    severidad_base(intoxicacion, Nivel).

%!  agravantes(+Caso, +Diagnostico, -Lista) is det.
%   CORTE: los cuadros crónicos no se agravan por condiciones del paciente;
%   para los agudos se recogen todos los agravantes presentes.
agravantes(_, Diagnostico, []) :-
    curso(Diagnostico, cronico), !.
agravantes(Caso, _, Lista) :-
    findall(A, agravante(Caso, A), Lista).

%!  agravante(+Caso, ?Agravante) is nondet.
agravante(Caso, paciente_vulnerable) :-
    paciente_vulnerable(Caso).
agravante(Caso, deshidratacion) :-
    deshidratacion(Caso).
agravante(Caso, compromiso_neurologico) :-
    compromiso_neurologico(Caso).

%!  subir_niveles(+Nivel, +K, -NivelFinal) is det.
%   Sube K niveles en la escala (critico es el tope).
%   CORTE: K = 0 es el caso base y excluye a la cláusula recursiva.
subir_niveles(Nivel0, 0, Nivel) :- !,
    Nivel = Nivel0.
subir_niveles(Nivel0, K, Nivel) :-
    K > 0,
    siguiente_nivel(Nivel0, Nivel1),
    K1 is K - 1,
    subir_niveles(Nivel1, K1, Nivel).

%!  certeza(+Caso, +Diagnostico, -Porcentaje) is det.
%   Factor de certeza simplificado: certeza base + 0.10 por cada signo de
%   apoyo presente, con tope de 0.95. Se devuelve en porcentaje entero.
certeza(caso(_, _, _, H), Diagnostico, Porcentaje) :-
    certeza_base(Diagnostico, Base),
    apoyo(Diagnostico, Apoyo),
    contar_presentes(Apoyo, H, N),
    Factor is min(0.95, Base + 0.10 * N),
    Porcentaje is round(Factor * 100).

%!  sustento(+Caso, +Diagnostico, -Hallazgos) is det.
%   Hallazgos del caso que respaldan el diagnóstico (explicación).
%   CORTE: la intoxicación agrega además las ingestas reportadas.
sustento(Caso, intoxicacion, Hallazgos) :- !,
    Caso = caso(_, _, _, H),
    findall(I, (member(I, H), sustancia(I, _)), Ingestas),
    perfil_presente(intoxicacion, H, Signos),
    append(Ingestas, Signos, Hallazgos).
sustento(caso(_, _, _, H), Diagnostico, Hallazgos) :-
    perfil_presente(Diagnostico, H, Hallazgos).

perfil_presente(Diagnostico, H, Presentes) :-
    requisito(Diagnostico, Requisitos),
    apoyo(Diagnostico, Apoyo),
    append(Requisitos, Apoyo, Todos),
    interseccion(Todos, H, Presentes).

%!  nivel_maximo(+Diagnosticos, -Nivel) is det.
%   Recorre la lista de diagnósticos detallados y devuelve el nivel mayor.
%   CORTE: la lista de un solo elemento es el caso base.
nivel_maximo([[_, _, N|_]], Nivel) :- !,
    Nivel = N.
nivel_maximo([[_, _, Nivel|_]|Resto], Maximo) :-
    nivel_maximo(Resto, MaximoResto),
    mayor_nivel(Nivel, MaximoResto, Maximo).

%   CORTE + FALLBACK: si A no es mayor o igual que B, el resultado es B.
mayor_nivel(A, B, Mayor) :-
    nivel_valor(A, VA),
    nivel_valor(B, VB),
    VA >= VB, !,
    Mayor = A.
mayor_nivel(_, B, B).

%!  prioridad_caso(+Caso, +Diagnosticos, -Prioridad) is det.
%   1) Sin hallazgos válidos -> indeterminado.
%   2) Con un signo de alarma -> critico (prevalece sobre todo lo demás).
%   3) En otro caso -> el nivel más alto entre los diagnósticos.
%   CORTE: las cláusulas se evalúan en orden de precedencia y son excluyentes.
prioridad_caso(caso(_, _, _, []), _, Prioridad) :- !,
    Prioridad = indeterminado.
prioridad_caso(Caso, _, Prioridad) :-
    signo_de_alarma(Caso), !,
    Prioridad = critico.
prioridad_caso(_, Diagnosticos, Prioridad) :-
    nivel_maximo(Diagnosticos, Prioridad).


/*  ===========================================================================
    SECCIÓN 7. META-PREDICADOS DE RECOLECCIÓN Y API PARA PYTHON
    =========================================================================== */

%!  preparar_caso(+Especie, +Edad, +Sexo, +Entrada, -Caso, -Ignorados) is semidet.
%   Valida la entrada recibida desde Python y construye el término caso/4.
%   entrada_segura/4 rechaza variables libres y átomos fuera de formato
%   antes de que lleguen a las reglas.
preparar_caso(Especie, Edad, Sexo, Entrada, Caso, Ignorados) :-
    entrada_segura(Especie, Edad, Sexo, Entrada),
    normalizar_entrada(Entrada, Validos, Ignorados),
    Caso = caso(Especie, Edad, Sexo, Validos),
    datos_paciente_validos(Caso).

%!  conclusiones(+Caso, -Diagnosticos) is det.
%   RECOLECCIÓN con setof/3: agrupa en una sola lista ordenada y SIN
%   DUPLICADOS todos los diagnósticos posibles del caso.
%   CORTE + FALLBACK:
%     - sin hallazgos válidos no se evalúa nada (lista vacía);
%     - setof/3 falla si no hay soluciones; en ese caso la última cláusula
%       devuelve el valor por defecto [sin_diagnostico_concluyente].
conclusiones(caso(_, _, _, []), []) :- !.
conclusiones(Caso, Diagnosticos) :-
    setof(D, diagnostico_posible(Caso, D), Diagnosticos), !.
conclusiones(_, [sin_diagnostico_concluyente]).

%!  detallar(+Caso, +Diagnostico, -Detalle) is det.
%   Detalle = [Id, Nombre, Severidad, Certeza, Indicacion, Sustento, Agravantes]
detallar(Caso, D, [D, Nombre, Nivel, Certeza, Indicacion, Sustento, Agravantes]) :-
    nombre_diagnostico(D, Nombre),
    severidad(Caso, D, Nivel),
    certeza(Caso, D, Certeza),
    indicacion_para(Caso, D, Indicacion),
    sustento(Caso, D, Sustento),
    agravantes(Caso, D, Agravantes).

%!  indicacion_para(+Caso, +Diagnostico, -Texto) is det.
%   CORTE + FALLBACK: si no hay diagnóstico pero sí signos de alarma, la
%   indicación genérica de "observar" sería peligrosa; se usa la de alarma.
%   En cualquier otro caso se usa la indicación propia del diagnóstico.
indicacion_para(Caso, sin_diagnostico_concluyente, Texto) :-
    signo_de_alarma(Caso), !,
    indicacion(alarma_sin_diagnostico, Texto).
indicacion_para(_, Diagnostico, Texto) :-
    indicacion(Diagnostico, Texto).

%!  diagnosticos_detallados(+Caso, -Detalles) is det.
%   Detalla cada conclusión y ordena de mayor a menor severidad y certeza.
diagnosticos_detallados(Caso, Ordenados) :-
    conclusiones(Caso, Diagnosticos),
    findall(Detalle,
            ( member(D, Diagnosticos),
              once(detallar(Caso, D, Detalle)) ),
            Detalles),
    ordenar_por_prioridad(Detalles, Ordenados).

ordenar_por_prioridad(Detalles, Ordenados) :-
    findall(Clave-Detalle,
            ( member(Detalle, Detalles),
              clave_orden(Detalle, Clave) ),
            Pares),
    sort(1, @>=, Pares, ParesOrdenados),
    pares_valores(ParesOrdenados, Ordenados).

clave_orden([_, _, Nivel, Certeza|_], Clave) :-
    nivel_valor(Nivel, Peso),
    Clave is Peso * 1000 + Certeza.

%!  catalogo_hallazgos(?Grupo, -Hallazgos) is nondet.
%   RECOLECCIÓN con setof/3 agrupando por Grupo: devuelve una solución por
%   cada grupo con la lista ordenada de sus hallazgos (menú de consola).
catalogo_hallazgos(Grupo, Hallazgos) :-
    setof(H, grupo_hallazgo(H, Grupo), Hallazgos).

%!  diagnosticar_todos(+Especie, +Edad, +Sexo, +Entrada, -Diagnosticos) is det.
%   PREDICADO PRINCIPAL DE RECOLECCIÓN: lista única y sin duplicados de
%   todas las conclusiones para el caso.
%   CORTE + FALLBACK: si los datos del paciente no son válidos se devuelve []
%   en lugar de fallar, para que Python nunca reciba un error.
diagnosticar_todos(Especie, Edad, Sexo, Entrada, Diagnosticos) :-
    preparar_caso(Especie, Edad, Sexo, Entrada, Caso, _), !,
    conclusiones(Caso, Diagnosticos).
diagnosticar_todos(_, _, _, _, []).

%!  analizar_caso(+Especie, +Edad, +Sexo, +Entrada,
%!                -Validos, -Ignorados, -Alarmas, -Diagnosticos,
%!                -Prioridad, -Recomendacion) is det.
%   Consulta completa invocada desde Python en una sola llamada.
%   CORTE + FALLBACK: si la entrada o los datos del paciente no son válidos
%   se responde con la prioridad datos_invalidos, sin lanzar errores.
analizar_caso(Especie, Edad, Sexo, Entrada,
              Validos, Ignorados, Alarmas, Diagnosticos, Prioridad, Recomendacion) :-
    preparar_caso(Especie, Edad, Sexo, Entrada, Caso, Ignorados), !,
    Caso = caso(_, _, _, Validos),
    alarmas_presentes(Caso, Alarmas),
    diagnosticos_detallados(Caso, Diagnosticos),
    prioridad_caso(Caso, Diagnosticos, Prioridad),
    recomendacion(Prioridad, Recomendacion).
analizar_caso(_, _, _, Entrada, [], Ignorados, [], [], datos_invalidos, Recomendacion) :-
    entrada_como_lista(Entrada, Ignorados),
    recomendacion(datos_invalidos, Recomendacion).

%   CORTE + FALLBACK: si la entrada no es una lista se envuelve en una.
entrada_como_lista(Entrada, Entrada) :-
    is_list(Entrada), !.
entrada_como_lista(Entrada, [Entrada]).


/*  ===========================================================================
    SECCIÓN 8. MÓDULO DE EXPLICABILIDAD ("¿POR QUÉ?")            [Entregable 2]
    Construye la traza de auditoría ("caja blanca") de cada conclusión:
      - un METAINTÉRPRETE DE DEMOSTRACIÓN que vuelve a probar la conclusión
        con las mismas cláusulas de la base (clause/2) y registra el árbol
        de reglas disparadas y los hallazgos que unificaron;
      - un METAINTÉRPRETE DE REFUTACIÓN ("¿por qué no?") que explica por qué
        falló una hipótesis: qué hallazgo falta o qué condición excluyente
        (\+) la descartó;
      - el análisis de cada hipótesis del catálogo (confirmada, excluida,
        bloqueada o parcial), que comparten este módulo y el de la Sección 9.
    PREVENCIÓN DE CICLOS: los metaintérpretes solo LEEN las reglas de las
    Secciones 3 a 7; ninguna de esas reglas llama a la Sección 8.
    =========================================================================== */

/* ---------------------------------------------------------------------------
   8.1 Hechos de apoyo a la explicación
   regla_explicable(?Patron, ?Nivel, ?Descripcion)
       Reglas que la traza abre. El resto de metas (hechos, utilidades de
       listas, aritmética) se ejecutan directamente y se registran como hojas.
       Los patrones específicos van antes que los genéricos.
   descripcion_negacion(?Patron, ?SiSeCumple, ?SiFalla)
       Lectura de cada negación por fallo (\+) usada en las reglas.
   nombre_nivel(?Nivel, ?Texto)
   nombre_agravante(?Agravante, ?Texto)
   --------------------------------------------------------------------------- */
% Nivel 3 - conclusión diagnóstica
regla_explicable(diagnostico_posible(_, _), 3,
    'Conclusión: la hipótesis es candidata y ningún diagnóstico dominante la excluye').
regla_explicable(candidato(_, parvovirosis), 3,
    'Parvovirosis: cuadro digestivo en un perro susceptible que cumple el perfil').
regla_explicable(candidato(_, moquillo), 3,
    'Moquillo: perro sin protección vacunal que cumple el perfil').
regla_explicable(candidato(_, dilatacion_torsion_gastrica), 3,
    'Dilatación-torsión gástrica: abdomen agudo con distensión y arcadas').
regla_explicable(candidato(_, obstruccion_uretral), 3,
    'Obstrucción uretral: retención urinaria en un gato macho').
regla_explicable(candidato(_, cistitis), 3,
    'Cistitis: al menos dos signos urinarios bajos').
regla_explicable(candidato(_, intoxicacion), 3,
    'Intoxicación: se reporta la ingesta de una sustancia tóxica').
regla_explicable(candidato(_, golpe_de_calor), 3,
    'Golpe de calor: hipertermia probable y al menos un signo de apoyo').
regla_explicable(candidato(_, obstruccion_intestinal), 3,
    'Obstrucción intestinal: vómito persistente y dos signos de apoyo').
regla_explicable(candidato(_, enfermedad_renal_cronica), 3,
    'Enfermedad renal crónica: poliuria y polidipsia en un paciente que no es cachorro').
regla_explicable(candidato(_, gastroenteritis_aguda), 3,
    'Gastroenteritis aguda: cuadro digestivo sin signos de alarma').
regla_explicable(candidato(_, Diagnostico), 3, Descripcion) :-
    diagnostico_aprendido(Diagnostico, Autor, _),
    nombre_diagnostico(Diagnostico, Nombre),
    format(atom(Descripcion),
           '~w: regla aprendida en Modo Experto (~w); el caso cumple su perfil',
           [Nombre, Autor]).
regla_explicable(candidato(_, _), 3,
    'Hipótesis diagnóstica').
regla_explicable(excluido(_, _), 3,
    'Exclusión: un diagnóstico dominante también es candidato').
% Nivel 2 - inferencia intermedia
regla_explicable(cumple_perfil(_, _), 2,
    'Perfil clínico: especie compatible, requisitos completos y apoyo mínimo').
regla_explicable(cuadro_digestivo(_), 2,
    'Cuadro digestivo: al menos un signo digestivo').
regla_explicable(abdomen_agudo(_), 2,
    'Abdomen agudo: dolor o distensión, con vómito persistente o arcadas').
regla_explicable(retencion_urinaria(_), 2,
    'Retención urinaria: esfuerzo para orinar sin producir orina').
regla_explicable(exposicion_toxica(_, _), 2,
    'Exposición tóxica: ingesta de una sustancia registrada').
regla_explicable(hipertermia_probable(_), 2,
    'Hipertermia probable: exposición al calor con jadeo excesivo').
regla_explicable(sin_proteccion_vacunal(_), 2,
    'Sin protección vacunal: no se reporta vacunación completa').
regla_explicable(susceptible_parvovirus(_), 2,
    'Susceptible a parvovirus: sin protección vacunal y cachorro o con esquema incompleto').
regla_explicable(signo_de_alarma(_), 2,
    'Signo de alarma: alarma directa o signos de shock').
regla_explicable(signos_de_shock(_), 2,
    'Signos de shock: depresión del estado general y perfusión deficiente').
regla_explicable(paciente_vulnerable(_), 2,
    'Paciente vulnerable: cachorro, geriátrico, gestante o con enfermedad crónica').
regla_explicable(deshidratacion(_), 2,
    'Deshidratación: dos o más indicadores de pérdida de líquidos').
regla_explicable(compromiso_neurologico(_), 2,
    'Compromiso neurológico: al menos un signo neurológico').
% Nivel 1 - validación preliminar
regla_explicable(etapa(_, _), 1,
    'Etapa de vida: clasificación de la edad según la especie').

descripcion_negacion(presente(vacunacion_completa, _),
    'No se reporta vacunación completa',
    'Se reporta vacunación completa: el paciente está protegido').
descripcion_negacion(etapa_vida(_, _, cachorro),
    'El paciente no es cachorro',
    'El paciente es cachorro').
descripcion_negacion(signo_de_alarma(_),
    'No hay signos de alarma',
    'Hay signos de alarma: el cuadro no puede considerarse inespecífico').
descripcion_negacion(excluido(_, _),
    'Ningún diagnóstico dominante la excluye',
    'Un diagnóstico dominante la excluye').

nombre_nivel(bajo,          'BAJO').
nombre_nivel(medio,         'MEDIO').
nombre_nivel(alto,          'ALTO').
nombre_nivel(critico,       'CRÍTICO').
nombre_nivel(indeterminado, 'INDETERMINADO').

nombre_agravante(paciente_vulnerable,
    'paciente vulnerable (cachorro, geriátrico, gestante o con enfermedad crónica)').
nombre_agravante(deshidratacion,         'deshidratación inferida').
nombre_agravante(compromiso_neurologico, 'compromiso neurológico').

/* ---------------------------------------------------------------------------
   8.2 Metaintérprete de demostración
   Nodos de la traza (términos internos):
     regla(Nivel, Meta, Hijos)     regla explicable que se disparó
     verificacion(Meta, Hijos)     comprobación de una lista de hallazgos
     hallazgo(H)                   hallazgo del caso que unificó
     negacion(Meta)                \+ Meta se cumplió (negación por fallo)
     dato(Atributo, Valor)         dato del paciente que se comprobó
     hecho(Meta)                   hecho de la base de conocimiento consultado
     condicion(Meta)               comparación verificada
   --------------------------------------------------------------------------- */

%!  explicable(+Meta, -Nivel) is semidet.
%   Meta corresponde a una regla que la traza debe abrir. subsumes_term/2
%   compara sin instanciar Meta.
%   CORTE: basta el primer patrón (el más específico) que la abarque.
explicable(Meta, Nivel) :-
    regla_explicable(Patron, Nivel, _),
    subsumes_term(Patron, Meta), !.

%!  descripcion_regla(+Meta, -Descripcion) is det.
%   CORTE + FALLBACK: descripción del patrón más específico o texto vacío.
descripcion_regla(Meta, Descripcion) :-
    regla_explicable(Patron, _, Descripcion),
    subsumes_term(Patron, Meta), !.
descripcion_regla(_, '').

%!  demostrar(+Caso, +Meta, -Nodos) is nondet.
%   METAINTÉRPRETE: demuestra Meta con las cláusulas de la base y devuelve
%   la lista de nodos que justifican la demostración.
%     - conjunción : concatena la justificación de cada meta;
%     - \+ Meta    : NEGACIÓN POR FALLO, se registra como negacion/1;
%     - once/1     : primera demostración de la meta interna;
%     - regla explicable: se resuelve con sus propias cláusulas (resolver/3);
%     - cualquier otra meta se ejecuta con call/1 y se registra como hoja.
%   CORTE: cada cláusula atiende una forma de meta; el corte impide que una
%   forma ya atendida se trate después como meta primitiva.
demostrar(_, true, []) :- !.
demostrar(Caso, (A, B), Nodos) :- !,
    demostrar(Caso, A, NodosA),
    demostrar(Caso, B, NodosB),
    append(NodosA, NodosB, Nodos).
demostrar(_, \+ Meta, [negacion(Meta)]) :- !,
    \+ Meta.
demostrar(Caso, once(Meta), Nodos) :- !,
    once(demostrar(Caso, Meta, Nodos)).
demostrar(Caso, Meta, [regla(Nivel, Meta, Hijos)]) :-
    explicable(Meta, Nivel), !,
    resolver(Caso, Meta, Hijos).
demostrar(Caso, Meta, Nodos) :-
    copy_term(Meta, Patron),
    call(Meta),
    hojas(Caso, Patron, Meta, Nodos).

%!  resolver(+Caso, +Meta, -Hijos) is nondet.
%   Resuelve una regla explicable con sus propias cláusulas (clause/2).
%   CORTE: respeta el corte de la cláusula original. Si el cuerpo tiene un
%   corte, la parte anterior se demuestra una sola vez y este corte descarta
%   las demás cláusulas de la regla, exactamente como haría Prolog.
resolver(Caso, Meta, Hijos) :-
    clause(Meta, Cuerpo),
    (   separar_corte(Cuerpo, Antes, Despues)
    ->  demostrar(Caso, Antes, HijosAntes), !,
        demostrar(Caso, Despues, HijosDespues),
        append(HijosAntes, HijosDespues, Hijos)
    ;   demostrar(Caso, Cuerpo, Hijos)
    ).

%!  separar_corte(+Cuerpo, -Antes, -Despues) is semidet.
%   Divide el cuerpo de una cláusula en la parte anterior y la posterior al
%   primer corte. Falla si el cuerpo no tiene corte.
%   CORTE: el corte puede estar solo o al inicio de la conjunción restante.
separar_corte(!, true, true) :- !.
separar_corte((!, Despues), true, Despues) :- !.
separar_corte((Meta, Resto), (Meta, Antes), Despues) :-
    separar_corte(Resto, Antes, Despues).

%!  hojas(+Caso, +Patron, +Meta, -Nodos) is det.
%   Convierte una meta primitiva ya demostrada en hojas de la traza. Patron
%   es la meta ANTES de ejecutarse: indica qué valores fijó la regla.
%   CORTE: cada cláusula reconoce una forma de meta; la última es el valor
%   por defecto (unificaciones internas que no aportan evidencia).
hojas(caso(_, _, _, H), _, presente(X, L), [hallazgo(X)]) :-
    L == H, !.
hojas(caso(_, _, _, H), _, memberchk(X, L), [hallazgo(X)]) :-
    L == H, !.
hojas(caso(_, _, _, H), _, member(X, L), [hallazgo(X)]) :-
    L == H, !.
hojas(caso(_, _, _, H), _, alguno_presente(L, Hs), [verificacion(alguno_presente(L, Hs), Nodos)]) :-
    Hs == H, !,
    interseccion(L, H, Presentes),
    hallazgos_a_nodos(Presentes, Nodos).
hojas(caso(_, _, _, H), _, contiene_todos(L, Hs), [verificacion(contiene_todos(L, Hs), Nodos)]) :-
    Hs == H, !,
    hallazgos_a_nodos(L, Nodos).
hojas(caso(_, _, _, H), _, contar_presentes(L, Hs, N), [verificacion(contar_presentes(L, Hs, N), Nodos)]) :-
    Hs == H, !,
    interseccion(L, H, Presentes),
    hallazgos_a_nodos(Presentes, Nodos).
hojas(_, _, etapa_vida(_, _, Etapa), [dato(etapa, Etapa)]) :- !.
hojas(_, _ = caso(Especie, _, Sexo, _), _, Nodos) :- !,
    findall(dato(Atributo, Valor),
            ( member(Atributo-Valor, [especie-Especie, sexo-Sexo]),
              nonvar(Valor) ),
            Nodos).
hojas(_, _, Meta, [hecho(Meta)]) :-
    es_hecho_base(Meta), !.
hojas(_, _, Meta, [condicion(Meta)]) :-
    es_condicion(Meta), !.
hojas(_, _, _, []).

%!  hallazgos_a_nodos(+Hallazgos, -Nodos) is det.
hallazgos_a_nodos(Hallazgos, Nodos) :-
    findall(hallazgo(H), member(H, Hallazgos), Nodos).

%!  es_hecho_base(+Meta) is semidet.
%   Meta es un hecho de la base de conocimiento (predicado sin reglas).
es_hecho_base(Meta) :-
    \+ predicate_property(Meta, built_in),
    predicate_property(Meta, number_of_rules(0)).

%!  es_condicion(+Meta) is semidet.
%   Comparaciones y pertenencias que la traza muestra como condiciones.
es_condicion(Meta) :-
    functor(Meta, Nombre, 2),
    memberchk(Nombre, [<, >, =<, >=, =:=, =\=, memberchk]).

/* ---------------------------------------------------------------------------
   8.3 Metaintérprete de refutación ("¿por qué no?")
   Nodos de fallo (términos internos):
     no_regla(Nivel, Meta, Alternativas)  la regla falló; una lista de fallos
                                          por cada cláusula (basta con que
                                          una de ellas llegue a cumplirse)
     falta(H)                             falta un hallazgo obligatorio
     falta_uno(Lista)                     falta al menos uno de la lista
     apoyo_insuficiente(K, Ausentes, Min) faltan K signos de apoyo
     excluyente(Meta, Evidencia)          \+ Meta falló porque Meta se cumple
     dato_incompatible(Atributo, Requerido, Actual)
     no_hecho(Meta)                       el hecho no existe en la base
     condicion_falsa(Meta)                una comparación no se cumplió
   --------------------------------------------------------------------------- */

%!  refutar(+Caso, +Meta, -Fallos) is det.
%   Meta falló para el caso; Fallos explica por qué.
%   CORTE: igual que en demostrar/3, una cláusula por cada forma de meta.
refutar(Caso, (A, B), Fallos) :- !,
    refutar_cuerpo(Caso, (A, B), Fallos).
refutar(Caso, \+ Meta, [excluyente(Meta, Evidencia)]) :- !,
    evidencia(Caso, Meta, Evidencia).
refutar(Caso, once(Meta), Fallos) :- !,
    refutar(Caso, Meta, Fallos).
refutar(Caso, Meta, Fallos) :-
    refutacion_especial(Caso, Meta, Fallos), !.
refutar(Caso, Meta, [no_regla(Nivel, Meta, Alternativas)]) :-
    explicable(Meta, Nivel), !,
    refutar_clausulas(Caso, Meta, Alternativas).
refutar(Caso, Meta, Fallos) :-
    refutar_primitiva(Caso, Meta, Fallos).

%!  evidencia(+Caso, +Meta, -Nodos) is det.
%   Demostración de una meta negada que sí se cumple (por qué falló el \+).
%   CORTE + FALLBACK: sin demostración se devuelve una evidencia vacía.
evidencia(Caso, Meta, Nodos) :-
    demostrar(Caso, Meta, Nodos), !.
evidencia(_, _, []).

%!  refutar_cuerpo(+Caso, +Cuerpo, -Fallos) is det.
%   Recorre la conjunción de izquierda a derecha. Las metas que se cumplen se
%   omiten y cada meta que falla se refuta. Si la meta fallida no comparte
%   variables libres con el resto del cuerpo, la revisión continúa para
%   informar TODO lo que falta; si las comparte, se detiene, porque el resto
%   depende de un valor que esa meta no llegó a producir.
%   CORTE: separa la conjunción de la meta simple.
refutar_cuerpo(Caso, (Meta, Resto), Fallos) :- !,
    refutar_meta(Caso, Meta, Resto, FallosMeta, Continuar),
    refutar_resto(Continuar, Caso, Resto, FallosResto),
    append(FallosMeta, FallosResto, Fallos).
refutar_cuerpo(Caso, Meta, Fallos) :-
    refutar_meta(Caso, Meta, true, Fallos, _).

%   CORTE + FALLBACK: si la meta se cumple no aporta fallos (y conserva sus
%   ligaduras para el resto del cuerpo); si falla, se refuta.
refutar_meta(_, Meta, _, [], si) :-
    once(Meta), !.
refutar_meta(Caso, Meta, Resto, Fallos, Continuar) :-
    refutar(Caso, Meta, Fallos),
    continuar(Meta, Resto, Continuar).

%   CORTE + FALLBACK: se continúa solo si las metas son independientes.
continuar(Meta, Resto, si) :-
    independientes(Meta, Resto), !.
continuar(_, _, no).

refutar_resto(si, Caso, Resto, Fallos) :- !,
    refutar_cuerpo(Caso, Resto, Fallos).
refutar_resto(no, _, _, []).

%!  independientes(+MetaA, +MetaB) is semidet.
%   Las metas no comparten variables libres.
independientes(MetaA, MetaB) :-
    term_variables(MetaA, VariablesA),
    term_variables(MetaB, VariablesB),
    \+ ( member(X, VariablesA), member(Y, VariablesB), X == Y ).

%!  refutar_clausulas(+Caso, +Meta, -Alternativas) is det.
%   Una lista de fallos por cada cláusula cuya cabeza unifica con Meta: la
%   regla falló porque fallaron todas.
refutar_clausulas(Caso, Meta, Alternativas) :-
    findall(Cuerpo, ( clause(Meta, Cuerpo), \+ clausula_ajena(Cuerpo) ), Cuerpos),
    refutar_alternativas(Caso, Cuerpos, Alternativas).

%!  clausula_ajena(+Cuerpo) is semidet.
%   La cláusula genérica de los diagnósticos aprendidos (Sección 5) unifica
%   con cualquier candidato/2; para un diagnóstico que no fue aprendido no
%   es una alternativa real y no debe aparecer en el árbol de refutación.
clausula_ajena((diagnostico_aprendido(D, _, _), _)) :-
    \+ diagnostico_aprendido(D, _, _).

%   CORTE: si la parte anterior al corte de una cláusula se cumplió, Prolog
%   no habría probado las cláusulas siguientes; la revisión se detiene ahí y
%   solo se refuta la parte posterior al corte.
refutar_alternativas(_, [], []).
refutar_alternativas(Caso, [Cuerpo|_], [Fallos]) :-
    separar_corte(Cuerpo, Antes, Despues),
    once(Antes), !,
    refutar_cuerpo(Caso, Despues, Fallos).
refutar_alternativas(Caso, [Cuerpo|Cuerpos], [Fallos|Alternativas]) :-
    parte_evaluada(Cuerpo, Parte),
    refutar_cuerpo(Caso, Parte, Fallos),
    refutar_alternativas(Caso, Cuerpos, Alternativas).

%   CORTE + FALLBACK: de una cláusula con corte solo se evalúa lo anterior.
parte_evaluada(Cuerpo, Antes) :-
    separar_corte(Cuerpo, Antes, _), !.
parte_evaluada(Cuerpo, Cuerpo).

%!  refutacion_especial(+Caso, +Meta, -Fallos) is semidet.
%   Refutaciones de reglas explicables con una lectura más precisa que la
%   genérica: el perfil clínico (revisa todas sus condiciones) y la
%   exposición tóxica (falta cualquier ingesta registrada).
refutacion_especial(Caso, cumple_perfil(C, Diagnostico),
                    [no_regla(2, cumple_perfil(C, Diagnostico), [Fallos])]) :-
    refutar_perfil(Caso, Diagnostico, Fallos).
refutacion_especial(_, exposicion_toxica(C, S),
                    [no_regla(2, exposicion_toxica(C, S), [[falta_uno(Ingestas)]])]) :-
    findall(Ingesta, sustancia(Ingesta, _), Ingestas).

%!  refutar_perfil(+Caso, +Diagnostico, -Fallos) is det.
%   Revisa por separado las tres condiciones de cumple_perfil/2 (especie,
%   requisitos y apoyo mínimo) para informar todo lo que falta.
refutar_perfil(caso(Especie, _, _, H), Diagnostico, Fallos) :-
    fallo_especie(Diagnostico, Especie, FallosEspecie),
    requisito(Diagnostico, Requisitos),
    diferencia(Requisitos, H, Faltantes),
    findall(falta(F), member(F, Faltantes), FallosRequisitos),
    fallo_apoyo(Diagnostico, H, FallosApoyo),
    append([FallosEspecie, FallosRequisitos, FallosApoyo], Fallos).

%   CORTE + FALLBACK: especie compatible o lista de especies admitidas.
fallo_especie(Diagnostico, Especie, []) :-
    especie_afectada(Diagnostico, Especie), !.
fallo_especie(Diagnostico, Especie, [dato_incompatible(especie, Admitidas, Especie)]) :-
    findall(E, especie_afectada(Diagnostico, E), Admitidas).

%   CORTE + FALLBACK: apoyo suficiente o cuántos signos faltan y cuáles.
fallo_apoyo(Diagnostico, H, []) :-
    apoyo(Diagnostico, Apoyo),
    contar_presentes(Apoyo, H, N),
    minimo_apoyo(Diagnostico, Minimo),
    N >= Minimo, !.
fallo_apoyo(Diagnostico, H, [apoyo_insuficiente(K, Ausentes, Minimo)]) :-
    apoyo(Diagnostico, Apoyo),
    contar_presentes(Apoyo, H, N),
    minimo_apoyo(Diagnostico, Minimo),
    K is Minimo - N,
    diferencia(Apoyo, H, Ausentes).

%!  refutar_primitiva(+Caso, +Meta, -Fallos) is det.
%   Explica el fallo de una meta primitiva.
%   CORTE: cada cláusula reconoce una forma de meta; la última es el valor
%   por defecto.
refutar_primitiva(caso(_, _, _, H), presente(X, L), [falta(X)]) :-
    L == H, !.
refutar_primitiva(caso(_, _, _, H), memberchk(X, L), [falta(X)]) :-
    L == H, !.
refutar_primitiva(caso(_, _, _, H), alguno_presente(L, Hs), [falta_uno(L)]) :-
    Hs == H, !.
refutar_primitiva(caso(_, _, _, H), contiene_todos(L, Hs), Fallos) :-
    Hs == H, !,
    diferencia(L, H, Faltantes),
    findall(falta(F), member(F, Faltantes), Fallos).
refutar_primitiva(caso(Especie, _, Sexo, _), _ = caso(EspecieReq, _, SexoReq, _), Fallos) :- !,
    findall(dato_incompatible(Atributo, Requerido, Actual),
            ( member(Atributo-Requerido-Actual,
                     [especie-EspecieReq-Especie, sexo-SexoReq-Sexo]),
              nonvar(Requerido),
              Requerido \== Actual ),
            Fallos).
refutar_primitiva(Caso, etapa_vida(_, _, Etapa), [dato_incompatible(etapa, Etapa, Actual)]) :- !,
    etapa(Caso, Actual).
refutar_primitiva(_, Meta, [no_hecho(Meta)]) :-
    es_hecho_base(Meta), !.
refutar_primitiva(_, Meta, [condicion_falsa(Meta)]).

/* ---------------------------------------------------------------------------
   8.4 Recolección de la traza
   --------------------------------------------------------------------------- */

%!  nodo_en(+Nodos, -Nodo) is nondet.
%   Recorre el árbol en preorden: cada nodo antes que sus hijos.
nodo_en(Nodos, Nodo) :-
    member(N, Nodos),
    (   Nodo = N
    ;   hijos_de(N, Hijos),
        nodo_en(Hijos, Nodo)
    ).

hijos_de(regla(_, _, Hijos), Hijos).
hijos_de(verificacion(_, Hijos), Hijos).

%!  reglas_disparadas(+Caso, +Nodos, -Reglas) is det.
%   Lista sin duplicados de las reglas (finales e intermedias) que se
%   dispararon, en el orden en que aparecen en el árbol:
%   [Nivel, Etiqueta, Descripcion].
reglas_disparadas(Caso, Nodos, Reglas) :-
    findall([Nivel, Etiqueta, Descripcion],
            ( nodo_en(Nodos, regla(Nivel, Meta, _)),
              etiqueta(Caso, Meta, Etiqueta),
              descripcion_regla(Meta, Descripcion) ),
            Todas),
    list_to_set(Todas, Reglas).

%!  hechos_verificados(+Nodos, -Hallazgos) is det.
%   Hallazgos ingresados por el usuario que unificaron durante la
%   demostración (ordenados y sin duplicados).
hechos_verificados(Nodos, Hallazgos) :-
    findall(H, nodo_en(Nodos, hallazgo(H)), Todos),
    sort(Todos, Hallazgos).

%!  datos_del_paciente(+Caso, -Datos) is det.
%   Datos del paciente validados por datos_paciente_validos/1.
datos_del_paciente(caso(Especie, Edad, Sexo, _),
                   [[especie, Especie], [edad_meses, Edad], [sexo, Sexo], [etapa, Etapa]]) :-
    etapa_vida(Especie, Edad, Etapa).

/* ---------------------------------------------------------------------------
   8.5 Justificación de la severidad y de la certeza
   --------------------------------------------------------------------------- */

%!  texto_severidad(+Caso, +Diagnostico, -Pasos) is det.
%   Reconstruye paso a paso cómo severidad/3 llegó al nivel final.
%   CORTE: replica la precedencia de severidad/3 (la alarma anula el resto).
texto_severidad(Caso, _, [Texto]) :-
    signo_de_alarma(Caso), !,
    alarmas_presentes(Caso, Alarmas),
    maplist(nombre_alarma, Alarmas, Nombres),
    enumerar(Nombres, Lista),
    format(atom(Texto),
           'Signo de alarma presente (~w): la primera cláusula de severidad/3 fija el nivel en CRÍTICO, sin importar el diagnóstico.',
           [Lista]).
texto_severidad(Caso, Diagnostico, [TextoBase|Resto]) :-
    nivel_base(Caso, Diagnostico, Base),
    texto_nivel_base(Diagnostico, Base, TextoBase),
    agravantes(Caso, Diagnostico, Agravantes),
    textos_agravantes(Diagnostico, Agravantes, TextosAgravantes),
    severidad(Caso, Diagnostico, Nivel),
    nombre_nivel(Nivel, NombreNivel),
    format(atom(TextoFinal), 'Nivel final: ~w.', [NombreNivel]),
    append(TextosAgravantes, [TextoFinal], Resto).

%   CORTE: la intoxicación tiene su propio nivel base.
texto_nivel_base(intoxicacion, Base, Texto) :- !,
    nombre_nivel(Base, Nombre),
    format(atom(Texto),
           'Nivel base: ~w, el de la sustancia más tóxica ingerida para la especie (toxicidad/3).',
           [Nombre]).
texto_nivel_base(_, Base, Texto) :-
    nombre_nivel(Base, Nombre),
    format(atom(Texto), 'Nivel base: ~w (severidad_base/2).', [Nombre]).

%   CORTE + FALLBACK: crónico, sin agravantes o un texto por agravante.
textos_agravantes(Diagnostico, _, ['Cuadro crónico: los agravantes no se aplican (curso/2).']) :-
    curso(Diagnostico, cronico), !.
textos_agravantes(_, [], ['Sin factores agravantes: se mantiene el nivel base.']) :- !.
textos_agravantes(_, Agravantes, Textos) :-
    findall(Texto,
            ( member(A, Agravantes),
              nombre_agravante(A, Nombre),
              format(atom(Texto), 'Agravante: ~w; sube un nivel (subir_niveles/3).', [Nombre]) ),
            Textos).

%   CORTE + FALLBACK: descripción del hecho signo_alarma/2 o del shock.
nombre_alarma(Signo, Nombre) :-
    signo_alarma(Signo, Nombre), !.
nombre_alarma(signos_de_shock, 'signos de shock').

%!  texto_certeza(+Caso, +Diagnostico, -Texto) is det.
%   Muestra el cálculo de certeza/3.
%   CORTE: distingue si se aplicó el tope de 0.95.
texto_certeza(Caso, Diagnostico, Texto) :-
    componentes_certeza(Caso, Diagnostico, Base, N, Suma, Porcentaje),
    Suma > 0.95, !,
    format(atom(Texto),
           'certeza_base ~2f + 0.10 × ~d signo(s) de apoyo = ~2f; se aplica el tope de 0.95 → ~d %.',
           [Base, N, Suma, Porcentaje]).
texto_certeza(Caso, Diagnostico, Texto) :-
    componentes_certeza(Caso, Diagnostico, Base, N, Suma, Porcentaje),
    format(atom(Texto),
           'certeza_base ~2f + 0.10 × ~d signo(s) de apoyo = ~2f → ~d %.',
           [Base, N, Suma, Porcentaje]).

componentes_certeza(Caso, Diagnostico, Base, N, Suma, Porcentaje) :-
    Caso = caso(_, _, _, H),
    certeza_base(Diagnostico, Base0),
    Base is float(Base0),
    apoyo(Diagnostico, Apoyo),
    contar_presentes(Apoyo, H, N),
    Suma is Base + 0.10 * N,
    certeza(Caso, Diagnostico, Porcentaje).

/* ---------------------------------------------------------------------------
   8.6 Análisis de las hipótesis del catálogo
   Lo comparten el panel de hipótesis descartadas (Sección 8) y el módulo
   de recomendación (Sección 9).
   --------------------------------------------------------------------------- */

%!  diagnostico_del_catalogo(?Diagnostico) is nondet.
%   Diagnósticos reales del catálogo (sin el valor por defecto).
diagnostico_del_catalogo(Diagnostico) :-
    nombre_diagnostico(Diagnostico, _),
    Diagnostico \== sin_diagnostico_concluyente.

%!  analizar_hipotesis(+Caso, +Diagnostico, -Analisis) is det.
%   Analisis = hipotesis(Estado, Coincidencias, Fallos, Requerimientos)
%     confirmada        la regla se disparó y nadie la excluye
%     excluida(Dom)     se disparó, pero el diagnóstico dominante Dom la
%                       excluye; Fallos es la demostración de la exclusión
%     parcial           falló, pero podría cumplirse con más hallazgos
%     bloqueada         falló por una condición que nuevos hallazgos no
%                       corrigen (\+, especie, sexo o edad)
%   Coincidencias: hallazgos del caso que pertenecen al perfil.
%   Requerimientos: lo que falta observar (solo para las parciales).
%   CORTE: los estados se evalúan en orden de precedencia.
analizar_hipotesis(Caso, D, hipotesis(confirmada, Coincidencias, [], [])) :-
    diagnostico_posible(Caso, D), !,
    coincidencias(Caso, D, Coincidencias).
analizar_hipotesis(Caso, D, hipotesis(excluida(Dominante), Coincidencias, Prueba, [])) :-
    candidato(Caso, D), !,
    once(( excluye(Dominante, D), candidato(Caso, Dominante) )),
    evidencia(Caso, excluido(Caso, D), Prueba),
    coincidencias(Caso, D, Coincidencias).
analizar_hipotesis(Caso, D, hipotesis(Estado, Coincidencias, Fallos, Requerimientos)) :-
    once(clause(candidato(Caso, D), Cuerpo)),
    refutar_cuerpo(Caso, Cuerpo, Fallos),
    coincidencias(Caso, D, Coincidencias),
    estado_por_fallos(Fallos, Estado),
    requerimientos_de(Estado, Fallos, Requerimientos).

%!  coincidencias(+Caso, +Diagnostico, -Coincidencias) is det.
coincidencias(caso(_, _, _, H), Diagnostico, Coincidencias) :-
    hallazgos_del_perfil(Diagnostico, Perfil),
    interseccion(Perfil, H, Coincidencias).

%!  hallazgos_del_perfil(+Diagnostico, -Perfil) is det.
%   Disparadores, requisitos y signos de apoyo del diagnóstico.
hallazgos_del_perfil(Diagnostico, Perfil) :-
    findall(I, disparador(Diagnostico, I), Disparadores),
    requisito(Diagnostico, Requisitos),
    apoyo(Diagnostico, Apoyo),
    append([Disparadores, Requisitos, Apoyo], Todos),
    list_to_set(Todos, Perfil).

%!  disparador(?Diagnostico, ?Hallazgo) is nondet.
%   Hallazgos que activan una regla aunque no figuren en su perfil: la
%   intoxicación se dispara con cualquier ingesta tóxica.
disparador(intoxicacion, Ingesta) :-
    sustancia(Ingesta, _).

%   CORTE + FALLBACK: parcial si todos los fallos son reparables.
estado_por_fallos(Fallos, parcial) :-
    todos_reparables(Fallos), !.
estado_por_fallos(_, bloqueada).

%   CORTE + FALLBACK: solo una hipótesis parcial tiene requerimientos.
requerimientos_de(parcial, Fallos, Requerimientos) :- !,
    requerimientos(Fallos, Brutos),
    simplificar(Brutos, Requerimientos).
requerimientos_de(_, _, []).

%!  reparable(+Fallo) is semidet.
%   El fallo se corrige agregando hallazgos. Las reglas son monótonas en los
%   hallazgos salvo en las negaciones por fallo: un \+ que ya falló, la
%   especie, el sexo o la edad no cambian al agregar hallazgos.
%   CORTE: en una regla con varias cláusulas basta una alternativa reparable.
reparable(falta(_)).
reparable(falta_uno(_)).
reparable(apoyo_insuficiente(_, _, _)).
reparable(no_regla(_, _, Alternativas)) :-
    member(Alternativa, Alternativas),
    todos_reparables(Alternativa), !.

todos_reparables([]).
todos_reparables([Fallo|Fallos]) :-
    reparable(Fallo),
    todos_reparables(Fallos).

%!  requerimientos(+Fallos, -Requerimientos) is det.
%   Traduce los fallos reparables a lo que habría que observar:
%     necesita(H)     el hallazgo H es obligatorio
%     uno_de(Lista)   basta uno de los hallazgos de Lista
%     k_de(K, Lista)  faltan K hallazgos cualesquiera de Lista
requerimientos([], []).
requerimientos([Fallo|Fallos], Requerimientos) :-
    requerimiento(Fallo, Propios),
    requerimientos(Fallos, Resto),
    append(Propios, Resto, Requerimientos).

%   CORTE + FALLBACK: en una regla con varias cláusulas se elige la
%   alternativa reparable más barata (la que exige menos hallazgos).
requerimiento(falta(H), [necesita(H)]) :- !.
requerimiento(falta_uno(Lista), [uno_de(Lista)]) :- !.
requerimiento(apoyo_insuficiente(K, Ausentes, _), [k_de(K, Ausentes)]) :- !.
requerimiento(no_regla(_, _, Alternativas), Requerimientos) :-
    findall(Costo-Simplificados,
            ( member(Alternativa, Alternativas),
              todos_reparables(Alternativa),
              requerimientos(Alternativa, Brutos),
              simplificar(Brutos, Simplificados),
              costo(Simplificados, Costo) ),
            Pares),
    keysort(Pares, [_-Requerimientos|_]), !.
requerimiento(_, []).

%!  simplificar(+Requerimientos, -Simplificados) is det.
%   Elimina lo que ya cubren los hallazgos obligatorios: un uno_de/1 que
%   contiene un obligatorio ya se cumple, y un k_de/2 descuenta los
%   obligatorios que también son de apoyo.
simplificar(Requerimientos, Simplificados) :-
    findall(H, member(necesita(H), Requerimientos), Obligatorios0),
    sort(Obligatorios0, Obligatorios),
    findall(necesita(H), member(H, Obligatorios), Necesita),
    findall(uno_de(L),
            ( member(uno_de(L), Requerimientos),
              \+ alguno_presente(L, Obligatorios) ),
            Unos0),
    sort(Unos0, Unos),
    findall(k_de(K, L),
            ( member(k_de(K0, L0), Requerimientos),
              descontar(K0, L0, Obligatorios, K, L),
              K > 0 ),
            Ks),
    append([Necesita, Unos, Ks], Simplificados).

descontar(K0, L0, Obligatorios, K, L) :-
    interseccion(L0, Obligatorios, Cubiertos),
    length(Cubiertos, C),
    K is K0 - C,
    diferencia(L0, Obligatorios, L).

%!  costo(+Requerimientos, -Costo) is det.
%   Número de hallazgos que habría que agregar.
costo([], 0).
costo([R|Rs], Costo) :-
    costo_requerimiento(R, C),
    costo(Rs, Resto),
    Costo is C + Resto.

%   CORTE + FALLBACK: k_de/2 cuesta K; los demás, uno.
costo_requerimiento(k_de(K, _), K) :- !.
costo_requerimiento(_, 1).

%!  fallo_bloqueante(+Fallos, -Fallo) is semidet.
%   Primer fallo NO reparable (el que bloquea la hipótesis). Solo desciende
%   en las reglas que tampoco son reparables.
fallo_bloqueante(Fallos, Fallo) :-
    member(F, Fallos),
    \+ reparable(F),
    bloqueante(F, Fallo), !.

%   CORTE: en una regla se busca dentro de sus alternativas; cualquier otro
%   fallo no reparable es el propio motivo.
bloqueante(no_regla(_, _, Alternativas), Fallo) :- !,
    member(Alternativa, Alternativas),
    fallo_bloqueante(Alternativa, Fallo).
bloqueante(Fallo, Fallo).

/* ---------------------------------------------------------------------------
   8.7 Textos y exportación de la traza a listas para Python
   Cada nodo se exporta como [Tipo, Nivel, Etiqueta, Descripcion, Hijos];
   PySwip lo entrega a Python como listas anidadas.
   --------------------------------------------------------------------------- */

%!  etiqueta(+Caso, +Termino, -Texto) is det.
%   Texto de un término para la traza: el caso completo se muestra como
%   «Caso» y su lista de hallazgos como «H».
etiqueta(Caso, Termino, Texto) :-
    abreviar(Caso, Termino, Abreviado),
    copy_term(Abreviado, Copia),
    numbervars(Copia, 0, _, [singletons(true)]),
    texto_termino(Copia, Texto).

%   CORTE: la negación y las comparaciones se escriben con espacios; el
%   resto, con la sintaxis estándar de Prolog.
texto_termino(\+ Meta, Texto) :- !,
    texto_termino(Meta, TextoMeta),
    format(atom(Texto), '\\+ ~w', [TextoMeta]).
texto_termino(Termino, Texto) :-
    compound(Termino),
    Termino =.. [Operador, A, B],
    memberchk(Operador, [<, >, =<, >=, =:=, =\=, =]), !,
    format(atom(Texto), '~W ~w ~W',
           [A, [numbervars(true)], Operador, B, [numbervars(true)]]).
texto_termino(Termino, Texto) :-
    format(atom(Texto), '~W',
           [Termino, [numbervars(true), spacing(next_argument), quoted(false)]]).

%   CORTE: el caso y su lista de hallazgos se reemplazan; los demás términos
%   compuestos se recorren argumento por argumento.
abreviar(Caso, Termino, 'Caso') :-
    Termino == Caso, !.
abreviar(caso(_, _, _, H), Termino, 'H') :-
    H \== [],
    Termino == H, !.
abreviar(Caso, Termino, Abreviado) :-
    compound(Termino), !,
    Termino =.. [Functor|Argumentos],
    maplist(abreviar(Caso), Argumentos, Abreviados),
    Abreviado =.. [Functor|Abreviados].
abreviar(_, Termino, Termino).

%!  nombre_legible(+Hallazgo, -Nombre) is det.
%   CORTE + FALLBACK: nombre registrado o el propio átomo.
nombre_legible(Hallazgo, Nombre) :-
    nombre_hallazgo(Hallazgo, Nombre), !.
nombre_legible(Hallazgo, Hallazgo).

%!  enumerar(+Textos, -Texto) is det.
%   'a, b o c'.
%   CORTE: casos de cero, uno y varios elementos.
enumerar([], '') :- !.
enumerar([Unico], Unico) :- !.
enumerar(Textos, Texto) :-
    append(Iniciales, [Ultimo], Textos),
    atomic_list_concat(Iniciales, ', ', Inicio),
    format(atom(Texto), '~w o ~w', [Inicio, Ultimo]).

%!  enumerar_hallazgos(+Hallazgos, -Texto) is det.
enumerar_hallazgos(Hallazgos, Texto) :-
    maplist(nombre_legible, Hallazgos, Nombres),
    enumerar(Nombres, Texto).

%!  texto_valor(+Valor, -Texto) is det.
%   CORTE + FALLBACK: una lista se enumera; un átomo se deja igual.
texto_valor(Valor, Texto) :-
    is_list(Valor), !,
    enumerar(Valor, Texto).
texto_valor(Valor, Valor).

%!  exportar_nodos(+Caso, +Nodos, -Listas) is det.
exportar_nodos(Caso, Nodos, Listas) :-
    maplist(exportar_nodo(Caso), Nodos, Listas).

%!  exportar_nodo(+Caso, +Nodo, -Lista) is det.
%   CORTE: una cláusula por tipo de nodo (el tipo se distingue en la cabeza).
exportar_nodo(Caso, regla(Nivel, Meta, Hijos), [regla, Nivel, Etiqueta, Descripcion, Listas]) :- !,
    etiqueta(Caso, Meta, Etiqueta),
    descripcion_regla(Meta, Descripcion),
    exportar_nodos(Caso, Hijos, Listas).
exportar_nodo(Caso, verificacion(Meta, Hijos), [verificacion, 0, Etiqueta, Descripcion, Listas]) :- !,
    etiqueta(Caso, Meta, Etiqueta),
    descripcion_verificacion(Meta, Descripcion),
    exportar_nodos(Caso, Hijos, Listas).
exportar_nodo(_, hallazgo(H), [hallazgo, 0, H, Nombre, []]) :- !,
    nombre_legible(H, Nombre).
exportar_nodo(Caso, negacion(Meta), [negacion, 0, Etiqueta, Descripcion, []]) :- !,
    etiqueta(Caso, \+ Meta, Etiqueta),
    lectura_negacion(Meta, Descripcion, _).
exportar_nodo(caso(_, Edad, _, _), dato(etapa, Etapa), [dato, 0, Etiqueta, Descripcion, []]) :- !,
    format(atom(Etiqueta), 'etapa = ~w', [Etapa]),
    format(atom(Descripcion), 'Etapa de vida según la edad (~d meses)', [Edad]).
exportar_nodo(_, dato(Atributo, Valor), [dato, 0, Etiqueta, 'Dato del paciente', []]) :- !,
    format(atom(Etiqueta), '~w = ~w', [Atributo, Valor]).
exportar_nodo(Caso, hecho(Meta), [hecho, 0, Etiqueta, 'Hecho de la base de conocimiento', []]) :- !,
    etiqueta(Caso, Meta, Etiqueta).
exportar_nodo(Caso, condicion(Meta), [condicion, 0, Etiqueta, 'Condición verificada', []]) :- !,
    etiqueta(Caso, Meta, Etiqueta).
exportar_nodo(Caso, no_regla(Nivel, Meta, [Fallos]), [no_regla, Nivel, Etiqueta, Descripcion, Listas]) :- !,
    etiqueta(Caso, Meta, Etiqueta),
    descripcion_regla(Meta, Descripcion),
    exportar_nodos(Caso, Fallos, Listas).
exportar_nodo(Caso, no_regla(Nivel, Meta, Alternativas), [no_regla, Nivel, Etiqueta, Descripcion, Listas]) :- !,
    etiqueta(Caso, Meta, Etiqueta),
    descripcion_regla(Meta, Descripcion),
    findall([alternativa, 0, Nombre, 'Esta cláusula tampoco se cumple', Sublistas],
            ( nth1(I, Alternativas, Fallos),
              format(atom(Nombre), 'Cláusula ~d', [I]),
              exportar_nodos(Caso, Fallos, Sublistas) ),
            Listas).
exportar_nodo(_, falta(H), [falta, 0, H, Descripcion, []]) :- !,
    nombre_legible(H, Nombre),
    format(atom(Descripcion), 'Falta «~w»: hallazgo obligatorio no ingresado', [Nombre]).
exportar_nodo(Caso, falta_uno(Lista), [falta_uno, 0, Etiqueta, Descripcion, []]) :- !,
    Caso = caso(_, _, _, H),
    etiqueta(Caso, alguno_presente(Lista, H), Etiqueta),
    enumerar_hallazgos(Lista, Texto),
    format(atom(Descripcion), 'Falta al menos uno de: ~w', [Texto]).
exportar_nodo(_, apoyo_insuficiente(K, Ausentes, Minimo), [apoyo_insuficiente, 0, Etiqueta, Descripcion, []]) :- !,
    format(atom(Etiqueta), 'contar_presentes(Apoyo, H, N), N < ~d', [Minimo]),
    enumerar_hallazgos(Ausentes, Texto),
    format(atom(Descripcion),
           'Faltan ~d signo(s) de apoyo para llegar al mínimo de ~d; pueden ser: ~w',
           [K, Minimo, Texto]).
exportar_nodo(Caso, excluyente(Meta, Evidencia), [excluyente, 0, Etiqueta, Descripcion, Listas]) :- !,
    etiqueta(Caso, \+ Meta, Etiqueta),
    lectura_negacion(Meta, _, Descripcion),
    exportar_nodos(Caso, Evidencia, Listas).
exportar_nodo(_, dato_incompatible(Atributo, Requerido, Actual), [dato_incompatible, 0, Etiqueta, Descripcion, []]) :- !,
    format(atom(Etiqueta), '~w = ~w', [Atributo, Actual]),
    texto_valor(Requerido, TextoRequerido),
    format(atom(Descripcion), 'La regla exige ~w: ~w; el paciente tiene ~w: ~w',
           [Atributo, TextoRequerido, Atributo, Actual]).
exportar_nodo(Caso, no_hecho(Meta), [no_hecho, 0, Etiqueta, 'No existe este hecho en la base de conocimiento', []]) :- !,
    etiqueta(Caso, Meta, Etiqueta).
exportar_nodo(Caso, condicion_falsa(Meta), [condicion_falsa, 0, Etiqueta, 'La condición no se cumple', []]) :-
    etiqueta(Caso, Meta, Etiqueta).

%!  descripcion_verificacion(+Meta, -Texto) is det.
%   CORTE: una lectura por cada utilidad de listas.
descripcion_verificacion(alguno_presente(_, _), 'Al menos uno de estos hallazgos está presente') :- !.
descripcion_verificacion(contiene_todos([], _), 'El perfil no exige hallazgos obligatorios') :- !.
descripcion_verificacion(contiene_todos(_, _), 'Todos los hallazgos obligatorios están presentes') :- !.
descripcion_verificacion(contar_presentes(_, _, N), Texto) :-
    format(atom(Texto), 'Hay ~d signo(s) de apoyo presentes', [N]).

%!  lectura_negacion(+Meta, -SiSeCumple, -SiFalla) is det.
%   CORTE + FALLBACK: lectura registrada o una genérica.
lectura_negacion(Meta, SiSeCumple, SiFalla) :-
    descripcion_negacion(Patron, SiSeCumple, SiFalla),
    subsumes_term(Patron, Meta), !.
lectura_negacion(_, 'La condición negada no se cumple (negación por fallo)',
                    'La condición negada sí se cumple').

%!  explicacion(+Caso, +Diagnostico, -Explicacion) is det.
%   Explicacion = [Id, Nombre, Arbol, Reglas, Hechos, Datos, Severidad, Certeza]
%   CORTE: el valor por defecto no tiene demostración propia; se explica con
%   la cláusula por defecto de conclusiones/2.
explicacion(Caso, sin_diagnostico_concluyente,
            [sin_diagnostico_concluyente, Nombre, [Nodo], [], [], Datos, Severidad, Certeza]) :- !,
    nombre_diagnostico(sin_diagnostico_concluyente, Nombre),
    Nodo = [regla, 3, 'conclusiones(Caso, [sin_diagnostico_concluyente])',
            'Ninguna regla candidato/2 se cumplió: setof/3 falló y se aplica el valor por defecto de conclusiones/2',
            []],
    datos_del_paciente(Caso, Datos),
    texto_severidad(Caso, sin_diagnostico_concluyente, Severidad),
    texto_certeza(Caso, sin_diagnostico_concluyente, Certeza).
explicacion(Caso, D, [D, Nombre, Arbol, Reglas, Hechos, Datos, Severidad, Certeza]) :-
    nombre_diagnostico(D, Nombre),
    once(demostrar(Caso, diagnostico_posible(Caso, D), Nodos)),
    exportar_nodos(Caso, Nodos, Arbol),
    reglas_disparadas(Caso, Nodos, Reglas),
    hechos_verificados(Nodos, Hechos),
    datos_del_paciente(Caso, Datos),
    texto_severidad(Caso, D, Severidad),
    texto_certeza(Caso, D, Certeza).

%!  descartada(+Caso, -Descartada) is nondet.
%   Hipótesis del catálogo que comparte al menos un hallazgo con el caso
%   pero no se concluyó. Descartada = Compartidos-[Id, Nombre, Tipo,
%   Resumen, Compartidos, Arbol].
descartada(Caso, N-[D, Nombre, Tipo, Resumen, Coincidencias, Arbol]) :-
    diagnostico_del_catalogo(D),
    analizar_hipotesis(Caso, D, hipotesis(Estado, Coincidencias, Fallos, Requerimientos)),
    Estado \== confirmada,
    Coincidencias \== [],
    length(Coincidencias, N),
    nombre_diagnostico(D, Nombre),
    motivo_descarte(Estado, Fallos, Requerimientos, Tipo, Resumen),
    raiz_descarte(Caso, D, Estado, Fallos, Raiz),
    exportar_nodos(Caso, Raiz, Arbol).

%   CORTE + FALLBACK: la exclusión ya trae su propia raíz (excluido/2); en
%   los demás estados los fallos cuelgan de la regla candidato/2 que falló.
raiz_descarte(_, _, excluida(_), Prueba, Prueba) :- !.
raiz_descarte(Caso, D, _, Fallos, [no_regla(3, candidato(Caso, D), [Fallos])]).

%!  motivo_descarte(+Estado, +Fallos, +Requerimientos, -Tipo, -Resumen) is det.
%   Tipo: exclusion | condicion_excluyente | dato_paciente |
%         evidencia_insuficiente | regla
%   CORTE: una cláusula por estado y por clase de fallo bloqueante.
motivo_descarte(excluida(Dominante), _, _, exclusion, Resumen) :- !,
    nombre_diagnostico(Dominante, Nombre),
    format(atom(Resumen),
           'Se descarta porque «~w» también se cumple y la excluye (excluye/2): explica mejor los mismos hallazgos.',
           [Nombre]).
motivo_descarte(parcial, _, Requerimientos, evidencia_insuficiente, Resumen) :- !,
    textos_requerimientos(Requerimientos, Textos),
    atomic_list_concat(Textos, '; ', Lista),
    format(atom(Resumen), 'Falta evidencia crítica: ~w.', [Lista]).
motivo_descarte(bloqueada, Fallos, _, condicion_excluyente, Resumen) :-
    fallo_bloqueante(Fallos, excluyente(Meta, _)), !,
    lectura_negacion(Meta, _, SiFalla),
    format(atom(Resumen), 'Descartada por una condición excluyente (\\+): ~w.', [SiFalla]).
motivo_descarte(bloqueada, Fallos, _, dato_paciente, Resumen) :-
    fallo_bloqueante(Fallos, dato_incompatible(Atributo, Requerido, Actual)), !,
    texto_valor(Requerido, TextoRequerido),
    format(atom(Resumen), 'No aplica a este paciente: la regla exige ~w ~w y el paciente es ~w.',
           [Atributo, TextoRequerido, Actual]).
motivo_descarte(_, _, _, regla, 'La regla no puede cumplirse con los datos del paciente.').

%!  textos_requerimientos(+Requerimientos, -Textos) is det.
textos_requerimientos(Requerimientos, Textos) :-
    maplist(texto_requerimiento, Requerimientos, Textos).

%   CORTE: una lectura por forma de requerimiento.
texto_requerimiento(necesita(H), Texto) :- !,
    nombre_legible(H, Nombre),
    format(atom(Texto), '«~w» (obligatorio)', [Nombre]).
texto_requerimiento(uno_de(Lista), Texto) :- !,
    enumerar_hallazgos(Lista, Opciones),
    format(atom(Texto), 'al menos uno de: ~w', [Opciones]).
texto_requerimiento(k_de(K, Lista), Texto) :-
    enumerar_hallazgos(Lista, Opciones),
    format(atom(Texto), '~d signo(s) de apoyo más entre: ~w', [K, Opciones]).


/*  ===========================================================================
    SECCIÓN 9. MÓDULO DE RECOMENDACIÓN ("¿QUÉ FALTA?")           [Entregable 2]
    Cuando la evidencia no alcanza para un dictamen definitivo (o hay un
    empate), evalúa las hipótesis parcialmente activas y pondera cada
    hallazgo aún no ingresado para decidir qué conviene preguntar primero.
    Peso de una pregunta = Σ peso_rol × gravedad × activación / 100 sobre
    las hipótesis en competencia; se multiplica por el factor de desempate si
    la pregunta favorece claramente a una sola de ellas. En un empate solo
    se ponderan las dos hipótesis empatadas.
    =========================================================================== */

/* ---------------------------------------------------------------------------
   9.1 Hechos del módulo de recomendación
   parametro(?Nombre, ?Valor)
   peso_rol(?Rol, ?Peso)            importancia del hallazgo para la hipótesis
   nombre_rol(?Rol, ?Texto)
   incompatibles(?HallazgoA, ?HallazgoB)   no pueden presentarse a la vez
   pregunta(?Hallazgo, ?Texto)      cómo preguntárselo al tutor
   como_verificar(?Hallazgo, ?Texto) prueba sencilla que puede hacer el tutor
   --------------------------------------------------------------------------- */
parametro(umbral_confirmacion, 80).   % certeza mínima (%) de un dictamen definitivo
parametro(margen_empate,        5).   % diferencia de certeza (%) que se considera empate
parametro(factor_desempate,     3).   % multiplicador de la pregunta que desempata

peso_rol(requisito,   3).
peso_rol(alternativa, 3).
peso_rol(minimo,      2).
peso_rol(refuerzo,    1).

nombre_rol(requisito,   'Hallazgo obligatorio de').
nombre_rol(alternativa, 'Requisito (basta uno de ellos) de').
nombre_rol(minimo,      'Signo de apoyo que falta para el mínimo de').
nombre_rol(refuerzo,    'Signo de apoyo que refuerza').

incompatibles(vacunacion_completa, vacunacion_incompleta).

% Signos digestivos
pregunta(vomito,                 '¿Ha vomitado en las últimas horas?').
pregunta(vomito_persistente,     '¿El vómito es repetido (más de 3 veces en el día) o no cede?').
pregunta(diarrea,                '¿Tiene diarrea?').
pregunta(diarrea_con_sangre,     '¿La diarrea tiene sangre roja o es negra?').
pregunta(arcadas_improductivas,  '¿Hace arcadas o intenta vomitar sin expulsar nada?').
pregunta(abdomen_distendido,     '¿El abdomen se ve hinchado o tenso como un tambor?').
pregunta(dolor_abdominal,        '¿Se queja o se encorva cuando le tocan el abdomen?').
pregunta(salivacion_excesiva,    '¿Babea más de lo habitual?').
pregunta(anorexia,               '¿Dejó de comer?').
pregunta(sin_defecar,            '¿Lleva más de 24 horas sin defecar?').
% Signos urinarios
pregunta(esfuerzo_para_orinar,   '¿Hace esfuerzo o adopta muchas veces la postura para orinar?').
pregunta(ausencia_de_orina,      '¿Al intentar orinar no sale orina o salen apenas unas gotas?').
pregunta(miccion_frecuente,      '¿Orina muchas veces y en poca cantidad?').
pregunta(sangre_en_orina,        '¿La orina tiene sangre o un color rojizo?').
pregunta(poliuria,               '¿Orina en mucha más cantidad de lo habitual?').
pregunta(polidipsia,             '¿Bebe mucha más agua de lo habitual?').
pregunta(lamido_genital,         '¿Se lame con insistencia la zona genital?').
% Signos respiratorios
pregunta(jadeo_excesivo,         '¿Jadea con intensidad aun estando en reposo?').
pregunta(dificultad_respiratoria, '¿Respira con dificultad, con la boca abierta o con ruido?').
pregunta(secrecion_nasal,        '¿Tiene secreción por la nariz?').
pregunta(tos,                    '¿Tose?').
% Signos neurológicos
pregunta(convulsiones,           '¿Ha tenido convulsiones?').
pregunta(temblores,              '¿Tiembla sin que haga frío?').
pregunta(desorientacion,         '¿Se ve desorientado, camina en círculos o no reconoce el entorno?').
pregunta(mioclonias,             '¿Tiene contracciones o tics musculares que se repiten?').
% Estado general
pregunta(letargo,                '¿Está decaído o duerme mucho más de lo normal?').
pregunta(fiebre,                 '¿Tiene fiebre (temperatura rectal mayor de 39.2 °C)?').
pregunta(encias_palidas,         '¿Las encías se ven pálidas o blancas?').
pregunta(encias_rojo_intenso,    '¿Las encías se ven de color rojo intenso?').
pregunta(llenado_capilar_lento,  '¿Al presionar la encía, el color tarda más de 2 segundos en volver?').
pregunta(colapso,                '¿Se desplomó o no puede levantarse?').
pregunta(perdida_de_peso,        '¿Ha perdido peso en las últimas semanas?').
pregunta(halitosis_uremica,      '¿Su aliento huele a orina o a amoníaco?').
pregunta(ojos_hundidos,          '¿Los ojos se ven hundidos?').
pregunta(piel_sin_elasticidad,   '¿Al pellizcar la piel del lomo, tarda en volver a su lugar?').
pregunta(inquietud,              '¿Está inquieto, se acuesta y se levanta sin encontrar posición?').
pregunta(vocalizacion_dolor,     '¿Llora, gime o maúlla de dolor?').
pregunta(hipotermia,             '¿Está frío al tacto o su temperatura rectal es menor de 37.5 °C?').
% Antecedentes
pregunta(vacunacion_completa,    '¿Tiene el esquema de vacunación completo y al día?').
pregunta(vacunacion_incompleta,  '¿La vacunación está incompleta o nunca fue vacunado?').
pregunta(gestante,               '¿Está gestante?').
pregunta(enfermedad_cronica_previa, '¿Tiene alguna enfermedad crónica ya diagnosticada?').
pregunta(raza_torax_profundo,    '¿Es de una raza grande de tórax profundo (gran danés, pastor alemán, bóxer)?').
pregunta(raza_braquicefala,      '¿Es de raza braquicéfala (bulldog, pug, persa)?').
pregunta(exposicion_calor,       '¿Estuvo expuesto a calor intenso (sol, carro cerrado, ejercicio en horas de calor)?').
pregunta(ingesta_objeto,         '¿Pudo haberse tragado un objeto (juguete, hueso, media, tela)?').
pregunta(ingesta_chocolate,      '¿Comió chocolate?').
pregunta(ingesta_xilitol,        '¿Comió algo con xilitol (chicles o dulces sin azúcar)?').
pregunta(ingesta_uvas,           '¿Comió uvas o uvas pasas?').
pregunta(ingesta_cebolla,        '¿Comió cebolla o ajo?').
pregunta(ingesta_ibuprofeno,     '¿Le dieron o se comió ibuprofeno?').
pregunta(ingesta_paracetamol,    '¿Le dieron o se comió paracetamol (acetaminofén)?').
pregunta(ingesta_lirio,          '¿Mordió o comió una planta de lirio?').
pregunta(ingesta_raticida,       '¿Pudo haber comido veneno para ratas?').

como_verificar(llenado_capilar_lento,
    'Presione la encía con un dedo hasta que se ponga blanca, suelte y cuente los segundos que tarda en volver el color rosado (lo normal es menos de 2 segundos).').
como_verificar(piel_sin_elasticidad,
    'Pellizque con suavidad la piel entre los omóplatos y suéltela: si tarda en volver a su lugar, hay deshidratación.').
como_verificar(fiebre,
    'Mida la temperatura rectal con un termómetro digital: lo normal en perros y gatos es de 38 a 39.2 °C.').
como_verificar(encias_palidas,
    'Levante el labio con buena luz y observe el color de las encías: lo normal es rosado.').
como_verificar(encias_rojo_intenso,
    'Levante el labio con buena luz y observe el color de las encías: lo normal es rosado.').
como_verificar(ojos_hundidos,
    'Observe si los ojos se ven hundidos en las órbitas o si se asoma el tercer párpado.').
como_verificar(ausencia_de_orina,
    'Observe al animal varios minutos en el arenero o en el paseo y verifique si realmente sale orina.').
como_verificar(abdomen_distendido,
    'Mire al animal de lado y desde arriba: el abdomen se ve abultado y al tocarlo está tenso o suena hueco.').

/* ---------------------------------------------------------------------------
   9.2 Estado de la evidencia
   --------------------------------------------------------------------------- */

%!  estado_evidencia(+Caso, +Detalles, -Estado) is det.
%   Detalles es la salida de diagnosticos_detallados/2 (ya ordenada).
%     sin_hallazgos          no hay hallazgos válidos
%     insuficiente           ningún perfil se completa
%     empate(D1, D2, C1, C2) los dos primeros tienen la misma severidad y
%                            certezas a no más de margen_empate puntos
%     certeza_baja(D, C)     el primero no alcanza el umbral de confirmación
%     definitivo(D, C)       dictamen definitivo
%   CORTE: los estados se evalúan en orden de precedencia. En el empate, la
%   severidad N se comparte en las dos cabezas: la unificación exige que sea
%   la misma.
estado_evidencia(caso(_, _, _, []), _, sin_hallazgos) :- !.
estado_evidencia(_, [[sin_diagnostico_concluyente|_]], insuficiente) :- !.
estado_evidencia(_, [[D1, _, N, C1|_], [D2, _, N, C2|_]|_], empate(D1, D2, C1, C2)) :-
    parametro(margen_empate, Margen),
    abs(C1 - C2) =< Margen, !.
estado_evidencia(_, [[D, _, _, C|_]|_], certeza_baja(D, C)) :-
    parametro(umbral_confirmacion, Umbral),
    C < Umbral, !.
estado_evidencia(_, [[D, _, _, C|_]|_], definitivo(D, C)).

%!  describir_estado(+Estado, -Tipo, -Activo, -Mensaje) is det.
%   Activo = si cuando corresponde activar el módulo de recomendación.
%   CORTE: una cláusula por estado.
describir_estado(sin_hallazgos, sin_hallazgos, no,
    'No se ingresaron hallazgos válidos: no hay hipótesis que evaluar.') :- !.
describir_estado(insuficiente, insuficiente, si,
    'Evidencia insuficiente: ningún perfil diagnóstico se completa con los hallazgos ingresados.') :- !.
describir_estado(empate(D1, D2, C1, C2), empate, si, Mensaje) :- !,
    nombre_diagnostico(D1, N1),
    nombre_diagnostico(D2, N2),
    parametro(margen_empate, Margen),
    format(atom(Mensaje),
           'Empate: «~w» (~d %) y «~w» (~d %) tienen la misma severidad y sus certezas difieren en ~d puntos o menos.',
           [N1, C1, N2, C2, Margen]).
describir_estado(certeza_baja(D, C), certeza_baja, si, Mensaje) :- !,
    nombre_diagnostico(D, Nombre),
    parametro(umbral_confirmacion, Umbral),
    format(atom(Mensaje),
           'Dictamen no definitivo: «~w» tiene una certeza de ~d %, por debajo del umbral de ~d %.',
           [Nombre, C, Umbral]).
describir_estado(definitivo(D, C), definitivo, no, Mensaje) :-
    nombre_diagnostico(D, Nombre),
    format(atom(Mensaje),
           'Dictamen definitivo: «~w», con una certeza de ~d %. No se requiere información adicional.',
           [Nombre, C]).

/* ---------------------------------------------------------------------------
   9.3 Hipótesis en competencia
   comp(Diagnostico, Estado, Activacion, Coincidencias, Requerimientos)
     Estado: confirmada | parcial | refutada_usuario
     Activacion: % del perfil ya cubierto = coincidencias / (coincidencias +
                 costo de lo que falta); 100 para las confirmadas.
   --------------------------------------------------------------------------- */

%!  hipotesis_en_competencia(+Caso, +Negados, -Competidoras) is det.
%   Confirmadas y parciales que comparten al menos un hallazgo con el caso,
%   ordenadas por activación. Negados son los hallazgos que el usuario
%   respondió que NO presenta: una parcial que los necesita queda refutada.
hipotesis_en_competencia(Caso, Negados, Competidoras) :-
    findall(Activacion-comp(D, Estado, Activacion, Coincidencias, Requerimientos),
            ( diagnostico_del_catalogo(D),
              analizar_hipotesis(Caso, D, hipotesis(Estado0, Coincidencias, _, Requerimientos)),
              Coincidencias \== [],
              estado_competencia(Estado0, Requerimientos, Negados, Estado),
              activacion(Estado, Coincidencias, Requerimientos, Activacion) ),
            Pares),
    sort(1, @>=, Pares, Ordenados),
    pares_valores(Ordenados, Competidoras).

%   CORTE: confirmada; parcial refutada por una respuesta negativa; parcial.
%   Las excluidas y las bloqueadas no compiten (no hay cláusula para ellas).
estado_competencia(confirmada, _, _, confirmada) :- !.
estado_competencia(parcial, Requerimientos, Negados, refutada_usuario) :-
    requerimiento_negado(Requerimientos, Negados), !.
estado_competencia(parcial, _, _, parcial).

%!  requerimiento_negado(+Requerimientos, +Negados) is semidet.
%   Algún requerimiento ya no puede cumplirse por las respuestas negativas.
requerimiento_negado(Requerimientos, Negados) :-
    member(necesita(H), Requerimientos),
    presente(H, Negados), !.
requerimiento_negado(Requerimientos, Negados) :-
    member(uno_de(Lista), Requerimientos),
    diferencia(Lista, Negados, []), !.
requerimiento_negado(Requerimientos, Negados) :-
    member(k_de(K, Lista), Requerimientos),
    diferencia(Lista, Negados, Posibles),
    length(Posibles, N),
    N < K, !.

%   CORTE + FALLBACK: 100 % si está confirmada; si no, proporción cubierta.
activacion(confirmada, _, _, 100) :- !.
activacion(_, Coincidencias, Requerimientos, Activacion) :-
    length(Coincidencias, C),
    costo(Requerimientos, Faltan),
    Activacion is round(100 * C / (C + Faltan)).

%!  activa(+Competidora) is semidet.
%   Compite de verdad: no fue refutada por el usuario.
activa(comp(_, Estado, _, _, _)) :-
    Estado \== refutada_usuario.

%!  nivel_gravedad(+Caso, +Diagnostico, -Nivel) is det.
%   Gravedad potencial del diagnóstico para este paciente: su nivel base
%   (nivel_base/3; en la intoxicación, el de la sustancia ingerida), sin
%   agravantes.
%   CORTE + FALLBACK: si aún no hay ingesta, el nivel base genérico.
nivel_gravedad(Caso, Diagnostico, Nivel) :-
    nivel_base(Caso, Diagnostico, Nivel), !.
nivel_gravedad(_, Diagnostico, Nivel) :-
    severidad_base(Diagnostico, Nivel).

%!  gravedad(+Caso, +Diagnostico, -Peso) is det.
%   Peso (1 a 4) de la gravedad potencial.
gravedad(Caso, Diagnostico, Peso) :-
    nivel_gravedad(Caso, Diagnostico, Nivel),
    nivel_valor(Nivel, Peso).

/* ---------------------------------------------------------------------------
   9.4 Ponderación de las preguntas
   Una pregunta es hallazgo(H) o grupo(Opciones) (basta uno de ellos).
   --------------------------------------------------------------------------- */

%!  sugerencias(+Caso, +Estado, +Negados, +Competidoras, -Sugerencias) is det.
%   Sugerencias = [sug(Pregunta, Peso, Desempata, Motivos), ...] ordenadas
%   de mayor a menor peso.
sugerencias(Caso, Estado, Negados, Competidoras, Sugerencias) :-
    foco(Estado, Competidoras, Activas),
    findall(Pregunta, pregunta_candidata(Caso, Negados, Activas, Pregunta), Preguntas0),
    sort(Preguntas0, Preguntas),
    findall(Peso-sug(Pregunta, Peso, Desempata, Motivos),
            ( member(Pregunta, Preguntas),
              ponderar(Caso, Pregunta, Activas, Peso, Desempata, Motivos) ),
            Pares),
    sort(1, @>=, Pares, Ordenados),
    pares_valores(Ordenados, Sugerencias).

%!  foco(+Estado, +Competidoras, -Foco) is det.
%   Hipótesis con las que se ponderan las preguntas.
%   CORTE: en un empate solo cuentan las dos hipótesis empatadas, porque el
%   objetivo es separarlas; en los demás estados, todas las activas.
foco(empate(D1, D2, _, _), Competidoras, Foco) :- !,
    include(empatada([D1, D2]), Competidoras, Foco).
foco(_, Competidoras, Foco) :-
    include(activa, Competidoras, Foco).

empatada(Diagnosticos, comp(D, _, _, _, _)) :-
    memberchk(D, Diagnosticos).

%!  pregunta_candidata(+Caso, +Negados, +Activas, -Pregunta) is nondet.
%   Hallazgos que todavía no se ingresaron ni se negaron, que son relevantes
%   para alguna hipótesis en competencia y que no contradicen el caso; y
%   grupos de alternativas (uno_de/1) aún abiertos.
pregunta_candidata(caso(_, _, _, H), Negados, Activas, hallazgo(Hallazgo)) :-
    member(comp(D, _, _, _, Requerimientos), Activas),
    hallazgo_relevante(D, Requerimientos, Hallazgo),
    \+ presente(Hallazgo, H),
    \+ presente(Hallazgo, Negados),
    \+ contradice(Hallazgo, H).
pregunta_candidata(_, Negados, Activas, grupo(Opciones)) :-
    member(comp(_, _, _, _, Requerimientos), Activas),
    member(uno_de(Lista), Requerimientos),
    diferencia(Lista, Negados, Opciones),
    Opciones \== [].

hallazgo_relevante(_, Requerimientos, H) :-
    member(necesita(H), Requerimientos).
hallazgo_relevante(_, Requerimientos, H) :-
    member(k_de(_, Lista), Requerimientos),
    member(H, Lista).
hallazgo_relevante(D, _, H) :-
    apoyo(D, Apoyo),
    member(H, Apoyo).

%!  contradice(+Hallazgo, +Hallazgos) is semidet.
contradice(Hallazgo, H) :-
    ( incompatibles(Hallazgo, Otro) ; incompatibles(Otro, Hallazgo) ),
    presente(Otro, H), !.

%!  rol(+Competidora, +Pregunta, -Rol) is semidet.
%   Papel principal de la pregunta para la hipótesis.
%   CORTE: los roles se prueban de mayor a menor peso y se queda el primero.
rol(comp(_, _, _, _, Requerimientos), hallazgo(H), requisito) :-
    presente(necesita(H), Requerimientos), !.
rol(comp(_, _, _, _, Requerimientos), hallazgo(H), minimo) :-
    member(k_de(_, Lista), Requerimientos),
    presente(H, Lista), !.
rol(comp(D, _, _, _, _), hallazgo(H), refuerzo) :-
    apoyo(D, Apoyo),
    presente(H, Apoyo), !.
rol(comp(_, _, _, _, Requerimientos), grupo(Opciones), alternativa) :-
    member(uno_de(Lista), Requerimientos),
    contiene_todos(Opciones, Lista), !.

%!  ponderar(+Caso, +Pregunta, +Activas, -Peso, -Desempata, -Motivos) is semidet.
%   Peso = Σ peso_rol × gravedad × activación / 100, multiplicado por el
%   factor de desempate cuando corresponde (redondeado a un decimal).
%   Motivos = [motivo(D, Rol, Activacion), ...].
ponderar(Caso, Pregunta, Activas, Peso, Desempata, Motivos) :-
    findall(Aporte-motivo(D, Rol, Activacion),
            ( member(Competidora, Activas),
              Competidora = comp(D, _, Activacion, _, _),
              rol(Competidora, Pregunta, Rol),
              peso_rol(Rol, PesoRol),
              gravedad(Caso, D, Gravedad),
              Aporte is PesoRol * Gravedad * Activacion / 100 ),
            Aportes),
    Aportes \== [],
    pares_valores(Aportes, Motivos),
    findall(A, member(A-_, Aportes), Valores),
    sum_list(Valores, Suma),
    desempata(Activas, Motivos, Desempata),
    factor(Desempata, Factor),
    Peso is round(Suma * Factor * 10) / 10.

%!  desempata(+Activas, +Motivos, -Desempata) is det.
%   Desempata = si cuando hay al menos dos hipótesis en competencia y la
%   pregunta tiene su rol más alto en UNA sola de ellas: confirmarla o
%   descartarla separa esa hipótesis de las demás.
%   CORTE + FALLBACK: en cualquier otro caso, no.
desempata(Activas, Motivos, si) :-
    length(Activas, N), N >= 2,
    findall(P, ( member(motivo(_, Rol, _), Motivos), peso_rol(Rol, P) ), Pesos),
    max_list(Pesos, Maximo),
    findall(Maximo, member(Maximo, Pesos), [_]), !.
desempata(_, _, no).

%   CORTE + FALLBACK: factor de desempate o 1.
factor(si, Factor) :-
    parametro(factor_desempate, Factor), !.
factor(_, 1).

/* ---------------------------------------------------------------------------
   9.5 Simulación: ¿qué pasaría si el usuario responde que sí?
   --------------------------------------------------------------------------- */

%!  efecto(+Caso, +Pregunta, -Texto) is det.
%   Vuelve a inferir el caso con el hallazgo agregado y compara: qué
%   diagnósticos aparecen o desaparecen, cómo cambian la certeza y la
%   prioridad, y si el dictamen pasaría a ser definitivo. En un grupo se
%   simula con la primera opción.
efecto(Caso, hallazgo(H), Texto) :-
    simular(Caso, H, Cambio),
    redactar_efecto('Si lo presenta', Cambio, Texto).
efecto(Caso, grupo([H|_]), Texto) :-
    simular(Caso, H, Cambio),
    nombre_legible(H, Nombre),
    format(atom(Prefijo), 'Si presenta alguno (p. ej., «~w»)', [Nombre]),
    redactar_efecto(Prefijo, Cambio, Texto).

%!  simular(+Caso, +Hallazgo, -Cambio) is det.
%   Cambio = cambio(Ganados, Perdidos, Certezas, PrioridadAntes,
%                   PrioridadDespues, Definitivo)
%   Certezas: [D-Antes-Despues] de los diagnósticos cuya certeza sube.
%   Definitivo: si | no, según el dictamen pase a ser definitivo.
simular(Caso, Hallazgo, cambio(Ganados, Perdidos, Certezas, PrioridadAntes, PrioridadDespues, Definitivo)) :-
    Caso = caso(Especie, Edad, Sexo, H),
    sort([Hallazgo|H], H2),
    Hipotetico = caso(Especie, Edad, Sexo, H2),
    diagnosticos_detallados(Caso, DetallesAntes),
    diagnosticos_detallados(Hipotetico, DetallesDespues),
    findall(D, member([D|_], DetallesAntes), Antes),
    findall(D, member([D|_], DetallesDespues), Despues),
    diferencia(Despues, [sin_diagnostico_concluyente|Antes], Ganados),
    diferencia(Antes, [sin_diagnostico_concluyente|Despues], Perdidos),
    findall(D-CA-CD,
            ( member([D, _, _, CA|_], DetallesAntes),
              D \== sin_diagnostico_concluyente,
              member([D, _, _, CD|_], DetallesDespues),
              CD > CA ),
            Certezas),
    prioridad_caso(Caso, DetallesAntes, PrioridadAntes),
    prioridad_caso(Hipotetico, DetallesDespues, PrioridadDespues),
    estado_evidencia(Caso, DetallesAntes, EstadoAntes),
    estado_evidencia(Hipotetico, DetallesDespues, EstadoDespues),
    pasa_a_definitivo(EstadoAntes, EstadoDespues, Definitivo).

%   CORTE + FALLBACK: si (pasa a definitivo), rompe (deja de haber empate)
%   o no.
pasa_a_definitivo(definitivo(_, _), _, no) :- !.
pasa_a_definitivo(_, definitivo(_, _), si) :- !.
pasa_a_definitivo(empate(_, _, _, _), Despues, rompe) :-
    Despues \= empate(_, _, _, _), !.
pasa_a_definitivo(_, _, no).

%!  redactar_efecto(+Prefijo, +Cambio, -Texto) is det.
redactar_efecto(Prefijo, Cambio, Texto) :-
    partes_efecto(Cambio, Partes),
    atomic_list_concat(Partes, '; ', Cuerpo),
    format(atom(Texto), '~w: ~w.', [Prefijo, Cuerpo]).

partes_efecto(cambio(Ganados, Perdidos, Certezas, PrioridadA, PrioridadB, Definitivo), Partes) :-
    parte_diagnosticos('se concluiría', Ganados, P1),
    parte_diagnosticos('se descartaría', Perdidos, P2),
    findall(Texto,
            ( member(D-CA-CD, Certezas),
              nombre_diagnostico(D, Nombre),
              format(atom(Texto), 'la certeza de ~w subiría de ~d % a ~d %', [Nombre, CA, CD]) ),
            P3),
    parte_prioridad(PrioridadA, PrioridadB, P4),
    parte_definitivo(Definitivo, P5),
    append([P1, P2, P3, P4, P5], Partes0),
    partes_o_sin_cambio(Partes0, Partes).

%   CORTE + FALLBACK: frase solo si cambia el estado del dictamen.
parte_definitivo(si, ['el dictamen pasaría a ser definitivo']) :- !.
parte_definitivo(rompe, ['se rompería el empate']) :- !.
parte_definitivo(_, []).

%   CORTE + FALLBACK: sin diagnósticos no hay frase.
parte_diagnosticos(_, [], []) :- !.
parte_diagnosticos(Verbo, Diagnosticos, [Texto]) :-
    maplist(nombre_diagnostico, Diagnosticos, Nombres),
    enumerar(Nombres, Lista),
    format(atom(Texto), '~w ~w', [Verbo, Lista]).

%   CORTE + FALLBACK: frase solo si la prioridad cambia.
parte_prioridad(Prioridad, Prioridad, []) :- !.
parte_prioridad(PrioridadA, PrioridadB, [Texto]) :-
    nombre_nivel(PrioridadA, NA),
    nombre_nivel(PrioridadB, NB),
    format(atom(Texto), 'la prioridad pasaría de ~w a ~w', [NA, NB]).

%   CORTE + FALLBACK: si nada cambia se dice explícitamente.
partes_o_sin_cambio([], ['el dictamen todavía no cambia, pero la hipótesis queda más cerca de su perfil']) :- !.
partes_o_sin_cambio(Partes, Partes).

/* ---------------------------------------------------------------------------
   9.6 Textos y exportación a listas para Python
   --------------------------------------------------------------------------- */

%!  texto_pregunta(+Pregunta, -Texto) is det.
%   CORTE + FALLBACK: pregunta registrada, pregunta de grupo o genérica.
texto_pregunta(hallazgo(H), Texto) :-
    pregunta(H, Texto), !.
texto_pregunta(hallazgo(H), Texto) :- !,
    nombre_legible(H, Nombre),
    format(atom(Texto), '¿Presenta «~w»?', [Nombre]).
texto_pregunta(grupo(Opciones), '¿Pudo haber ingerido alguna sustancia tóxica? Indique cuál.') :-
    forall(member(H, Opciones), sustancia(H, _)), !.
texto_pregunta(grupo(Opciones), '¿Presenta vómito o diarrea? Indique cuál.') :-
    indicadores(cuadro_digestivo, Digestivos),
    contiene_todos(Opciones, Digestivos), !.
texto_pregunta(grupo(Opciones), Texto) :-
    enumerar_hallazgos(Opciones, Lista),
    format(atom(Texto), '¿Presenta alguno de estos hallazgos: ~w?', [Lista]).

%!  categoria(+Pregunta, -Categoria) is det.
%   prueba (exploración sencilla), sintoma o antecedente.
%   CORTE: la exploración tiene prioridad; un grupo toma la de su primera
%   opción.
categoria(grupo([H|_]), Categoria) :- !,
    categoria(hallazgo(H), Categoria).
categoria(hallazgo(H), prueba) :-
    como_verificar(H, _), !.
categoria(hallazgo(H), sintoma) :-
    signo(H, _), !.
categoria(_, antecedente).

%   CORTE + FALLBACK: instrucción registrada o texto vacío.
instruccion(hallazgo(H), Texto) :-
    como_verificar(H, Texto), !.
instruccion(_, '').

hallazgos_pregunta(hallazgo(H), [H]).
hallazgos_pregunta(grupo(Opciones), Opciones).

tipo_pregunta(hallazgo(_), hallazgo).
tipo_pregunta(grupo(_), grupo).

%!  exportar_sugerencia(+Caso, +Sugerencia, -Lista) is det.
%   [Tipo, Categoria, Hallazgos, Pregunta, Peso, Desempata, Motivos,
%    Efecto, ComoVerificar]
exportar_sugerencia(Caso, sug(Pregunta, Peso, Desempata, Motivos),
                    [Tipo, Categoria, Hallazgos, Texto, Peso, Desempata, TextosMotivos, Efecto, Instruccion]) :-
    tipo_pregunta(Pregunta, Tipo),
    categoria(Pregunta, Categoria),
    hallazgos_pregunta(Pregunta, Hallazgos),
    texto_pregunta(Pregunta, Texto),
    maplist(texto_motivo(Caso), Motivos, TextosMotivos),
    efecto(Caso, Pregunta, Efecto),
    instruccion(Pregunta, Instruccion).

texto_motivo(Caso, motivo(D, Rol, Activacion), Texto) :-
    nombre_rol(Rol, TextoRol),
    nombre_diagnostico(D, Nombre),
    nivel_gravedad(Caso, D, Nivel),
    nombre_nivel(Nivel, NombreNivel),
    format(atom(Texto), '~w «~w» (gravedad ~w, activación ~d %)',
           [TextoRol, Nombre, NombreNivel, Activacion]).

%!  exportar_competidora(+Caso, +Competidoras, +Competidora, -Lista) is det.
%   [Id, Nombre, Estado, Activacion, Gravedad, Coincidencias, Falta, Excluiria]
%   Excluiria: confirmadas que esta hipótesis excluiría si se confirma.
exportar_competidora(Caso, Competidoras, comp(D, Estado, Activacion, Coincidencias, Requerimientos),
                     [D, Nombre, Estado, Activacion, Nivel, Coincidencias, Falta, Excluiria]) :-
    nombre_diagnostico(D, Nombre),
    nivel_gravedad(Caso, D, Nivel),
    textos_requerimientos(Requerimientos, Falta),
    findall(NombreX,
            ( excluye(D, X),
              member(comp(X, confirmada, _, _, _), Competidoras),
              nombre_diagnostico(X, NombreX) ),
            Excluiria).


/*  ===========================================================================
    SECCIÓN 10. API PARA PYTHON DEL ENTREGABLE 2
    Predicados que invoca motor.py. Todos validan la entrada con
    preparar_caso/6 (que usa entrada_segura/4) y, como analizar_caso/10,
    tienen una cláusula por defecto: Python nunca recibe un fallo.
    =========================================================================== */

%!  explicar_caso(+Especie, +Edad, +Sexo, +Entrada, -Explicaciones) is det.
%   MÓDULO "¿POR QUÉ?": una explicación por cada conclusión, en el mismo
%   orden de diagnosticos_detallados/2:
%   [Id, Nombre, Arbol, Reglas, Hechos, Datos, Severidad, Certeza]
%   CORTE + FALLBACK: con datos no válidos devuelve [].
explicar_caso(Especie, Edad, Sexo, Entrada, Explicaciones) :-
    preparar_caso(Especie, Edad, Sexo, Entrada, Caso, _), !,
    diagnosticos_detallados(Caso, Detalles),
    findall(Explicacion,
            ( member([D|_], Detalles),
              once(explicacion(Caso, D, Explicacion)) ),
            Explicaciones).
explicar_caso(_, _, _, _, []).

%!  hipotesis_descartadas(+Especie, +Edad, +Sexo, +Entrada, -Descartadas) is det.
%   Hipótesis que comparten hallazgos con el caso pero no se concluyeron,
%   ordenadas por número de hallazgos compartidos:
%   [Id, Nombre, Tipo, Resumen, Compartidos, Arbol]
%   CORTE + FALLBACK: con datos no válidos devuelve [].
hipotesis_descartadas(Especie, Edad, Sexo, Entrada, Descartadas) :-
    preparar_caso(Especie, Edad, Sexo, Entrada, Caso, _), !,
    findall(Par, descartada(Caso, Par), Pares),
    sort(1, @>=, Pares, Ordenados),
    pares_valores(Ordenados, Descartadas).
hipotesis_descartadas(_, _, _, _, []).

%!  que_falta(+Especie, +Edad, +Sexo, +Entrada, +Negados,
%!            -Estado, -Competidoras, -Sugerencias) is det.
%   MÓDULO "¿QUÉ FALTA?":
%     Estado       = [Tipo, Activo, Mensaje]
%     Competidoras = hipótesis en competencia (ver exportar_competidora/4)
%     Sugerencias  = preguntas ordenadas por peso (ver exportar_sugerencia/3)
%   Negados: hallazgos que el usuario respondió que NO presenta.
%   CORTE + FALLBACK: con datos no válidos responde datos_invalidos.
que_falta(Especie, Edad, Sexo, Entrada, Negados0,
          [Tipo, Activo, Mensaje], Competidoras, Sugerencias) :-
    preparar_caso(Especie, Edad, Sexo, Entrada, Caso, _), !,
    atomos_seguros(Negados0, Negados),
    diagnosticos_detallados(Caso, Detalles),
    estado_evidencia(Caso, Detalles, Estado),
    describir_estado(Estado, Tipo, Activo, Mensaje),
    hipotesis_en_competencia(Caso, Negados, Comps),
    maplist(exportar_competidora(Caso, Comps), Comps, Competidoras),
    sugerencias(Caso, Estado, Negados, Comps, Sugs),
    maplist(exportar_sugerencia(Caso), Sugs, Sugerencias).
que_falta(_, _, _, _, _, [datos_invalidos, no, Mensaje], [], []) :-
    recomendacion(datos_invalidos, Mensaje).

%!  pregunta_desempate(+Especie, +Edad, +Sexo, +Entrada, +Negados, -Pregunta) is semidet.
%   CONSULTA DE DESEMPATE: la pregunta de mayor peso (primera sugerencia de
%   que_falta/8). Falla si no hay nada que preguntar.
pregunta_desempate(Especie, Edad, Sexo, Entrada, Negados, Pregunta) :-
    que_falta(Especie, Edad, Sexo, Entrada, Negados, _, _, [Pregunta|_]).



/*  ===========================================================================
    SECCIÓN 11. LENGUAJE NATURAL CON DCG                          [Entregable 3]
    El tutor describe el caso con sus palabras ("mi perrito de 4 meses vomita
    mucho, tiene diarrea con sangre y no tiene fiebre") y esta sección extrae
    los hechos simbólicos que alimentan al motor de inferencia:
      1. texto_a_palabras/2 normaliza el texto (minúsculas, sin tildes, sin
         signos) y lo divide en palabras; los números quedan como números;
      2. la gramática descripcion//1 (Definite Clause Grammar) recorre las
         palabras y reconoce fragmentos: hallazgos, negaciones, especie,
         sexo, edad y mediciones numéricas;
      3. resumen//5, otra DCG, recorre el camino inverso: a partir de los
         hechos extraídos GENERA la oración con la que el sistema confirma lo
         que entendió. Así la comunicación con Python es bidireccional:
         texto -> hechos -> texto.
    El léxico es conocimiento declarativo (expresion/2) y el Modo Experto
    puede ampliarlo en caliente (expresion_aprendida/4, Sección 12).
    =========================================================================== */

/* ---------------------------------------------------------------------------
   11.1 Léxico
   expresion(?Texto, ?Hallazgo)
       Forma en que un tutor suele decir el hallazgo. Una palabra terminada
       en * es una raíz: "vomit*" reconoce vomita, vomitó, vomitando...
       Las tildes no importan: el léxico pasa por la misma normalización
       que el texto del usuario.
   palabra_paciente(?Texto, ?Especie, ?Sexo)   Sexo = no_indicado si la
                                               palabra no lo revela
   palabra_sexo(?Texto, ?Sexo)
   palabra_numero(?Palabra, ?Valor)
   unidad_edad(?Texto, ?Meses)                 meses que vale cada unidad
   negador(?Palabra)       relleno_negacion(?Palabra)    palabra_vacia(?Palabra)
   --------------------------------------------------------------------------- */
% Signos digestivos
expresion("vomit*", vomito).
expresion("devuelve la comida", vomito).
expresion("devolvi* la comida", vomito).
expresion("vomit* mucho", vomito_persistente).
expresion("vomit* muchas veces", vomito_persistente).
expresion("vomit* varias veces", vomito_persistente).
expresion("vomit* repetid*", vomito_persistente).
expresion("vomit* sin parar", vomito_persistente).
expresion("vomit* todo el dia", vomito_persistente).
expresion("vomit* a cada rato", vomito_persistente).
expresion("vomit* persistente*", vomito_persistente).
expresion("vomit* constante*", vomito_persistente).
expresion("no para de vomit*", vomito_persistente).
expresion("diarrea*", diarrea).
expresion("heces liquidas", diarrea).
expresion("heces blandas", diarrea).
expresion("popo liquid*", diarrea).
expresion("popo aguad*", diarrea).
expresion("diarrea* con sangre", diarrea_con_sangre).
expresion("diarrea* sanguinolenta*", diarrea_con_sangre).
expresion("diarrea* negra*", diarrea_con_sangre).
expresion("heces con sangre", diarrea_con_sangre).
expresion("heces negras", diarrea_con_sangre).
expresion("popo con sangre", diarrea_con_sangre).
expresion("sangre en las heces", diarrea_con_sangre).
expresion("sangre en la popo", diarrea_con_sangre).
expresion("arcada*", arcadas_improductivas).
expresion("intenta vomit* sin", arcadas_improductivas).
expresion("intenta vomit* y no puede", arcadas_improductivas).
expresion("quiere vomit* y no puede", arcadas_improductivas).
expresion("trata de vomit*", arcadas_improductivas).
expresion("abdomen distendido", abdomen_distendido).
expresion("abdomen hinchado", abdomen_distendido).
expresion("abdomen tenso", abdomen_distendido).
expresion("barriga hinchada", abdomen_distendido).
expresion("barriga inflada", abdomen_distendido).
expresion("barriga dura", abdomen_distendido).
expresion("panza hinchada", abdomen_distendido).
expresion("panza inflada", abdomen_distendido).
expresion("estomago hinchado", abdomen_distendido).
expresion("dolor abdominal", dolor_abdominal).
expresion("dolor de barriga", dolor_abdominal).
expresion("dolor de estomago", dolor_abdominal).
expresion("dolor de panza", dolor_abdominal).
expresion("dolor en el abdomen", dolor_abdominal).
expresion("le duele la barriga", dolor_abdominal).
expresion("le duele el estomago", dolor_abdominal).
expresion("le duele la panza", dolor_abdominal).
expresion("se encorva", dolor_abdominal).
expresion("babe*", salivacion_excesiva).
expresion("saliva mucho", salivacion_excesiva).
expresion("saliva excesiva", salivacion_excesiva).
expresion("mucha baba", salivacion_excesiva).
expresion("salivacion*", salivacion_excesiva).
expresion("espuma por la boca", salivacion_excesiva).
expresion("no come", anorexia).
expresion("no quiere comer", anorexia).
expresion("no ha comido", anorexia).
expresion("dejo de comer", anorexia).
expresion("sin apetito", anorexia).
expresion("no tiene apetito", anorexia).
expresion("perdio el apetito", anorexia).
expresion("rechaza la comida", anorexia).
expresion("inapetente", anorexia).
expresion("anorexia", anorexia).
expresion("no defeca", sin_defecar).
expresion("no ha defecado", sin_defecar).
expresion("sin defecar", sin_defecar).
expresion("no hace popo", sin_defecar).
expresion("no ha hecho popo", sin_defecar).
expresion("no evacua", sin_defecar).
expresion("estreñid*", sin_defecar).
expresion("estrenid*", sin_defecar).
% Signos urinarios
expresion("esfuerzo para orinar", esfuerzo_para_orinar).
expresion("hace fuerza para orinar", esfuerzo_para_orinar).
expresion("puja* para orinar", esfuerzo_para_orinar).
expresion("le cuesta orinar", esfuerzo_para_orinar).
expresion("dificultad para orinar", esfuerzo_para_orinar).
expresion("intenta orinar", esfuerzo_para_orinar).
expresion("se agacha para orinar", esfuerzo_para_orinar).
expresion("no orina", ausencia_de_orina).
expresion("no puede orinar", ausencia_de_orina).
expresion("no ha orinado", ausencia_de_orina).
expresion("no sale orina", ausencia_de_orina).
expresion("no le sale orina", ausencia_de_orina).
expresion("no hace pipi", ausencia_de_orina).
expresion("sin orinar", ausencia_de_orina).
expresion("solo gotas", ausencia_de_orina).
expresion("orina muchas veces", miccion_frecuente).
expresion("orina a cada rato", miccion_frecuente).
expresion("orina seguido", miccion_frecuente).
expresion("orina poquito", miccion_frecuente).
expresion("orina frecuente*", miccion_frecuente).
expresion("miccion frecuente", miccion_frecuente).
expresion("va mucho al arenero", miccion_frecuente).
expresion("sangre en la orina", sangre_en_orina).
expresion("orina con sangre", sangre_en_orina).
expresion("orina roja", sangre_en_orina).
expresion("orina rojiza", sangre_en_orina).
expresion("pipi con sangre", sangre_en_orina).
expresion("hematuria", sangre_en_orina).
expresion("orina mucho", poliuria).
expresion("orina demasiado", poliuria).
expresion("orina en exceso", poliuria).
expresion("orina abundante", poliuria).
expresion("mucha orina", poliuria).
expresion("hace mucho pipi", poliuria).
expresion("poliuria", poliuria).
expresion("bebe mucha agua", polidipsia).
expresion("bebe mucho", polidipsia).
expresion("bebe demasiada agua", polidipsia).
expresion("toma mucha agua", polidipsia).
expresion("toma mucho", polidipsia).
expresion("mucha sed", polidipsia).
expresion("sed excesiva", polidipsia).
expresion("tiene mucha sed", polidipsia).
expresion("polidipsia", polidipsia).
expresion("se lame los genitales", lamido_genital).
expresion("se lame la zona genital", lamido_genital).
expresion("se lame el pene", lamido_genital).
expresion("se lame la vulva", lamido_genital).
expresion("lamido genital", lamido_genital).
% Signos respiratorios
expresion("jade*", jadeo_excesivo).
expresion("respira agitad*", jadeo_excesivo).
expresion("respiracion agitada", jadeo_excesivo).
expresion("dificultad para respirar", dificultad_respiratoria).
expresion("dificultad respiratoria", dificultad_respiratoria).
expresion("le cuesta respirar", dificultad_respiratoria).
expresion("respira con dificultad", dificultad_respiratoria).
expresion("respira con la boca abierta", dificultad_respiratoria).
expresion("respira con ruido", dificultad_respiratoria).
expresion("no puede respirar", dificultad_respiratoria).
expresion("se ahoga", dificultad_respiratoria).
expresion("ahogo", dificultad_respiratoria).
expresion("secrecion nasal", secrecion_nasal).
expresion("secrecion por la nariz", secrecion_nasal).
expresion("moco*", secrecion_nasal).
expresion("flujo nasal", secrecion_nasal).
expresion("tos", tos).
expresion("tose", tos).
expresion("tosiendo", tos).
expresion("tosio", tos).
% Signos neurológicos
expresion("convulsi*", convulsiones).
expresion("epilep*", convulsiones).
expresion("le dio un ataque", convulsiones).
expresion("tiembla", temblores).
expresion("temblor*", temblores).
expresion("temblando", temblores).
expresion("tirita*", temblores).
expresion("desorientad*", desorientacion).
expresion("camina en circulos", desorientacion).
expresion("da vueltas", desorientacion).
expresion("confundid*", desorientacion).
expresion("mareado*", desorientacion).
expresion("se tambalea", desorientacion).
expresion("no reconoce", desorientacion).
expresion("mioclon*", mioclonias).
expresion("tics", mioclonias).
expresion("tics musculares", mioclonias).
expresion("espasmo*", mioclonias).
expresion("sacudidas", mioclonias).
% Estado general
expresion("decaid*", letargo).
expresion("letargic*", letargo).
expresion("letargo", letargo).
expresion("apatic*", letargo).
expresion("desanimad*", letargo).
expresion("aplanad*", letargo).
expresion("cansad*", letargo).
expresion("debil", letargo).
expresion("debilidad", letargo).
expresion("sin energia", letargo).
expresion("duerme mucho", letargo).
expresion("no quiere jugar", letargo).
expresion("fiebre", fiebre).
expresion("febril", fiebre).
expresion("calentura", fiebre).
expresion("temperatura alta", fiebre).
expresion("encias palidas", encias_palidas).
expresion("encias blancas", encias_palidas).
expresion("encias descoloridas", encias_palidas).
expresion("mucosas palidas", encias_palidas).
expresion("encias rojas", encias_rojo_intenso).
expresion("encias muy rojas", encias_rojo_intenso).
expresion("encias rojo intenso", encias_rojo_intenso).
expresion("mucosas rojas", encias_rojo_intenso).
expresion("llenado capilar lento", llenado_capilar_lento).
expresion("llenado capilar prolongado", llenado_capilar_lento).
expresion("tarda en volver el color", llenado_capilar_lento).
expresion("colaps*", colapso).
expresion("desmay*", colapso).
expresion("se desplomo", colapso).
expresion("se cayo", colapso).
expresion("no se puede levantar", colapso).
expresion("no puede levantarse", colapso).
expresion("no se levanta", colapso).
expresion("perdida de peso", perdida_de_peso).
expresion("perdio peso", perdida_de_peso).
expresion("ha perdido peso", perdida_de_peso).
expresion("bajo de peso", perdida_de_peso).
expresion("adelgaz*", perdida_de_peso).
expresion("aliento a orina", halitosis_uremica).
expresion("aliento a amoniaco", halitosis_uremica).
expresion("mal aliento", halitosis_uremica).
expresion("halitosis", halitosis_uremica).
expresion("ojos hundidos", ojos_hundidos).
expresion("ojos sumidos", ojos_hundidos).
expresion("piel sin elasticidad", piel_sin_elasticidad).
expresion("la piel no vuelve", piel_sin_elasticidad).
expresion("la piel tarda en volver", piel_sin_elasticidad).
expresion("inquiet*", inquietud).
expresion("intranquil*", inquietud).
expresion("ansios*", inquietud).
expresion("no se acomoda", inquietud).
expresion("llora", vocalizacion_dolor).
expresion("llorando", vocalizacion_dolor).
expresion("gime", vocalizacion_dolor).
expresion("gimiendo", vocalizacion_dolor).
expresion("se queja", vocalizacion_dolor).
expresion("quej*", vocalizacion_dolor).
expresion("chilla", vocalizacion_dolor).
expresion("maulla de dolor", vocalizacion_dolor).
expresion("grita de dolor", vocalizacion_dolor).
expresion("hipotermia", hipotermia).
expresion("esta frio", hipotermia).
expresion("frio al tacto", hipotermia).
expresion("temperatura baja", hipotermia).
% Antecedentes
expresion("vacunad*", vacunacion_completa).
expresion("vacunas al dia", vacunacion_completa).
expresion("tiene las vacunas", vacunacion_completa).
expresion("todas las vacunas", vacunacion_completa).
expresion("vacunacion completa", vacunacion_completa).
expresion("no esta vacunad*", vacunacion_incompleta).
expresion("no vacunad*", vacunacion_incompleta).
expresion("sin vacuna*", vacunacion_incompleta).
expresion("no tiene vacunas", vacunacion_incompleta).
expresion("no tiene las vacunas", vacunacion_incompleta).
expresion("le faltan vacunas", vacunacion_incompleta).
expresion("nunca lo vacunaron", vacunacion_incompleta).
expresion("nunca la vacunaron", vacunacion_incompleta).
expresion("no lo han vacunado", vacunacion_incompleta).
expresion("no la han vacunado", vacunacion_incompleta).
expresion("vacunacion incompleta", vacunacion_incompleta).
expresion("gestante", gestante).
expresion("embarazad*", gestante).
expresion("preñada", gestante).
expresion("prenada", gestante).
expresion("enfermedad cronica", enfermedad_cronica_previa).
expresion("diabetic*", enfermedad_cronica_previa).
expresion("diabetes", enfermedad_cronica_previa).
expresion("cardiopata", enfermedad_cronica_previa).
expresion("gran danes", raza_torax_profundo).
expresion("pastor aleman", raza_torax_profundo).
expresion("boxer", raza_torax_profundo).
expresion("doberman", raza_torax_profundo).
expresion("san bernardo", raza_torax_profundo).
expresion("weimaraner", raza_torax_profundo).
expresion("raza grande", raza_torax_profundo).
expresion("torax profundo", raza_torax_profundo).
expresion("bulldog", raza_braquicefala).
expresion("pug", raza_braquicefala).
expresion("carlino", raza_braquicefala).
expresion("shih tzu", raza_braquicefala).
expresion("persa", raza_braquicefala).
expresion("braquicefal*", raza_braquicefala).
expresion("calor", exposicion_calor).
expresion("al sol", exposicion_calor).
expresion("insolacion", exposicion_calor).
expresion("golpe de sol", exposicion_calor).
expresion("carro cerrado", exposicion_calor).
expresion("auto cerrado", exposicion_calor).
expresion("dentro del carro", exposicion_calor).
expresion("juguete", ingesta_objeto).
expresion("hueso", ingesta_objeto).
expresion("media", ingesta_objeto).
expresion("calcetin", ingesta_objeto).
expresion("piedra", ingesta_objeto).
expresion("pelota", ingesta_objeto).
expresion("tela", ingesta_objeto).
expresion("objeto", ingesta_objeto).
expresion("cuerpo extraño", ingesta_objeto).
expresion("cuerpo extrano", ingesta_objeto).
expresion("chocolat*", ingesta_chocolate).
expresion("cacao", ingesta_chocolate).
expresion("brownie", ingesta_chocolate).
expresion("xilitol", ingesta_xilitol).
expresion("chicle*", ingesta_xilitol).
expresion("goma de mascar", ingesta_xilitol).
expresion("sin azucar", ingesta_xilitol).
expresion("uva*", ingesta_uvas).
expresion("pasas", ingesta_uvas).
expresion("cebolla*", ingesta_cebolla).
expresion("ajo", ingesta_cebolla).
expresion("ajos", ingesta_cebolla).
expresion("ibuprofeno", ingesta_ibuprofeno).
expresion("advil", ingesta_ibuprofeno).
expresion("paracetamol", ingesta_paracetamol).
expresion("acetaminofen", ingesta_paracetamol).
expresion("dolex", ingesta_paracetamol).
expresion("tylenol", ingesta_paracetamol).
expresion("lirio*", ingesta_lirio).
expresion("azucena*", ingesta_lirio).
expresion("raticida", ingesta_raticida).
expresion("matarratas", ingesta_raticida).
expresion("veneno para ratas", ingesta_raticida).
expresion("veneno de ratas", ingesta_raticida).

palabra_paciente("perra",     perro, hembra).
palabra_paciente("perrita",   perro, hembra).
palabra_paciente("cachorra",  perro, hembra).
palabra_paciente("perro",     perro, no_indicado).
palabra_paciente("perrito",   perro, no_indicado).
palabra_paciente("perrit*",   perro, no_indicado).
palabra_paciente("cachorr*",  perro, no_indicado).
palabra_paciente("canin*",    perro, no_indicado).
palabra_paciente("gata",      gato,  hembra).
palabra_paciente("gatita",    gato,  hembra).
palabra_paciente("gato",      gato,  no_indicado).
palabra_paciente("gatit*",    gato,  no_indicado).
palabra_paciente("gatic*",    gato,  no_indicado).
palabra_paciente("felin*",    gato,  no_indicado).
palabra_paciente("minin*",    gato,  no_indicado).
palabra_paciente("michi*",    gato,  no_indicado).

palabra_sexo("macho",        macho).
palabra_sexo("machito",      macho).
palabra_sexo("castrado",     macho).
palabra_sexo("hembra",       hembra).
palabra_sexo("hembrita",     hembra).
palabra_sexo("castrada",     hembra).
palabra_sexo("esterilizada", hembra).

palabra_numero(un, 1).     palabra_numero(uno, 1).    palabra_numero(una, 1).
palabra_numero(dos, 2).    palabra_numero(tres, 3).   palabra_numero(cuatro, 4).
palabra_numero(cinco, 5).  palabra_numero(seis, 6).   palabra_numero(siete, 7).
palabra_numero(ocho, 8).   palabra_numero(nueve, 9).  palabra_numero(diez, 10).
palabra_numero(once, 11).  palabra_numero(doce, 12).  palabra_numero(quince, 15).

unidad_edad("mes*",    1).
unidad_edad("año*",   12).
unidad_edad("anos",   12).
unidad_edad("ano",    12).
unidad_edad("semana*", 0.25).

negador(no).  negador(sin).  negador(nunca).  negador(tampoco).  negador(ni).

relleno_negacion(tiene).     relleno_negacion(tenia).    relleno_negacion(tuvo).
relleno_negacion(presenta).  relleno_negacion(presento). relleno_negacion(muestra).
relleno_negacion(ha).        relleno_negacion(hay).      relleno_negacion(le).
relleno_negacion(se).        relleno_negacion(esta).     relleno_negacion(noto).
relleno_negacion(veo).       relleno_negacion(he).       relleno_negacion(visto).
relleno_negacion(notado).    relleno_negacion(nada).     relleno_negacion(de).

palabra_vacia(W) :-
    memberchk(W, [el, la, los, las, lo, un, una, unos, unas, mi, mis, su, sus, tu,
                  de, del, a, al, y, e, o, u, que, con, en, por, para, es, son,
                  esta, estan, estuvo, ha, han, he, hay, tiene, tienen, tenia, tuvo,
                  presenta, presento, muestra, le, les, se, me, muy, mas, pero,
                  tambien, ademas, desde, hace, hoy, ayer, anoche, manana, tarde,
                  noche, dia, dias, hora, horas, como, cuando, porque, pues, ya,
                  poco, mucho, bastante, algo, todo, creo, parece, veo, note,
                  noto, edad, años, anos, meses, ultimamente, rato, buenas,
                  hola, doctor, doctora, ayuda, favor, ahora, esta, este, ese,
                  esa, eso, esto, ni, sin, no, nada, casi, bien, mal, poquito,
                  seguido, vez, veces, entonces, luego, despues, comio,
                  comido, trago, tomo, ingirio, mordio, quedo, muchisimo,
                  demasiado, estaba, estuvo, anda, siento, encuentro]).

%   La raza revela la especie aunque el tutor no diga "perro" o "gato".
raza_especie(bulldog, perro).   raza_especie(pug, perro).
raza_especie(carlino, perro).   raza_especie(boxer, perro).
raza_especie(doberman, perro).  raza_especie(pastor, perro).
raza_especie(danes, perro).     raza_especie(bernardo, perro).
raza_especie(weimaraner, perro). raza_especie(tzu, perro).
raza_especie(persa, gato).

/* ---------------------------------------------------------------------------
   11.2 Normalización del texto
   --------------------------------------------------------------------------- */

%!  texto_a_palabras(+Texto, -Palabras) is det.
%   "¿Mi Perrito VOMITÓ 3 veces?" -> [mi, perrito, vomito, 3, veces]
%   Minúsculas, sin tildes y sin signos; los números quedan como números y
%   el asterisco se conserva (marca de raíz en el léxico).
texto_a_palabras(Texto, Palabras) :-
    text_to_string(Texto, Cadena),
    string_lower(Cadena, Minusculas),
    string_chars(Minusculas, Caracteres0),
    maplist(normalizar_caracter, Caracteres0, Caracteres),
    string_chars(Limpia, Caracteres),
    split_string(Limpia, " ", " ", Partes),
    convlist(palabra_token, Partes, Palabras).

%   CORTE: cada carácter se normaliza con la primera cláusula que aplica.
normalizar_caracter(C, N) :- sin_tilde(C, N), !.
normalizar_caracter(C, C) :- char_type(C, alnum), !.
normalizar_caracter(C, C) :- memberchk(C, ['.', '*']), !.
normalizar_caracter(_, ' ').

sin_tilde('á', a).  sin_tilde('é', e).  sin_tilde('í', i).
sin_tilde('ó', o).  sin_tilde('ú', u).  sin_tilde('ü', u).

%!  palabra_token(+Parte, -Token) is semidet.
%   Quita puntos sobrantes ("fiebre." -> fiebre) y convierte los números.
%   Falla con las partes vacías, que convlist/3 descarta.
palabra_token(Parte, Token) :-
    split_string(Parte, "", ".", [Recortada]),
    Recortada \== "",
    (   number_string(Numero, Recortada)
    ->  Token = Numero
    ;   atom_string(Token, Recortada)
    ).

/* ---------------------------------------------------------------------------
   11.3 Léxico compilado
   Cada expresión se convierte una vez en una lista de palabras o raíces
   (prefijo(R)) para no normalizar el léxico en cada consulta. Se recompila
   al cargar el archivo y cada vez que el Modo Experto enseña una expresión.
   --------------------------------------------------------------------------- */
:- dynamic patron_lexico/2.

%!  compilar_lexico is det.
compilar_lexico :-
    retractall(patron_lexico(_, _)),
    forall(( expresion_del_lexico(Texto, Hallazgo),
             compilar_patron(Texto, Patron),
             Patron \== [] ),
           assertz(patron_lexico(Patron, Hallazgo))).

%!  expresion_del_lexico(?Texto, ?Hallazgo) is nondet.
%   Léxico original más lo aprendido en Modo Experto (si el hallazgo existe).
expresion_del_lexico(Texto, Hallazgo) :-
    expresion(Texto, Hallazgo).
expresion_del_lexico(Texto, Hallazgo) :-
    expresion_aprendida(Texto, Hallazgo, _, _),
    hallazgo_valido(Hallazgo).

%!  compilar_patron(+Texto, -Patron) is det.
compilar_patron(Texto, Patron) :-
    texto_a_palabras(Texto, Palabras),
    maplist(elemento_patron, Palabras, Patron).

%   CORTE: una palabra terminada en * es una raíz; el resto, palabras exactas.
elemento_patron(Palabra, prefijo(Raiz)) :-
    atom(Palabra),
    sub_atom(Palabra, _, 1, 0, '*'), !,
    sub_atom(Palabra, 0, _, 1, Raiz).
elemento_patron(Palabra, Palabra).

%!  coincide(+Elemento, +Palabra) is semidet.
coincide(prefijo(Raiz), Palabra) :- !,
    atom(Palabra),
    sub_atom(Palabra, 0, _, _, Raiz).
coincide(Elemento, Palabra) :-
    Elemento == Palabra.

%!  coincide_secuencia(+Patron, +Palabras, -Resto) is semidet.
coincide_secuencia([], Resto, Resto).
coincide_secuencia([E|Es], [P|Ps], Resto) :-
    coincide(E, P),
    coincide_secuencia(Es, Ps, Resto).

%!  coincide_texto(+Texto, +Palabra) is semidet.
%   Una palabra coincide con una entrada de una sola palabra del léxico.
coincide_texto(Texto, Palabra) :-
    compilar_patron(Texto, [Elemento]),
    coincide(Elemento, Palabra).

/* ---------------------------------------------------------------------------
   11.4 Gramática de análisis (DCG)
   descripcion//1 produce una lista de fragmentos f(Tipo, Valor, Palabras):
     hallazgo  H                 el tutor afirma un hallazgo
     negado    [H, ...]          el tutor lo niega ("no tiene fiebre ni tos")
     paciente  [Especie, Sexo]   "mi perrita", "el gato"
     sexo      Sexo              "es macho"
     edad      Meses             "de 4 meses", "tiene dos años"
     medicion  [Variable, Valor] "temperatura de 40.2", "vomitó 5 veces"
     vacia     Palabra           artículos, preposiciones, verbos de relleno
     desconocida Palabra         palabra que el sistema aún no conoce
   Los fragmentos se prueban en este orden y el corte de descripcion//1
   se queda con el primero que encaja (análisis voraz, sin retroceso entre
   fragmentos). expresion_larga//1 elige la expresión MÁS LARGA del léxico,
   por eso "no come" (anorexia) gana frente a la negación de "come".
   --------------------------------------------------------------------------- */

descripcion([F|Fs]) -->
    fragmento_con_palabras(F), !,
    descripcion(Fs).
descripcion([]) --> [].

%   Guarda las palabras que consumió cada fragmento (para resaltarlas en la
%   interfaz y para que la explicación cite al usuario).
fragmento_con_palabras(f(Tipo, Valor, Palabras), Entrada, Resto) :-
    fragmento(Tipo, Valor, Entrada, Resto),
    append(Palabras, Resto, Entrada).

fragmento(medicion, [Variable, Valor]) --> medicion(Variable, Valor).
fragmento(edad, Meses)                 --> edad(Meses).
fragmento(hallazgo, Hallazgo)          --> expresion_larga(Hallazgo).
fragmento(paciente, [Especie, Sexo])   --> paciente(Especie, Sexo).
fragmento(sexo, Sexo)                  --> sexo(Sexo).
fragmento(negado, Hallazgos)           --> negacion(Hallazgos).
fragmento(vacia, Palabra)              --> [Palabra], { palabra_vacia(Palabra) }.
fragmento(desconocida, Palabra)        --> [Palabra].

%   Mediciones numéricas: Python las convierte en hechos discretos
%   (preprocesamiento.py) antes de enviarlas al motor.
medicion(temperatura, T) -->
    [P], { coincide_texto("temperatura", P) ; coincide_texto("fiebre", P) },
    relleno_corto, numero(T), { T >= 30, T =< 45 }.
medicion(temperatura, T) -->
    numero(T), { T >= 30, T =< 45 },
    [U], { memberchk(U, [grados, grado, c, centigrados]) }.
medicion(vomitos_24h, N) -->
    [P], { coincide_texto("vomit*", P) }, relleno_corto,
    numero(N), [V], { memberchk(V, [veces, vez]) }.
medicion(llenado_capilar, S) -->
    [llenado], [capilar], relleno_corto, numero(S),
    opcional_segundos.
medicion(dias_sin_defecar, N) -->
    numero(N), [D], { coincide_texto("dia*", D) }, [sin],
    relleno_corto, [P], { coincide_texto("defec*", P) ; P == popo ; coincide_texto("evacu*", P) }.

relleno_corto --> [P], { memberchk(P, [de, es, esta, en, mas, unos, unas, hace, hecho, ha, le, el, la]) }, relleno_corto.
relleno_corto --> [].

opcional_segundos --> [S], { coincide_texto("segundo*", S) }, !.
opcional_segundos --> [].

edad(Meses) -->
    numero(N), [U], { unidad_edad(Texto, Factor), coincide_texto(Texto, U) },
    { Meses is round(N * Factor) }.

numero(N) --> [N], { number(N) }.
numero(N) --> [P], { atom(P), palabra_numero(P, N) }.

%!  expresion_larga(-Hallazgo)// is semidet.
%   No terminal escrito a mano (la DCG lo llama con las dos listas de
%   diferencia): prueba todos los patrones del léxico al comienzo de la
%   entrada y se queda con el que consume más palabras.
expresion_larga(Hallazgo, Entrada, Resto) :-
    findall(N-H-R,
            ( patron_lexico(Patron, H),
              coincide_secuencia(Patron, Entrada, R),
              length(Patron, N) ),
            Coincidencias),
    Coincidencias \== [],
    sort(1, @>=, Coincidencias, [_-Hallazgo-Resto|_]).

paciente(Especie, Sexo) -->
    [P], { once(( palabra_paciente(Texto, Especie, Sexo),
                  coincide_texto(Texto, P) )) }.

sexo(Sexo) -->
    [P], { once(( palabra_sexo(Texto, Sexo), coincide_texto(Texto, P) )) }.

%   "no tiene fiebre ni tos", "sin vómito", "nunca ha convulsionado"
negacion(Hallazgos) -->
    [N], { negador(N) },
    relleno_negacion,
    lista_negada(Hallazgos).

relleno_negacion --> [P], { relleno_negacion(P) }, relleno_negacion.
relleno_negacion --> [].

lista_negada([H|Hs]) -->
    expresion_larga(H),
    resto_negado(Hs).

%   Solo "ni" y "o" prolongan la negación: en "no tiene fiebre y vomita"
%   el vómito es una afirmación.
resto_negado(Hs) -->
    [C], { memberchk(C, [ni, o]) }, relleno_negacion,
    lista_negada(Hs), !.
resto_negado([]) --> [].

/* ---------------------------------------------------------------------------
   11.5 Gramática de generación (DCG en sentido inverso)
   A partir de los hechos extraídos produce la oración de confirmación:
   "Entendí que se trata de un perro macho de 4 meses que presenta vómito
    y diarrea con sangre, y que no presenta fiebre."
   --------------------------------------------------------------------------- */

resumen(Especie, Edad, Sexo, Hallazgos, Negados) -->
    ['Entendí que se trata de'],
    sujeto(Especie, Sexo, Edad),
    presenta(Hallazgos),
    no_presenta(Hallazgos, Negados),
    ['.'].

sujeto(no_indicado, _, Edad) --> !, ['un paciente'], edad_texto(Edad).
sujeto(Especie, Sexo, Edad) -->
    { especie_paciente(Especie, Nombre0), downcase_atom(Nombre0, Nombre) },
    [un, Nombre], sexo_texto(Sexo), edad_texto(Edad).

sexo_texto(no_indicado) --> !, [].
sexo_texto(Sexo) --> [Sexo].

edad_texto(no_indicado) --> !, [].
edad_texto(Meses) --> { Meses >= 24, Meses mod 12 =:= 0 }, !, { A is Meses // 12 }, [de, A, 'años'].
edad_texto(12) --> !, [de, '1 año'].
edad_texto(1) --> !, [de, '1 mes'].
edad_texto(Meses) --> [de, Meses, meses].

presenta([]) --> !, [cuyos, 'hallazgos aún no se identifican'].
presenta(Hallazgos) --> [que, presenta], enumeracion_hallazgos(Hallazgos, y).

no_presenta(_, []) --> !, [].
no_presenta([], Negados) --> !, [y, que, no, presenta], enumeracion_hallazgos(Negados, ni).
no_presenta(_, Negados) --> [',', y, que, no, presenta], enumeracion_hallazgos(Negados, ni).

%   Conjuncion = y para lo que presenta, ni para lo que no presenta.
enumeracion_hallazgos(Hallazgos, Conjuncion) -->
    { maplist(nombre_en_minuscula, Hallazgos, Nombres) },
    enumeracion(Nombres, Conjuncion).

enumeracion([X], _)       --> !, [X].
enumeracion([X, Y], C)    --> !, [X, C, Y].
enumeracion([X|Xs], C)    --> [X, ','], enumeracion(Xs, C).

nombre_en_minuscula(Hallazgo, Nombre) :-
    nombre_legible(Hallazgo, Nombre0),
    downcase_atom(Nombre0, Nombre).

%!  oracion(+Palabras, -Texto) is det.
%   Une las palabras y pega las comas y el punto a la palabra anterior.
oracion(Palabras, Texto) :-
    atomic_list_concat(Palabras, ' ', Crudo),
    atomic_list_concat(Partes1, ' ,', Crudo),
    atomic_list_concat(Partes1, ',', SinComa),
    atomic_list_concat(Partes2, ' .', SinComa),
    atomic_list_concat(Partes2, '.', Texto).

/* ---------------------------------------------------------------------------
   11.6 Del análisis a los hechos del caso
   --------------------------------------------------------------------------- */

%!  interpretar_texto(+Texto, -Especie, -Edad, -Sexo, -Hallazgos, -Negados,
%!                    -Mediciones, -Desconocidas, -Fragmentos, -Resumen) is det.
%   API PARA PYTHON. Analiza la oración del usuario con la DCG y devuelve:
%     Especie, Edad (meses), Sexo   o no_indicado si el texto no los dice
%     Hallazgos     afirmados (lista ordenada, sin duplicados)
%     Negados       negados que no se afirmaron en otra parte del texto
%     Mediciones    [[Variable, Valor], ...] para el preprocesamiento numérico
%     Desconocidas  palabras con contenido que el léxico no reconoce
%     Fragmentos    [[Tipo, Valor, Texto], ...] en el orden de la oración
%     Resumen       oración generada con resumen//5 (camino inverso)
%   Valida la entrada: debe ser un texto sin variables (ground/1).
%   CORTE + FALLBACK: si el texto no es válido se devuelve un análisis vacío.
interpretar_texto(Texto, Especie, Edad, Sexo, Hallazgos, Negados,
                  Mediciones, Desconocidas, Fragmentos, Resumen) :-
    ground(Texto),
    ( atom(Texto) ; string(Texto) ), !,
    texto_a_palabras(Texto, Palabras),
    phrase(descripcion(Fs), Palabras),
    primer_valor(Fs, especie, Especie),
    primer_valor(Fs, edad, Edad),
    primer_valor(Fs, sexo, Sexo),
    findall(H, ( member(f(hallazgo, H, _), Fs), hallazgo_valido(H) ), Hs0),
    sort(Hs0, Hallazgos),
    findall(H, ( member(f(negado, L, _), Fs), member(H, L),
                 hallazgo_valido(H), \+ memberchk(H, Hallazgos) ), Ns0),
    sort(Ns0, Negados),
    findall([V, X], member(f(medicion, [V, X], _), Fs), Mediciones),
    findall(P, ( member(f(desconocida, P, _), Fs), atom(P) ), Ds0),
    list_to_set(Ds0, Desconocidas),
    maplist(exportar_fragmento, Fs, Fragmentos),
    phrase(resumen(Especie, Edad, Sexo, Hallazgos, Negados), PalabrasResumen),
    oracion(PalabrasResumen, Resumen).
interpretar_texto(_, no_indicado, no_indicado, no_indicado, [], [], [], [], [],
                  'No se recibió un texto para interpretar.').

%!  primer_valor(+Fragmentos, +Dato, -Valor) is det.
%   Primer valor de especie, sexo o edad mencionado en el texto.
%   CORTE + FALLBACK: si el texto no lo menciona, no_indicado.
primer_valor(Fs, especie, Especie) :-
    member(f(paciente, [Especie, _], _), Fs), !.
primer_valor(Fs, especie, Especie) :-
    member(f(hallazgo, _, Palabras), Fs),
    member(Palabra, Palabras),
    raza_especie(Palabra, Especie), !.
primer_valor(Fs, sexo, Sexo) :-
    member(f(sexo, Sexo, _), Fs), !.
primer_valor(Fs, sexo, Sexo) :-
    member(f(paciente, [_, Sexo], _), Fs),
    Sexo \== no_indicado, !.
primer_valor(Fs, edad, Edad) :-
    member(f(edad, Edad, _), Fs), !.
primer_valor(_, _, no_indicado).

exportar_fragmento(f(Tipo, Valor, Palabras), [Tipo, Valor, Texto]) :-
    atomic_list_concat(Palabras, ' ', Texto).


/*  ===========================================================================
    SECCIÓN 12. ADQUISICIÓN DINÁMICA DE CONOCIMIENTO (MODO EXPERTO) [Entregable 3]
    El panel "Modo experto" de la interfaz envía aquí lo que el veterinario
    quiere enseñar. Cada predicado:
      1. valida los datos en Prolog (identificador nuevo, hallazgos que
         existen, perfil que exige evidencia, severidad válida...);
      2. inyecta las cláusulas en memoria con assertz/1, de modo que el
         motor las usa en la siguiente consulta sin reiniciar;
      3. reescribe la Sección 13 de ESTE archivo con portray_clause/2, para
         que lo aprendido sobreviva a un reinicio de la aplicación.
    Un diagnóstico aprendido no necesita una regla candidato/2 propia: la
    cláusula genérica de la Sección 5 lo concluye cuando el caso cumple su
    perfil, y los módulos "¿Por qué?" y "¿Qué falta?" lo tratan igual que a
    los diagnósticos originales porque leen los mismos hechos.
    =========================================================================== */

:- use_module(library(filesex)).    % copy_file/2

/* ---------------------------------------------------------------------------
   12.1 Validación
   --------------------------------------------------------------------------- */

%!  identificador_valido(+Id) is semidet.
%   Átomo en minúscula formado solo por letras a-z, dígitos y guion bajo.
identificador_valido(Id) :-
    atomo_minuscula(Id),
    atom_codes(Id, [Primero|Codigos]),
    code_type(Primero, csymf),
    forall(member(C, Codigos),
           ( code_type(C, csym), C < 128 )).

%!  texto_no_vacio(+Texto) is semidet.
texto_no_vacio(Texto) :-
    atom(Texto),
    normalize_space(atom(Limpio), Texto),
    Limpio \== ''.

%!  errores_diagnostico(+Datos, -Errores) is det.
%   Lista de problemas del diagnóstico propuesto ([] si es válido).
errores_diagnostico(Datos, Errores) :-
    findall(Mensaje, error_diagnostico(Datos, Mensaje), Errores).

error_diagnostico(Datos, 'Los datos contienen variables libres.') :-
    \+ ground(Datos).
error_diagnostico(diagnostico(Id, _, _, _, _, _, _, _, _, _, _, _, _),
                  'El identificador debe usar solo letras minúsculas, números y guion bajo.') :-
    \+ identificador_valido(Id).
error_diagnostico(diagnostico(Id, _, _, _, _, _, _, _, _, _, _, _, _), Mensaje) :-
    nombre_diagnostico(Id, Nombre),
    format(atom(Mensaje), 'Ya existe un diagnóstico con el identificador «~w» (~w).', [Id, Nombre]).
error_diagnostico(diagnostico(_, Nombre, _, _, _, _, _, _, _, _, _, _, _),
                  'Escriba el nombre del diagnóstico.') :-
    \+ texto_no_vacio(Nombre).
error_diagnostico(diagnostico(_, _, Especies, _, _, _, _, _, _, _, _, _, _),
                  'Elija al menos una especie (perro o gato).') :-
    \+ ( is_list(Especies), Especies \== [],
         forall(member(E, Especies), especie_paciente(E, _)) ).
error_diagnostico(diagnostico(_, _, _, Curso, _, _, _, _, _, _, _, _, _),
                  'El curso debe ser agudo o cronico.') :-
    \+ memberchk(Curso, [agudo, cronico]).
error_diagnostico(diagnostico(_, _, _, _, Requisitos, Apoyo, _, _, _, _, _, _, _), Mensaje) :-
    append(Requisitos, Apoyo, Todos),
    member(H, Todos),
    \+ hallazgo_valido(H),
    format(atom(Mensaje), 'El hallazgo «~w» no existe en la base de conocimiento.', [H]).
error_diagnostico(diagnostico(_, _, _, _, Requisitos, Apoyo, _, _, _, _, _, _, _), Mensaje) :-
    member(H, Requisitos),
    memberchk(H, Apoyo),
    format(atom(Mensaje), '«~w» no puede ser a la vez obligatorio y de apoyo.', [H]).
error_diagnostico(diagnostico(_, _, _, _, _, Apoyo, Minimo, _, _, _, _, _, _), Mensaje) :-
    length(Apoyo, N),
    \+ ( integer(Minimo), Minimo >= 0, Minimo =< N ),
    format(atom(Mensaje), 'El mínimo de signos de apoyo debe estar entre 0 y ~w.', [N]).
error_diagnostico(diagnostico(_, _, _, _, Requisitos, _, Minimo, _, _, _, _, _, _),
                  'El perfil debe exigir evidencia: al menos un hallazgo obligatorio o un mínimo de apoyo mayor que 0.') :-
    Requisitos == [],
    Minimo == 0.
error_diagnostico(diagnostico(_, _, _, _, _, _, _, Severidad, _, _, _, _, _),
                  'La severidad debe ser bajo, medio, alto o critico.') :-
    \+ nivel_valor(Severidad, _).
error_diagnostico(diagnostico(_, _, _, _, _, _, _, _, Certeza, _, _, _, _),
                  'La certeza base debe ser un entero entre 10 y 90 (%).') :-
    \+ ( integer(Certeza), Certeza >= 10, Certeza =< 90 ).
error_diagnostico(diagnostico(_, _, _, _, _, _, _, _, _, Indicacion, _, _, _),
                  'Escriba la indicación para el tutor.') :-
    \+ texto_no_vacio(Indicacion).
error_diagnostico(diagnostico(Id, _, _, _, _, _, _, _, _, _, Excluye, ExcluidoPor, _), Mensaje) :-
    append(Excluye, ExcluidoPor, Otros),
    member(D, Otros),
    \+ ( diagnostico_del_catalogo(D), D \== Id ),
    format(atom(Mensaje), 'El diagnóstico «~w» no existe en el catálogo.', [D]).
error_diagnostico(diagnostico(_, _, _, _, _, _, _, _, _, _, _, _, Autor),
                  'Escriba el nombre del experto que enseña la regla.') :-
    \+ texto_no_vacio(Autor).

/* ---------------------------------------------------------------------------
   12.2 Construcción de las cláusulas
   --------------------------------------------------------------------------- */

%!  fecha_actual(-Fecha) is det.
fecha_actual(Fecha) :-
    get_time(Ahora),
    format_time(atom(Fecha), '%Y-%m-%d %H:%M', Ahora).

%!  clausulas_diagnostico(+Datos, +Fecha, -Clausulas) is det.
%   Hechos que definen el diagnóstico aprendido. No hace falta una regla:
%   la cláusula genérica candidato/2 de la Sección 5 usa estos hechos.
clausulas_diagnostico(diagnostico(Id, Nombre, Especies, Curso, Requisitos, Apoyo,
                                  Minimo, Severidad, Certeza, Indicacion,
                                  Excluye, ExcluidoPor, Autor),
                      Fecha, Clausulas) :-
    Base is Certeza / 100,
    findall(especie_afectada(Id, E), member(E, Especies), Especiales),
    findall(excluye(Id, D), member(D, Excluye), Dominadas),
    findall(excluye(D, Id), member(D, ExcluidoPor), Dominantes),
    append([ [ diagnostico_aprendido(Id, Autor, Fecha),
               nombre_diagnostico(Id, Nombre) ],
             Especiales,
             [ curso(Id, Curso),
               requisito(Id, Requisitos),
               apoyo(Id, Apoyo),
               minimo_apoyo(Id, Minimo),
               certeza_base(Id, Base),
               severidad_base(Id, Severidad),
               indicacion(Id, Indicacion) ],
             Dominadas,
             Dominantes ],
           Clausulas).

%!  texto_clausulas(+Clausulas, -Texto) is det.
%   Las cláusulas tal como quedarán escritas en el archivo .pl.
texto_clausulas(Clausulas, Texto) :-
    with_output_to(atom(Texto),
                   forall(member(C, Clausulas), portray_clause(C))).

/* ---------------------------------------------------------------------------
   12.3 Aprender (assertz/1 + escritura persistente)
   --------------------------------------------------------------------------- */

%!  vista_previa_diagnostico(+Datos, -Errores, -Texto) is det.
%   API PARA PYTHON. Valida el diagnóstico y muestra las cláusulas que se
%   escribirían, sin modificar nada.
vista_previa_diagnostico(Datos, Errores, Texto) :-
    errores_diagnostico(Datos, Errores),
    (   ground(Datos)
    ->  catch(( clausulas_diagnostico(Datos, 'AAAA-MM-DD hh:mm', Clausulas),
                texto_clausulas(Clausulas, Texto) ),
              _, Texto = '')
    ;   Texto = ''
    ).

%!  aprender_diagnostico(+Datos, -Estado, -Mensajes) is det.
%   API PARA PYTHON. Datos =
%     diagnostico(Id, Nombre, Especies, Curso, Requisitos, Apoyo, Minimo,
%                 Severidad, CertezaPct, Indicacion, Excluye, ExcluidoPor, Autor)
%   Estado = ok | error. Si es válido, cada cláusula entra a la memoria con
%   assertz/1 y se reescribe la Sección 13 del archivo.
%   CORTE: con errores no se toca la memoria ni el archivo.
aprender_diagnostico(Datos, error, Errores) :-
    errores_diagnostico(Datos, Errores),
    Errores \== [], !.
aprender_diagnostico(Datos, ok, [Mensaje]) :-
    fecha_actual(Fecha),
    clausulas_diagnostico(Datos, Fecha, Clausulas),
    forall(member(C, Clausulas), assertz(C)),
    persistir_conocimiento,
    arg(1, Datos, Id),
    arg(2, Datos, Nombre),
    length(Clausulas, N),
    format(atom(Mensaje),
           'Se aprendió «~w» (~w): ~w cláusulas en memoria y en la Sección 13 del archivo.',
           [Nombre, Id, N]).

%!  aprender_hallazgo(+Datos, -Estado, -Mensajes) is det.
%   API PARA PYTHON. Datos = hallazgo(Id, Nombre, Grupo, Pregunta, Expresiones, Autor)
%   Agrega un signo (o antecedente) nuevo, su pregunta para el módulo
%   "¿Qué falta?" y las expresiones con que la DCG lo reconocerá.
aprender_hallazgo(Datos, error, Errores) :-
    findall(M, error_hallazgo(Datos, M), Errores),
    Errores \== [], !.
aprender_hallazgo(hallazgo(Id, Nombre, Grupo, Pregunta, Expresiones, Autor), ok, [Mensaje]) :-
    fecha_actual(Fecha),
    (   sistema_organico(Grupo)
    ->  Tipo = signo(Id, Grupo)
    ;   Tipo = antecedente(Id, Grupo)
    ),
    findall(expresion_aprendida(E, Id, Autor, Fecha), member(E, Expresiones), Lexico),
    Clausulas = [ hallazgo_aprendido(Id, Autor, Fecha), Tipo,
                  nombre_hallazgo(Id, Nombre), pregunta(Id, Pregunta) | Lexico ],
    forall(member(C, Clausulas), assertz(C)),
    compilar_lexico,
    persistir_conocimiento,
    length(Lexico, N),
    format(atom(Mensaje), 'Se aprendió el hallazgo «~w» (~w) con ~w expresiones para el lenguaje natural.',
           [Nombre, Id, N]).

sistema_organico(G) :- memberchk(G, [digestivo, urinario, respiratorio, neurologico, general]).

error_hallazgo(Datos, 'Los datos contienen variables libres.') :-
    \+ ground(Datos).
error_hallazgo(hallazgo(Id, _, _, _, _, _),
               'El identificador debe usar solo letras minúsculas, números y guion bajo.') :-
    \+ identificador_valido(Id).
error_hallazgo(hallazgo(Id, _, _, _, _, _), Mensaje) :-
    hallazgo_valido(Id),
    format(atom(Mensaje), 'Ya existe el hallazgo «~w».', [Id]).
error_hallazgo(hallazgo(_, Nombre, _, _, _, _), 'Escriba el nombre del hallazgo.') :-
    \+ texto_no_vacio(Nombre).
error_hallazgo(hallazgo(_, _, Grupo, _, _, _), 'Elija un grupo válido.') :-
    \+ nombre_grupo(Grupo, _).
error_hallazgo(hallazgo(_, _, _, Pregunta, _, _), 'Escriba la pregunta para el tutor.') :-
    \+ texto_no_vacio(Pregunta).
error_hallazgo(hallazgo(_, _, _, _, Expresiones, _),
               'Escriba al menos una expresión con la que el tutor lo describiría.') :-
    \+ ( is_list(Expresiones), member(E, Expresiones), texto_no_vacio(E) ).
error_hallazgo(hallazgo(_, _, _, _, _, Autor), 'Escriba el nombre del experto.') :-
    \+ texto_no_vacio(Autor).

%!  aprender_expresion(+Texto, +Hallazgo, +Autor, -Estado, -Mensajes) is det.
%   API PARA PYTHON. Enseña a la DCG una forma nueva de decir un hallazgo
%   que ya existe (sinónimo).
aprender_expresion(Texto, Hallazgo, Autor, error, Errores) :-
    findall(M, error_expresion(Texto, Hallazgo, Autor, M), Errores),
    Errores \== [], !.
aprender_expresion(Texto, Hallazgo, Autor, ok, [Mensaje]) :-
    fecha_actual(Fecha),
    assertz(expresion_aprendida(Texto, Hallazgo, Autor, Fecha)),
    compilar_lexico,
    persistir_conocimiento,
    nombre_legible(Hallazgo, Nombre),
    format(atom(Mensaje), 'Desde ahora «~w» se interpreta como «~w».', [Texto, Nombre]).

error_expresion(Texto, Hallazgo, Autor, 'Los datos contienen variables libres.') :-
    \+ ground(Texto-Hallazgo-Autor).
error_expresion(Texto, _, _, 'Escriba la expresión.') :-
    \+ texto_no_vacio(Texto).
error_expresion(_, Hallazgo, _, Mensaje) :-
    \+ hallazgo_valido(Hallazgo),
    format(atom(Mensaje), 'El hallazgo «~w» no existe.', [Hallazgo]).
error_expresion(Texto, Hallazgo, _, Mensaje) :-
    texto_no_vacio(Texto),
    compilar_patron(Texto, Patron),
    patron_lexico(Patron, Hallazgo),
    format(atom(Mensaje), 'El léxico ya reconoce «~w» como ese hallazgo.', [Texto]).
error_expresion(_, _, Autor, 'Escriba el nombre del experto.') :-
    \+ texto_no_vacio(Autor).

/* ---------------------------------------------------------------------------
   12.4 Olvidar lo aprendido (retract/1 + escritura persistente)
   --------------------------------------------------------------------------- */

%!  olvidar(+Tipo, +Id, -Estado, -Mensajes) is det.
%   API PARA PYTHON. Tipo = diagnostico | hallazgo | expresion. Solo se
%   puede olvidar lo que se aprendió en Modo Experto: el conocimiento
%   original del archivo no se toca.
olvidar(diagnostico, Id, ok, [Mensaje]) :-
    diagnostico_aprendido(Id, _, _), !,
    forall(clausula_de_diagnostico(Id, C), retract(C)),
    persistir_conocimiento,
    format(atom(Mensaje), 'Se olvidó el diagnóstico «~w».', [Id]).
olvidar(hallazgo, Id, error, [Mensaje]) :-
    hallazgo_aprendido(Id, _, _),
    usado_por(Id, D), !,
    format(atom(Mensaje), 'No se puede olvidar «~w»: lo usa el diagnóstico «~w».', [Id, D]).
olvidar(hallazgo, Id, ok, [Mensaje]) :-
    hallazgo_aprendido(Id, _, _), !,
    forall(clausula_de_hallazgo(Id, C), retract(C)),
    compilar_lexico,
    persistir_conocimiento,
    format(atom(Mensaje), 'Se olvidó el hallazgo «~w».', [Id]).
olvidar(expresion, Texto, ok, [Mensaje]) :-
    expresion_aprendida(Texto, _, _, _), !,
    retractall(expresion_aprendida(Texto, _, _, _)),
    compilar_lexico,
    persistir_conocimiento,
    format(atom(Mensaje), 'Se olvidó la expresión «~w».', [Texto]).
olvidar(_, Id, error, [Mensaje]) :-
    format(atom(Mensaje), '«~w» no es conocimiento aprendido en Modo Experto.', [Id]).

usado_por(Hallazgo, Diagnostico) :-
    ( requisito(Diagnostico, L) ; apoyo(Diagnostico, L) ),
    memberchk(Hallazgo, L).

%!  clausula_de_diagnostico(+Id, -Clausula) is nondet.
%   Todas las cláusulas que pertenecen a un diagnóstico aprendido.
clausula_de_diagnostico(Id, Clausula) :-
    member(Clausula, [ diagnostico_aprendido(Id, _, _), nombre_diagnostico(Id, _),
                       especie_afectada(Id, _), curso(Id, _), requisito(Id, _),
                       apoyo(Id, _), minimo_apoyo(Id, _), certeza_base(Id, _),
                       severidad_base(Id, _), indicacion(Id, _),
                       excluye(Id, _), excluye(_, Id) ]),
    clause(Clausula, true).

%!  clausula_de_hallazgo(+Id, -Clausula) is nondet.
clausula_de_hallazgo(Id, Clausula) :-
    member(Clausula, [ hallazgo_aprendido(Id, _, _), signo(Id, _), antecedente(Id, _),
                       nombre_hallazgo(Id, _), pregunta(Id, _),
                       expresion_aprendida(_, Id, _, _) ]),
    clause(Clausula, true).

/* ---------------------------------------------------------------------------
   12.5 Persistencia en el archivo .pl
   La Sección 13 empieza en una línea marca. Todo lo que está por encima se
   copia tal cual; lo que está por debajo se reescribe con lo que hay en
   memoria. Antes de escribir se guarda una copia en base_conocimiento.pl.bak.
   --------------------------------------------------------------------------- */

%!  marca_aprendizaje(-Marca) is det.
%   Se arma por partes para que el texto de la marca no aparezca en el
%   código y solo exista una vez en el archivo.
marca_aprendizaje(Marca) :-
    atomic_list_concat(['%% >>> CONOCIMIENTO APRENDIDO', ' EN CALIENTE >>>'], Marca).

%!  persistir_conocimiento is det.
persistir_conocimiento :-
    archivo_base(Archivo),
    marca_aprendizaje(Marca),
    % Se lee línea por línea hasta la marca. Buscar la marca dentro del
    % archivo completo como una sola cadena (sub_string/5) es muy lento con
    % textos largos que tienen tildes.
    setup_call_cleanup(
        open(Archivo, read, Entrada, [encoding(utf8)]),
        lineas_hasta_marca(Entrada, Marca, Encabezado),
        close(Entrada)), !,
    atom_concat(Archivo, '.bak', Respaldo),
    copy_file(Archivo, Respaldo),
    setup_call_cleanup(
        open(Archivo, write, Salida, [encoding(utf8), newline(posix)]),
        ( forall(member(Linea, Encabezado), format(Salida, '~s~n', [Linea])),
          escribir_aprendido(Salida) ),
        close(Salida)).

%!  lineas_hasta_marca(+Entrada, +Marca, -Lineas) is semidet.
%   Líneas del archivo hasta la marca, incluida. Falla si no hay marca, y
%   en ese caso persistir_conocimiento/0 no escribe nada.
lineas_hasta_marca(Entrada, Marca, Lineas) :-
    read_line_to_string(Entrada, Linea0),
    Linea0 \== end_of_file,
    split_string(Linea0, "", "\r", [Linea]),
    (   atom_string(Marca, Linea)
    ->  Lineas = [Linea]
    ;   Lineas = [Linea|Resto],
        lineas_hasta_marca(Entrada, Marca, Resto)
    ).

%!  escribir_aprendido(+Salida) is det.
%   Escribe lo aprendido agrupado y con un comentario por cada elemento.
escribir_aprendido(Salida) :-
    forall(hallazgo_aprendido(H, Autor, Fecha),
           ( format(Salida, '~n%% Hallazgo aprendido: ~w · experto: ~w · ~w~n', [H, Autor, Fecha]),
             forall(clausula_de_hallazgo(H, C), portray_clause(Salida, C)) )),
    (   expresion_suelta(_)
    ->  format(Salida, '~n%% Expresiones aprendidas para hallazgos existentes~n', [])
    ;   true
    ),
    forall(expresion_suelta(C), portray_clause(Salida, C)),
    forall(diagnostico_aprendido(D, Autor, Fecha),
           ( format(Salida, '~n%% Diagnóstico aprendido: ~w · experto: ~w · ~w~n', [D, Autor, Fecha]),
             forall(clausula_de_diagnostico(D, C), portray_clause(Salida, C)) )).

expresion_suelta(expresion_aprendida(T, H, A, F)) :-
    expresion_aprendida(T, H, A, F),
    \+ hallazgo_aprendido(H, _, _).

/* ---------------------------------------------------------------------------
   12.6 Consultas del panel
   --------------------------------------------------------------------------- */

%!  conocimiento_aprendido(-Diagnosticos, -Hallazgos, -Expresiones) is det.
%   API PARA PYTHON. Lo aprendido en Modo Experto, para listarlo:
%     Diagnosticos [[Id, Nombre, Autor, Fecha, Requisitos, Apoyo, Minimo, Severidad, Especies]]
%     Hallazgos    [[Id, Nombre, Grupo, Autor, Fecha]]
%     Expresiones  [[Texto, Hallazgo, Autor, Fecha]]
conocimiento_aprendido(Diagnosticos, Hallazgos, Expresiones) :-
    findall([Id, Nombre, Autor, Fecha, R, A, M, S, Es],
            ( diagnostico_aprendido(Id, Autor, Fecha),
              nombre_diagnostico(Id, Nombre),
              requisito(Id, R), apoyo(Id, A), minimo_apoyo(Id, M),
              severidad_base(Id, S),
              findall(E, especie_afectada(Id, E), Es) ),
            Diagnosticos),
    findall([Id, Nombre, Grupo, Autor, Fecha],
            ( hallazgo_aprendido(Id, Autor, Fecha),
              nombre_hallazgo(Id, Nombre),
              grupo_hallazgo(Id, Grupo) ),
            Hallazgos),
    findall([T, H, Autor, Fecha], expresion_aprendida(T, H, Autor, Fecha), Expresiones).

%!  texto_aprendido(-Texto) is det.
%   API PARA PYTHON. Lo aprendido tal como está en memoria, en sintaxis
%   Prolog (para compararlo con lo escrito en el archivo).
texto_aprendido(Texto) :-
    with_output_to(atom(Texto), ( current_output(Salida), escribir_aprendido(Salida) )).

:- initialization(compilar_lexico).


/*  ===========================================================================
    SECCIÓN 13. CONOCIMIENTO APRENDIDO EN CALIENTE                 [Entregable 3]
    Las cláusulas debajo de la marca las escribe persistir_conocimiento/0
    cada vez que el Modo Experto aprende u olvida algo. Al reiniciar la
    aplicación, consult/1 las vuelve a cargar junto con el resto del archivo:
    así el aprendizaje sobrevive a los reinicios.
    NO edite a mano por debajo de la marca: se reescribe en cada cambio.
    =========================================================================== */
%% >>> CONOCIMIENTO APRENDIDO EN CALIENTE >>>

%% Hallazgo aprendido: ictericia · experto: Dra. Ospina · 2026-11-09 23:57
hallazgo_aprendido(ictericia, 'Dra. Ospina', '2026-11-09 23:57').
signo(ictericia, general).
nombre_hallazgo(ictericia, 'Piel u ojos amarillos (ictericia)').
pregunta(ictericia, '¿Tiene la piel, las encías o el blanco de los ojos amarillos?').
expresion_aprendida('ojos amarillos', ictericia, 'Dra. Ospina', '2026-11-09 23:57').
expresion_aprendida('piel amarilla', ictericia, 'Dra. Ospina', '2026-11-09 23:57').
expresion_aprendida('amarill*', ictericia, 'Dra. Ospina', '2026-11-09 23:57').

%% Diagnóstico aprendido: leptospirosis · experto: Dra. Ospina · 2026-11-09 23:58
diagnostico_aprendido(leptospirosis, 'Dra. Ospina', '2026-11-09 23:58').
nombre_diagnostico(leptospirosis, 'Leptospirosis').
especie_afectada(leptospirosis, perro).
especie_afectada(leptospirosis, gato).
curso(leptospirosis, agudo).
requisito(leptospirosis, [ictericia]).
apoyo(leptospirosis, [fiebre, letargo, anorexia, vomito, vomito_persistente]).
minimo_apoyo(leptospirosis, 1).
certeza_base(leptospirosis, 0.6).
severidad_base(leptospirosis, alto).
indicacion(leptospirosis, 'Use guantes al manipular la orina, no lo deje en contacto con agua estancada y acuda hoy al veterinario.').
