import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ANIM, FONTE, fmt, useApi } from "./lib.js";
import { Block, Sheet, SOURCES, Status, Swatch, WholeBar } from "./Sheet.jsx";

const AXIS = { stroke: "#d9d7e3", tick: { fill: "#626262", fontSize: 13 }, tickLine: false };
const TECH = ["EOL", "SOL"].map((id) => FONTE[id]);

// Lost energy is a model estimate, so it is drawn hatched (DESIGN.md: hatch means estimated).
const Hatch = ({ id, cor }) => (
  <pattern id={id} patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
    <rect width="6" height="6" fill={cor} fillOpacity="0.28" /><rect width="2.5" height="6" fill={cor} />
  </pattern>
);

function Tip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.value > 0).reverse();
  return (
    <div className="tip">
      <div className="tip-h">{fmt.mes(label)}</div>
      {rows.map((p) => (
        <div key={p.dataKey} className="tip-r"><Swatch cor={FONTE[p.dataKey].cor} hatch />{FONTE[p.dataKey].nome}
          <span>{fmt.num(p.value)} GWh · {fmt.reais(p.payload[`${p.dataKey}_rs`])}</span></div>
      ))}
    </div>
  );
}

export default function Curtailment({ f }) {
  const q = useApi("curtailment", { de: f.de, ate: f.ate, uf: f.uf, fonte: f.fonte });
  const [focus, setFocus] = useState(null);
  const d = q.data;

  const { months, tot } = useMemo(() => {
    const m = new Map(), t = { mwh: 0, esp: 0, perd: 0, rs: 0, EOL: 0, SOL: 0 };
    (d?.serie || []).forEach((r) => {
      const row = m.get(r.mes) || { mes: r.mes };
      row[r.fonte] = (row[r.fonte] || 0) + r.mwh_restrito / 1e3;
      row[`${r.fonte}_rs`] = (row[`${r.fonte}_rs`] || 0) + (r.valor_rs_perdido || 0);
      m.set(r.mes, row);
      t.mwh += r.mwh || 0; t.esp += r.mwh_esperado || 0; t.perd += r.mwh_restrito || 0; t.rs += r.valor_rs_perdido || 0;
      t[r.fonte] += r.mwh_restrito || 0;
    });
    return { months: [...m.values()].sort((a, b) => a.mes.localeCompare(b.mes)), tot: t };
  }, [d]);
  const present = TECH.filter((x) => tot[x.id] > 0);
  const scope = ["Eólica e solar", f.uf || "Brasil", f.fonte && FONTE[f.fonte]?.nome, `${fmt.data(f.de)} – ${fmt.data(f.ate)}`]
    .filter(Boolean).join(" · ");
  const usinas = d?.usinas || [];
  const max = Math.max(...usinas.map((u) => u.valor_rs_perdido || 0), 1);
  const go = (id) => { location.hash = `#/usina/${encodeURIComponent(id)}`; };

  const margin = d && months.length > 0 && (
    <>
      <Block title="Energia perdida no período">
        <p className="total"><span className="num">{fmt.gwh(tot.perd)}</span> GWh</p>
        <p className="total-sub">{fmt.reais(tot.rs)} ao PLD horário · {fmt.pct2(tot.perd / tot.esp)} do que o modelo esperava gerar</p>
        <WholeBar parts={present.map((x) => ({ ...x, v: tot[x.id], hatch: true }))} label="Parte de cada fonte na energia perdida" />
      </Block>
      <Block title="Legenda">
        <ul className="legend">
          {present.map((x) => (
            <li key={x.id} className={focus && focus !== x.id ? "is-dim" : ""}>
              <button type="button" onMouseEnter={() => setFocus(x.id)} onMouseLeave={() => setFocus(null)}
                      onFocus={() => setFocus(x.id)} onBlur={() => setFocus(null)}>
                <Swatch cor={x.cor} hatch />{x.nome}<span className="num">{fmt.pct(tot[x.id] / tot.perd)}</span>
              </button>
            </li>
          ))}
        </ul>
      </Block>
      <Block title="Notas">
        <ol className="notes">
          <li>O modelo (<b>curtailment_expected_cf</b>, Unity Catalog) estima quanto cada usina geraria sem restrição, a partir do clima Open-Meteo, da hora e do histórico da usina.</li>
          <li>Hora restrita: esperado ≥ 10% da capacidade e geração abaixo de uma fração do esperado, calibrada contra as restrições que o ONS publica.</li>
          <li>Perda = esperado − gerado nas horas restritas, valorada ao PLD da hora: valor <em className="tag tag--est">estimado</em> pelo modelo (hachurado).</li>
        </ol>
      </Block>
      <Block title="Fontes dos dados">{SOURCES}</Block>
    </>
  );

  const below = usinas.length > 0 && (
    <div className="board-wrap board-wrap--top">
      <h2>Usinas com maior perda</h2>
      <table className="board board--rank">
        <thead><tr><th className="num">#</th><th>Usina · CEG</th><th>UF</th><th className="num">Energia perdida</th>
          <th className="num">R$ perdidos</th><th className="num">Horas restritas<br /><small>modelo · ONS</small></th></tr></thead>
        <tbody>
          {usinas.map((u, i) => (
            <tr key={u.plant_id} tabIndex={0} onClick={() => go(u.plant_id)} onKeyDown={(e) => e.key === "Enter" && go(u.plant_id)}
                className={focus && focus !== u.fonte ? "is-dim" : ""}>
              <td className="num muted">{i + 1}</td>
              <td className="name"><span><Swatch cor={FONTE[u.fonte]?.cor} shape="dot" />{u.nome}</span>
                <small>{u.plant_id.startsWith("SURR-") ? "sem CEG" : u.plant_id} · {fmt.num(u.capacidade_mw, 0)} MW</small></td>
              <td>{u.uf}</td>
              <td className="num">{fmt.energia(u.mwh_restrito)}</td>
              <td className="num share"><span className="sharebar" style={{ "--w": (u.valor_rs_perdido || 0) / max }} />{fmt.reais(u.valor_rs_perdido)}</td>
              <td className="num">{fmt.int(u.horas_modelo)} · {u.horas_ons == null ? "—" : fmt.int(u.horas_ons)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="panel-note">"—" em horas ONS: sem registro de restrição do ONS no período (os arquivos solares de out–dez/2024 não trazem a marcação); o modelo cobre essas horas.</p>
    </div>
  );

  return (
    <Sheet title="Curtailment · energia perdida" scope={q.loading && d ? `${scope} · ${q.waking ? "acordando o banco…" : "atualizando…"}` : scope}
           corners={{ tl: fmt.data(f.de), tr: fmt.data(f.ate) }} margin={margin} below={below}>
      {!d ? <Status {...q} /> : !months.length ? <Status empty="Sem eólica ou solar para estes filtros." /> : (
        <figure className="plot">
          <ResponsiveContainer width="100%" height={380}>
            <BarChart data={months} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap="22%">
              <defs>{present.map((x) => <Hatch key={x.id} id={`h-${x.id}`} cor={x.cor} />)}</defs>
              <CartesianGrid vertical={false} stroke="#ecebf2" />
              <XAxis dataKey="mes" {...AXIS} tickFormatter={fmt.mes} minTickGap={18} />
              <YAxis {...AXIS} axisLine={false} width={64} tickFormatter={(v) => fmt.num(v, 0)}
                     label={{ value: "GWh perdidos por mês", angle: -90, position: "insideLeft", offset: 4, fill: "#626262", fontSize: 12, style: { textAnchor: "middle" } }} />
              <Tooltip content={<Tip />} cursor={{ fill: "rgba(84,23,144,0.06)" }} />
              {present.map((x) => (
                <Bar key={x.id} dataKey={x.id} stackId="a" fill={`url(#h-${x.id})`} stroke={x.cor} strokeWidth={1}
                     fillOpacity={focus && focus !== x.id ? 0.18 : 1} strokeOpacity={focus && focus !== x.id ? 0.25 : 1}
                     maxBarSize={28} animationDuration={700} isAnimationActive={ANIM} />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <details className="as-table">
            <summary>Ver como tabela</summary>
            <table className="board">
              <thead><tr><th>Mês</th>{present.map((x) => <th key={x.id} className="num">{x.nome} (GWh)</th>)}{present.map((x) => <th key={x.id + "rs"} className="num">{x.nome} (R$)</th>)}</tr></thead>
              <tbody>{months.map((r) => (
                <tr key={r.mes}><td>{fmt.mes(r.mes)}</td>{present.map((x) => <td key={x.id} className="num">{fmt.num(r[x.id] || 0)}</td>)}
                  {present.map((x) => <td key={x.id + "rs"} className="num">{fmt.reais(r[`${x.id}_rs`] || 0)}</td>)}</tr>
              ))}</tbody>
            </table>
          </details>
        </figure>
      )}
    </Sheet>
  );
}
