"""Genera la copia de revisión en Word (con clave y origen de cada pregunta).

Uso:  python3 revision_word.py data/examenes/Archivo.json revision/CODIGO_REVISION_DOCENTE.docx "Grupo 11-2 B"
Requiere python-docx (pip install python-docx).
"""
import json
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt

ruta, salida, grupo = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ""
ex = json.loads(Path(ruta).read_text(encoding="utf-8"))["examen"]
pregs = ex["preguntas"]

doc = Document()
doc.styles["Normal"].font.name = "Calibri"
doc.styles["Normal"].font.size = Pt(10.5)
doc.add_heading(ex["titulo"], 1)
doc.add_paragraph(f'{ex["institucion"]} · {ex["nivel"]} {grupo} · {ex["curso_lectivo"]} · Docente: {ex["profesor"]}')
doc.add_paragraph("COPIA DE REVISIÓN PARA EL DOCENTE. En la plataforma, el orden de las preguntas (dentro de cada tema) "
                  "y de las opciones cambia para cada estudiante; aquí se muestra el orden original del archivo. "
                  "Junto al tema se indica la pregunta del cuestionario de la que proviene (si aplica).")
doc.add_paragraph(f'{len(pregs)} preguntas de selección única, 4 opciones, 1 punto cada una.')

for p in pregs:
    tema = p["tema"] + (f'  ·  {p["origen"]}' if p.get("origen") else "")
    t = doc.add_paragraph()
    t.add_run(tema).italic = True
    q = doc.add_paragraph()
    q.add_run(f'{p["numero"]}. {p["pregunta"]}').bold = True
    for l, txt in p["opciones"].items():
        doc.add_paragraph(f"{l})  {txt}", style="List Paragraph")

doc.add_page_break()
doc.add_heading("Clave de respuestas (solo docente)", 2)
doc.add_paragraph(",  ".join(f'{p["numero"]}-{p["respuesta_correcta"]}' for p in pregs))
Path(salida).parent.mkdir(parents=True, exist_ok=True)
doc.save(salida)
print("Generado", salida)
