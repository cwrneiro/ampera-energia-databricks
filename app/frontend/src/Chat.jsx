import { useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { FONTE, FONTES, apiPost, fmt } from "./lib.js";

// Genie chat (spec 14): a slide-out drawer on every sheet. The backend asks the Genie space on behalf of
// the signed-in user, so Unity Catalog grants decide what each person can see.

const AXIS = { stroke: "#d9d7e3", tick: { fill: "#626262", fontSize: 12 }, tickLine: false };
const NUM = new Set(["INT", "LONG", "SHORT", "BYTE", "DOUBLE", "FLOAT", "DECIMAL"]);
const DATE = new Set(["DATE", "TIMESTAMP", "TIMESTAMP_NTZ"]);
// Generic series: the survey purples, then greys (fonte hues only when the category *is* a fonte).
const RAMP = ["#541790", "#9b7fd0", "#2b0c4a", "#c4b3e6", "#6e6478", "#b5b5b5"];
const FONTE_BY_NAME = Object.fromEntries(FONTES.flatMap((f) => [[f.id, f], [f.nome.toLowerCase(), f]]));
const SUGESTOES = [
  "Quanto a eólica perdeu por curtailment em 2026, em GWh e R$?",
  "Quais os 5 conjuntos que mais geraram em 2025?",
  "Geração solar por mês em 2025",
  "Qual o PLD capturado por fonte?",
];

const short = (v) => {
  const a = Math.abs(v);
  if (v === 0) return "0";
  return a >= 1e9 ? `${fmt.num(v / 1e9)} bi` : a >= 1e6 ? `${fmt.num(v / 1e6)} mi` : a >= 1e4 ? `${fmt.num(v / 1e3)} mil` : fmt.num(v, a < 10 ? 2 : 0);
};
const cell = (v, tipo) => (v == null ? "—" : NUM.has(tipo) ? fmt.num(Number(v), Math.abs(Number(v)) < 10 ? 2 : 1) : DATE.has(tipo) ? fmt.data(String(v).slice(0, 10)) : v);

const KEYCOL = /(^|_)(key|id|ceg|cod|codigo)$/i;
const ORDINAL = /^(rank|ranking|posicao|ordem|pos)(_|$)/i;  // a rank is a position, not a measure to plot

// Picks a chart from the result's column types: date → line, category + number → bar,
// two numbers → scatter, a single row → its figures, otherwise a table.
export function pickChart(colunas, linhas) {
  const idx = (pred) => colunas.findIndex((c) => pred(c.tipo));
  const nums = colunas.map((c, i) => (NUM.has(c.tipo) && !ORDINAL.test(c.nome) ? i : -1)).filter((i) => i >= 0);
  const d = idx((t) => DATE.has(t)), texts = colunas.map((c, i) => (!NUM.has(c.tipo) && !DATE.has(c.tipo) ? i : -1)).filter((i) => i >= 0);
  const cat = texts.find((i) => !KEYCOL.test(colunas[i].nome)) ?? texts[0] ?? -1;  // label with the name, not the *_key / id column
  if (!linhas.length || !nums.length) return { kind: "table" };
  if (linhas.length === 1 && nums.length <= 4) return { kind: "figure", ys: nums };
  if (d >= 0) return { kind: "line", x: d, ys: nums.slice(0, 3), by: cat >= 0 && nums.length === 1 ? cat : -1 };
  if (cat >= 0) return { kind: "bar", x: cat, ys: nums.slice(0, 2) };
  if (nums.length >= 2) return { kind: "scatter", x: nums[0], y: nums[1] };
  return { kind: "table" };
}

// Genie answers use a little Markdown: **bold** and "- " bullet lines. Render just that, as React nodes
// (no HTML injection, no dependency).
const bold = (t) => t.split(/\*\*(.+?)\*\*/g).map((x, i) => (i % 2 ? <b key={i}>{x}</b> : x));
function Md({ text }) {
  const blocks = [];
  text.split("\n").forEach((l) => {
    const li = l.match(/^\s*[-*]\s+(.*)/);
    const last = blocks.at(-1);
    if (li) (last?.ul ? last.items : (blocks.push({ ul: true, items: [] }), blocks.at(-1).items)).push(li[1]);
    else if (l.trim()) blocks.push({ p: l });
  });
  return blocks.map((b, i) => (b.ul ? <ul key={i}>{b.items.map((x, j) => <li key={j}>{bold(x)}</li>)}</ul> : <p key={i}>{bold(b.p)}</p>));
}

function Tip({ active, payload, label, xfmt }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tip">
      {label != null && <div className="tip-h">{xfmt ? xfmt(label) : label}</div>}
      {payload.map((p) => (
        <div key={p.dataKey + p.name} className="tip-r"><span className="sw" style={{ "--c": p.color }} aria-hidden="true" />{p.name}
          <span>{fmt.num(p.value, Math.abs(p.value) < 10 ? 2 : 1)}</span></div>
      ))}
    </div>
  );
}

