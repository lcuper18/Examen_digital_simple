import io
import zipfile

from tests.test_actividades import _preparar

MB = 1024 * 1024


def _ruta(mid):
    return f"/api/docente/notas/importar-hoja?materia_id={mid}"


def test_un_archivo_demasiado_grande_se_rechaza_antes_de_procesarlo(client):
    hd, mid = _preparar(client)
    # 6 MB declarados: pasa el filtro general (10 MB) pero no el de las cargas de archivos (5 MB)
    r = client.post(_ruta(mid), headers=hd, content=b"x" * (6 * MB))
    assert r.status_code == 413 and "máximo 5 MB" in r.json()["detail"]
    # más de 10 MB: lo corta el filtro general, ya sea una carga de archivo o un cuerpo JSON
    r = client.post(_ruta(mid), headers=hd, content=b"x" * (11 * MB))
    assert r.status_code == 413 and "máximo 10 MB" in r.json()["detail"]
    r = client.post("/api/docente/estudiantes/importar", headers=hd, json={"csv": "x" * (11 * MB)})
    assert r.status_code == 413


def test_sin_content_length_tambien_se_corta_mientras_se_lee(client):
    hd, mid = _preparar(client)
    trozos = (b"x" * MB for _ in range(6))   # llega por partes (chunked): no hay Content-Length que mirar
    r = client.post(_ruta(mid), headers=hd, content=trozos)
    assert r.status_code == 413


def test_un_excel_que_se_descomprime_enorme_se_rechaza(client):
    hd, mid = _preparar(client)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("relleno.bin", b"\0" * (60 * MB))   # pesa ~60 KB comprimido, 60 MB abierto
    assert len(buffer.getvalue()) < MB
    r = client.post(_ruta(mid), headers=hd, content=buffer.getvalue())
    assert r.status_code == 413 and "al abrirse" in r.json()["detail"]


def test_un_archivo_normal_sigue_funcionando(client):
    hd, mid = _preparar(client)
    hoja = "Id;Nombre;Tareas\n102340567;PEREZ SOTO ANA;8\n".encode()
    r = client.post(_ruta(mid), headers=hd, content=hoja)
    assert r.status_code == 200 and r.json()["importados"] == 1
