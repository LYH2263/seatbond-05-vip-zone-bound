from datetime import datetime, timedelta

from app.models.models import Hall, SeatHold, Showtime, VipZone


def _make_hall(db, **kw) -> Hall:
    hall = Hall(
        name=kw.pop("name", "测试厅"),
        rows=kw.pop("rows", 6),
        cols=kw.pop("cols", 10),
        aisle_cols=kw.pop("aisle_cols", "4,5"),
    )
    db.add(hall)
    db.flush()
    return hall


def _make_showtime(db, hall_id: int) -> Showtime:
    st = Showtime(
        hall_id=hall_id, film_title="测试片", start_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(st)
    db.flush()
    return st


# ---- VIP zone read/write + boundary rejection ----


def test_vip_zones_get_put_roundtrip(client, db):
    hall = _make_hall(db)
    db.commit()
    r = client.put(
        f"/api/halls/{hall.id}/vip-zones",
        json={"zones": [{"row": 2, "start_col": 3, "end_col": 8}, {"row": 4, "start_col": 9, "end_col": 10}]},
    )
    assert r.status_code == 200, r.text
    assert {(z["row"], z["start_col"], z["end_col"]) for z in r.json()} == {
        (2, 3, 8),
        (4, 9, 10),
    }
    r = client.get(f"/api/halls/{hall.id}/vip-zones")
    assert len(r.json()) == 2
    # halls list embeds zones too
    r = client.get("/api/halls")
    got = next(h for h in r.json() if h["id"] == hall.id)
    assert len(got["vip_zones"]) == 2


def test_put_vip_zones_replaces_existing(client, db):
    hall = _make_hall(db)
    db.add(VipZone(hall_id=hall.id, row=1, start_col=1, end_col=2))
    db.commit()
    r = client.put(
        f"/api/halls/{hall.id}/vip-zones",
        json={"zones": [{"row": 3, "start_col": 7, "end_col": 9}]},
    )
    assert r.status_code == 200
    assert [(z["row"], z["start_col"], z["end_col"]) for z in r.json()] == [(3, 7, 9)]


def test_vip_zone_row_out_of_bounds_rejected(client, db):
    hall = _make_hall(db, rows=6, cols=10)
    db.commit()
    r = client.put(
        f"/api/halls/{hall.id}/vip-zones",
        json={"zones": [{"row": 7, "start_col": 1, "end_col": 3}]},
    )
    assert r.status_code == 422
    assert "排号越界" in r.json()["detail"]


def test_vip_zone_col_out_of_bounds_rejected(client, db):
    hall = _make_hall(db, rows=6, cols=10)
    db.commit()
    r = client.put(
        f"/api/halls/{hall.id}/vip-zones",
        json={"zones": [{"row": 1, "start_col": 9, "end_col": 11}]},
    )
    assert r.status_code == 422
    assert "列号越界" in r.json()["detail"]


def test_vip_zone_reversed_span_rejected(client, db):
    hall = _make_hall(db)
    db.commit()
    r = client.put(
        f"/api/halls/{hall.id}/vip-zones",
        json={"zones": [{"row": 1, "start_col": 8, "end_col": 3}]},
    )
    assert r.status_code == 422


def test_vip_zones_unknown_hall_404(client):
    r = client.get("/api/halls/9999/vip-zones")
    assert r.status_code == 404
    r = client.put("/api/halls/9999/vip-zones", json={"zones": []})
    assert r.status_code == 404


# ---- hold request: VIP switch both paths (seed shape) ----


def _seed_vip_short_by_one(db) -> tuple[int, int]:
    """Hall 2 shape: VIP free seats are exactly one fewer than a party of 4."""
    hall = _make_hall(db, rows=6, cols=10, aisle_cols="4,5")
    st = _make_showtime(db, hall.id)
    db.add_all(
        [
            SeatHold(showtime_id=st.id, order_code="SB-1003", row=2, start_col=1, end_col=2, party_size=2),
            SeatHold(showtime_id=st.id, order_code="SB-1004", row=2, start_col=3, end_col=3, party_size=1),
            VipZone(hall_id=hall.id, row=2, start_col=3, end_col=8),
            VipZone(hall_id=hall.id, row=4, start_col=9, end_col=10),
        ]
    )
    db.commit()
    return hall.id, st.id


def test_vip_request_short_by_one_fails(client, db):
    _hall_id, sid = _seed_vip_short_by_one(db)
    r = client.post("/api/holds", json={"showtime_id": sid, "party_size": 4, "require_vip": True})
    assert r.status_code == 409
    assert "VIP区" in r.json()["detail"]
    # conflict recorded
    rows = client.get("/api/conflicts").json()
    assert any(c["showtime_id"] == sid and c["party_size"] == 4 for c in rows)


def test_regular_request_succeeds_without_touching_vip(client, db):
    _hall_id, sid = _seed_vip_short_by_one(db)
    r = client.post("/api/holds", json={"showtime_id": sid, "party_size": 4, "require_vip": False})
    assert r.status_code == 200, r.text
    hold = r.json()
    assert hold["is_vip"] is False
    # block must not eat any VIP cell (row2 cols 3-8 incl. aisles, row4 cols 9-10)
    vip_cells = {(2, c) for c in range(3, 9)} | {(4, 9), (4, 10)}
    held = {(hold["row"], c) for c in range(hold["start_col"], hold["end_col"] + 1)}
    assert not (held & vip_cells)


def test_vip_request_succeeds_inside_zone(client, db):
    _hall_id, sid = _seed_vip_short_by_one(db)
    r = client.post("/api/holds", json={"showtime_id": sid, "party_size": 3, "require_vip": True})
    assert r.status_code == 200, r.text
    hold = r.json()
    assert hold["is_vip"] is True
    # aisle cols 4,5 split zone row2 3-8 into {3} and {6,7,8}; c3 is occupied
    assert (hold["row"], hold["start_col"], hold["end_col"]) == (2, 6, 8)


def test_regular_request_never_uses_vip_even_if_only_fit_there(client, db):
    hall = _make_hall(db, rows=1, cols=8, aisle_cols="")
    st = _make_showtime(db, hall.id)
    db.add(VipZone(hall_id=hall.id, row=1, start_col=3, end_col=6))
    # col 1 held -> regular cols are {2, 7, 8}; a party of 4 would only "fit" via VIP
    db.add(SeatHold(showtime_id=st.id, order_code="SB-X1", row=1, start_col=1, end_col=1, party_size=1))
    db.commit()
    r = client.post("/api/holds", json={"showtime_id": st.id, "party_size": 4})
    assert r.status_code == 409
    # party of 2 still bonds in the regular segment 7-8
    r = client.post("/api/holds", json={"showtime_id": st.id, "party_size": 2})
    assert r.status_code == 200
    hold = r.json()
    assert (hold["row"], hold["start_col"], hold["end_col"]) == (1, 7, 8)
    assert hold["is_vip"] is False


def test_vip_request_without_zones_fails(client, db):
    hall = _make_hall(db, rows=1, cols=8, aisle_cols="")
    st = _make_showtime(db, hall.id)
    db.commit()
    r = client.post("/api/holds", json={"showtime_id": st.id, "party_size": 2, "require_vip": True})
    assert r.status_code == 409


# ---- seatmap VIP outline readable ----


def test_seatmap_marks_vip_cells(client, db):
    hall_id, sid = _seed_vip_short_by_one(db)
    r = client.get(f"/api/seatmap/{sid}")
    assert r.status_code == 200
    data = r.json()
    vip_cells = {(c["row"], c["col"]) for c in data["cells"] if c["is_vip"]}
    assert vip_cells == {(2, c) for c in range(3, 9)} | {(4, 9), (4, 10)}
    # aisle + VIP flags coexist; aisle still breaks runs
    c45 = [c for c in data["cells"] if c["row"] == 2 and c["col"] in (4, 5)]
    assert all(c["is_aisle"] and c["is_vip"] for c in c45)
    # outline survives via halls embed too
    hall = next(h for h in client.get("/api/halls").json() if h["id"] == hall_id)
    assert len(hall["vip_zones"]) == 2
