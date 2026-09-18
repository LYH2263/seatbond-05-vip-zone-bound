import { useEffect, useState } from "react";
import { api } from "../api/client";

type Show = { id: number; film_title: string; hall_name?: string };
type Hold = {
  id: number;
  order_code: string;
  row: number;
  start_col: number;
  end_col: number;
  party_size: number;
  vip_request: boolean;
};

export default function HoldPage() {
  const [shows, setShows] = useState<Show[]>([]);
  const [sid, setSid] = useState<number | "">("");
  const [party, setParty] = useState(3);
  const [prefRow, setPrefRow] = useState("");
  const [vip, setVip] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [last, setLast] = useState<Hold | null>(null);

  useEffect(() => {
    api<Show[]>("/showtimes").then((s) => {
      setShows(s);
      if (s[0]) setSid(s[0].id);
    });
  }, []);

  async function submit() {
    setMsg("");
    setErr("");
    try {
      const body: Record<string, unknown> = {
        showtime_id: sid,
        party_size: party,
        vip_request: vip,
      };
      if (prefRow) body.preferred_row = Number(prefRow);
      const hold = await api<Hold>("/holds", { method: "POST", body: JSON.stringify(body) });
      setLast(hold);
      setMsg(
        `已锁${vip ? "VIP" : ""}座 ${hold.order_code}：第${hold.row}排 ${hold.start_col}-${hold.end_col}`
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <>
      <h2>锁座</h2>
      <div className="toolbar">
        <select value={sid} onChange={(e) => setSid(Number(e.target.value))}>
          {shows.map((s) => (
            <option key={s.id} value={s.id}>
              {s.film_title} · {s.hall_name}
            </option>
          ))}
        </select>
        <label>
          人数{" "}
          <input
            type="number"
            min={1}
            max={12}
            value={party}
            onChange={(e) => setParty(Number(e.target.value))}
            style={{ width: 72 }}
          />
        </label>
        <label>
          优先排{" "}
          <input
            value={prefRow}
            onChange={(e) => setPrefRow(e.target.value)}
            placeholder="可选"
            style={{ width: 72 }}
          />
        </label>
        <label className="vip-toggle">
          <input type="checkbox" checked={vip} onChange={(e) => setVip(e.target.checked)} />
          VIP 需求
        </label>
        <button onClick={submit}>{vip ? "仅在VIP区找连座" : "查找并锁连座"}</button>
      </div>
      <p className="vip-hint">
        {vip
          ? "已开 VIP 需求：只在该厅已登记的 VIP 区间内找连续空座，人数不足直接失败，不会拼区间外普通座。"
          : "未开 VIP 需求：只在普通区找连座，不会占用 VIP 区间内座位。"}
      </p>
      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}
      {last && (
        <p className="mono">
          订单 {last.order_code} · {last.party_size} 人 · {last.vip_request ? "VIP" : "普通"} · R{last.row} C
          {last.start_col}-{last.end_col}
        </p>
      )}
    </>
  );
}
