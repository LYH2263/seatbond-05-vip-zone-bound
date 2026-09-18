from app.services.bond_engine import (
    HoldSpan,
    SeatCell,
    complement_spans,
    contiguous_runs,
    find_bond_across_rows,
    find_contiguous_block,
)


def _row(cols, aisles=(), row=1):
    return [SeatCell(row=row, col=c, is_aisle=(c in aisles)) for c in cols]


def test_vip_request_stays_inside_zone():
    # VIP 区 3-6，连座 4 人必须落在区内，不得拼右侧普通座
    cells = _row(range(1, 13), aisles={5, 6})
    # 过道把 VIP 区 3-6 切成 3-4 一段，4 人在区内必败
    assert find_contiguous_block(cells, [], 1, 4, bounds=[(3, 6)]) is None
    # 2 人可以：取区内最左连续段 3-4
    assert find_contiguous_block(cells, [], 1, 2, bounds=[(3, 6)]) == HoldSpan(1, 3, 4)


def test_vip_request_does_not_stitch_normal_seats():
    # VIP 区只有 1-2 两格，3 人需求不得把普通座 3 拼进来
    cells = _row(range(1, 9))
    assert find_contiguous_block(cells, [], 1, 3, bounds=[(1, 2)]) is None


def test_normal_request_keeps_out_of_vip():
    # VIP 区 1-4 全满座也不能用；补集覆盖 5-12，过道列 5-6 再由 aisle 规则切段
    cells = _row(range(1, 13), aisles={5, 6})
    normal = complement_spans([(1, 4)], 1, 12)
    assert normal == [(5, 12)]
    assert find_contiguous_block(cells, [], 1, 4, bounds=normal) == HoldSpan(1, 7, 10)


def test_normal_request_excludes_inner_vip_zone():
    # VIP 区在中间 5-7，普通区被切成左右两段
    assert complement_spans([(5, 7)], 1, 10) == [(1, 4), (8, 10)]
    cells = _row(range(1, 11))
    # 4 人只能落左段，不会跨越 VIP
    assert find_contiguous_block(cells, [], 1, 4, bounds=[(1, 4), (8, 10)]) == HoldSpan(1, 1, 4)
    # 5 人两段都不够
    assert find_contiguous_block(cells, [], 1, 5, bounds=[(1, 4), (8, 10)]) is None


def test_aisle_segments_vip_zone():
    # VIP 区 3-8 跨过道 5、6 → 3-4 与 7-8 各 2 座，3 人必败
    cells = _row(range(1, 13), aisles={5, 6})
    assert contiguous_runs([c for c in cells if 3 <= c.col <= 8]) == [(3, 4), (7, 8)]
    assert find_contiguous_block(cells, [], 1, 3, bounds=[(3, 8)]) is None


def test_across_rows_vip_and_normal_paths():
    seats = {
        1: _row(range(1, 9), row=1),  # VIP 1-3（3座）
        2: _row(range(1, 9), row=2),
    }
    # VIP 路径：第1排仅3座，4人放不下；第2排无VIP区间 → 全厅VIP路径必败
    vip_bounds = {1: [(1, 3)], 2: []}
    assert find_bond_across_rows(seats, [], 4, vip_bounds) is None
    # 普通路径：第1排 4-8 有5格，4 人成功且不吃 VIP
    normal_bounds = {1: complement_spans([(1, 3)], 1, 8), 2: [(1, 8)]}
    assert find_bond_across_rows(seats, [], 4, normal_bounds) == HoldSpan(1, 4, 7)
