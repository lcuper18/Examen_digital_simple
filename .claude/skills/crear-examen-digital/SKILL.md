---
name: crear-examen-digital
description: Elabora un examen de selección única para la plataforma Examen Digital (JSON en data/examenes + código en data/codigos.json) a partir del documento de temas, la tabla de especificaciones y los materiales de estudio del docente. Úsala cuando el docente pida "el examen de <subárea/grupo>", "un examen nuevo para la plataforma" o similar.
---

# Crear un examen para la plataforma Examen Digital

Resultado: `data/examenes/<Archivo>.json`, la entrada en `data/codigos.json`, una prueba automática y una copia en Word para revisión del docente. Los ejemplos reales son `ADM02` y `GCS02` (ver `ejemplo_banco_GCS02.json`).

## 1. Reunir las fuentes (no preguntar lo que se puede leer)
Carpeta del docente: `/Users/lfallas/Documents/CTPLP/2026/LUIS FALLAS x/<grupo y subárea>/`
- `PRUEBAS/<periodo>/Temas_Examenes_*.docx`: **manda sobre todo lo demás**.
- `PRUEBAS/<periodo>/Tabla_Especificaciones_*.docx`: puntos, horas y tipos de ítem por tema.
- `MATERIALES/*.docx`: material de estudio con "Cuestionario de Práctica" y clave.
- `PRUEBAS/<periodo>/Examen_en_Clase_*.docx`: el examen en papel (para alinear, sin copiarlo).

Los .docx se leen con python-docx (`pip install python-docx`; no hay pandoc): recorrer `doc.element.body` para párrafos y tablas en orden.

## 2. Reglas de contenido (aprendidas con el docente)
1. **Examen en clase ≠ examen en casa.** El documento de temas separa ambos. Se aplica el *en clase*, y solo se usan los temas de la columna **«Qué debes estudiar»**. Nada de contenido del material que esa columna no nombre (p. ej. ISO 25030, Seis Sigma, riesgos si no están listados). Si el tema dice «parcial», cubrir solo lo que nombra.
2. **Reparto por puntos u horas.** Usar los puntos de *selección única* de la tabla de especificaciones multiplicados por el factor que dé el total pedido (p. ej. ×3 → 60). Si no hay puntos, repartir por horas (8 h → 5 preguntas, 16 h → 10 en un examen de 60).
3. **Un tercio (~20 de 60) tomado literalmente de los cuestionarios del material**, porque el estudiantado estudió con ellos; solo de temas que estén en la lista. El resto, nuevas y del mismo estilo. Marcar las literales con `origen` ("Cuestionario 02 · P22"). Los cuestionarios de los materiales ya tienen 4 opciones (A–D), así que las literales entran sin cambios; confirmarlo en cada material antes de copiar.
4. **Lenguaje para estudiantes de secundaria** (11.º): frases cortas, ejemplos concretos (una app de notas, un equipo del colegio), sin jerga innecesaria ni preguntas obvias. Ni triviales ni confusas; revisar sobre todo las primeras preguntas de cada tema.
5. **Cálculos pequeños** (media, mediana, moda, rango): datos de 4 a 6 valores, cuentas que se hacen a mano o con calculadora; en la mediana evitar que coincida con la media, y que el distractor sea el error típico.
6. **Distractores plausibles y del mismo tipo**: otras categorías del mismo material (p. ej. los otros modelos de decisión, las otras dimensiones de calidad), sin chistes ni absurdos.
7. Una sola respuesta correcta indiscutible. 4 opciones (a–d), sin «todas/ninguna de las anteriores».

## 3. Construir
1. Redactar el banco en un JSON (formato en la cabecera de `scripts/construir_examen.py`, ejemplo completo en `ejemplo_banco_GCS02.json`) dentro del scratchpad. Código nuevo, con sufijo de período (`GCS02`, `ADM02`).
2. Desde la raíz del proyecto:
   `python3 .claude/skills/crear-examen-digital/scripts/construir_examen.py <banco.json>`
   El script reparte la letra correcta por igual (n/4 por letra), exige que la correcta no sea la más larga en más del 35 %, revisa opciones/preguntas repetidas, escribe el JSON y registra el código. Si falla por longitud, acortar correctas o alargar incorrectas en el banco y repetir.
3. Agregar a `tests/test_examenes_datos.py` una prueba como `test_examen_gcs02_cobertura_y_equilibrio` (60 preguntas, reparto por tema, 20 con `origen`, letras entre 12 y 18) y correr `.venv/bin/python -m pytest -q`.
4. Copia en Word:
   `python3 .claude/skills/crear-examen-digital/scripts/revision_word.py data/examenes/<Archivo>.json revision/<CODIGO>_REVISION_DOCENTE.docx "<grupo>"`
   (`revision/` está en .gitignore). Enviarla al docente con SendUserFile.
5. Commit: `feat(exam): <CODIGO> examen en clase de <subárea> (<periodo>, N preguntas)`.

## 4. Al entregar, decir al docente
- El reparto por tema contra la lista oficial de temas (tabla) y qué quedó fuera a propósito.
- Cómo se alinea con el examen en papel y qué partes (correspondencia, respuesta corta, caso) no están en la plataforma.
- Letras: 15/15/15/15 y cuántas correctas son la opción más larga.
- Cómo probarlo: servidor en el puerto **8090** (el 8000 lo usa Docker en esa Mac; el 8001 chocaba con Packet Tracer), `http://<IP>:8090`, IP con `ipconfig getifaddr en0` (puede cambiar). Probar con un estudiante de la sección y **borrar el intento** de prueba en Resultados (un intento por estudiante y examen).
- Lanzar el servidor con `run_in_terminal` (queda en el panel de Terminal); en segundo plano se apaga si la app se cierra.
