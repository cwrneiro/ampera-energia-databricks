import { useEffect, useState } from "react";

// Chart entry animation (the plot "ink-draw") is off when the user asks for reduced motion.
export const ANIM = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Fonte palette, validated with the dataviz validator (light, #ffffff): fixed order, never cycled.
export const FONTES = [
  { id: "HID", nome: "Hidráulica", cor: "#0089f7" },
  { id: "EOL", nome: "Eólica", cor: "#8047c6" },
  { id: "SOL", nome: "Solar", cor: "#f26200" },
  { id: "THERM", nome: "Térmica", cor: "#b0175a" },
  { id: "NUC", nome: "Nuclear", cor: "#00a39b" },
  { id: "OTHER", nome: "Outras", cor: "#8f8a2a" },
];
export const FONTE = Object.fromEntries(FONTES.map((f) => [f.id, f]));

// Match methods: their own ramp, never a fonte hue (≥ ΔE 15 from EOL purple). Resolved methods are
// purples (estimated = measured hue + hatch), unresolved/aggregate are greys, unmatched is ink.
// Adjacent pairs pass the dataviz CVD/normal-vision checks; light tints rely on the legend + table.
export const METODOS = [
  { id: "ceg", nome: "CEG exato", cor: "#541790",
    desc: "Código CEG do ONS igual ao da ANEEL SIGA, após normalizar o sufixo (.01 → .1)." },
  { id: "member_measured", nome: "Membro medido", cor: "#b08ae8", grao: "usina",
    desc: "Conjunto do ONS resolvido pela geração que o próprio ONS publica por usina-membro." },
  { id: "member_estimated", nome: "Membro estimado", cor: "#b08ae8", hatch: true, grao: "usina",
    desc: "Conjunto sem medição por membro: rateio pela capacidade instalada (estimado)." },
  { id: "ai_decide", nome: "Decisão por IA", cor: "#cbb5f1",
    desc: "Sem CEG nem nome parecido: ai_decide escolheu entre 3 candidatos da SIGA com confiança ≥ 90%." },
  { id: "fuzzy", nome: "Nome aproximado", cor: "#e3d8f6",
    desc: "Sem CEG: nome normalizado + UF + fonte, com numerais iguais, e uma nota de confiança." },
  { id: "ons_conjunto", nome: "Conjunto ONS", cor: "#6e6478",
    desc: "Conjunto publicado pelo ONS que ainda não se desdobra em usinas." },
  { id: "ons_aggregate", nome: "Agregado estadual", cor: "#b5b5b5",
    desc: "Totais por estado que o ONS publica sem usina (ex.: geração distribuída)." },
  { id: "unmatched", nome: "Não reconciliado", cor: "#0a0a0a",
    desc: "Linha do ONS sem correspondência na ANEEL SIGA." },
];
export const METODO = Object.fromEntries(METODOS.map((m) => [m.id, m]));

const nf = (d) => new Intl.NumberFormat("pt-BR", { maximumFractionDigits: d, minimumFractionDigits: d });
const n0 = nf(0), n1 = nf(1), n2 = nf(2);
export const fmt = {
  int: (v) => (v == null ? "—" : n0.format(v)),
  twh: (mwh) => (mwh == null ? "—" : n1.format(mwh / 1e6)),
  gwh: (mwh) => (mwh == null ? "—" : n1.format(mwh / 1e3)),
  // Picks the unit so the number stays readable: MWh, GWh or TWh.
  energia: (mwh) => {
    if (mwh == null) return "—";
    const a = Math.abs(mwh);
    if (a >= 1e6) return `${n1.format(mwh / 1e6)} TWh`;
    if (a >= 1e3) return `${n1.format(mwh / 1e3)} GWh`;
    return `${n0.format(mwh)} MWh`;
  },
  pct: (x) => (x == null ? "—" : `${n1.format(100 * x)}%`),
  pct2: (x) => (x == null ? "—" : `${n2.format(100 * x)}%`),
  rs: (v) => (v == null ? "—" : `R$ ${n0.format(v)}`),
  // R$ with a readable magnitude: bi / mi / plain.
  reais: (v) => (v == null ? "—" : Math.abs(v) >= 1e9 ? `R$ ${n1.format(v / 1e9)} bi` : Math.abs(v) >= 1e6 ? `R$ ${n1.format(v / 1e6)} mi` : `R$ ${n0.format(v)}`),
  rsbi: (v) => (v == null ? "—" : `R$ ${n1.format(v / 1e9)} bi`),
  rsmwh: (v) => (v == null ? "—" : `R$ ${n0.format(v)}/MWh`),
  num: (v, d = 1) => (v == null ? "—" : nf(d).format(v)),
  mes: (iso) => new Date(iso + "T12:00:00").toLocaleDateString("pt-BR", { month: "short", year: "2-digit" }).replace(". de ", "/").replace(" de ", "/"),
  dia: (iso) => new Date(iso + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }).replace(". de ", " ").replace(" de ", " "),
  data: (iso) => new Date(iso + "T12:00:00").toLocaleDateString("pt-BR"),
};

export async function api(path, params = {}) {
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v));
  const r = await fetch(`/api/${path}${q.size ? "?" + q : ""}`);
  if (r.status === 503) throw Object.assign(new Error("O banco ainda está acordando."), { waking: true });
  if (!r.ok) throw new Error(r.status === 404 ? "Não encontrado." : `Erro ${r.status} ao ler o Lakebase.`);
  return r.json();
}

export async function apiPost(path, body) {
  const r = await fetch(`/api/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(r.status === 403 ? "Sem permissão para estes dados no Unity Catalog." : j.detail || `Erro ${r.status}.`);
  return j;
}

const WAKE_RETRIES = 10, WAKE_EVERY_MS = 3000; // ~30 s on top of the server's own retries

// Fetch hook: { data, error, loading, waking, retry }. Keeps the previous data while a new request
// runs, so boards update values in place instead of blanking. A waking database (503) is a loading
// state that retries on its own, not an error.
export function useApi(path, params = {}) {
  const key = path + JSON.stringify(params);
  const [state, setState] = useState({ data: null, error: null, loading: true, waking: false });
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true, timer;
    const run = (tries) => api(path, params)
      .then((data) => live && setState({ data, error: null, loading: false, waking: false }))
      .catch((error) => {
        if (!live) return;
        if (error.waking && tries < WAKE_RETRIES) {
          setState((s) => ({ ...s, loading: true, waking: true, error: null }));
          timer = setTimeout(() => run(tries + 1), WAKE_EVERY_MS);
        } else setState((s) => ({ data: s.data, error, loading: false, waking: false }));
      });
    setState((s) => ({ ...s, loading: true, error: null }));
    run(0);
    return () => { live = false; clearTimeout(timer); };
  }, [key, n]); // eslint-disable-line react-hooks/exhaustive-deps
  return { ...state, retry: () => setN((x) => x + 1) };
}

// SIGA municipio often carries " - UF"; show the place once.
export const lugar = (p) => [p?.municipio?.replace(/\s*-\s*[A-Z]{2}$/, ""), p?.uf].filter(Boolean).join(" · ");
export const CADASTRO = { siga: "ANEEL SIGA", ons: "ONS (sem cadastro SIGA)" };
