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
    bounds: list[tuple[int, int]] | None = None,
) -> HoldSpan | None:
    """Find leftmost contiguous empty seats of party_size in a row.

    bounds: optional inclusive (lo, hi) column spans the search is restricted to.
    An empty list forbids the whole row; None allows every non-aisle seat.
    Aisle breaks and occupied holes still apply inside each bound.
    """
    if party_size <= 0:
        return None
    allowed: set[int] | None = None
    if bounds is not None:
        allowed = set()
        for lo, hi in bounds:
            allowed.update(range(lo, hi + 1))
    taken = occupied_cols(holds, row)
    for start, end in contiguous_runs(row_cells):
        cols = range(start, end + 1)
        if allowed is not None:
            free = [c for c in cols if c in allowed and c not in taken]
        else:
            free = [c for c in cols if c not in taken]
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


def complement_spans(
    excluded: list[tuple[int, int]], lo: int, hi: int
) -> list[tuple[int, int]]:
    """Inclusive column spans inside [lo, hi] not covered by excluded spans.

    Used to keep non-VIP requests out of VIP zones.
    """
    if lo > hi:
        return []
    cuts = sorted((max(s, lo), min(e, hi)) for s, e in excluded if e >= lo and s <= hi)
    out: list[tuple[int, int]] = []
    cur = lo
    for s, e in cuts:
        if s > cur:
            out.append((cur, s - 1))
        cur = max(cur, e + 1)
    if cur <= hi:
        out.append((cur, hi))
    return out


def find_bond_across_rows(
    seats_by_row: dict[int, list[SeatCell]],
    holds: list[HoldSpan],
    party_size: int,
    bounds_by_row: dict[int, list[tuple[int, int]]] | None = None,
) -> HoldSpan | None:
    for row in sorted(seats_by_row.keys()):
        bounds = None if bounds_by_row is None else bounds_by_row.get(row, [])
        block = find_contiguous_block(seats_by_row[row], holds, row, party_size, bounds)
        if block is not None:
            return block
    return None


def conflicts_with(existing: list[HoldSpan], candidate: HoldSpan) -> list[HoldSpan]:
    hits: list[HoldSpan] = []
    for h in existing:
        if h.row != candidate.row:
            continue
        if h.end_col < candidate.start_col or candidate.end_col < h.start_col:
            continue
        hits.append(h)
    return hits
