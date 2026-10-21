import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl); // Vite doesn't emit MapLibre 6's worker on its own
import { FONTE, FONTES, fmt, lugar } from "./lib.js";
import { Block, Sheet, Swatch } from "./Sheet.jsx";

const STYLE = "https://tiles.openfreemap.org/styles/positron"; // OpenFreeMap: free, no key (decision #21)
const BRASIL = [[-74.5, -34.2], [-33.5, 5.6]];
const MAX_MWH = 60e6; // radius scale ceiling (largest plants ~ 60 TWh over 24 months)

const STEP = 5; // graticule every 5°
const GRATICULE = { type: "FeatureCollection", features: [
  ...Array.from({ length: 81 / STEP + 1 }, (_, i) => -90 + i * STEP).map((lon) =>
    ({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[lon, -60], [lon, 20]] } })),
  ...Array.from({ length: 80 / STEP + 1 }, (_, i) => -60 + i * STEP).map((lat) =>
    ({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[-90, lat], [-10, lat]] } })),
] };

const deg = (v, pos, neg) => `${fmt.num(Math.abs(v), 0)}°${v >= 0 ? pos : neg}`;
const radius = ["interpolate", ["linear"], ["sqrt", ["max", ["get", "mwh"], 0]], 0, 2.5, Math.sqrt(1e5), 4, Math.sqrt(1e6), 7, Math.sqrt(MAX_MWH), 26];
const sizeFor = (mwh) => { // same piecewise scale as `radius`, for the size legend
  const s = Math.sqrt(mwh), pts = [[0, 2.5], [Math.sqrt(1e5), 4], [Math.sqrt(1e6), 7], [Math.sqrt(MAX_MWH), 26]];
  for (let i = 1; i < pts.length; i++) if (s <= pts[i][0]) return pts[i - 1][1] + ((s - pts[i - 1][0]) / (pts[i][0] - pts[i - 1][0])) * (pts[i][1] - pts[i - 1][1]);
  return 26;
};

const WIDE = matchMedia("(min-width: 901px)"); // overlays float over the map only above 900px

