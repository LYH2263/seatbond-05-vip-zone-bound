# SeatBond

影院连座锁座：按场次厅图查找连续空座，过道列断开，冲突检测既有持座。
支持按排登记VIP列区间：VIP需求只在区间内找连座，普通需求不进VIP区，过道切段规则同时生效。

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4100 |
| API | http://localhost:9100 |
| API 文档 | http://localhost:9100/docs |
| Postgres | localhost:5442 |

健康检查：`GET http://localhost:9100/api/health`

## 页面

- `/halls` — 影厅
- `/showtimes` — 场次
- `/seatmap` — 座位图（大网格热力）
- `/hold` — 锁座
- `/orders` — 订单
- `/conflicts` — 冲突

## 使用说明

1. 在影厅页点「维护VIP区间」，按排登记起止列（不同排可不同，越界会被拒绝）；区间跨过道时仍会被过道切段。
2. 在座位图查看占用热力，VIP区间以金色描边标出（过道上的区间为虚线）。
3. 在锁座页输入连座人数，勾选「VIP需求」则只在VIP区间内找连座，不勾选则只在普通区搜索，提交后到订单/冲突页查看结果。

### VIP接口

- `GET /api/halls/{hall_id}/vip-zones` — 读取某厅全部VIP区间
- `PUT /api/halls/{hall_id}/vip-zones` — 全量覆盖区间，body：`{"zones":[{"row":2,"start_col":3,"end_col":8}]}`；排/列越界返回 422
- `POST /api/holds` 增加 `require_vip`（默认 false）；锁座结果 `is_vip` 标记是否VIP需求
- `GET /api/seatmap/{id}` 每个格子带 `is_vip`，供座位图描边

## 开发与测试

```bash
docker compose exec api pytest -q
```

注：表结构由 `create_all` 初始化，新增字段（如 `seat_holds.is_vip`、`vip_zones` 表）需要在旧库上清库重建。
