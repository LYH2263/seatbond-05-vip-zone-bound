"""Contiguous seat bonding: aisle columns break runs; holds conflict on overlap."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeatCell:
    row: int
    col: int
    is_aisle: bool = False


@dataclass(frozen=True)
class HoldSpan:
    row: int
    start_col: int
    end_col: int  # inclusive


def contiguous_runs(row_cells: list[SeatCell]) -> list[tuple[int, int]]:
    """Return inclusive (start_col, end_col) runs of non-aisle seats, broken by aisles."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    prev_col: int | None = None
    for cell in sorted(row_cells, key=lambda c: c.col):
        if cell.is_aisle:
            if start is not None and prev_col is not None:
                runs.append((start, prev_col))
            start = None
            prev_col = None
            continue
        if start is None:
            start = cell.col
        elif prev_col is not None and cell.col != prev_col + 1:
            runs.append((start, prev_col))
            start = cell.col
        prev_col = cell.col
    if start is not None and prev_col is not None:
        runs.append((start, prev_col))
    return runs


def occupied_cols(holds: list[HoldSpan], row: int) -> set[int]:
    cols: set[int] = set()
    for h in holds:
        if h.row != row:
            continue
        for c in range(h.start_col, h.end_col + 1):
            cols.add(c)
    return cols


def find_contiguous_block(
    row_cells: list[SeatCell],
    holds: list[HoldSpan],
    row: int,
    party_size: int,
    allowed_cols: set[int] | None = None,
) -> HoldSpan | None:
    """Find leftmost contiguous empty seats of party_size in a row.

    When ``allowed_cols`` is given, only those columns are eligible: a VIP
    request restricts the search to VIP intervals, while a regular request
    excludes VIP columns. Aisles still break runs, and an excluded column
    sitting between eligible ones breaks the run too — seats on opposite
    sides of a VIP cell must never be bonded together.
    """
    if party_size <= 0:
        return None
    if allowed_cols is not None:
        row_cells = [c for c in row_cells if c.col in allowed_cols]
    taken = occupied_cols(holds, row)
    for start, end in contiguous_runs(row_cells):
        free = [c for c in range(start, end + 1) if c not in taken]
        # free may have holes if holds punched middle — rebuild consecutive segments
        seg_start: int | None = None
        prev: int | None = None
        for col in free:
            if seg_start is None:
                seg_start = col
            elif prev is not None and col != prev + 1:
                if prev - seg_start + 1 >= party_size:
                    return HoldSpan(row=row, start_col=seg_start, end_col=seg_start + party_size - 1)
                seg_start = col
            prev = col
        if seg_start is not None and prev is not None and prev - seg_start + 1 >= party_size:
            return HoldSpan(row=row, start_col=seg_start, end_col=seg_start + party_size - 1)
    return None


def find_bond_across_rows(
    seats_by_row: dict[int, list[SeatCell]],
    holds: list[HoldSpan],
    party_size: int,
    allowed_cols_by_row: dict[int, set[int]] | None = None,
) -> HoldSpan | None:
    for row in sorted(seats_by_row.keys()):
        allowed = allowed_cols_by_row.get(row) if allowed_cols_by_row is not None else None
        block = find_contiguous_block(seats_by_row[row], holds, row, party_size, allowed)
        if block is not None:
            return block
    return None


def vip_cols_by_row(
    zones: list[tuple[int, int, int]], rows: int
) -> dict[int, set[int]]:
    """Expand (row, start_col, end_col) VIP zones into per-row column sets."""
    out: dict[int, set[int]] = {r: set() for r in range(1, rows + 1)}
    for row, start, end in zones:
        out.setdefault(row, set()).update(range(start, end + 1))
    return out


def regular_cols_by_row(
    seats_by_row: dict[int, list[SeatCell]],
    vip_by_row: dict[int, set[int]],
) -> dict[int, set[int]]:
    """Columns a non-VIP request may use: real seats outside VIP intervals."""
    out: dict[int, set[int]] = {}
    for row, cells in seats_by_row.items():
        seat_cols = {c.col for c in cells if not c.is_aisle}
        out[row] = seat_cols - vip_by_row.get(row, set())
    return out


def conflicts_with(existing: list[HoldSpan], candidate: HoldSpan) -> list[HoldSpan]:
    hits: list[HoldSpan] = []
    for h in existing:
        if h.row != candidate.row:
            continue
        if h.end_col < candidate.start_col or candidate.end_col < h.start_col:
            continue
        hits.append(h)
    return hits
