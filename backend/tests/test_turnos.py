import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.servicio import ServicioTurnos


@pytest.fixture
def client(tmp_path):
    servicio = ServicioTurnos(db_path=str(tmp_path / "test.db"), num_mesas=4)
    with TestClient(crear_app(servicio)) as c:
        yield c


def tomar(client, n=1):
    return [client.post("/api/turnos").json() for _ in range(n)]


def test_estado_inicial_cuatro_mesas_libres(client):
    estado = client.get("/api/estado").json()
    assert len(estado["mesas"]) == 4
    assert all(not m["ocupada"] for m in estado["mesas"])
    assert estado["fila"] == []


def test_primeros_cuatro_turnos_van_directo_a_mesas(client):
    turnos = tomar(client, 4)
    assert [t["codigo"] for t in turnos] == ["A-001", "A-002", "A-003", "A-004"]
    assert [t["mesa_id"] for t in turnos] == [1, 2, 3, 4]
    assert all(t["estado"] == "atendiendo" for t in turnos)


def test_quinto_turno_espera_en_fila(client):
    tomar(client, 4)
    quinto = client.post("/api/turnos").json()
    assert quinto["estado"] == "espera"
    assert quinto["posicion"] == 1
    assert client.get("/api/estado").json()["estadisticas"]["en_espera"] == 1


def test_mesa_que_se_libera_toma_el_siguiente_en_orden(client):
    tomar(client, 6)  # A-005 y A-006 en espera
    res = client.post("/api/mesas/3/finalizar").json()
    assert res["asignados"] == [{"turno": "A-005", "mesa_id": 3}]
    res = client.post("/api/mesas/1/finalizar").json()
    assert res["asignados"] == [{"turno": "A-006", "mesa_id": 1}]
    estado = client.get("/api/estado").json()
    assert estado["fila"] == []
    assert estado["estadisticas"]["atendidos"] == 2


def test_finalizar_mesa_libre_da_error(client):
    r = client.post("/api/mesas/2/finalizar")
    assert r.status_code == 409


def test_mesa_pausada_no_recibe_turnos(client):
    client.patch("/api/mesas/1", json={"activa": False})
    turno = client.post("/api/turnos").json()
    assert turno["mesa_id"] == 2
    tomar(client, 3)  # mesas 2,3,4 ocupadas, uno en fila
    assert client.get("/api/estado").json()["estadisticas"]["en_espera"] == 1
    res = client.patch("/api/mesas/1", json={"activa": True}).json()
    assert res["asignados"][0]["mesa_id"] == 1


def test_cancelar_turno_en_espera(client):
    turnos = tomar(client, 5)
    r = client.delete(f"/api/turnos/{turnos[4]['id']}")
    assert r.status_code == 200
    assert client.get("/api/estado").json()["fila"] == []


def test_websocket_recibe_actualizaciones(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["evento"] == "conectado"
        client.post("/api/turnos")
        msg = ws.receive_json()
        assert msg["evento"] == "turno_creado"
        assert msg["estado"]["mesas"][0]["turno"]["codigo"] == "A-001"


def test_reiniciar(client):
    tomar(client, 6)
    client.post("/api/reiniciar")
    estado = client.get("/api/estado").json()
    assert estado["fila"] == [] and not any(m["ocupada"] for m in estado["mesas"])
    assert client.post("/api/turnos").json()["codigo"] == "A-001"
