from backend.routes.informes import nivel_y_seccion, redondear_entero
from tests.test_actividades import _crear, _nota, _preparar


def _guardar_notas(client, hd, mid, uno, dos=None):
    notas = [{"estudiante_id": 1, **uno}] + ([{"estudiante_id": 2, **dos}] if dos else [])
    assert client.put("/api/docente/notas", headers=hd, json={"materia_id": mid, "notas": notas}).status_code == 200


def test_nivel_y_redondeo_escolar():
    assert nivel_y_seccion("11-2") == ("UNDÉCIMO AÑO", "UNDÉCIMO AÑO-2")
    assert nivel_y_seccion("10-1")[0] == "DÉCIMO AÑO" and nivel_y_seccion("X") == ("X", "X")
    assert [redondear_entero(x) for x in (74.4, 74.5, 74.6, 84.0)] == [74, 75, 75, 84]


def test_acta_con_formato_oficial(client):
    hd, mid = _preparar(client)
    # TC 25/25, tareas 10/10, P1 y P2 sin nota, proyecto 7/15 -> 25 + 10 + 3.5 (7/15 de 15 = 7) ... se calcula abajo
    _guardar_notas(client, hd, mid, dict(trabajo_cotidiano=100, tareas=100, prueba01=50, prueba02=0, proyecto=50, asistencia=100))
    d = client.get(f"/api/docente/informes/acta?materia_id={mid}", headers=hd).json()
    e = d["encabezado"]
    assert e["direccion_regional"] == "Guápiles" and e["circuito"] == "06" and e["nivel"] == "UNDÉCIMO AÑO"
    assert e["seccion"] == "UNDÉCIMO AÑO-1" and e["periodo"] == 1
    ana = next(x for x in d["estudiantes"] if x["estudiante_id"] == 1)
    assert ana["cedula"] == "102340567" and ana["nombre"] == "PEREZ SOTO ANA"
    # 25 + 10 + 11.25 + 0 + 7.5 + 5 = 58.75 -> 58.8 en el sistema, 59 en el acta
    assert ana["nota_decimal"] == 58.8 and ana["nota"] == 59 and ana["completa"]
    assert not next(x for x in d["estudiantes"] if x["estudiante_id"] == 2)["completa"]
    assert client.get(f"/api/docente/informes/acta/excel?materia_id={mid}", headers=hd).status_code == 200
    assert client.get(f"/api/docente/informes/acta?materia_id={mid}").status_code == 401


def test_registro_csv_tiene_el_formato_del_docente_y_se_puede_reimportar(client):
    hd, mid = _preparar(client)
    _guardar_notas(client, hd, mid,
                   dict(trabajo_cotidiano=100, tareas=70, prueba01=84.9777, prueba02=51.7, proyecto=68.3333, asistencia=100),
                   dict(trabajo_cotidiano=50, tareas=0, prueba01=0, prueba02=0, proyecto=0, asistencia=40))
    r = client.get(f"/api/docente/informes/registro?materia_id={mid}", headers=hd)
    texto = r.text
    assert texto.startswith("﻿Id;Nombre;Trabajo cotidiano;Tareas;Prueba1;Prueba2;Proyecto;Asistencia\n")
    assert "102340567;PEREZ SOTO ANA;25;7;19,12;11,63;10,25;5\n" in texto
    assert "703440226;MORA RUIZ LUIS;12,5;0;0;0;0;2\n" in texto

    # lo exportado se vuelve a cargar y deja las notas como estaban (con redondeo a centésimas de punto)
    assert client.post(f"/api/docente/notas/importar-hoja?materia_id={mid}", headers=hd, content=r.content).json()["importados"] == 2
    assert round(_nota(client, hd, mid, 1, "prueba01") * 22.5 / 100, 2) == 19.12
    assert _nota(client, hd, mid, 2, "asistencia") == 40
    assert client.get(f"/api/docente/informes/registro/excel?materia_id={mid}", headers=hd).status_code == 200


