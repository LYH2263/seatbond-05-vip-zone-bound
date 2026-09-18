from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import ConflictLog, Hall, SeatHold, Showtime, VipZone


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(Hall.id).limit(1)):
        return
    h1 = Hall(name="一号厅", rows=8, cols=12, aisle_cols="5,6")
    h2 = Hall(name="二号厅", rows=6, cols=10, aisle_cols="4,5")
    db.add_all([h1, h2])
    db.flush()
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    s1 = Showtime(hall_id=h1.id, film_title="星际旅人", start_at=now + timedelta(hours=2))
    s2 = Showtime(hall_id=h1.id, film_title="雾都夜曲", start_at=now + timedelta(hours=5))
    s3 = Showtime(hall_id=h2.id, film_title="山海经异", start_at=now + timedelta(hours=3))
    db.add_all([s1, s2, s3])
    db.flush()
    db.add_all(
        [
            SeatHold(showtime_id=s1.id, order_code="SB-1001", row=3, start_col=2, end_col=4, party_size=3),
            SeatHold(showtime_id=s1.id, order_code="SB-1002", row=5, start_col=7, end_col=9, party_size=3),
            SeatHold(showtime_id=s3.id, order_code="SB-1003", row=2, start_col=1, end_col=2, party_size=2),
            # 占掉VIP区间第2排第3列：VIP剩余空座恰为3（6-8列连座），4人VIP请求必差一座
            SeatHold(showtime_id=s3.id, order_code="SB-1004", row=2, start_col=3, end_col=3, party_size=1),
        ]
    )
    # 二号厅VIP区间，按排各自登记：
    # 第2排 3-8列跨过道4,5列，非过道VIP座为3与6-8两段（过道切段）；
    # 第4排 9-10列为另一段更短的VIP区，演示多排区间可不同。
    db.add_all(
        [
            VipZone(hall_id=h2.id, row=2, start_col=3, end_col=8),
            VipZone(hall_id=h2.id, row=4, start_col=9, end_col=10),
        ]
    )
    db.add(ConflictLog(showtime_id=s1.id, party_size=4, reason="与既有持座重叠：第3排 2-4"))
    db.commit()
