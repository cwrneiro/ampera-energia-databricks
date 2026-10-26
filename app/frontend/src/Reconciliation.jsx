import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ANIM, METODO, METODOS, fmt, useApi } from "./lib.js";
import { Block, Sheet, SOURCES, Status, Swatch, WholeBar } from "./Sheet.jsx";

const AXIS = { stroke: "#d9d7e3", tick: { fill: "#626262", fontSize: 13 }, tickLine: false };

function Tip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.value > 0).reverse();
  const total = rows.reduce((s, p) => s + p.value, 0);
  return (
    <div className="tip">
      <div className="tip-h">{fmt.mes(label)}</div>
      {rows.map((p) => (
        <div key={p.dataKey} className="tip-r"><Swatch cor={METODO[p.dataKey].cor} hatch={METODO[p.dataKey].hatch} />
          {METODO[p.dataKey].nome}<span>{fmt.num(p.value, 2)} TWh · {fmt.pct2(p.value / total)}</span></div>
      ))}
    </div>
  );
}

// ai_decide verdicts (spec 12): applied matches and the human review queue, with each candidate's
// probability — the probabilities are the explanation (no generated rationale). The state is what the
// pipeline did (final match_method), not ai_decide's confidence: a plant the fuzzy rung or an override
// placed is resolved, and only "revisar" rows count as work left and MWh at stake.
const STATE = { ai_decide: "aplicada", override: "manual", fuzzy: "fuzzy" };
const STATE_TAG = { aplicada: ["Aplicada", "state--ok"], manual: ["Resolvida · manual", "state--ok"], fuzzy: ["Resolvida · fuzzy", "state--ok"], revisar: ["Revisar", ""] };
const stateOf = (r) => STATE[r.match_method] || "revisar";
const StateTag = ({ r }) => { const [l, cls] = STATE_TAG[stateOf(r)]; return <span className={`state ${cls}`}>{l}</span>; };