def test_informe_para_encargados_no_filtra_la_nota_interna(client):
    hd, mid = _preparar(client)
    _guardar_notas(client, hd, mid, dict(trabajo_cotidiano=100, tareas=100, prueba01=100, prueba02=100, proyecto=100, asistencia=100))
    aid = _crear(client, hd, mid, criterios=[], puntos_max=10).json()["id"]
    client.put(f"/api/docente/actividades/{aid}/calificaciones", headers=hd, json={"calificaciones": [
        {"estudiante_id": 1, "estado": "entregado", "puntos": 9, "observacion": "Buen trabajo", "nota_interna": "SECRETO"},
        {"estudiante_id": 2, "estado": "sin_entrega", "observacion": "No entregó", "nota_interna": "SECRETO"},
    ]})
    client.put("/api/docente/asistencia/sesion", headers=hd, json={
        "materia_id": mid, "fecha": "2026-03-02", "lecciones": 2,
        "registros": [{"estudiante_id": 1, "estado": "A", "observacion": "enferma"}, {"estudiante_id": 2, "estado": "P"}]})

    r = client.get("/api/docente/informes/encargados?seccion=11-1&periodo=1", headers=hd)
    assert r.status_code == 200 and "SECRETO" not in r.text
    d = r.json()
    ana = next(i for i in d["informes"] if i["estudiante"]["id"] == 1)["materias"]
    ana = next(m for m in ana if m["actividades"])
    assert [c["puntos"] for c in ana["componentes"]][:2] == [25, 5.0] or ana["componentes"][0]["puntos"] == 25
    assert ana["actividades"][0]["puntos"] == 9 and ana["actividades"][0]["observacion"] == "Buen trabajo"
    assert ana["asistencia"]["ausencias"] == 2 and ana["asistencia"]["puntos"] == 0 and ana["asistencia"]["lecciones"] == 2
    luis = next(i for i in d["informes"] if i["estudiante"]["id"] == 2)["materias"]
    assert next(m for m in luis if m["actividades"])["actividades"][0]["estado"] == "sin_entrega"

    uno = client.get("/api/docente/informes/encargados?seccion=11-1&periodo=1&estudiante_id=2", headers=hd).json()
    assert [i["estudiante"]["id"] for i in uno["informes"]] == [2]
    assert client.get("/api/docente/informes/encargados?seccion=11-1&periodo=1&estudiante_id=99", headers=hd).status_code == 404
    assert client.get("/api/docente/informes/encargados?seccion=99-9&periodo=1", headers=hd).status_code == 404


def test_consolidado_marca_aprobado_reprobado_o_incompleto(client):
    hd, mid = _preparar(client)
    _guardar_notas(client, hd, mid, dict(trabajo_cotidiano=100, tareas=100, prueba01=100, prueba02=100, proyecto=100, asistencia=100),
                   dict(trabajo_cotidiano=10, tareas=0, prueba01=0, prueba02=0, proyecto=0, asistencia=0))
    d = client.get("/api/docente/reportes/seccion?seccion=11-1&periodo=1", headers=hd).json()
    estados = {e["estudiante_id"]: e["estado"] for e in d["estudiantes"]}
    assert estados[1] == "Incompleto"   # las otras dos materias del periodo no tienen notas
    assert all(e["reprobadas"] >= 0 for e in d["estudiantes"])


def test_plantilla_del_colegio_se_rellena_con_su_formato(client):
    hd, mid = _preparar(client)
    # Ana completa; Luis sin Proyecto (debe ir 0 y avisarse)
    _guardar_notas(client, hd, mid,
                   dict(trabajo_cotidiano=100, tareas=70, prueba01=84.9777, prueba02=51.7, proyecto=68.3333, asistencia=100),
                   dict(trabajo_cotidiano=50, tareas=0, prueba01=40, prueba02=60, proyecto=None, asistencia=40))
    # Plantilla como la del colegio: BOM, CRLF, ';', orden no alfabético y un estudiante que no está en Lectiva
    plantilla = ("﻿Id;Nombre;Trabajo cotidiano;Tareas;Prueba;Proyecto;Asistencia\r\n"
                 "703440226;MORA RUIZ LUIS;0;0;0;0;0\r\n"
                 "999999999;OTRO ESTUDIANTE;0;0;0;0;0\r\n"
                 "102340567;PEREZ SOTO ANA;0;0;0;0;0\r\n").encode("utf-8")
    d = client.post(f"/api/docente/informes/plantilla-colegio?materia_id={mid}", headers=hd, content=plantilla).json()
    texto = d["contenido"]
    assert texto.startswith("﻿Id;Nombre;Trabajo cotidiano;Tareas;Prueba;Proyecto;Asistencia\r\n")
    lineas = texto.split("\r\n")
    # mismo orden y nombres de la plantilla; Prueba = 19.12 + 11.63 = 30.75; punto decimal
    assert lineas[1] == "703440226;MORA RUIZ LUIS;12.5;0;22.5;0;2"
    assert lineas[2] == "999999999;OTRO ESTUDIANTE;0;0;0;0;0"
    assert lineas[3] == "102340567;PEREZ SOTO ANA;25;7;30.75;10.25;5"
    assert "," not in texto.replace("Trabajo cotidiano", "")
    av = d["avisos"]
    assert av["sin_pareja"] == ["OTRO ESTUDIANTE"] and av["fuera_de_plantilla"] == []
    assert av["incompletos"] == [{"nombre": "MORA RUIZ LUIS", "componentes": ["Proyecto"]}]
    assert d["columnas"] == ["Trabajo cotidiano", "Tareas", "Prueba", "Proyecto", "Asistencia"]

    sin_columnas = "Id;Nombre;Otra\r\n1;X;0\r\n".encode("utf-8")
    assert client.post(f"/api/docente/informes/plantilla-colegio?materia_id={mid}", headers=hd, content=sin_columnas).status_code == 400
    assert client.post(f"/api/docente/informes/plantilla-colegio?materia_id={mid}", content=plantilla).status_code == 401
