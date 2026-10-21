import { useMemo } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ANIM, CADASTRO, FONTE, METODO, fmt, lugar, useApi } from "./lib.js";
import { Block, Sheet, SOURCES, Status, Swatch } from "./Sheet.jsx";

const AXIS = { stroke: "#d9d7e3", tick: { fill: "#626262", fontSize: 13 }, tickLine: false };
const INK = "#0a0a0a", MUTED = "#8a8794";

function Tip({ active, payload, label, unit, names }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tip">
      <div className="tip-h">{fmt.data(label)}</div>
      {payload.filter((p) => p.value != null).map((p) => (
        <div key={p.dataKey} className="tip-r"><Swatch cor={p.color} hatch={p.dataKey === "est"} />{names[p.dataKey]}
          <span>{fmt.num(p.value, unit === "MWh" ? 0 : 1)} {unit}</span></div>
      ))}
    </div>
  );
}

function Panel({ title, note, children, legend }) {
  return (
    <figure className="panel">
      <figcaption><h2>{title}</h2>{legend && <div className="keys">{legend}</div>}</figcaption>
      {children}
      {note && <p className="panel-note">{note}</p>}
    </figure>
  );
}

const Key = ({ cor, hatch, dash, children }) => (
  <span className="key">{dash ? <i className="line-key line-key--dash" style={{ "--c": cor }} /> : hatch != null ? <Swatch cor={cor} hatch={hatch} /> : <i className="line-key" style={{ "--c": cor }} />}{children}</span>
);

// Per fonte, the weather variable that drives output. Measured vs modeled never share a label.
function weatherSpec(u, dias) {
  const med = dias.find((d) => d.fonte_medicao)?.fonte_medicao;
  if (u.fonte === "EOL") return {
    title: "Vento", unit: "m/s", model: "vento_100m_ms_modelo", meas: "vento_ms_medido",
    names: { m: "Modelado ERA5, 100 m", x: med === "INMET" ? "Medido INMET, 10 m" : "Medido ONS na usina" },
    note: med === "INMET" ? "INMET mede o vento a 10 m: um indicador fraco do vento no rotor (100 m)." : null,
  };
  if (u.fonte === "SOL") return {
    title: "Irradiância", unit: "W/m²", model: "irradiancia_wm2_modelo", meas: "irradiancia_wm2_medida",
    names: { m: "Modelada ERA5, plano horizontal", x: med === "INMET" ? "Medida INMET, horizontal" : "Medida ONS, provável plano do painel" },
    note: med !== "INMET" ? "A medição do ONS deve estar no plano do painel (rastreadores), por isso fica acima da horizontal." : null,
  };
  if (u.fonte === "HID") return { title: "Chuva na célula da usina", unit: "mm/dia", model: "precip_mm_modelo", bars: true, names: { m: "Modelada ERA5" } };
  return { title: "Temperatura", unit: "°C", model: "temp_c_modelo", names: { m: "Modelada ERA5, 2 m" } };
}