function AiReview() {
  const q = useApi("reconciliation/ai");
  const [view, setView] = useState("revisar");
  const all = q.data || [];
  const inView = all.filter((r) => view === "todas" || stateOf(r) === (view === "aplicadas" ? "aplicada" : "revisar"));
  const rows = inView.filter((r) => r.mwh_total > 0);  // retired registry entries with no generation change no number
  const hidden = inView.length - rows.length;
  const count = (st) => all.filter((r) => stateOf(r) === st).length;
  const n = { aplicadas: count("aplicada"), revisar: count("revisar"), todas: all.length };
  const stake = all.filter((r) => stateOf(r) === "revisar").reduce((a, r) => a + (r.mwh_total || 0), 0);
  const cand = (r, k) => ({ id: r[`${k}_id`], nome: r[`${k}_nome`], mun: r[`${k}_municipio`], p: r[`ai_prob_${k}`], k: k.toUpperCase() });
  // Resolved rows highlight the plant the pipeline used; open ones, ai_decide's pick.
  const picked = (r, c) => (stateOf(r) === "revisar" ? r.ai_choice === c.k : c.id != null && c.id === r.plant_id);
  return (
    <section className="ai-review">
      <div className="ai-head">
        <div>
          <h2>Decisões da IA para usinas sem CEG</h2>
          <p className="lede">Para cada usina do ONS cujo CEG não liga à SIGA, a função <b>ai_decide</b> escolhe entre os 3 candidatos da SIGA
            de nome mais parecido na mesma UF, ou nenhum, com probabilidades calibradas. Com confiança ≥ 90% a escolha entra na
            reconciliação; abaixo disso a usina fica na fila de revisão{q.data ? ` (${fmt.energia(stake)} em jogo)` : ""}, a menos que o nome aproximado ou um ajuste manual já a tenha resolvido.</p>
        </div>
        <div className="seg-ctl" role="radiogroup" aria-label="Decisões">
          {[["revisar", "Fila de revisão"], ["aplicadas", "Aplicadas"], ["todas", "Todas"]].map(([k, l]) => (
            <button key={k} role="radio" aria-checked={view === k} onClick={() => setView(k)}>{l} <span className="num">{q.data ? n[k] : ""}</span></button>
          ))}
        </div>
      </div>
      {!q.data ? <Status {...q} /> : !rows.length ? <Status empty="Nenhuma usina nesta lista." /> : (
        <table className="board board--ai">
          <thead><tr><th>Usina no ONS</th><th>Candidatos da SIGA (probabilidade)</th><th className="num">Confiança</th><th>Situação</th><th className="num">Energia</th></tr></thead>
          <tbody>
            {rows.slice(0, 60).map((r) => (
              <tr key={r.ons_key}>
                <td className="name"><span>{r.nom_usina}</span><small>{r.uf} · {r.tipo} · {r.ons_key}</small></td>
                <td>
                  <ul className="cands">
                    {["a", "b", "c"].map((k) => cand(r, k)).filter((c) => c.id).concat([{ k: "nenhum", nome: "Nenhum destes", p: r.ai_prob_nenhum }]).map((c) => (
                      <li key={c.k} className={picked(r, c) ? "is-pick" : ""}>
                        <span className="cand-bar" style={{ "--w": c.p || 0 }} aria-hidden="true" />
                        <span className="cand-name">{c.nome}{c.id && <small>{c.id}{c.mun ? ` · ${c.mun}` : ""}</small>}</span>
                        <span className="num">{fmt.pct(c.p)}</span>
                      </li>
                    ))}
                  </ul>
                </td>
                <td className="num">{fmt.pct(r.ai_confidence)}</td>
                <td><StateTag r={r} /></td>
                <td className="num">{fmt.energia(r.mwh_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {hidden > 0 && <p className="panel-note">{hidden} usina{hidden > 1 ? "s" : ""} sem geração no período não aparece{hidden > 1 ? "m" : ""} na lista.</p>}
      <p className="panel-note">Para confirmar ou corrigir uma usina: inserir uma linha em <b>ampera_silver.plant_match_override</b> (a mais recente vence na próxima atualização).</p>
    </section>
  );
}

export default function Reconciliation() {
  const q = useApi("reconciliation");
  const [grao, setGrao] = useState("usina");
  const [focus, setFocus] = useState(null);
  const all = q.data || [];

  const { months, totals, total, other } = useMemo(() => {
    const rows = all.filter((r) => r.grao === grao);
    const m = new Map(), t = {};
    rows.forEach((r) => {
      const row = m.get(r.mes) || { mes: r.mes };
      row[r.match_method] = (row[r.match_method] || 0) + r.mwh / 1e6;
      m.set(r.mes, row);
      t[r.match_method] = t[r.match_method] || { mwh: 0, n: 0 };
      t[r.match_method].mwh += r.mwh;
      t[r.match_method].n = Math.max(t[r.match_method].n, r.n_usinas);
    });
    const sum = (g) => all.filter((r) => r.grao === g).reduce((s, r) => s + r.mwh, 0);
    return { months: [...m.values()].sort((a, b) => a.mes.localeCompare(b.mes)), totals: t, total: sum(grao),
             other: sum(grao === "usina" ? "publicado" : "usina") };
  }, [all, grao]);

  const metodos = METODOS.filter((x) => totals[x.id]);
  // SUCCESS #1 / spec 02: unmatched over plant-level MWh as published (ceg + fuzzy + unmatched);
  // complexes and state totals are separate categories, not unmatched.
  const pub = (m) => all.filter((r) => r.grao === "publicado" && r.match_method === m).reduce((s, r) => s + r.mwh, 0);
  const unmatched = pub("unmatched");
  const plantLevel = pub("ceg") + pub("fuzzy") + pub("ai_decide") + unmatched;
  const dup = grao === "usina" ? other - total : total - other;

  const toggle = (
    <div className="seg-ctl" role="radiogroup" aria-label="Grão">
      {[["usina", "Grão usina"], ["publicado", "Grão publicado (ONS)"]].map(([g, n]) => (
        <button key={g} role="radio" aria-checked={grao === g} onClick={() => setGrao(g)}>{n}</button>
      ))}
    </div>
  );

  const margin = q.data && (
    <>
      <Block title="Não reconciliado, sobre a energia publicada por usina">
        <p className="total"><span className="num">{fmt.pct2(unmatched / plantLevel)}</span></p>
        <p className="total-sub">{fmt.energia(unmatched)} de {fmt.energia(plantLevel)} que o ONS publica por usina (conjuntos e agregados estaduais são categorias à parte). Sobre o total do {grao === "usina" ? "grão usina" : "grão publicado"}: {fmt.pct2(unmatched / total)}.</p>
      </Block>
      <Block title="Legenda">
        <ul className="legend legend--desc">
          {metodos.map((x) => (
            <li key={x.id} className={focus && focus !== x.id ? "is-dim" : ""}
                onMouseEnter={() => setFocus(x.id)} onMouseLeave={() => setFocus(null)}>
              <div className="lg-h"><Swatch cor={x.cor} hatch={x.hatch} />{x.nome}<span className="num">{fmt.pct2(totals[x.id].mwh / total)}</span></div>
              <p>{x.desc}</p>
            </li>
          ))}
        </ul>
      </Block>
      <Block title="Notas">
        <ol className="notes">
          <li><b>Grão publicado</b>: como o ONS publica — conjuntos inteiros e {fmt.energia(dup)} de usinas que aparecem duas vezes (sozinhas e dentro do conjunto).</li>
          <li><b>Grão usina</b>: conjuntos desdobrados em usinas, sem dupla contagem. É o grão das demais folhas.</li>
        </ol>
      </Block>
      <Block title="Fontes dos dados">{SOURCES}</Block>
    </>
  );

  const below = q.data && (
    <>
    <table className="board">
      <thead><tr><th>Método</th><th className="num">Energia</th><th className="num">Parte</th><th className="num">Usinas (máx./mês)</th></tr></thead>
      <tbody>
        {metodos.map((x) => (
          <tr key={x.id} className={focus && focus !== x.id ? "is-dim" : ""}
              onMouseEnter={() => setFocus(x.id)} onMouseLeave={() => setFocus(null)}>
            <td><Swatch cor={x.cor} hatch={x.hatch} /> {x.nome}</td>
            <td className="num">{fmt.energia(totals[x.id].mwh)}</td>
            <td className="num">{fmt.pct2(totals[x.id].mwh / total)}</td>
            <td className="num">{fmt.int(totals[x.id].n)}</td>
          </tr>
        ))}
        <tr className="sum"><td>Total</td><td className="num">{fmt.energia(total)}</td><td className="num">100%</td><td /></tr>
      </tbody>
    </table>
    <AiReview />
    </>
  );

  return (
    <Sheet title="Como o ONS liga à ANEEL SIGA"
           scope={`Energia por método de reconciliação${q.data ? ` · ${fmt.energia(total)} no ${grao === "usina" ? "grão usina" : "grão publicado"}` : ""}`}
           actions={toggle}
           corners={{ tl: months[0] && fmt.mes(months[0].mes), tr: months.at(-1) && fmt.mes(months.at(-1).mes) }}
           margin={margin} below={below}>
      {!q.data ? <Status {...q} /> : (
        <>
          <div className="whole">
            <WholeBar parts={metodos.map((x) => ({ ...x, v: totals[x.id].mwh }))} label="Participação de cada método no total (legenda na margem)" />
          </div>
          <figure className="plot">
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={months} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap="22%">
                <defs>
                  <pattern id="hatch" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
                    <rect width="6" height="6" fill={METODO.member_estimated.cor} fillOpacity="0.3" /><rect width="2.5" height="6" fill={METODO.member_estimated.cor} />
                  </pattern>
                </defs>
                <CartesianGrid vertical={false} stroke="#ecebf2" />
                <XAxis dataKey="mes" {...AXIS} tickFormatter={fmt.mes} minTickGap={18} />
                <YAxis {...AXIS} axisLine={false} width={64} tickFormatter={(v) => fmt.num(v, 0)}
                       label={{ value: "TWh por mês", angle: -90, position: "insideLeft", offset: 4, fill: "#626262", fontSize: 12, style: { textAnchor: "middle" } }} />
                <Tooltip content={<Tip />} cursor={{ fill: "rgba(84,23,144,0.06)" }} />
                {metodos.map((x) => (
                  <Bar key={x.id} dataKey={x.id} stackId="a" fill={x.hatch ? "url(#hatch)" : x.cor} stroke="#fff" strokeWidth={1.5}
                       fillOpacity={focus && focus !== x.id ? 0.18 : 1} maxBarSize={28} animationDuration={700} isAnimationActive={ANIM} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </figure>
        </>
      )}
    </Sheet>
  );
}
