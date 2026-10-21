import { useMemo, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ANIM, FONTE, FONTES, METODO, fmt, useApi } from "./lib.js";
import { Block, Sheet, SOURCES, Status, Swatch, WholeBar } from "./Sheet.jsx";

const AXIS = { stroke: "#d9d7e3", tick: { fill: "#626262", fontSize: 13 }, tickLine: false };

function SeriesTip({ active, payload, label, unit, mensal }) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.value > 0).reverse();
  const total = rows.reduce((s, p) => s + p.value, 0);
  return (
    <div className="tip">
      <div className="tip-h">{mensal ? fmt.mes(label) : fmt.data(label)}</div>
      {rows.map((p) => (
        <div key={p.dataKey} className="tip-r"><Swatch cor={FONTE[p.dataKey].cor} />{FONTE[p.dataKey].nome}
          <span>{fmt.num(p.value)} {unit}</span></div>
      ))}
      <div className="tip-r tip-t">Total<span>{fmt.num(total)} {unit}</span></div>
    </div>
  );
}

function Series({ data, mensal, focus }) {
  const unit = mensal ? "TWh" : "GWh";
  const div = mensal ? 1e6 : 1e3;
  const rows = useMemo(() => {
    const m = new Map();
    data.forEach((r) => {
      const row = m.get(r.p) || { p: r.p };
      row[r.fonte] = (row[r.fonte] || 0) + r.mwh / div;
      m.set(r.p, row);
    });
    return [...m.values()].sort((a, b) => a.p.localeCompare(b.p));
  }, [data, div]);
  const present = FONTES.filter((f) => rows.some((r) => r[f.id] > 0));
  const Chart = mensal ? BarChart : AreaChart;
  return (
    <figure className="plot">
      <ResponsiveContainer width="100%" height={380}>
        <Chart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap="22%">
          <CartesianGrid vertical={false} stroke="#ecebf2" />
          <XAxis dataKey="p" {...AXIS} tickFormatter={mensal ? fmt.mes : fmt.dia} minTickGap={18} />
          <YAxis {...AXIS} axisLine={false} width={64} tickFormatter={(v) => fmt.num(v, 0)}
                 label={{ value: mensal ? "TWh por mês" : "GWh por dia", angle: -90, position: "insideLeft", offset: 4, fill: "#626262", fontSize: 12, style: { textAnchor: "middle" } }} />
          <Tooltip content={<SeriesTip unit={unit} mensal={mensal} />} cursor={{ fill: "rgba(84,23,144,0.06)" }} />
          {present.map((f) =>
            mensal ? (
              <Bar key={f.id} dataKey={f.id} stackId="a" fill={f.cor} stroke="#fff" strokeWidth={1.5}
                   fillOpacity={focus && focus !== f.id ? 0.18 : 1} maxBarSize={28} animationDuration={700} isAnimationActive={ANIM} />
            ) : (
              <Area key={f.id} dataKey={f.id} stackId="a" type="monotone" stroke={f.cor} strokeWidth={2} fill={f.cor}
                    fillOpacity={focus && focus !== f.id ? 0.04 : 0.16} strokeOpacity={focus && focus !== f.id ? 0.25 : 1}
                    animationDuration={700} isAnimationActive={ANIM} />
            ))}
        </Chart>
      </ResponsiveContainer>
      <details className="as-table">
        <summary>Ver como tabela</summary>
        <table className="board">
          <thead><tr><th>{mensal ? "Mês" : "Dia"}</th>{present.map((f) => <th key={f.id} className="num">{f.nome} ({unit})</th>)}</tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.p}><td>{mensal ? fmt.mes(r.p) : fmt.data(r.p)}</td>{present.map((f) => <td key={f.id} className="num">{fmt.num(r[f.id] || 0)}</td>)}</tr>
          ))}</tbody>
        </table>
      </details>
    </figure>
  );
}