export default function Plant({ id, plant }) {
  const q = useApi(`plant/${encodeURIComponent(id)}`);
  const u = q.data?.usina || plant;
  const dias = q.data?.dias || [];
  const f = u && FONTE[u.fonte];

  const s = useMemo(() => {
    if (!dias.length) return null;
    const sum = (k) => dias.reduce((a, d) => a + (d[k] || 0), 0);
    const mwh = sum("mwh"), valor = sum("valor_rs");
    const pldDays = dias.filter((d) => d.pld_medio_rs_mwh != null);
    const pldMedio = pldDays.reduce((a, d) => a + d.pld_medio_rs_mwh, 0) / (pldDays.length || 1);
    return { mwh, est: sum("mwh_estimado"), valor, capt: mwh ? valor / mwh : null, pldMedio,
             fc: u?.capacidade_mw ? mwh / (u.capacidade_mw * 24 * dias.length) : null,
             meas: dias.some((d) => d.vento_ms_medido != null || d.irradiancia_wm2_medida != null),
             med: dias.find((d) => d.fonte_medicao)?.fonte_medicao };
  }, [dias, u]);

  const rows = useMemo(() => dias.map((d) => ({ ...d, med: (d.mwh || 0) - (d.mwh_estimado || 0), est: d.mwh_estimado || null })), [dias]);

  if (!u) return <Sheet title="Usina" margin={null}><Status {...q} /></Sheet>;
  const w = weatherSpec(u, dias);
  const scope = [u.ceg || "sem CEG", f?.nome || u.fonte, lugar(u),
                 u.capacidade_mw && `${fmt.num(u.capacidade_mw)} MW`].filter(Boolean).join(" · ");
  const sync = { syncId: "usina", data: rows, margin: { top: 8, right: 8, bottom: 0, left: 0 } };
  const xa = <XAxis dataKey="dia" {...AXIS} tickFormatter={fmt.mes} minTickGap={40} />;

  const margin = s && (
    <>
      <Block title="Total do período">
        <p className="total"><span className="num">{fmt.energia(s.mwh)}</span></p>
        <p className="total-sub">últimos 30 dias {fmt.energia(u.mwh_30d)}{s.fc != null && <> · fator de capacidade {fmt.pct(s.fc)}</>}</p>
        <dl className="facts">
          <dt>Valor ao PLD</dt><dd className="num">{fmt.reais(s.valor)}</dd>
          <dt>PLD capturado</dt><dd className="num">{fmt.rsmwh(s.capt)}</dd>
          <dt>PLD médio</dt><dd className="num">{fmt.rsmwh(s.pldMedio)}</dd>
          {s.est > 0 && <><dt><em className="tag tag--est">estimado</em></dt><dd className="num">{fmt.pct(s.est / s.mwh)} da energia</dd></>}
        </dl>
      </Block>
      <Block title="Ficha">
        <dl className="facts">
          <dt>Fonte</dt><dd><Swatch cor={f?.cor} shape="dot" />{f?.nome || u.fonte}{u.tipo ? ` · ${u.tipo}` : ""}</dd>
          <dt>Reconciliação</dt><dd>{METODO[u.match_method]?.nome || u.match_method}</dd>
          {u.nom_conjunto && <><dt>Conjunto</dt><dd>{u.nom_conjunto}</dd></>}
          <dt>Cadastro</dt><dd>{CADASTRO[u.fonte_cadastro] || u.fonte_cadastro || "—"}</dd>
          {u.lat != null && <><dt>Coordenadas</dt><dd className="num">{fmt.num(u.lat, 3)}, {fmt.num(u.lon, 3)}</dd></>}
        </dl>
      </Block>
      <Block title="Notas">
        <ol className="notes">
          <li>Clima modelado: Open-Meteo (ERA5), célula de 0,25° da usina.</li>
          <li>{s.med ? `Medição: ${s.med === "ONS" ? "ONS, na própria usina" : "estação INMET a até 50 km"}.` : "Sem medição em campo para esta usina: só o clima modelado."}</li>
          {s.est > 0 && <li>Parte da energia é estimada por rateio de capacidade no conjunto (hachurado).</li>}
        </ol>
      </Block>
      <Block title="Fontes dos dados">{SOURCES}</Block>
    </>
  );

  return (
    <Sheet title={u.nome} scope={scope}
           actions={u.lat != null && <a className="btn btn--ghost" href="#/mapa">Voltar ao mapa</a>}
           corners={u.lat != null ? { tl: `${fmt.num(Math.abs(u.lat), 2)}°${u.lat < 0 ? "S" : "N"}`, tr: `${fmt.num(Math.abs(u.lon), 2)}°${u.lon < 0 ? "O" : "L"}`, bl: dias[0] && fmt.data(dias[0].dia), br: dias.at(-1) && fmt.data(dias.at(-1).dia) } : {}}
           margin={margin}>
      {!dias.length ? <Status {...q} empty={q.data && "Sem geração registrada no período."} /> : (
        <div className="panels">
          <Panel title="Geração diária, MWh" legend={s.est > 0 && <><Key cor={f?.cor} hatch={false}>medida</Key><Key cor={f?.cor} hatch>estimado</Key></>}>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart {...sync}>
                <defs>
                  <pattern id="hatch-p" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
                    <rect width="6" height="6" fill={f?.cor} fillOpacity="0.15" /><rect width="2" height="6" fill={f?.cor} />
                  </pattern>
                </defs>
                <CartesianGrid vertical={false} stroke="#ecebf2" />
                {xa}
                <YAxis {...AXIS} axisLine={false} width={64} tickFormatter={(v) => fmt.num(v, 0)} />
                <Tooltip content={<Tip unit="MWh" names={{ med: "Medida", est: "Estimado" }} />} />
                <Area dataKey="med" stackId="g" type="monotone" stroke={f?.cor} strokeWidth={1.5} fill={f?.cor} fillOpacity={0.16} animationDuration={700} isAnimationActive={ANIM} dot={false} />
                {s.est > 0 && <Area dataKey="est" stackId="g" type="monotone" stroke={f?.cor} strokeWidth={1} fill="url(#hatch-p)" animationDuration={700} isAnimationActive={ANIM} dot={false} />}
              </AreaChart>
            </ResponsiveContainer>
          </Panel>
          <Panel title="PLD capturado × médio, R$/MWh" legend={<><Key cor={INK}>capturado</Key><Key cor={MUTED} dash>médio do submercado</Key></>}>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart {...sync}>
                <CartesianGrid vertical={false} stroke="#ecebf2" />
                {xa}
                <YAxis {...AXIS} axisLine={false} width={64} tickFormatter={(v) => fmt.num(v, 0)} />
                <Tooltip content={<Tip unit="R$/MWh" names={{ pld_capturado_rs_mwh: "Capturado", pld_medio_rs_mwh: "Médio" }} />} />
                <Line dataKey="pld_medio_rs_mwh" stroke={MUTED} strokeWidth={1.5} strokeDasharray="4 3" dot={false} animationDuration={700} isAnimationActive={ANIM} />
                <Line dataKey="pld_capturado_rs_mwh" stroke={INK} strokeWidth={2} dot={false} animationDuration={700} isAnimationActive={ANIM} />
              </LineChart>
            </ResponsiveContainer>
          </Panel>
          <Panel title={`${w.title}, ${w.unit}`} note={w.note}
                 legend={w.meas && <><Key cor={f?.cor}>{w.names.x}</Key><Key cor={MUTED} dash>{w.names.m}</Key></>}>
            <ResponsiveContainer width="100%" height={200}>
              {w.bars ? (
                <BarChart {...sync}>
                  <CartesianGrid vertical={false} stroke="#ecebf2" />
                  {xa}
                  <YAxis {...AXIS} axisLine={false} width={64} tickFormatter={(v) => fmt.num(v, 0)} />
                  <Tooltip content={<Tip unit={w.unit} names={{ [w.model]: w.names.m }} />} />
                  <Bar dataKey={w.model} fill={f?.cor} animationDuration={700} isAnimationActive={ANIM} />
                </BarChart>
              ) : (
                <LineChart {...sync}>
                  <CartesianGrid vertical={false} stroke="#ecebf2" />
                  {xa}
                  <YAxis {...AXIS} axisLine={false} width={64} tickFormatter={(v) => fmt.num(v, 0)} />
                  <Tooltip content={<Tip unit={w.unit} names={{ [w.model]: w.names.m, ...(w.meas && { [w.meas]: w.names.x }) }} />} />
                  <Line dataKey={w.model} stroke={w.meas ? MUTED : f?.cor} strokeWidth={w.meas ? 1.5 : 2} strokeDasharray={w.meas ? "4 3" : undefined} dot={false} animationDuration={700} isAnimationActive={ANIM} />
                  {w.meas && <Line dataKey={w.meas} stroke={f?.cor} strokeWidth={2} dot={false} connectNulls={false} animationDuration={700} isAnimationActive={ANIM} />}
                </LineChart>
              )}
            </ResponsiveContainer>
          </Panel>
        </div>
      )}
    </Sheet>
  );
}
