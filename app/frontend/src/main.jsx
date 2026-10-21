import { StrictMode, Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { FONTES, useApi } from "./lib.js";
import { Status } from "./Sheet.jsx";
import Overview from "./Overview.jsx";
import Reconciliation from "./Reconciliation.jsx";
const MapSheet = lazy(() => import("./MapSheet.jsx")); // MapLibre is most of the bundle
import Plant from "./Plant.jsx";

// Hash routing: the backend only serves static files, so no server-side fallback is needed.
function useRoute() {
  const [hash, setHash] = useState(location.hash);
  useEffect(() => {
    const on = () => { setHash(location.hash); window.scrollTo(0, 0); };
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  const [, page = "", id] = hash.replace(/^#/, "").split("/");
  return { page, id: id && decodeURIComponent(id) };
}

const SHEETS = [
  { page: "", nome: "Visão geral", hint: "geração por fonte, CEG e conjunto" },
  { page: "reconciliacao", nome: "Reconciliação", hint: "como o ONS liga à ANEEL" },
  { page: "mapa", nome: "Mapa", hint: "usinas por coordenada" },
  { page: "usina", nome: "Usina", hint: "preço e clima de uma usina" },
];

function Brand() {
  return (
    <a className="brand" href="#/" aria-label="Ampera Energia — início">
      <span className="wordmark">Ampera<b>Energia</b></span>
    </a>
  );
}

function SheetIndex({ page, lastPlant }) {
  return (
    <nav className="index" aria-label="Folhas">
      {SHEETS.map((s) => {
        const href = s.page === "usina" ? (lastPlant ? `#/usina/${encodeURIComponent(lastPlant)}` : null) : `#/${s.page}`;
        const current = page === s.page;
        return href ? (
          <a key={s.page} href={href} className="index-cell" aria-current={current ? "page" : undefined}>
            <span className="index-name">{s.nome}</span><span className="index-hint">{s.hint}</span>
          </a>
        ) : (
          <span key={s.page} className="index-cell is-off" title="Escolha uma usina no mapa ou nos rankings">
            <span className="index-name">{s.nome}</span><span className="index-hint">escolha no mapa</span>
          </span>
        );
      })}
    </nav>
  );
}

function Filters({ f, set, meta, plants, show, slim }) {
  const ufs = useMemo(() => [...new Set(plants.map((p) => p.uf).filter(Boolean))].sort(), [plants]);
  const conjuntos = useMemo(() => {
    const m = new Map();
    plants.forEach((p) => p.conjunto_key && !m.has(p.conjunto_key) && m.set(p.conjunto_key, p.nom_conjunto || p.conjunto_key));
    return [...m].sort((a, b) => a[1].localeCompare(b[1], "pt-BR"));
  }, [plants]);
  const plantLabel = (p) => `${p.nome} · ${p.plant_id}`;
  const current = plants.find((p) => p.plant_id === f.usina);
  const [txt, setTxt] = useState("");
  useEffect(() => setTxt(current ? plantLabel(current) : ""), [f.usina]); // eslint-disable-line react-hooks/exhaustive-deps
  const any = f.uf || f.fonte || f.conjunto || f.usina || (meta && (f.de !== meta.de || f.ate !== meta.ate));
  const upd = (k) => (e) => set({ ...f, [k]: e.target.value || null });
  // Phones: filters fold behind one disclosure so the sheet reaches the first screen.
  const narrow = useMemo(() => matchMedia("(max-width: 520px)"), []);
  const [open, setOpen] = useState(!narrow.matches);
  useEffect(() => {
    const on = () => setOpen(!narrow.matches);
    narrow.addEventListener("change", on);
    return () => narrow.removeEventListener("change", on);
  }, [narrow]);
  const n = [f.uf, f.fonte, f.conjunto, f.usina].filter(Boolean).length;
  const clear = () => set({ de: meta?.de, ate: meta?.ate });
  // Map sheet's filter menu: closes on a click outside it or Esc, like any menu.
  const pop = useRef(null);
  useEffect(() => {
    if (!slim) return undefined;
    const close = (e) => {
      const d = pop.current;
      if (d?.open && (e.key === "Escape" || (e.type === "pointerdown" && !d.contains(e.target)))) d.open = false;
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", close); };
  }, [slim]);
  const fields = (
    <>
      {show.periodo && (
        <div className="f-period" role="group" aria-labelledby="f-period-l">
          <span id="f-period-l">Período</span>
          <div className="f-row"><input type="date" aria-label="De" value={f.de || ""} min={meta?.de} max={f.ate || meta?.ate} onChange={upd("de")} />
          <span aria-hidden="true">–</span>
          <input type="date" aria-label="Até" value={f.ate || ""} min={f.de || meta?.de} max={meta?.ate} onChange={upd("ate")} /></div>
        </div>
      )}
      <label>UF
        <select value={f.uf || ""} onChange={upd("uf")}>
          <option value="">Todas</option>
          {ufs.map((u) => <option key={u}>{u}</option>)}
        </select>
      </label>
      <label>Fonte
        <select value={f.fonte || ""} onChange={upd("fonte")}>
          <option value="">Todas</option>
          {FONTES.map((x) => <option key={x.id} value={x.id}>{x.nome}</option>)}
        </select>
      </label>
      {show.conjunto && (
        <label className="f-wide">Conjunto
          <select value={f.conjunto || ""} onChange={upd("conjunto")}>
            <option value="">Todos</option>
            {conjuntos.map(([k, n]) => <option key={k} value={k}>{n}</option>)}
          </select>
        </label>
      )}
      {show.usina && (
        <label className="f-wide">Usina (nome ou CEG)
          <input list="usinas" value={txt} placeholder="Buscar usina…" onChange={(e) => {
            setTxt(e.target.value);
            const id = e.target.value.split(" · ")[1];
            if (id && plants.some((p) => p.plant_id === id)) set({ ...f, usina: id });
            if (!e.target.value) set({ ...f, usina: null });
          }} />
          <datalist id="usinas">{plants.map((p) => <option key={p.plant_id} value={plantLabel(p)} />)}</datalist>
        </label>
      )}
    </>
  );
  // Map sheet: an icon button at the map's top-right opens the filters as a menu.
  if (slim) {
    return (
      <details className="filters-pop" ref={pop}>
        <summary aria-label={`Filtros${n ? `, ${n} ativo${n > 1 ? "s" : ""}` : ""}`} title="Filtros">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <path d="M3.5 5h17l-6.5 8v5.5l-4 2V13z" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" />
          </svg>
          {n > 0 && <b className="num">{n}</b>}
        </summary>
        <form className="filters filters--pop" onSubmit={(e) => e.preventDefault()} aria-label="Filtros">
          <div className="pop-head">
            <h2>Filtros</h2>
            {n > 0 && <button type="button" className="link-btn" onClick={clear}>Limpar</button>}
          </div>
          {fields}
        </form>
      </details>
    );
  }
  return (
    <details className="filters-wrap" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
    <summary className="filters-toggle">Filtros{n > 0 && <b className="num"> · {n} ativo{n > 1 ? "s" : ""}</b>}</summary>
    <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Filtros">
      {fields}
      {any && <button type="button" className="btn btn--ghost" onClick={clear}>Limpar filtros</button>}
    </form>
    </details>
  );
}

function App() {
  const { page, id } = useRoute();
  const meta = useApi("meta");
  const plantsQ = useApi("plants");
  const plants = plantsQ.data || [];
  const [f, setF] = useState({});
  const [lastPlant, setLastPlant] = useState(null);
  useEffect(() => { if (meta.data && !f.de) setF((x) => ({ de: meta.data.de, ate: meta.data.ate, ...x })); }, [meta.data]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (page === "usina" && id) setLastPlant(id); }, [page, id]);
  const byId = useMemo(() => Object.fromEntries(plants.map((p) => [p.plant_id, p])), [plants]);

  const show = page === "" ? { periodo: true, conjunto: true, usina: true } : null;
  const ready = meta.data && plantsQ.data && f.de;

  return (
    <>
      <header className="top">
        <Brand />
        <SheetIndex page={page} lastPlant={lastPlant} />
      </header>
      {show && ready && <Filters f={f} set={setF} meta={meta.data} plants={plants} show={show} />}
      <main className={page === "mapa" ? "main--fit" : undefined}>
        {!ready ? (
          <div className="sheet sheet--boot">
            <Status loading={!meta.error && !plantsQ.error} error={meta.error || plantsQ.error} waking={meta.waking || plantsQ.waking}
                    retry={() => { meta.retry(); plantsQ.retry(); }} />
          </div>
        ) : page === "reconciliacao" ? <Reconciliation />
          : page === "mapa" ? <Suspense fallback={<div className="sheet sheet--boot"><Status loading /></div>}><MapSheet f={f} plants={plants}
              filters={<Filters f={f} set={setF} meta={meta.data} plants={plants} show={{ conjunto: true }} slim />} /></Suspense>
          : page === "usina" && id ? <Plant id={id} plant={byId[id]} />
          : <Overview f={f} setF={setF} meta={meta.data} byId={byId} />}
      </main>
    </>
  );
}

createRoot(document.getElementById("root")).render(<StrictMode><App /></StrictMode>);
