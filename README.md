# SeatBond

影院连座锁座：按场次厅图查找连续空座，过道列断开，冲突检测既有持座。
VIP 区按排登记列区间：VIP 需求只在区间内找连座（不拼普通座），普通需求只在普通区找（不占 VIP）。

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

- `/halls` — 影厅（含每排 VIP 列区间维护：排号/起止列，越界与同排重叠拒绝）
- `/showtimes` — 场次
- `/seatmap` — 座位图（大网格热力，VIP 区间金色描边 + 图例）
- `/hold` — 锁座（含「VIP 需求」开关）
- `/orders` — 订单
- `/conflicts` — 冲突

## VIP 规则

- VIP 区间按排登记，不同排可不同；`PUT /api/halls/{id}/vip-zones` 全量替换该厅区间。
- 打开 VIP 需求（`vip_request=true`）：仅在 VIP 区间内搜索连续空座，人数不足返回 409，绝不把区间外普通座拼进来。
- 未开 VIP 需求：在 VIP 区间的补集（普通区）搜索，绝不占用 VIP 格。
- 过道规则同时生效：VIP 区间跨过道列时仍被切段，可能因此人数不足。
- 种子场景：一号厅第 1 排 VIP 1-4（仅 4 座），5 人开 VIP 必败；关掉需求在普通区锁到 7-11；第 6 排 VIP 3-8 跨过道 5、6，切成两段。

## 使用说明

1. 在影厅与场次页确认厅图与排期，在影厅页「维护VIP」登记各排 VIP 列区间。
2. 打开座位图查看占用热力与 VIP 描边，在锁座页输入连座人数、按需打开 VIP 需求并提交。
3. 订单页查看持座结果；冲突页查看重叠请求。

## 开发与测试

```bash
docker compose exec api pytest -q
```
