from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ConflictLog, Hall, SeatHold, Showtime, VipZone
from app.schemas.schemas import (
    ConflictOut,
    HallOut,
    HoldOut,
    HoldRequest,
    SeatMapCell,
    SeatMapOut,
    ShowtimeOut,
    VipZoneOut,
    VipZonesUpdate,
)
from app.services.bond_engine import (
    HoldSpan,
    SeatCell,
    conflicts_with,
    find_bond_across_rows,
    find_contiguous_block,
    regular_cols_by_row,
    vip_cols_by_row,
)

api_router = APIRouter()


def _aisles(hall: Hall) -> list[int]:
    if not hall.aisle_cols.strip():
        return []
    return [int(x) for x in hall.aisle_cols.split(",") if x.strip()]


def _hall_out(h: Hall) -> HallOut:
    return HallOut(
        id=h.id,
        name=h.name,
        rows=h.rows,
        cols=h.cols,
        aisle_cols=_aisles(h),
        vip_zones=[VipZoneOut.model_validate(z) for z in h.vip_zones],
    )


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/halls", response_model=list[HallOut])
def list_halls(db: Session = Depends(get_db)):
    halls = db.scalars(select(Hall).order_by(Hall.id)).all()
    return [_hall_out(h) for h in halls]


@api_router.get("/halls/{hall_id}/vip-zones", response_model=list[VipZoneOut])
def get_vip_zones(hall_id: int, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "影厅不存在")
    zones = db.scalars(
        select(VipZone).where(VipZone.hall_id == hall_id).order_by(VipZone.row, VipZone.start_col)
    ).all()
    return zones


@api_router.put("/halls/{hall_id}/vip-zones", response_model=list[VipZoneOut])
def put_vip_zones(hall_id: int, body: VipZonesUpdate, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "影厅不存在")
    # Boundary rejection: every interval must live inside the hall grid.
    for z in body.zones:
        if z.row < 1 or z.row > hall.rows:
            raise HTTPException(422, f"VIP区间排号越界：第{z.row}排（影厅共{hall.rows}排）")
        if z.start_col < 1 or z.end_col > hall.cols:
            raise HTTPException(
                422, f"VIP区间列号越界：{z.start_col}-{z.end_col}（影厅共{hall.cols}列）"
            )
    db.query(VipZone).filter(VipZone.hall_id == hall_id).delete(synchronize_session=False)
    created = [
        VipZone(hall_id=hall_id, row=z.row, start_col=z.start_col, end_col=z.end_col)
        for z in body.zones
    ]
    db.add_all(created)
    db.commit()
    for z in created:
        db.refresh(z)
    return sorted(created, key=lambda z: (z.row, z.start_col))


@api_router.get("/showtimes", response_model=list[ShowtimeOut])
def list_showtimes(db: Session = Depends(get_db)):
    rows = db.scalars(select(Showtime).order_by(Showtime.start_at)).all()
    out = []
    for s in rows:
        hall = db.get(Hall, s.hall_id)
        out.append(
            ShowtimeOut(
                id=s.id,
                hall_id=s.hall_id,
                film_title=s.film_title,
                start_at=s.start_at,
                hall_name=hall.name if hall else None,
            )
        )
    return out


def _vip_cells(hall: Hall, db: Session) -> dict[int, set[int]]:
    zones = db.scalars(select(VipZone).where(VipZone.hall_id == hall.id)).all()
    return vip_cols_by_row([(z.row, z.start_col, z.end_col) for z in zones], hall.rows)


@api_router.get("/seatmap/{showtime_id}", response_model=SeatMapOut)
def seatmap(showtime_id: int, db: Session = Depends(get_db)):
    st = db.get(Showtime, showtime_id)
    if not st:
        raise HTTPException(404, "场次不存在")
    hall = db.get(Hall, st.hall_id)
    assert hall
    aisles = set(_aisles(hall))
    vip = _vip_cells(hall, db)
    holds = db.scalars(select(SeatHold).where(SeatHold.showtime_id == showtime_id)).all()
    occupied: set[tuple[int, int]] = set()
    for h in holds:
        for c in range(h.start_col, h.end_col + 1):
            occupied.add((h.row, c))
    cells: list[SeatMapCell] = []
    for r in range(1, hall.rows + 1):
        for c in range(1, hall.cols + 1):
            occ = (r, c) in occupied
            in_vip = c in vip.get(r, set())
            cells.append(
                SeatMapCell(
                    row=r,
                    col=c,
                    is_aisle=c in aisles,
                    is_vip=in_vip,
                    occupied=occ,
                    heat=1.0 if occ else (0.15 if c in aisles else 0.0),
                )
            )
    return SeatMapOut(
        showtime_id=showtime_id,
        hall_name=hall.name,
        rows=hall.rows,
        cols=hall.cols,
        cells=cells,
    )