function Plot({ r }) {
  const { colunas: cols, linhas } = r;
  const spec = useMemo(() => pickChart(cols, linhas), [cols, linhas]);
  const n = (v) => (v == null ? null : Number(v));
  if (spec.kind === "figure") {
    return (
      <dl className="chat-figures">
        {spec.ys.map((i) => <div key={i}><dt>{cols[i].nome}</dt><dd className="num">{short(n(linhas[0][i]))}</dd></div>)}
      </dl>
    );
  }
  const common = { margin: { top: 8, right: 12, bottom: 0, left: 0 } };
  const yAxis = <YAxis {...AXIS} axisLine={false} width={52} tickFormatter={short} />;
  if (spec.kind === "line") {
    const monthly = linhas.every((l) => String(l[spec.x]).slice(8, 10) === "01");  // first-of-month series
    const dfmt = (v) => (monthly ? fmt.mes(String(v).slice(0, 10)) : fmt.data(String(v).slice(0, 10)));
    let data, series;
    // Series keys are synthetic (s0, s1, …): Recharts reads a dataKey with dots ("Conj. São Roque") as a path.
    if (spec.by >= 0) {  // long format (date, category, value) -> one line per category, top 6
      const y = spec.ys[0], m = new Map(), tot = {};
      linhas.forEach((l) => { const k = l[spec.by] ?? "—"; tot[k] = (tot[k] || 0) + (n(l[y]) || 0); });
      const top = Object.keys(tot).sort((a, b) => tot[b] - tot[a]).slice(0, 6);
      const key = Object.fromEntries(top.map((k, i) => [k, `s${i}`]));
      linhas.forEach((l) => {
        const s = key[l[spec.by] ?? "—"], x = l[spec.x];
        const row = m.get(x) || { x };
        if (s) row[s] = n(l[y]);
        m.set(x, row);
      });
      data = [...m.values()].sort((a, b) => String(a.x).localeCompare(String(b.x)));
      series = top.map((k, i) => ({ key: `s${i}`, nome: k, cor: FONTE_BY_NAME[String(k).toLowerCase()]?.cor || RAMP[i] }));
    } else {
      data = linhas.map((l) => Object.fromEntries([["x", l[spec.x]], ...spec.ys.map((i, j) => [`s${j}`, n(l[i])])]))
        .sort((a, b) => String(a.x).localeCompare(String(b.x)));
      series = spec.ys.map((i, j) => ({ key: `s${j}`, nome: cols[i].nome, cor: RAMP[j] }));
    }
    return (
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} {...common}>
          <CartesianGrid vertical={false} stroke="#ecebf2" />
          <XAxis dataKey="x" {...AXIS} tickFormatter={dfmt} minTickGap={24} />
          {yAxis}
          <Tooltip content={<Tip xfmt={dfmt} />} />
          {series.length > 1 && <Legend iconType="plainline" wrapperStyle={{ fontSize: 12 }} />}
          {series.map((s) => <Line key={s.key} dataKey={s.key} name={s.nome} stroke={s.cor} strokeWidth={2} dot={data.length < 30} isAnimationActive={false} />)}
        </LineChart>
      </ResponsiveContainer>
    );
  }
  if (spec.kind === "bar") {
    const data = linhas.slice(0, 15).map((l) => Object.fromEntries([["x", l[spec.x] ?? "—"], ...spec.ys.map((i, j) => [`s${j}`, n(l[i])])]));
    const fonteCor = (x) => FONTE_BY_NAME[String(x).toLowerCase()]?.cor;
    const h = Math.max(140, data.length * 26 + 30);
    return (
      <ResponsiveContainer width="100%" height={h}>
        <BarChart data={data} layout="vertical" {...common} barCategoryGap="22%">
          <CartesianGrid horizontal={false} stroke="#ecebf2" />
          <XAxis type="number" {...AXIS} tickFormatter={short} />
          <YAxis type="category" dataKey="x" {...AXIS} width={128} interval={0}
                 tickFormatter={(v) => (String(v).length > 18 ? String(v).slice(0, 17) + "…" : v)} />
          <Tooltip content={<Tip />} cursor={{ fill: "rgba(84,23,144,0.06)" }} />
          {spec.ys.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
          {spec.ys.map((i, j) => (
            <Bar key={i} dataKey={`s${j}`} name={cols[i].nome} fill={RAMP[j]} maxBarSize={18} isAnimationActive={false}
                 shape={(p) => <rect x={p.x} y={p.y} width={Math.max(p.width, 0)} height={p.height} rx={2} fill={(j === 0 && fonteCor(p.payload.x)) || RAMP[j]} />} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }
  if (spec.kind === "scatter") {
    const data = linhas.map((l) => ({ x: n(l[spec.x]), y: n(l[spec.y]) }));
    return (
      <ResponsiveContainer width="100%" height={220}>
        <ScatterChart {...common}>
          <CartesianGrid stroke="#ecebf2" />
          <XAxis type="number" dataKey="x" name={cols[spec.x].nome} {...AXIS} tickFormatter={short} />
          <YAxis type="number" dataKey="y" name={cols[spec.y].nome} {...AXIS} axisLine={false} width={52} tickFormatter={short} />
          <Tooltip content={<Tip />} />
          <Scatter data={data} fill="#541790" fillOpacity={0.6} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }
  return null;
}

function Answer({ r }) {
  const spec = useMemo(() => pickChart(r.colunas, r.linhas), [r]);
  const [view, setView] = useState(spec.kind === "table" ? "tabela" : "grafico");
  return (
    <div className="chat-a">
      {r.texto && <div className="chat-text"><Md text={r.texto} /></div>}
      {r.descricao && r.descricao !== r.texto && <p className="chat-desc">{r.descricao}</p>}
      {r.linhas.length > 0 && (
        <>
          {spec.kind !== "table" && (
            <div className="seg-ctl seg-ctl--sm" role="radiogroup" aria-label="Ver resultado como">
              {[["grafico", "Gráfico"], ["tabela", "Tabela"]].map(([k, l]) => (
                <button key={k} role="radio" aria-checked={view === k} onClick={() => setView(k)}>{l}</button>
              ))}
            </div>
          )}
          {view === "grafico" && spec.kind !== "table" ? <Plot r={r} /> : (
            <div className="chat-table">
              <table className="board">
                <thead><tr>{r.colunas.map((c) => <th key={c.nome} className={NUM.has(c.tipo) ? "num" : ""}>{c.nome}</th>)}</tr></thead>
                <tbody>{r.linhas.slice(0, 100).map((l, i) => (
                  <tr key={i}>{l.map((v, j) => <td key={j} className={NUM.has(r.colunas[j].tipo) ? "num" : ""}>{cell(v, r.colunas[j].tipo)}</td>)}</tr>
                ))}</tbody>
              </table>
            </div>
          )}
          <p className="chat-meta">{fmt.int(r.linhas.length)} linha{r.linhas.length > 1 ? "s" : ""}{r.linhas.length >= 500 ? " (primeiras 500)" : ""}</p>
        </>
      )}
      {r.sql && (
        <details className="chat-sql">
          <summary>Ver SQL gerado pelo Genie</summary>
          <pre><code>{r.sql}</code></pre>
        </details>
      )}
    </div>
  );
}

export default function Chat() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([]);
  const [conversa, setConversa] = useState(null);
  const [txt, setTxt] = useState("");
  const [busy, setBusy] = useState(false);
  const input = useRef(null), log = useRef(null), btn = useRef(null);
  const gen = useRef(0);  // bumped by "Nova conversa": a reply for an earlier conversation is dropped

  useEffect(() => { if (open) input.current?.focus(); }, [open]);
  const [scrolled, setScrolled] = useState(false);  // label shows at the top, collapses to the icon so it never covers the side notes
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 80);
    on(); window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  useEffect(() => {
    if (!open) return undefined;
    const esc = (e) => { if (e.key === "Escape") { setOpen(false); btn.current?.focus(); } };
    addEventListener("keydown", esc);
    return () => removeEventListener("keydown", esc);
  }, [open]);
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" }); }, [msgs, busy]);

  const ask = async (q) => {
    const pergunta = q.trim();
    if (!pergunta || busy) return;
    setTxt(""); setBusy(true);
    setMsgs((m) => [...m, { q: pergunta }]);
    const g = gen.current;
    try {
      const r = await apiPost("genie", { pergunta, conversa });
      if (g !== gen.current) return;
      setConversa(r.conversa);
      setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, r } : x)));
    } catch (e) {
      if (g !== gen.current) return;
      setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, erro: e.message } : x)));
    } finally {
      if (g === gen.current) { setBusy(false); input.current?.focus(); }
    }
  };
  const novo = () => { gen.current += 1; setMsgs([]); setConversa(null); setBusy(false); input.current?.focus(); };
  const last = msgs.at(-1)?.r?.sugestoes || [];

  return (
    <>
      <button ref={btn} type="button" className={"chat-toggle" + (scrolled ? " is-compact" : "")} aria-label="Pergunte ao Genie" aria-expanded={open} aria-controls="chat" onClick={() => setOpen((o) => !o)}>
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <path d="M4 5.5h16v10H9.5L5.5 19v-3.5H4z" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" />
          <path d="M8 10.5h8M8 13h5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
        </svg>
        <span className="chat-label">Pergunte ao Genie</span>
      </button>
      <aside id="chat" className={"chat" + (open ? " is-open" : "")} aria-label="Chat com o Genie" aria-hidden={!open} inert={!open}>
        <header className="chat-head">
          <div>
            <h2>Pergunte aos dados</h2>
            <p>Genie responde sobre as tabelas gold — geração, reconciliação, PLD, clima e curtailment — com as suas permissões do Unity Catalog.</p>
          </div>
          <div className="chat-actions">
            {msgs.length > 0 && <button type="button" className="link-btn" onClick={novo}>Nova conversa</button>}
            <button type="button" className="chat-close" aria-label="Fechar chat" onClick={() => { setOpen(false); btn.current?.focus(); }}>
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" /></svg>
            </button>
          </div>
        </header>
        <div className="chat-log" ref={log} aria-live="polite">
          {!msgs.length && (
            <div className="chat-empty">
              <p>Pergunte em português, como para um analista. Cada resposta mostra o SQL que o Genie rodou.</p>
              <ul>{SUGESTOES.map((s) => <li key={s}><button type="button" className="chip" onClick={() => ask(s)}>{s}</button></li>)}</ul>
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className="chat-turn">
              <p className="chat-q">{m.q}</p>
              {m.r ? <Answer r={m.r} /> : m.erro ? (
                <div className="status status--error" role="alert"><p>{m.erro}</p><button className="btn" onClick={() => ask(m.q)}>Tentar de novo</button></div>
              ) : <div className="status"><span className="ink-load" />O Genie está consultando os dados…</div>}
            </div>
          ))}
          {!busy && last.length > 0 && (
            <ul className="chat-follow">{last.slice(0, 3).map((s) => <li key={s}><button type="button" className="chip" onClick={() => ask(s)}>{s}</button></li>)}</ul>
          )}
        </div>
        <form className="chat-form" onSubmit={(e) => { e.preventDefault(); ask(txt); }}>
          <label htmlFor="chat-q" className="sr-only">Sua pergunta</label>
          <textarea id="chat-q" ref={input} rows={2} value={txt} placeholder="Ex.: geração eólica na Bahia em 2025, por mês"
                    onChange={(e) => setTxt(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(txt); } }} />
          <button className="btn" type="submit" disabled={busy || !txt.trim()}>Enviar</button>
        </form>
      </aside>
    </>
  );
}
