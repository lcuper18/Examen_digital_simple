import io

from openpyxl import Workbook

from backend import database
from tests.test_docente import _docente, _materia


def _preparar(client):
    """Dos estudiantes de 11-1 con nombres y cédulas distintos (el conftest los deja iguales)."""
    with database.get_db_context() as conn:
        conn.execute("UPDATE estudiantes SET seccion = '11-1'")
        conn.execute("UPDATE estudiantes SET nombre='ANA', apellido1='PEREZ', apellido2='SOTO', cedula='1-0234-0567' WHERE id=1")
        conn.execute("UPDATE estudiantes SET nombre='LUIS', apellido1='MORA', apellido2='RUIZ', cedula='7-0344-0226' WHERE id=2")
        conn.commit()
    hd = _docente(client)
    return hd, _materia(client, hd)


def _nota(client, hd, mid, estudiante_id, componente):
    notas = client.get(f"/api/docente/notas?materia_id={mid}", headers=hd).json()["notas"]
    return next(n for n in notas if n["estudiante_id"] == estudiante_id)[componente]


def _crear(client, hd, mid, nombre="Tarea 1", criterios=None, **extra):
    cuerpo = {"materia_id": mid, "componente": "tareas", "nombre": nombre,
              "criterios": criterios if criterios is not None else [{"nombre": "A", "puntos": 6}, {"nombre": "B", "puntos": 4}]}
    return client.post("/api/docente/actividades", headers=hd, json={**cuerpo, **extra})


def test_crear_actividad_valida_y_calcula_puntos(client):
    hd, mid = _preparar(client)
    assert client.get(f"/api/docente/actividades?materia_id={mid}").status_code == 401
    assert _crear(client, hd, mid, componente="inventado").status_code == 400
    assert _crear(client, hd, mid, criterios=[]).status_code == 400            # sin puntos ni criterios
    assert _crear(client, hd, mid, criterios=[], puntos_max=20).status_code == 200
    assert _crear(client, hd, mid, criterios=[], puntos_max=5).status_code == 409  # mismo nombre
    r = _crear(client, hd, mid, nombre="Tarea 2")
    assert r.status_code == 200
    a = next(x for x in client.get(f"/api/docente/actividades?materia_id={mid}", headers=hd).json()["actividades"]
             if x["nombre"] == "Tarea 2")
    assert a["puntos_max"] == 10 and len(a["criterios"]) == 2


def test_calificar_recalcula_el_componente(client):
    hd, mid = _preparar(client)
    t1 = _crear(client, hd, mid).json()["id"]                          # 10 puntos con rúbrica
    t2 = _crear(client, hd, mid, nombre="Tarea 2", criterios=[], puntos_max=20).json()["id"]
    cal = lambda aid, filas: client.put(f"/api/docente/actividades/{aid}/calificaciones", headers=hd,
                                        json={"calificaciones": filas})

    # criterio que supera su máximo, estado inventado, estudiante de otra sección
    assert cal(t1, [{"estudiante_id": 1, "estado": "entregado", "criterios": [7, 4]}]).status_code == 400
    assert cal(t1, [{"estudiante_id": 1, "estado": "x"}]).status_code == 400
    assert cal(t1, [{"estudiante_id": 99, "estado": "entregado", "puntos": 1}]).status_code == 400

    # sin calificar nada, la nota no se toca
    assert _nota(client, hd, mid, 1, "tareas") is None

    assert cal(t1, [{"estudiante_id": 1, "estado": "entregado", "criterios": [5, 3], "observacion": "Bien", "nota_interna": "x"},
                    {"estudiante_id": 2, "estado": "sin_entrega"}]).status_code == 200
    assert _nota(client, hd, mid, 1, "tareas") == 80       # 8 de 10
    assert _nota(client, hd, mid, 2, "tareas") == 0        # sin entrega cuenta 0

    # una segunda tarea: (8 + 10) de (10 + 20)
    assert cal(t2, [{"estudiante_id": 1, "estado": "tardio", "puntos": 10},
                    {"estudiante_id": 2, "estado": "revision", "puntos": 15}]).status_code == 200
    assert round(_nota(client, hd, mid, 1, "tareas"), 4) == 60.0
    assert _nota(client, hd, mid, 2, "tareas") == 0        # en revisión no cuenta: sigue 0 de 10

    # exonerar de la segunda y corregir
    assert cal(t2, [{"estudiante_id": 1, "estado": "exonerado"}]).status_code == 200
    assert _nota(client, hd, mid, 1, "tareas") == 80

    det = client.get(f"/api/docente/actividades/{t1}/calificaciones", headers=hd).json()
    uno = next(c for c in det["calificaciones"] if c["estudiante_id"] == 1)
    assert uno["puntos"] == 8 and uno["criterios"] == [5, 3] and uno["observacion"] == "Bien" and uno["nota_interna"] == "x"

    # eliminar una actividad recalcula con la que queda
    assert client.delete(f"/api/docente/actividades/{t1}", headers=hd).status_code == 200
    assert client.get(f"/api/docente/actividades/{t1}/calificaciones", headers=hd).status_code == 404


