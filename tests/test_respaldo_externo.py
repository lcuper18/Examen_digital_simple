import shutil
import sqlite3
from datetime import date

from backend import database, respaldo_externo
from tests.test_docente import _docente


def _archivos(carpeta):
    return sorted(p.name for p in (carpeta / respaldo_externo.SUBCARPETA).glob("lectiva_respaldo_*.sqlite"))


def _elegir(client, hd, carpeta):
    return client.put("/api/docente/respaldo", headers=hd, json={"carpeta": str(carpeta)})


def test_elegir_carpeta_hace_la_primera_copia_y_queda_el_estado(client, tmp_path):
    hd = _docente(client)
    externo = tmp_path / "usb"
    externo.mkdir()
    r = _elegir(client, hd, externo)
    assert r.status_code == 200 and r.json()["copia"]["ok"] and r.json()["error"] is None and r.json()["ultimo"]
    hoy = f"lectiva_respaldo_{date.today().isoformat()}.sqlite"
    assert _archivos(externo) == [hoy]
    # solo el archivo de la copia: sin temporales ni archivos -wal/-shm de SQLite
    assert sorted(p.name for p in (externo / respaldo_externo.SUBCARPETA).iterdir()) == [hoy]
    # la copia es una base válida con los estudiantes
    con = sqlite3.connect(externo / respaldo_externo.SUBCARPETA / hoy)
    assert con.execute("SELECT COUNT(*) FROM estudiantes").fetchone()[0] == 2
    con.close()
    assert client.get("/api/docente/respaldo", headers=hd).json()["carpeta"] == str(externo.resolve())
    # no se cuela entre los ajustes que ve la interfaz
    assert not any(k.startswith("respaldo_externo_") for k in client.get("/api/docente/ajustes", headers=hd).json()["ajustes"])


def test_la_copia_del_dia_se_reescribe_con_lo_nuevo_y_se_poda_a_30(client, tmp_path):
    hd = _docente(client)
    externo = tmp_path / "usb"
    externo.mkdir()
    _elegir(client, hd, externo)
    destino = externo.resolve() / respaldo_externo.SUBCARPETA
    for dia in range(1, 33):   # 32 copias viejas + un archivo ajeno que no se debe tocar
        (destino / f"lectiva_respaldo_2000-01-{dia:02d}.sqlite").write_bytes(b"x")
    (destino / "mis_notas.txt").write_text("no tocar")

    with database.get_db_context() as conn:
        conn.execute("UPDATE estudiantes SET nombre = 'CAMBIADO' WHERE id = 1")
        conn.commit()
    assert client.post("/api/docente/respaldo/ahora", headers=hd).json()["copia"]["ok"]

    nombres = _archivos(externo)
    assert len(nombres) == 30 and nombres[-1] == f"lectiva_respaldo_{date.today().isoformat()}.sqlite"
    assert "lectiva_respaldo_2000-01-01.sqlite" not in nombres and (destino / "mis_notas.txt").exists()
    con = sqlite3.connect(destino / nombres[-1])
    assert con.execute("SELECT nombre FROM estudiantes WHERE id = 1").fetchone()[0] == "CAMBIADO"
    con.close()


def test_si_la_carpeta_desaparece_se_avisa_y_no_se_inventa(client, tmp_path):
    hd = _docente(client)
    externo = tmp_path / "usb" / "respaldos"
    externo.mkdir(parents=True)
    _elegir(client, hd, externo)
    shutil.rmtree(tmp_path / "usb")          # como desconectar la memoria USB

    r = client.post("/api/docente/respaldo/ahora", headers=hd).json()
    assert r["copia"]["ok"] is False and "no existe o no está disponible" in r["copia"]["error"]
    assert r["error"] and not (tmp_path / "usb").exists()   # no recreó la ruta
    alertas = client.get("/api/docente/resumen", headers=hd).json()["alertas"]
    assert any(a["tipo"] == "respaldo" and a["ir"] == "ajustes" for a in alertas)

    # al volver la memoria, la siguiente copia funciona y la alerta desaparece
    externo.mkdir(parents=True)
    assert client.post("/api/docente/respaldo/ahora", headers=hd).json()["copia"]["ok"]
    assert not any(a["tipo"] == "respaldo" for a in client.get("/api/docente/resumen", headers=hd).json()["alertas"])


def test_una_copia_danada_no_reemplaza_a_la_buena(client, tmp_path, monkeypatch):
    hd = _docente(client)
    externo = tmp_path / "usb"
    externo.mkdir()
    _elegir(client, hd, externo)
    buena = externo.resolve() / respaldo_externo.SUBCARPETA / f"lectiva_respaldo_{date.today().isoformat()}.sqlite"
    antes = buena.read_bytes()

    def falla(copia):
        raise respaldo_externo.RespaldoError("La copia salió dañada; se conserva la anterior.")

    monkeypatch.setattr(respaldo_externo, "_verificar", falla)
    r = client.post("/api/docente/respaldo/ahora", headers=hd).json()
    assert r["copia"]["ok"] is False and buena.read_bytes() == antes
    assert not list((buena.parent).glob(".*.tmp"))   # sin archivos temporales sueltos


def test_carpetas_no_validas_y_desactivar(client, tmp_path):
    hd = _docente(client)
    assert _elegir(client, hd, "relativa/carpeta").status_code == 400
    assert _elegir(client, hd, tmp_path / "no-existe").status_code == 400
    assert _elegir(client, hd, database.PROJECT_ROOT / "respaldos").status_code == 400   # dentro del proyecto
    assert client.get("/api/docente/respaldo", headers=hd).json()["carpeta"] == ""        # no se guardó nada

    assert client.post("/api/docente/respaldo/ahora", headers=hd).status_code == 400      # sin configurar
    externo = tmp_path / "usb"
    externo.mkdir()
    _elegir(client, hd, externo)
    pasos = {p["id"]: p["hecho"] for p in client.get("/api/docente/primeros-pasos", headers=hd).json()["pasos"]}
    assert pasos["respaldo"] is True
    assert client.put("/api/docente/respaldo", headers=hd, json={"carpeta": ""}).json()["carpeta"] == ""
    assert _archivos(externo)   # desactivar no borra las copias que ya existen
    assert client.get("/api/docente/respaldo").status_code == 401
