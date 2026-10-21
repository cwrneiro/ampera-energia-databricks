// The sheet: title block, a neat-line frame that owns exactly one plot, supporting boards below the
// frame, and a margin column for legend, notes and sources — the grammar every page shares.

// full: the frame takes the whole sheet and the plot carries its own title and key as overlays
// (the map sheet).
export function Sheet({ title, scope, actions, corners = {}, margin, children, below, full }) {
  const head = (
    <header className="sheet-title">
      <div>
        <h1>{title}</h1>
        {scope && <p className="scope">{scope}</p>}
      </div>
      {actions && <div className="sheet-actions">{actions}</div>}
    </header>
  );
  return (
    <section className={"sheet" + (full ? " sheet--full" : "")}>
      {!full && head}
      <div className="sheet-body">
        <div className="sheet-main">
          <div className="neat">
            <svg className="neat-line" aria-hidden="true">
              <rect pathLength="1" />
            </svg>
            {Object.entries(corners).map(([pos, text]) => text && (
              <span key={pos} className={`corner corner--${pos}`}>{text}</span>
            ))}
            <div className="neat-inner">{children}</div>
          </div>
          {below && <div className="below">{below}</div>}
        </div>
        {!full && <aside className="margin">{margin}</aside>}
      </div>
    </section>
  );
}

export function Block({ title, children }) {
  return (
    <section className="block">
      {title && <h2>{title}</h2>}
      {children}
    </section>
  );
}

export function Status({ loading, error, retry, empty, waking }) {
  if (error) {
    return (
      <div className="status status--error" role="alert">
        <p>{error.message} {error.waking ? "Tente de novo em alguns segundos." : "Verifique a conexão e tente de novo."}</p>
        <button className="btn" onClick={retry}>Tentar de novo</button>
      </div>
    );
  }
  if (waking) {
    return (
      <div className="status" aria-live="polite">
        <span className="ink-load" />Acordando o banco de dados…
        <p className="status-sub">O Lakebase desliga quando fica ocioso e volta em alguns segundos.</p>
      </div>
    );
  }
  if (loading) return <div className="status" aria-live="polite"><span className="ink-load" />Lendo o Lakebase…</div>;
  if (empty) return <div className="status">{empty}</div>;
  return null;
}

// Swatch beside text carries identity; text itself stays in ink.
export function Swatch({ cor, hatch, shape = "sq" }) {
  return <span className={`sw sw--${shape}${hatch ? " sw--hatch" : ""}`} style={{ "--c": cor }} aria-hidden="true" />;
}

// One bar that visibly fills 100%: every segment of the whole, separated by surface gaps.
export function WholeBar({ parts, label }) {
  const total = parts.reduce((s, p) => s + (p.v || 0), 0) || 1;
  return (
    <div className="wholebar" role="img" aria-label={label}>
      {parts.filter((p) => p.v > 0).map((p) => (
        <span key={p.id} className={p.hatch ? "seg seg--hatch" : "seg"}
              style={{ flexGrow: p.v / total, "--c": p.cor }} title={`${p.nome}: ${(100 * p.v / total).toFixed(2)}%`} />
      ))}
    </div>
  );
}

export const SOURCES = (
  <ul className="sources">
    <li><b>ONS</b> geração horária por usina e conjunto</li>
    <li><b>ANEEL SIGA</b> cadastro, CEG, coordenadas, capacidade</li>
    <li><b>CCEE</b> PLD horário por submercado</li>
    <li><b>Open-Meteo (ERA5)</b> clima modelado · <b>INMET</b> estações</li>
  </ul>
);
