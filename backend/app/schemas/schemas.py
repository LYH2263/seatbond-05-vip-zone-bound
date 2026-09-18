from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class VipZoneIn(BaseModel):
    row: int = Field(ge=1)
    start_col: int = Field(ge=1)
    end_col: int = Field(ge=1)

    @model_validator(mode="after")
    def _check_span(self):
        if self.end_col < self.start_col:
            raise ValueError("VIP区间止列不能小于起列")
        return self


class VipZoneOut(BaseModel):
    id: int
    hall_id: int
    row: int
    start_col: int
    end_col: int
    model_config = {"from_attributes": True}


class VipZonesUpdate(BaseModel):
    zones: list[VipZoneIn]


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
    status: str
    is_vip: bool = False
    model_config = {"from_attributes": True}


class HoldRequest(BaseModel):
    showtime_id: int
    party_size: int = Field(ge=1, le=12)
    preferred_row: int | None = None
    require_vip: bool = False


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
    is_vip: bool = False
    occupied: bool
    heat: float


class SeatMapOut(BaseModel):
    showtime_id: int
    hall_name: str
    rows: int
    cols: int
    cells: list[SeatMapCell]
