import { Fragment, useEffect, useState } from "react";
import { api } from "../api/client";

type VipZone = { id: number; hall_id: number; row: number; start_col: number; end_col: number };
type Hall = { id: number; name: string; rows: number; cols: number; aisle_cols: number[]; vip_zones: VipZone[] };
type DraftZone = { row: string; start_col: string; end_col: string };

export default function HallsPage() {
  const [rows, setRows] = useState<Hall[]>([]);
  const [editing, setEditing] = useState<number | null>(null);
  const [drafts, setDrafts] = useState<DraftZone[]>([]);
  const [form, setForm] = useState<DraftZone>({ row: "", start_col: "", end_col: ""});
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  function load() {
    api<Hall[]>("/halls").then(setRows);
  }
  useEffect(load, []);

  function startEdit(h: Hall) {
    setEditing(h.id);
    setDrafts(h.vip_zones.map((z) => ({ row: String(z.row), start_col: String(z.start_col), end_col: String(z.end_col) })));
    setForm({ row: "", start_col: "", end_col: "" });
    setMsg("");
    setErr("");
  }

  function addDraft() {
    if (!form.row || !form.start_col || !form.end_col) return;
    setDrafts((d) => [...d, form]);
    setForm({ row: "", start_col: "", end_col: "" });
  }

  async function save(hid: number) {
    setMsg("");
    setErr("");
    try {
      const zones = drafts.map((d) => ({
        row: Number(d.row),
        start_col: Number(d.start_col),
        end_col: Number(d.end_col),
      }));
      await api(`/halls/${hid}/vip-zones`, { method: "PUT", body: JSON.stringify({ zones }) });
      setEditing(null);
      load();
      setMsg("VIP 区间已保存");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <>
      <h2>影厅</h2>
      <table className="table">
        <thead>
          <tr>
            <th>名称</th>
            <th>行×列</th>
            <th>过道列</th>
            <th>VIP 区间（按排）</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => (
            <Fragment key={h.id}>
              <tr>
                <td>{h.name}</td>
                <td className="mono">
                  {h.rows} × {h.cols}
                </td>
                <td className="mono">{h.aisle_cols.join(", ") || "—"}</td>
                <td className="mono">
                  {h.vip_zones.length === 0
                    ? "—"
                    : h.vip_zones
                        .map((z) => `R${z.row}:${z.start_col}-${z.end_col}`)
                        .join("，")}
                </td>
                <td>
                  <button className="btn-ghost" onClick={() => (editing === h.id ? setEditing(null) : startEdit(h))}>
                    {editing === h.id ? "收起" : "维护VIP"}
                  </button>
                </td>
              </tr>
              {editing === h.id && (
                <tr key={`${h.id}-vip-edit`} className="vip-edit-row">
                  <td colSpan={5}>
                    <div className="vip-edit">
                      <div className="vip-edit-head">
                        维护「{h.name}」VIP 列区间（{h.rows} 排 × {h.cols} 列，起止列含端点）
                      </div>
                      {drafts.length === 0 && <p className="stub-empty">暂无 VIP 区间，普通需求将使用全厅。</p>}
                      {drafts.map((d, i) => (
                        <span key={i} className="vip-chip">
                          R{d.row} : {d.start_col}-{d.end_col}
                          <button className="btn-ghost chip-del" onClick={() => setDrafts(drafts.filter((_, j) => j !== i))}>
                            ×
                          </button>
                        </span>
                      ))}
                      <div className="toolbar vip-add">
                        <label>
                          排{" "}
                          <input
                            type="number"
                            min={1}
                            max={h.rows}
                            value={form.row}
                            onChange={(e) => setForm({ ...form, row: e.target.value })}
                            style={{ width: 64 }}
                          />
                        </label>
                        <label>
                          起列{" "}
                          <input
                            type="number"
                            min={1}
                            max={h.cols}
                            value={form.start_col}
                            onChange={(e) => setForm({ ...form, start_col: e.target.value })}
                            style={{ width: 64 }}
                          />
                        </label>
                        <label>
                          止列{" "}
                          <input
                            type="number"
                            min={1}
                            max={h.cols}
                            value={form.end_col}
                            onChange={(e) => setForm({ ...form, end_col: e.target.value })}
                            style={{ width: 64 }}
                          />
                        </label>
                        <button className="btn-ghost" onClick={addDraft}>
                          添一行区间
                        </button>
                        <button onClick={() => save(h.id)}>保存区间</button>
                      </div>
                      <div className="vip-hint">同排区间不可重叠；越界将被拒绝。VIP 锁座只在区间内找连座，普通锁座不会占用区间内座位。</div>
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}
    </>
  );
}
