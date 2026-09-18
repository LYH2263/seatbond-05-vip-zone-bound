from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Hall, Showtime
from app.services.seed import seed_if_empty


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield db
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    return TestClient(app)


def _make_hall_show(db, rows=8, cols=12, aisle="5,6"):
    hall = Hall(name="测试厅", rows=rows, cols=cols, aisle_cols=aisle)
    db.add(hall)
    db.flush()
    st = Showtime(hall_id=hall.id, film_title="测试片", start_at=datetime(2026, 9, 17, 10, 0, 0))
    db.add(st)
    db.commit()
    return hall.id, st.id


def test_put_vip_zones_roundtrip(db_session, client):
    hid, _ = _make_hall_show(db_session)
    r = client.put(f"/api/halls/{hid}/vip-zones", json={"zones": [{"row": 1, "start_col": 1, "end_col": 4}]})
    assert r.status_code == 200
    assert r.json() == [
        {"id": 1, "hall_id": hid, "row": 1, "start_col": 1, "end_col": 4}
    ]
    r = client.get(f"/api/halls/{hid}/vip-zones")
    assert r.status_code == 200
    assert r.json()[0]["row"] == 1
    halls = client.get("/api/halls").json()
    assert halls[0]["vip_zones"][0]["end_col"] == 4


def test_vip_zone_row_out_of_bounds_rejected(db_session, client):
    hid, _ = _make_hall_show(db_session)
    r = client.put(
        f"/api/halls/{hid}/vip-zones", json={"zones": [{"row": 9, "start_col": 1, "end_col": 4}]}
    )
    assert r.status_code == 400


def test_vip_zone_col_out_of_bounds_rejected(db_session, client):
    hid, _ = _make_hall_show(db_session)
    r = client.put(
        f"/api/halls/{hid}/vip-zones", json={"zones": [{"row": 1, "start_col": 1, "end_col": 13}]}
    )
    assert r.status_code == 400
    r = client.put(
        f"/api/halls/{hid}/vip-zones", json={"zones": [{"row": 1, "start_col": 8, "end_col": 3}]}
    )
    assert r.status_code == 400


def test_vip_zone_overlap_rejected(db_session, client):
    hid, _ = _make_hall_show(db_session)
    r = client.put(
        f"/api/halls/{hid}/vip-zones",
        json={"zones": [{"row": 2, "start_col": 1, "end_col": 5}, {"row": 2, "start_col": 4, "end_col": 8}]},
    )
    assert r.status_code == 400
    # 不同排允许不同区间
    r = client.put(
        f"/api/halls/{hid}/vip-zones",
        json={"zones": [{"row": 1, "start_col": 1, "end_col": 4}, {"row": 2, "start_col": 3, "end_col": 8}]},
    )
    assert r.status_code == 200


def test_put_replaces_zones(db_session, client):
    hid, _ = _make_hall_show(db_session)
    client.put(
        f"/api/halls/{hid}/vip-zones", json={"zones": [{"row": 1, "start_col": 1, "end_col": 4}]}
    )
    client.put(
        f"/api/halls/{hid}/vip-zones", json={"zones": [{"row": 3, "start_col": 2, "end_col": 9}]}
    )
    zones = client.get(f"/api/halls/{hid}/vip-zones").json()
    assert [(z["row"], z["start_col"], z["end_col"]) for z in zones] == [(3, 2, 9)]


def test_vip_request_succeeds_inside_zone(db_session, client):
    hid, sid = _make_hall_show(db_session)
    client.put(
        f"/api/halls/{hid}/vip-zones", json={"zones": [{"row": 1, "start_col": 1, "end_col": 4}]}
    )
    r = client.post("/api/holds", json={"showtime_id": sid, "party_size": 2, "vip_request": True})
    assert r.status_code == 200
    hold = r.json()
    assert hold["vip_request"] is True
    assert hold["row"] == 1 and 1 <= hold["start_col"] and hold["end_col"] <= 4


def test_vip_request_one_seat_short_fails(db_session, client):
    hid, sid = _make_hall_show(db_session)
    client.put(
        f"/api/halls/{hid}/vip-zones", json={"zones": [{"row": 1, "start_col": 1, "end_col": 4}]}
    )
    r = client.post("/api/holds", json={"showtime_id": sid, "party_size": 5, "vip_request": True})
    assert r.status_code == 409
    assert "VIP" in r.json()["detail"]
    conflicts = client.get("/api/conflicts").json()
    assert "VIP" in conflicts[0]["reason"]


def test_normal_request_avoids_vip_zone(db_session, client):
    hid, sid = _make_hall_show(db_session)
    client.put(
        f"/api/halls/{hid}/vip-zones", json={"zones": [{"row": 1, "start_col": 1, "end_col": 4}]}
    )
    r = client.post("/api/holds", json={"showtime_id": sid, "party_size": 5})
    assert r.status_code == 200
    hold = r.json()
    # 过道 5-6，普通区第1排首个5连座是 7-11；绝不吃进 VIP 1-4
    assert hold["row"] == 1
    assert hold["start_col"] == 7 and hold["end_col"] == 11
    assert hold["vip_request"] is False


def test_vip_toggle_both_paths_seed_scenario(db_session, client):
    """种子场景：VIP 空位比 5 人少一，开 VIP 必败；关掉在普通区成功且不吃 VIP。"""
    seed_if_empty(db_session)
    hall = db_session.scalar(select(Hall).where(Hall.name == "一号厅"))
    st = db_session.scalar(select(Showtime).where(Showtime.hall_id == hall.id))

    r = client.post("/api/holds", json={"showtime_id": st.id, "party_size": 5, "vip_request": True})
    assert r.status_code == 409

    r = client.post("/api/holds", json={"showtime_id": st.id, "party_size": 5})
    assert r.status_code == 200
    hold = r.json()
    assert (hold["row"], hold["start_col"], hold["end_col"]) == (1, 7, 11)


def test_aisle_splits_vip_zone(db_session, client):
    hid, sid = _make_hall_show(db_session)
    # VIP 3-8 跨过道 5、6，切成 3-4 / 7-8，3 人必败
    client.put(
        f"/api/halls/{hid}/vip-zones", json={"zones": [{"row": 6, "start_col": 3, "end_col": 8}]}
    )
    r = client.post("/api/holds", json={"showtime_id": sid, "party_size": 3, "vip_request": True})
    assert r.status_code == 409
    r = client.post("/api/holds", json={"showtime_id": sid, "party_size": 2, "vip_request": True})
    assert r.status_code == 200
    hold = r.json()
    assert (hold["row"], hold["start_col"], hold["end_col"]) == (6, 3, 4)


def test_seatmap_marks_vip_cells(db_session, client):
    hid, sid = _make_hall_show(db_session)
    client.put(
        f"/api/halls/{hid}/vip-zones",
        json={"zones": [{"row": 1, "start_col": 1, "end_col": 4}, {"row": 6, "start_col": 3, "end_col": 8}]},
    )
    r = client.get(f"/api/seatmap/{sid}")
    assert r.status_code == 200
    cells = {(c["row"], c["col"]): c for c in r.json()["cells"]}
    assert cells[(1, 1)]["is_vip"] is True
    assert cells[(1, 4)]["is_vip"] is True
    assert cells[(1, 5)]["is_aisle"] is True and cells[(1, 5)]["is_vip"] is False
    assert cells[(1, 7)]["is_vip"] is False
    assert cells[(6, 3)]["is_vip"] is True
    assert cells[(2, 1)]["is_vip"] is False