@api_router.get("/holds", response_model=list[HoldOut])
def list_holds(db: Session = Depends(get_db)):
    return db.scalars(select(SeatHold).order_by(SeatHold.id.desc())).all()


@api_router.get("/conflicts", response_model=list[ConflictOut])
def list_conflicts(db: Session = Depends(get_db)):
    return db.scalars(select(ConflictLog).order_by(ConflictLog.id.desc())).all()


@api_router.post("/holds", response_model=HoldOut)
def create_hold(body: HoldRequest, db: Session = Depends(get_db)):
    st = db.get(Showtime, body.showtime_id)
    if not st:
        raise HTTPException(404, "场次不存在")
    hall = db.get(Hall, st.hall_id)
    assert hall
    aisles = set(_aisles(hall))
    existing = db.scalars(select(SeatHold).where(SeatHold.showtime_id == body.showtime_id)).all()
    holds = [HoldSpan(row=h.row, start_col=h.start_col, end_col=h.end_col) for h in existing]
    seats_by_row: dict[int, list[SeatCell]] = {}
    for r in range(1, hall.rows + 1):
        seats_by_row[r] = [
            SeatCell(row=r, col=c, is_aisle=c in aisles) for c in range(1, hall.cols + 1)
        ]

    # VIP requests may only bond inside VIP intervals; regular requests must
    # stay entirely outside them. Never mix the two regions to fill a party.
    vip = _vip_cells(hall, db)
    if body.require_vip:
        allowed_by_row = {r: vip.get(r, set()) - aisles for r in seats_by_row}
        region = "VIP区"
    else:
        allowed_by_row = regular_cols_by_row(seats_by_row, vip)
        region = "普通区"

    block = None
    if body.preferred_row:
        if body.preferred_row < 1 or body.preferred_row > hall.rows:
            raise HTTPException(422, f"优先排越界：第{body.preferred_row}排（影厅共{hall.rows}排）")
        block = find_contiguous_block(
            seats_by_row.get(body.preferred_row, []),
            holds,
            body.preferred_row,
            body.party_size,
            allowed_by_row.get(body.preferred_row, set()),
        )
    if block is None:
        block = find_bond_across_rows(seats_by_row, holds, body.party_size, allowed_by_row)
    if block is None:
        db.add(
            ConflictLog(
                showtime_id=body.showtime_id,
                party_size=body.party_size,
                reason=f"{region}无足够连续空座（人数 {body.party_size}，过道与VIP边界可能切段）",
            )
        )
        db.commit()
        raise HTTPException(409, f"{region}无足够连续空座")

    hits = conflicts_with(holds, block)
    if hits:
        db.add(
            ConflictLog(
                showtime_id=body.showtime_id,
                party_size=body.party_size,
                reason=f"与既有持座重叠：第{hits[0].row}排 {hits[0].start_col}-{hits[0].end_col}",
            )
        )
        db.commit()
        raise HTTPException(409, "与既有持座冲突")

    # Defence in depth: verify the picked block really sits in the requested region.
    block_cols = set(range(block.start_col, block.end_col + 1))
    if body.require_vip:
        if not block_cols <= vip.get(block.row, set()):
            raise HTTPException(409, "VIP连座必须全部落在VIP区间内")
    elif block_cols & vip.get(block.row, set()):
        raise HTTPException(409, "普通需求不得占用VIP区间座位")

    code = f"SB-{int(datetime.utcnow().timestamp()) % 100000:05d}"
    hold = SeatHold(
        showtime_id=body.showtime_id,
        order_code=code,
        row=block.row,
        start_col=block.start_col,
        end_col=block.end_col,
        party_size=body.party_size,
        is_vip=body.require_vip,
    )
    db.add(hold)
    db.commit()
    db.refresh(hold)
    return hold
