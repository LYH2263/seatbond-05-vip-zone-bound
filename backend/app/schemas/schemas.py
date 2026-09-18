from datetime import datetime
from pydantic import BaseModel, Field


class VipZoneIn(BaseModel):
    row: int = Field(ge=1)
    start_col: int = Field(ge=1)
    end_col: int = Field(ge=1)


class VipZonesPayload(BaseModel):
    zones: list[VipZoneIn]


class VipZoneOut(VipZoneIn):
    id: int
    hall_id: int
    model_config = {"from_attributes": True}


class HallOut(BaseModel):
    id: int
    name: str
    rows: int
    cols: int
    aisle_cols: list[int]
    vip_zones: list[VipZoneOut] = []
    model_config = {"from_attributes": True}


class ShowtimeOut(BaseModel):
    id: int
    hall_id: int
    film_title: str
    start_at: datetime
    hall_name: str | None = None
    model_config = {"from_attributes": True}


class HoldOut(BaseModel):
    id: int
    showtime_id: int
    order_code: str
    row: int
    start_col: int
    end_col: int
    party_size: int
    vip_request: bool = False
    status: str
    model_config = {"from_attributes": True}


class HoldRequest(BaseModel):
    showtime_id: int
    party_size: int = Field(ge=1, le=12)
    preferred_row: int | None = None
    vip_request: bool = False


class ConflictOut(BaseModel):
    id: int
    showtime_id: int
    party_size: int
    reason: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SeatMapCell(BaseModel):
    row: int
    col: int
    is_aisle: bool
    is_vip: bool
    occupied: bool
    heat: float


class SeatMapOut(BaseModel):
    showtime_id: int
    hall_name: str
    rows: int
    cols: int
    cells: list[SeatMapCell]
