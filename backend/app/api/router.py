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
    VipZonesPayload,
)
from app.services.bond_engine import (
    HoldSpan,
    SeatCell,
    complement_spans,
    conflicts_with,
    find_bond_across_rows,
    find_contiguous_block,
)

api_router = APIRouter()


def _aisles(hall: Hall) -> list[int]:
    if not hall.aisle_cols.strip():
        return []
    return [int(x) for x in hall.aisle_cols.split(",") if x.strip()]


def _vip_spans_by_row(db: Session, hall_id: int) -> dict[int, list[tuple[int, int]]]:
    zones = db.scalars(select(VipZone).where(VipZone.hall_id == hall_id)).all()
    spans: dict[int, list[tuple[int, int]]] = {}
    for z in zones:
        spans.setdefault(z.row, []).append((z.start_col, z.end_col))
    return spans


def _vip_cell_set(spans: dict[int, list[tuple[int, int]]]) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for r, row_spans in spans.items():
        for lo, hi in row_spans:
            for c in range(lo, hi + 1):
                cells.add((r, c))
    return cells


def _hall_out(h: Hall) -> HallOut:
    zones = sorted(h.vip_zones, key=lambda z: (z.row, z.start_col))
    return HallOut(
        id=h.id,
        name=h.name,
        rows=h.rows,
        cols=h.cols,
        aisle_cols=_aisles(h),
        vip_zones=[
            VipZoneOut(id=z.id, hall_id=z.hall_id, row=z.row, start_col=z.start_col, end_col=z.end_col)
            for z in zones
        ],
    )


def _has_overlap(spans: list[tuple[int, int]]) -> bool:
    ordered = sorted(spans)
    return any(b >= c for (_, b), (c, _) in zip(ordered, ordered[1:]))


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/halls", response_model=list[HallOut])
def list_halls(db: Session = Depends(get_db)):
    return [_hall_out(h) for h in db.scalars(select(Hall).order_by(Hall.id)).all()]


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
def put_vip_zones(hall_id: int, body: VipZonesPayload, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "影厅不存在")

    by_row: dict[int, list[tuple[int, int]]] = {}
    for z in body.zones:
        if z.row < 1 or z.row > hall.rows:
            raise HTTPException(400, f"VIP 区间排号越界：第{z.row}排（影厅共 {hall.rows} 排）")
        if z.start_col < 1 or z.end_col > hall.cols or z.start_col > z.end_col:
            raise HTTPException(
                400,
                f"VIP 区间列号越界：第{z.row}排 {z.start_col}-{z.end_col}（影厅共 {hall.cols} 列）",
            )
        by_row.setdefault(z.row, []).append((z.start_col, z.end_col))
    for r, spans in by_row.items():
        if _has_overlap(spans):
            raise HTTPException(400, f"第{r}排 VIP 区间互相重叠")

    db.execute(VipZone.__table__.delete().where(VipZone.hall_id == hall_id))
    created = [
        VipZone(hall_id=hall_id, row=r, start_col=lo, end_col=hi)
        for r, spans in by_row.items()
        for lo, hi in spans
    ]
    db.add_all(created)
    db.commit()
    zones = db.scalars(
        select(VipZone).where(VipZone.hall_id == hall_id).order_by(VipZone.row, VipZone.start_col)
    ).all()
    return zones


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


@api_router.get("/seatmap/{showtime_id}", response_model=SeatMapOut)
def seatmap(showtime_id: int, db: Session = Depends(get_db)):
    st = db.get(Showtime, showtime_id)
    if not st:
        raise HTTPException(404, "场次不存在")
    hall = db.get(Hall, st.hall_id)
    assert hall
    aisles = set(_aisles(hall))
    vip = _vip_cell_set(_vip_spans_by_row(db, hall.id))
    holds = db.scalars(select(SeatHold).where(SeatHold.showtime_id == showtime_id)).all()
    occupied: set[tuple[int, int]] = set()
    for h in holds:
        for c in range(h.start_col, h.end_col + 1):
            occupied.add((h.row, c))
    cells: list[SeatMapCell] = []
    for r in range(1, hall.rows + 1):
        for c in range(1, hall.cols + 1):
            occ = (r, c) in occupied
            is_vip_cell = (r, c) in vip
            cells.append(
                SeatMapCell(
                    row=r,
                    col=c,
                    is_aisle=c in aisles,
                    is_vip=is_vip_cell,
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
    vip_spans = _vip_spans_by_row(db, hall.id)
    existing = db.scalars(select(SeatHold).where(SeatHold.showtime_id == body.showtime_id)).all()
    holds = [HoldSpan(row=h.row, start_col=h.start_col, end_col=h.end_col) for h in existing]
    seats_by_row: dict[int, list[SeatCell]] = {}
    for r in range(1, hall.rows + 1):
        seats_by_row[r] = [
            SeatCell(row=r, col=c, is_aisle=c in aisles) for c in range(1, hall.cols + 1)
        ]

    # VIP 需求：只在 VIP 区间内找连座，绝不拼区间外普通座；
    # 普通需求：在 VIP 补集（普通区）内找，绝不占用 VIP 格。
    # 两种路径都经过过道切段：VIP 区间被过道切开时同样可能人数不足。
    if body.vip_request:
        bounds_by_row = {r: list(spans) for r, spans in vip_spans.items()}
        for r in seats_by_row:
            bounds_by_row.setdefault(r, [])
        miss_reason = f"VIP 区无足够连续空座（人数 {body.party_size}）"
    else:
        bounds_by_row = {
            r: complement_spans(vip_spans.get(r, []), 1, hall.cols) for r in seats_by_row
        }
        miss_reason = f"普通区无足够连续空座（人数 {body.party_size}）"

    block = None
    if body.preferred_row:
        block = find_contiguous_block(
            seats_by_row.get(body.preferred_row, []),
            holds,
            body.preferred_row,
            body.party_size,
            bounds_by_row.get(body.preferred_row, []),
        )
    if block is None:
        block = find_bond_across_rows(seats_by_row, holds, body.party_size, bounds_by_row)
    if block is None:
        db.add(
            ConflictLog(
                showtime_id=body.showtime_id,
                party_size=body.party_size,
                reason=miss_reason,
            )
        )
        db.commit()
        raise HTTPException(409, miss_reason)

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

    code = f"SB-{int(datetime.utcnow().timestamp()) % 100000:05d}"
    hold = SeatHold(
        showtime_id=body.showtime_id,
        order_code=code,
        row=block.row,
        start_col=block.start_col,
        end_col=block.end_col,
        party_size=body.party_size,
        vip_request=body.vip_request,
    )
    db.add(hold)
    db.commit()
    db.refresh(hold)
    return hold