function Ranking({ title, rows, total, kind, onPick, byId }) {
  const max = Math.max(...rows.map((r) => r.mwh || 0), 1);
  return (
    <div className="board-wrap">
      <h2>{title}</h2>
      <table className="board board--rank">
        <thead><tr><th className="num">#</th><th>{kind === "usina" ? "Usina · CEG" : "Conjunto"}</th><th>UF</th><th className="num">Energia</th><th className="num">Parte</th></tr></thead>
        <tbody>
          {rows.map((r, i) => {
            const id = kind === "usina" ? r.plant_id : r.conjunto_key;
            const est = r.mwh_estimado > 0 ? r.mwh_estimado / r.mwh : 0;
            return (
              <tr key={id} tabIndex={0} onClick={() => onPick(id)} onKeyDown={(e) => e.key === "Enter" && onPick(id)}>
                <td className="num muted">{i + 1}</td>
                <td className="name">
                  <span>{kind === "usina" ? r.nome : r.nom_conjunto}</span>
                  <small>{kind === "usina" ? (id.startsWith("SURR-") ? `sem CEG · ${METODO[byId[id]?.match_method]?.nome || "chave substituta"}` : id) : `${r.n_usinas} usinas`}
                    {est > 0 && <em className="tag tag--est">estimado {fmt.pct(est)}</em>}</small>
                </td>
                <td>{r.uf}</td>
                <td className="num">{fmt.energia(r.mwh)}</td>
                <td className="num share"><span className="sharebar" style={{ "--w": r.mwh / max }} />{fmt.pct(r.mwh / total)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function PriceByFonte({ fontes, focus, setFocus }) {
  const rows = FONTES.map((f) => ({ ...f, ...fontes.find((x) => x.fonte === f.id) })).filter((r) => r.mwh > 0 && r.pld_medio);
  if (!rows.length) return null;
  const vals = rows.flatMap((r) => [r.pld_medio, r.pld_capturado]);
  const lo = Math.floor(Math.min(...vals) / 20) * 20, hi = Math.ceil(Math.max(...vals) / 20) * 20;
  const x = (v) => `${(100 * (v - lo)) / (hi - lo)}%`;
  const ticks = []; for (let t = lo; t <= hi; t += (hi - lo) / 4) ticks.push(t);
  return (
    <div className="price">
      <h2>PLD capturado × PLD médio, por fonte</h2>
      <p className="lede">Capturado = valor da energia ao PLD horário ÷ energia gerada. Abaixo do médio: a fonte gera nas horas mais baratas.</p>
      <div className="dumbbell" role="table" aria-label="PLD capturado e médio por fonte">
        <div className="db-axis" aria-hidden="true">{ticks.map((t) => <span key={t} style={{ left: x(t) }}>{fmt.num(t, 0)}</span>)}</div>
        {rows.map((r) => {
          const d = r.pld_capturado / r.pld_medio - 1;
          return (
            <div key={r.id} role="row" className={"db-row" + (focus && focus !== r.id ? " is-dim" : "")}
                 onMouseEnter={() => setFocus(r.id)} onMouseLeave={() => setFocus(null)}>
              <span role="rowheader" className="db-name"><Swatch cor={r.cor} shape="dot" />{r.nome}</span>
              <span role="cell" className="db-track">
                {ticks.map((t) => <i key={t} className="db-grid" style={{ left: x(t) }} />)}
                <i className="db-link" style={{ left: x(Math.min(r.pld_medio, r.pld_capturado)), width: `calc(${x(Math.max(r.pld_medio, r.pld_capturado))} - ${x(Math.min(r.pld_medio, r.pld_capturado))})` }} />
                <i className="db-dot db-dot--avg" style={{ left: x(r.pld_medio) }} title={`Médio ${fmt.rsmwh(r.pld_medio)}`} />
                <i className="db-dot" style={{ left: x(r.pld_capturado), "--c": r.cor }} title={`Capturado ${fmt.rsmwh(r.pld_capturado)}`} />
              </span>
              <span role="cell" className="db-val num">{fmt.rsmwh(r.pld_capturado)}</span>
              <span role="cell" className={"db-delta num" + (d < 0 ? " neg" : "")}>{d > 0 ? "+" : "−"}{fmt.pct(Math.abs(d))}</span>
            </div>
          );
        })}
        <div className="db-key"><span><i className="db-dot db-dot--avg" /> PLD médio (R$/MWh)</span><span><i className="db-dot" style={{ "--c": "#626262" }} /> PLD capturado</span></div>
      </div>
    </div>
  );
}

export default function Overview({ f, setF, meta, byId }) {
  const q = useApi("overview", f);
  const [focus, setFocus] = useState(null);
  const o = q.data;
  const mensal = o?.grao !== "day";
  const scope = [
    f.uf || "Brasil",
    f.fonte ? FONTE[f.fonte].nome : "todas as fontes",
    f.conjunto && (o?.ranking_conjuntos.find((c) => c.conjunto_key === f.conjunto)?.nom_conjunto || "conjunto"),
    f.usina && (byId[f.usina]?.nome || f.usina),
    `${fmt.data(f.de)} – ${fmt.data(f.ate)}`,
  ].filter(Boolean).join(" · ");
  const fontes = o ? FONTES.map((x) => ({ ...x, v: o.fontes.find((r) => r.fonte === x.id)?.mwh || 0 })) : [];

  const margin = o && (
    <>
      <Block title="Total do período">
        <p className="total"><span className="num">{fmt.twh(o.kpis.mwh)}</span> TWh</p>
        <p className="total-sub">{fmt.int(o.kpis.n_usinas)} usinas · {fmt.rsbi(o.kpis.valor_rs)} ao PLD · capturado médio {fmt.rsmwh(o.kpis.pld_capturado)}</p>
        <WholeBar parts={fontes.map((x) => ({ ...x, v: x.v }))} label="Participação de cada fonte no total" />
      </Block>
      <Block title="Legenda">
        <ul className="legend">
          {fontes.filter((x) => x.v > 0).map((x) => (
            <li key={x.id} className={focus && focus !== x.id ? "is-dim" : ""}>
              <button type="button" onMouseEnter={() => setFocus(x.id)} onMouseLeave={() => setFocus(null)}
                      onFocus={() => setFocus(x.id)} onBlur={() => setFocus(null)}
                      onClick={() => setF({ ...f, fonte: f.fonte === x.id ? null : x.id })}
                      aria-pressed={f.fonte === x.id} title="Filtrar por esta fonte">
                <Swatch cor={x.cor} />{x.nome}<span className="num">{fmt.pct(x.v / o.kpis.mwh)}</span>
              </button>
            </li>
          ))}
        </ul>
      </Block>
      <Block title="Notas">
        <ol className="notes">
          <li><b>{fmt.pct2(o.kpis.mwh_estimado / o.kpis.mwh)}</b> da energia é <em className="tag tag--est">estimado</em>: conjuntos sem medição por usina, rateados pela capacidade.</li>
          <li>Grão usina: cada MWh contado uma vez (sem as usinas que o ONS publica também dentro do conjunto).</li>
          <li>Série {mensal ? "mensal; períodos de até 3 meses mostram dias" : "diária"}. Horários em Brasília.</li>
        </ol>
      </Block>
      <Block title="Fontes dos dados">{SOURCES}</Block>
    </>
  );

  const below = o && (
    <>
      <div className="boards">
        <Ranking title="Maiores usinas (CEG)" rows={o.ranking_usinas} total={o.kpis.mwh} kind="usina" byId={byId}
                 onPick={(id) => { location.hash = `#/usina/${encodeURIComponent(id)}`; }} />
        <Ranking title="Maiores conjuntos" rows={o.ranking_conjuntos} total={o.kpis.mwh} kind="conjunto"
                 onPick={(id) => setF({ ...f, conjunto: f.conjunto === id ? null : id })} />
      </div>
      <PriceByFonte fontes={o.fontes} focus={focus} setFocus={setFocus} />
    </>
  );

  return (
    <Sheet title="Geração reconciliada" scope={q.loading && o ? `${scope} · ${q.waking ? "acordando o banco…" : "atualizando…"}` : scope}
           corners={{ tl: fmt.data(f.de), tr: fmt.data(f.ate) }}
           margin={margin} below={below}>
      {!o ? <Status {...q} /> : (
        <>
          {q.error && <Status {...q} />}
          <Series data={o.serie} mensal={mensal} focus={focus} />
        </>
      )}
    </Sheet>
  );
}