export default function MapSheet({ f, plants, filters }) {
  const el = useRef(null), map = useRef(null), wrap = useRef(null), left = useRef(null), foot = useRef(null);
  const view = useRef({ target: BRASIL, gap: 12, moved: false }); // what to refit to on resize
  // Fit inside what the overlays leave clear: the title/legend panel on the left, the footer below.
  const pad = (x) => WIDE.matches
    ? { top: x, right: x, bottom: foot.current.offsetHeight + x, left: left.current.offsetWidth + 12 + x } : x;
  // Filter changes glide on the house ease (MapLibre jumps instead under reduced motion); resizes jump.
  const fit = (animate = false) => map.current.fitBounds(view.current.target, { padding: pad(view.current.gap), maxZoom: 9, animate,
    duration: 900, easing: (t) => (t === 1 ? 1 : 1 - 2 ** (-10 * t)) });
  const [sel, setSel] = useState(null);
  const [focus, setFocus] = useState(null);
  const [grat, setGrat] = useState({ lons: [], lats: [] });
  const [ready, setReady] = useState(false);

  const shown = useMemo(() => plants.filter((p) => p.lat != null &&
    (!f.uf || p.uf === f.uf) && (!f.fonte || p.fonte === f.fonte) && (!f.conjunto || p.conjunto_key === f.conjunto)), [plants, f]);
  const geo = useMemo(() => ({
    type: "FeatureCollection",
    features: shown.map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: { id: p.plant_id, nome: p.nome, fonte: p.fonte, mwh: p.mwh_total || 0 } })),
  }), [shown]);
  const cover = useMemo(() => {
    const tot = plants.reduce((s, p) => s + (p.mwh_total || 0), 0);
    const loc = plants.filter((p) => p.lat != null);
    return { n: loc.length, sem: plants.length - loc.length, share: loc.reduce((s, p) => s + (p.mwh_total || 0), 0) / tot };
  }, [plants]);

  useEffect(() => {
    const m = new maplibregl.Map({ container: el.current, style: STYLE, bounds: BRASIL, attributionControl: { compact: true },
                                   dragRotate: false, pitchWithRotate: false });
    m.touchZoomRotate.disableRotation();
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    const tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, className: "map-tip" });
    const upd = () => {
      const b = m.getBounds();
      // Degree labels where the graticule meets the neat line.
      const snap = (a, z) => Array.from({ length: Math.floor(z / STEP) - Math.ceil(a / STEP) + 1 }, (_, i) => (Math.ceil(a / STEP) + i) * STEP);
      setGrat({
        // label every 10° when 5° labels would collide
        lons: snap(b.getWest(), b.getEast()).map((v) => ({ v, x: m.project([v, b.getNorth()]).x }))
          .filter((g, _, a) => a.length < 2 || a[1].x - a[0].x >= 44 || g.v % (2 * STEP) === 0),
        lats: snap(b.getSouth(), b.getNorth()).map((v) => ({ v, y: m.project([b.getWest(), v]).y })),
      });
    };
    // Basemap labels in Portuguese where OpenMapTiles has them.
    m.on("style.load", () => m.getStyle().layers.forEach((l) => {
      if (l.type === "symbol" && l.layout?.["text-field"]) m.setLayoutProperty(l.id, "text-field", ["coalesce", ["get", "name:pt"], ["get", "name"]]);
    }));
    m.on("movestart", (e) => { if (e.originalEvent) view.current.moved = true; }); // viewer panned/zoomed
    const ro = new ResizeObserver(() => {
      m.resize();
      // map controls sit above the footer
      wrap.current.style.setProperty("--foot", `${WIDE.matches ? foot.current.offsetHeight : 0}px`);
      if (!view.current.moved && m.loaded()) fit();
    });
    ro.observe(el.current);
    ro.observe(foot.current);
    m.on("load", () => {
      fit();
      m.addSource("graticule", { type: "geojson", data: GRATICULE });
      m.addLayer({ id: "graticule", type: "line", source: "graticule",
                   paint: { "line-color": "#541790", "line-opacity": 0.3, "line-width": 0.75 } });
      m.addSource("plants", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "plants", type: "circle", source: "plants", paint: {
        "circle-color": ["match", ["get", "fonte"], ...FONTES.flatMap((x) => [x.id, x.cor]), "#8f8a2a"],
        "circle-radius": radius, "circle-opacity": 0.85,
        "circle-stroke-color": "#ffffff", "circle-stroke-width": 1, // surface ring
      }, layout: { "circle-sort-key": ["-", ["get", "mwh"]] } });
      m.on("mousemove", "plants", (e) => {
        m.getCanvas().style.cursor = "pointer";
        const p = e.features[0].properties;
        tip.setLngLat(e.lngLat).setHTML(`<b></b><span></span>`).addTo(m);
        const node = tip.getElement().querySelector(".maplibregl-popup-content");
        node.querySelector("b").textContent = p.nome;
        node.querySelector("span").textContent = `${FONTE[p.fonte]?.nome || p.fonte} · ${fmt.energia(p.mwh)}`;
      });
      m.on("mouseleave", "plants", () => { m.getCanvas().style.cursor = ""; tip.remove(); });
      m.on("click", "plants", (e) => setSel(e.features[0].properties.id));
      m.on("click", (e) => { if (!m.queryRenderedFeatures(e.point, { layers: ["plants"] }).length) setSel(null); });
      upd();
      setReady(true);
    });
    m.on("move", upd); // degree labels track the camera, glides included
    map.current = m;
    return () => { ro.disconnect(); m.remove(); map.current = null; };
  }, []);

  useEffect(() => { if (ready) map.current.getSource("plants").setData(geo); }, [ready, geo]);

  // A filter frames its plants (UF, fonte or conjunto); no filter frames Brazil.
  useEffect(() => {
    if (!ready) return;
    const framed = (f.uf || f.fonte || f.conjunto) && shown.length;
    const lons = framed ? shown.map((x) => x.lon) : [], lats = framed ? shown.map((x) => x.lat) : [];
    view.current = framed
      ? { target: [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], gap: 48, moved: false }
      : { target: BRASIL, gap: 12, moved: false };
    fit(true);
  }, [ready, shown]); // eslint-disable-line react-hooks/exhaustive-deps

  // Signature interaction: the selected plant (or hovered fonte) lifts, everything else dims.
  useEffect(() => {
    if (!ready) return;
    const m = map.current;
    const lit = sel ? ["==", ["get", "id"], sel] : focus ? ["==", ["get", "fonte"], focus] : true;
    m.setPaintProperty("plants", "circle-opacity", ["case", lit, 0.88, 0.14]);
    m.setPaintProperty("plants", "circle-stroke-width", sel ? ["case", lit, 2.5, 0.5] : 1);
    m.setPaintProperty("plants", "circle-stroke-color", sel ? ["case", lit, "#0a0a0a", "#ffffff"] : "#ffffff");
  }, [ready, sel, focus]);

  useEffect(() => {
    if (!sel) return undefined;
    const esc = (e) => e.key === "Escape" && setSel(null);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [sel]);

  const p = sel && plants.find((x) => x.plant_id === sel);
  const counts = Object.fromEntries(FONTES.map((x) => [x.id, shown.filter((s) => s.fonte === x.id).length]));

  const scope = [f.uf || "Brasil", f.fonte && FONTE[f.fonte].nome, f.conjunto && plants.find((x) => x.conjunto_key === f.conjunto)?.nom_conjunto]
    .filter(Boolean).join(" · ");

  // The map takes the whole sheet; its title and key float over it: title + legend top-left,
  // filters (and the selected plant) top-right, notes and sources along the foot.
  return (
    <Sheet full>
      <div className="map-wrap" ref={wrap}>
        <div className="map-stage">
          <div className="map" ref={el} role="region" aria-label="Mapa de usinas" />
          <div className="grat" aria-hidden="true">
            {grat.lons.map((g) => <span key={`x${g.v}`} className="grat-x" style={{ left: g.x }}>{deg(g.v, "L", "O")}</span>)}
            {grat.lats.map((g) => <span key={`y${g.v}`} className="grat-y" style={{ top: g.y }}>{deg(g.v, "N", "S")}</span>)}
          </div>
        </div>
        <div className="ov-left" ref={left}>
          <header className="map-head">
            <h1>Usinas por coordenada</h1>
            <p className="scope">{scope} · clique em uma usina para ver a ficha</p>
          </header>
          <Block title="Legenda">
            <ul className="legend">
              {FONTES.filter((x) => counts[x.id]).map((x) => (
                <li key={x.id} className={focus && focus !== x.id ? "is-dim" : ""}>
                  <button type="button" onMouseEnter={() => setFocus(x.id)} onMouseLeave={() => setFocus(null)}
                          onFocus={() => setFocus(x.id)} onBlur={() => setFocus(null)}>
                    <Swatch cor={x.cor} shape="dot" />{x.nome}<span className="num">{fmt.int(counts[x.id])}</span>
                  </button>
                </li>
              ))}
            </ul>
            <div className="sizes" aria-hidden="true">
              {[1e6, 10e6, 50e6].map((v) => (
                <span key={v}><i style={{ width: 2 * sizeFor(v), height: 2 * sizeFor(v) }} />{fmt.energia(v)}</span>
              ))}
            </div>
            <p className="sizes-cap">Círculo proporcional à energia gerada em 24 meses.</p>
          </Block>
        </div>
        <div className="ov-right">
          {filters}
          {p && (
            <section className="pick" aria-label="Usina selecionada">
              <h3>{p.nome}</h3>
              <p className="muted">{p.ceg || "sem CEG (chave substituta)"}</p>
              <dl className="facts">
                <dt>Fonte</dt><dd><Swatch cor={FONTE[p.fonte]?.cor} shape="dot" />{FONTE[p.fonte]?.nome || p.fonte}</dd>
                <dt>Local</dt><dd>{lugar(p)}</dd>
                <dt>Capacidade</dt><dd className="num">{p.capacidade_mw ? `${fmt.num(p.capacidade_mw)} MW` : "—"}</dd>
                <dt>Energia 24 m</dt><dd className="num">{fmt.energia(p.mwh_total)}</dd>
                {p.nom_conjunto && <><dt>Conjunto</dt><dd>{p.nom_conjunto}</dd></>}
              </dl>
              <a className="btn" href={`#/usina/${encodeURIComponent(p.plant_id)}`}>Abrir ficha da usina</a>
              <button type="button" className="btn btn--ghost" onClick={() => setSel(null)}>Limpar seleção</button>
            </section>
          )}
        </div>
        <footer className="map-foot" ref={foot}>
          <ol className="notes" aria-label="Notas">
            <li>{fmt.int(shown.length)} usinas na folha. Coordenadas da ANEEL SIGA: {fmt.int(cover.n)} usinas, {fmt.pct(cover.share)} da energia.</li>
            <li>{fmt.int(cover.sem)} cadastros sem coordenada (agregados e conjuntos do ONS) não aparecem no mapa.</li>
          </ol>
        </footer>
      </div>
    </Sheet>
  );
}
