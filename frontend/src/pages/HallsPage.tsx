import { Fragment, useEffect, useState } from "react";
import { api } from "../api/client";

type VipZone = { id?: number; row: number; start_col: number; end_col: number };
type Hall = { id: number; name: string; rows: number; cols: number; aisle_cols: number[]; vip_zones: VipZone[] };
type Draft = { row: string; start_col: string; end_col: string };

const emptyDraft: Draft = { row: "", start_col: "", end_col: "" };

export default function HallsPage() {
  const [rows, setRows] = useState<Hall[]>([]);
  const [editing, setEditing] = useState<number | null>(null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [form, setForm] = useState<Draft>(emptyDraft);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  function refresh() {
    return api<Hall[]>("/halls").then(setRows);
  }

  useEffect(() => {
    refresh();
  }, []);

  function startEdit(h: Hall) {
    setEditing(h.id);
    setMsg("");
    setErr("");
    setDrafts(
      [...h.vip_zones]
        .sort((a, b) => a.row - b.row || a.start_col - b.start_col)
        .map((z) => ({ row: String(z.row), start_col: String(z.start_col), end_col: String(z.end_col) }))
    );
    setForm(emptyDraft);
  }

  function cancelEdit() {
    setEditing(null);
    setDrafts([]);
    setErr("");
  }

  function addDraft() {
    if (!form.row || !form.start_col || !form.end_col) {
      setErr("请填写排号与起止列");
      return;
    }
    setDrafts((d) =>
      [...d, form].sort(
        (a, b) => Number(a.row) - Number(b.row) || Number(a.start_col) - Number(b.start_col)
      )
    );
    setForm(emptyDraft);
    setErr("");
  }

  async function save(h: Hall) {
    setErr("");
    setMsg("");
    const zones = drafts.map((d) => ({
      row: Number(d.row),
      start_col: Number(d.start_col),
      end_col: Number(d.end_col),
    }));
    try {
      await api(`/halls/${h.id}/vip-zones`, {
        method: "PUT",
        body: JSON.stringify({ zones }),
      });
      await refresh();
      setEditing(null);
      setMsg(`${h.name} VIP区间已保存（${zones.length} 段）`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  function zoneText(h: Hall) {
    if (h.vip_zones.length === 0) return "—";
    return [...h.vip_zones]
      .sort((a, b) => a.row - b.row || a.start_col - b.start_col)
      .map((z) => `R${z.row}:${z.start_col}-${z.end_col}`)
      .join("  ");
  }

  return (
    <>
      <h2>影厅</h2>
      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}
      <table className="table">
        <thead>
          <tr>
            <th>名称</th>
            <th>行×列</th>
            <th>过道列</th>
            <th>VIP区间（排:起列-止列）</th>
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
                <td className="mono vip-cell-text">{zoneText(h)}</td>
                <td>
                  {editing === h.id ? (
                    <span className="toolbar" style={{ margin: 0 }}>
                      <button onClick={() => save(h)}>保存</button>
                      <button className="btn-ghost" onClick={cancelEdit}>
                        取消
                      </button>
                    </span>
                  ) : (
                    <button className="btn-ghost" onClick={() => startEdit(h)}>
                      维护VIP区间
                    </button>
                  )}
                </td>
              </tr>
              {editing === h.id && (
                <tr key={`${h.id}-vip-edit`}>
                  <td colSpan={5}>
                    <div className="vip-editor">
                      <div className="stub-title">
                        {h.name} · {h.rows}排 {h.cols}列 · 区间不能越过厅图边界
                      </div>
                      <table className="table vip-edit-table">
                        <tbody>
                          {drafts.map((d, i) => (
                            <tr key={i}>
                              <td>
                                第
                                <input
                                  value={d.row}
                                  onChange={(e) =>
                                    setDrafts((ds) =>
                                      ds.map((x, j) => (j === i ? { ...x, row: e.target.value } : x))
                                    )
                                  }
                                  style={{ width: 56 }}
                                />
                                排
                              </td>
                              <td>
                                起列
                                <input
                                  value={d.start_col}
                                  onChange={(e) =>
                                    setDrafts((ds) =>
                                      ds.map((x, j) =>
                                        j === i ? { ...x, start_col: e.target.value } : x
                                      )
                                    )
                                  }
                                  style={{ width: 56 }}
                                />
                              </td>
                              <td>
                                止列
                                <input
                                  value={d.end_col}
                                  onChange={(e) =>
                                    setDrafts((ds) =>
                                      ds.map((x, j) =>
                                        j === i ? { ...x, end_col: e.target.value } : x
                                      )
                                    )
                                  }
                                  style={{ width: 56 }}
                                />
                              </td>
                              <td>
                                <button
                                  className="btn-ghost btn-danger"
                                  onClick={() => setDrafts((ds) => ds.filter((_, j) => j !== i))}
                                >
                                  删除
                                </button>
                              </td>
                            </tr>
                          ))}
                          <tr>
                            <td>
                              第
                              <input
                                value={form.row}
                                placeholder="排"
                                onChange={(e) => setForm((f) => ({ ...f, row: e.target.value }))}
                                style={{ width: 56 }}
                              />
                              排
                            </td>
                            <td>
                              起列
                              <input
                                value={form.start_col}
                                placeholder="列"
                                onChange={(e) =>
                                  setForm((f) => ({ ...f, start_col: e.target.value }))
                                }
                                style={{ width: 56 }}
                              />
                            </td>
                            <td>
                              止列
                              <input
                                value={form.end_col}
                                placeholder="列"
                                onChange={(e) => setForm((f) => ({ ...f, end_col: e.target.value }))}
                                style={{ width: 56 }}
                              />
                            </td>
                            <td>
                              <button className="btn-ghost" onClick={addDraft}>
                                + 新增区间
                              </button>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                      <p className="vip-hint">
                        区间跨过道列时仍会被过道切段；锁座时VIP需求只在区间内找连座。
                      </p>
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </>
  );
}
