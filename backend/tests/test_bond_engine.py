from app.services.bond_engine import (
    HoldSpan,
    SeatCell,
    conflicts_with,
    contiguous_runs,
    find_bond_across_rows,
    find_contiguous_block,
    regular_cols_by_row,
    vip_cols_by_row,
)


def _row(cols, aisles=()):
    return [SeatCell(row=1, col=c, is_aisle=(c in aisles)) for c in cols]


def test_aisle_breaks_runs():
    cells = _row(range(1, 11), aisles={5, 6})
    assert contiguous_runs(cells) == [(1, 4), (7, 10)]


def test_find_contiguous_skips_occupied():
    cells = _row(range(1, 9))
    holds = [HoldSpan(row=1, start_col=2, end_col=3)]
    block = find_contiguous_block(cells, holds, 1, 3)
    assert block == HoldSpan(row=1, start_col=4, end_col=6)


def test_party_too_large_returns_none():
    cells = _row(range(1, 5), aisles={3})
    assert find_contiguous_block(cells, [], 1, 3) is None


def test_conflict_overlap():
    existing = [HoldSpan(row=2, start_col=4, end_col=6)]
    cand = HoldSpan(row=2, start_col=6, end_col=8)
    assert conflicts_with(existing, cand) == existing


def test_find_across_rows():
    seats = {
        1: _row(range(1, 5)),
        2: [SeatCell(row=2, col=c) for c in range(1, 9)],
    }
    holds = [HoldSpan(row=1, start_col=1, end_col=4)]
    block = find_bond_across_rows(seats, holds, 4)
    assert block == HoldSpan(row=2, start_col=1, end_col=4)


# ---- VIP region restrictions ----


def test_vip_request_stays_inside_zone():
    cells = _row(range(1, 9))
    vip = vip_cols_by_row([(1, 4, 7)], rows=1)
    block = find_contiguous_block(cells, [], 1, 3, allowed_cols=vip[1])
    # leftmost block inside the zone, never pulled left into regular seats
    assert block == HoldSpan(row=1, start_col=4, end_col=6)


def test_vip_request_cannot_borrow_regular_seats_when_short():
    # zone covers cols 6-8 (3 seats) plus isolated col 3; party of 4 must fail
    cells = _row(range(1, 9))
    vip = vip_cols_by_row([(1, 3, 3), (1, 6, 8)], rows=1)
    assert find_contiguous_block(cells, [], 1, 4, allowed_cols=vip[1]) is None


def test_regular_request_excludes_vip_and_keeps_run_intact():
    # VIP zone splits the regular area; the excluded column must break the run
    cells = _row(range(1, 9))
    vip = vip_cols_by_row([(1, 4, 5)], rows=1)
    regular = regular_cols_by_row({1: cells}, vip)
    block = find_contiguous_block(cells, [], 1, 3, allowed_cols=regular[1])
    assert block == HoldSpan(row=1, start_col=1, end_col=3)
    # no block of 4 exists outside the zone
    assert find_contiguous_block(cells, [], 1, 4, allowed_cols=regular[1]) is None


def test_vip_zone_segmented_by_aisle_is_too_small():
    # VIP interval 3-8 spans aisle cols 4,5 -> real VIP seats are 3 and 6-8
    cells = _row(range(1, 11), aisles={4, 5})
    vip = vip_cols_by_row([(1, 3, 8)], rows=1)
    vip_seats = vip[1] - {4, 5}
    assert find_contiguous_block(cells, [], 1, 4, allowed_cols=vip_seats) is None
    block = find_contiguous_block(cells, [], 1, 3, allowed_cols=vip_seats)
    assert block == HoldSpan(row=1, start_col=6, end_col=8)


def test_occupied_vip_seat_makes_party_short_by_one():
    # 4 VIP seats 6-9, one occupied -> 3 free, party of 4 must fail (seed shape)
    cells = _row(range(1, 11))
    vip = vip_cols_by_row([(1, 6, 9)], rows=1)
    holds = [HoldSpan(row=1, start_col=6, end_col=6)]
    assert find_contiguous_block(cells, holds, 1, 4, allowed_cols=vip[1]) is None
    assert find_contiguous_block(cells, holds, 1, 3, allowed_cols=vip[1]) == HoldSpan(
        row=1, start_col=7, end_col=9
    )