def _hoja_xlsx(filas):
    libro = Workbook()
    hoja = libro.active
    for f in filas:
        hoja.append(f)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def test_importar_hoja_de_calificacion(client):
    hd, mid = _preparar(client)
    datos = _hoja_xlsx([
        ["TAREA: Inventario"], [],
        ["N.º", "Estudiante", "Entrega", "E1 Inventario (4)", "E2 Diagnóstico (5,5)", "Total (9,5)", "Estado",
         "Observaciones para el estudiante", "Notas internas del docente"],
        [1, "PEREZ SOTO, Ana", "PDF", 3, 5, None, "Calificado", "Muy bien", "interna"],
        [2, "Luis Mora Ruiz", "Sin entrega", 0, 0, None, "Sin entrega", "No entregó", None],
        [3, "NADIE CONOCIDO, Fulano", "PDF", 1, 1, None, "Calificado", "", None],
        [None, "Nota: E2 se otorgó completo a quienes entregaron.", None, None, None, None, None, None, None],
    ])
    url = f"/api/docente/actividades/importar?materia_id={mid}&componente=tareas&nombre=Tarea%20inventario"
    r = client.post(url, headers=hd, content=datos)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["importadas"] == 2 and j["sin_pareja"] == ["NADIE CONOCIDO, Fulano"] and j["puntos_max"] == 9.5
    det = client.get(f"/api/docente/actividades/{j['actividad_id']}/calificaciones", headers=hd).json()
    ana = next(c for c in det["calificaciones"] if c["estudiante_id"] == 1)
    luis = next(c for c in det["calificaciones"] if c["estudiante_id"] == 2)
    assert ana["estado"] == "entregado" and ana["puntos"] == 8 and ana["criterios"] == [3, 5] and ana["nota_interna"] == "interna"
    assert luis["estado"] == "sin_entrega" and luis["puntos"] == 0
    assert round(_nota(client, hd, mid, 1, "tareas"), 2) == round(8 / 9.5 * 100, 2)

    # importar de nuevo reemplaza (no duplica) y una hoja sin criterios se rechaza
    assert client.post(url, headers=hd, content=datos).status_code == 200
    assert len(client.get(f"/api/docente/actividades?materia_id={mid}", headers=hd).json()["actividades"]) == 1
    sin_criterios = _hoja_xlsx([["Estudiante", "Estado"], ["Ana Perez Soto", "Calificado"]])
    assert client.post(url, headers=hd, content=sin_criterios).status_code == 400


def test_importar_notas_desde_csv_en_puntos(client):
    hd, mid = _preparar(client)
    csv = ("﻿Id;Nombre;Trabajo cotidiano;Tareas;Prueba1;Prueba2;Proyecto;Asistencia\n"
           "703440226;MORA RUIZ LUIS;25;5;22,5;;10,25;5\n"
           "102340567;PEREZ SOTO ANA;12,5;7;30;0;15;5\n"
           "999999999;DESCONOCIDO;25;5;22,5;0;10;5\n").encode()
    r = client.post(f"/api/docente/notas/importar-hoja?materia_id={mid}", headers=hd, content=csv)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["importados"] == 2 and j["sin_pareja"] == ["DESCONOCIDO"] and len(j["avisos"]) == 1  # Prueba1 = 30 > 22.5
    assert _nota(client, hd, mid, 2, "trabajo_cotidiano") == 100
    assert round(_nota(client, hd, mid, 2, "proyecto"), 2) == round(10.25 / 15 * 100, 2)
    assert _nota(client, hd, mid, 2, "prueba02") is None      # celda vacía: no se toca
    assert _nota(client, hd, mid, 1, "trabajo_cotidiano") == 50
    assert _nota(client, hd, mid, 1, "prueba01") is None      # superaba el máximo: se avisó y se omitió
    assert client.post(f"/api/docente/notas/importar-hoja?materia_id={mid}", headers=hd, content=b"x;y\n1;2\n").status_code == 400
