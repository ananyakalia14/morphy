import { useMemo } from "react";

type DatabaseItem = {
  name: string;
  tag: string;
  badge: string;
  icon: (color: string) => React.ReactNode;
};

// Supported databases & query connectors
const ROW_1: DatabaseItem[] = [
  {
    name: "PostgreSQL",
    tag: "Primary Live Engine",
    badge: "LIVE",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 6c0-1.66 3.58-3 8-3s8 1.34 8 3v12c0 1.66-3.58 3-8 3s-8-1.34-8-3V6z" />
        <path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
        <path d="M12 9v12" />
      </svg>
    ),
  },
  {
    name: "SQLite",
    tag: "Native Analytical Engine",
    badge: "EMBEDDED",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="16" rx="3" />
        <path d="M7 8h10" />
        <path d="M7 12h7" />
        <path d="M7 16h4" />
      </svg>
    ),
  },
  {
    name: "Apache Parquet",
    tag: "Columnar File Import",
    badge: "STORAGE",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="5" height="18" rx="1" />
        <rect x="10" y="3" width="5" height="18" rx="1" fill={c} fillOpacity="0.2" />
        <rect x="17" y="3" width="4" height="18" rx="1" />
      </svg>
    ),
  },
  {
    name: "CSV Imports",
    tag: "Tabular Stream Ingestion",
    badge: "STREAM",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <path d="M8 13h8" />
        <path d="M8 17h6" />
      </svg>
    ),
  },
  {
    name: "Redis",
    tag: "Fingerprint & SQL Cache",
    badge: "CACHE",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <path d="m12 3-9 5 9 5 9-5z" />
        <path d="m3 12 9 5 9-5" />
        <path d="m3 16 9 5 9-5" />
      </svg>
    ),
  },
  {
    name: "DuckDB",
    tag: "Embedded In-Memory OLAP",
    badge: "ANALYTIC",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <circle cx="9" cy="10" r="1.5" fill={c} />
        <path d="M15 13c-1.5 2-4.5 2-6 0" />
      </svg>
    ),
  },
];

const ROW_2: DatabaseItem[] = [
  {
    name: "Snowflake",
    tag: "Enterprise Data Warehouse",
    badge: "CLOUD",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2v20" />
        <path d="m4.93 4.93 14.14 14.14" />
        <path d="m19.07 4.93-14.14 14.14" />
        <circle cx="12" cy="12" r="3" fill={c} fillOpacity="0.25" />
      </svg>
    ),
  },
  {
    name: "Google BigQuery",
    tag: "Federated SQL Engine",
    badge: "WAREHOUSE",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
        <path d="M11 7v8" />
        <path d="M7 11h8" />
      </svg>
    ),
  },
  {
    name: "MySQL",
    tag: "Relational Connector",
    badge: "SQL",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <ellipse cx="12" cy="6" rx="8" ry="3" />
        <path d="M4 6v6c0 1.66 3.58 3 8 3s8-1.34 8-3V6" />
        <path d="M4 12v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" />
      </svg>
    ),
  },
  {
    name: "ClickHouse",
    tag: "Column-Oriented DBMS",
    badge: "FAST OLAP",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="10" width="3" height="10" rx="0.5" />
        <rect x="8" y="4" width="3" height="16" rx="0.5" fill={c} />
        <rect x="13" y="8" width="3" height="12" rx="0.5" />
        <rect x="18" y="12" width="3" height="8" rx="0.5" />
      </svg>
    ),
  },
  {
    name: "MongoDB",
    tag: "Document Model Dialect",
    badge: "NOSQL",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2C9 7 6 11 6 15a6 6 0 0 0 12 0c0-4-3-8-6-13z" />
        <path d="M12 2v20" />
      </svg>
    ),
  },
  {
    name: "Apache Arrow",
    tag: "Zero-Copy Data Transport",
    badge: "INTEROP",
    icon: (c) => (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={c} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <line x1="5" y1="12" x2="19" y2="12" />
        <polyline points="12 5 19 12 12 19" />
      </svg>
    ),
  },
];

export function DatabaseContributionGrid() {
  const TOTAL_COLS = 47;
  const PAD_LEFT = 6;
  const LETTER_COLS = 35;

  const cells = useMemo(() => {
    // Coordinate set for MORPHY
    const letterPoints = new Set<string>();
    const addLetter = (pts: [number, number][], offset: number) => {
      for (const [r, c] of pts) {
        letterPoints.add(`${r},${c + offset}`);
      }
    };

    // M
    addLetter([
      [0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],
      [1,1],[2,2],[1,3],
      [0,4],[1,4],[2,4],[3,4],[4,4],[5,4],[6,4]
    ], 0);

    // O
    addLetter([
      [1,0],[2,0],[3,0],[4,0],[5,0],
      [0,1],[6,1],
      [0,2],[6,2],
      [0,3],[6,3],
      [1,4],[2,4],[3,4],[4,4],[5,4]
    ], 6);

    // R
    addLetter([
      [0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],
      [0,1],[3,1],
      [0,2],[3,2],[4,2],
      [0,3],[3,3],[5,3],
      [1,4],[2,4],[6,4]
    ], 12);

    // P
    addLetter([
      [0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],
      [0,1],[3,1],
      [0,2],[3,2],
      [0,3],[3,3],
      [1,4],[2,4]
    ], 18);

    // H
    addLetter([
      [0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],
      [3,1],[3,2],[3,3],
      [0,4],[1,4],[2,4],[3,4],[4,4],[5,4],[6,4]
    ], 24);

    // Y
    addLetter([
      [0,0],[1,0],[2,1],
      [3,2],[4,2],[5,2],[6,2],
      [2,3],[1,4],[0,4]
    ], 30);

    // Build the 7 rows x 47 cols matrix
    const matrix: { isLetter: boolean; level: number; key: string }[] = [];
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < TOTAL_COLS; c++) {
        const letterCol = c - PAD_LEFT;
        const isLetter =
          letterCol >= 0 &&
          letterCol < LETTER_COLS &&
          letterPoints.has(`${r},${letterCol}`);

        // Seeded background variation
        const pseudoRand = ((r * 13 + c * 37 + (r ^ c) * 7) % 100);
        let bgLevel = 0;
        if (pseudoRand > 75) bgLevel = 2;
        else if (pseudoRand > 48) bgLevel = 1;

        matrix.push({
          isLetter,
          level: isLetter ? (pseudoRand > 80 ? 5 : 4) : bgLevel,
          key: `${r}-${c}`,
        });
      }
    }
    return matrix;
  }, []);

  return (
    <section className="engine-matrix-section" aria-label="Supported database matrix and telemetry">
      <div className="engine-matrix-card">
        {/* Top telemetry status bar */}
        <div className="matrix-top-bar">
          <span className="matrix-user-handle">@morphy</span>
        </div>

        {/* GitHub-style Heatmap Grid spelling MORPHY */}
        <div className="matrix-heatmap-scroll" tabIndex={0} role="region" aria-label="MORPHY contribution matrix">
          <div className="matrix-heatmap-grid">
            {cells.map((cell) => (
              <div
                key={cell.key}
                className={`matrix-tile ${cell.isLetter ? "tile-letter" : ""} tile-lvl-${cell.level}`}
              />
            ))}
          </div>
        </div>

        {/* Subtle Horizontal Divider */}
        <div className="matrix-card-divider" aria-hidden="true" />

        {/* Supported Databases / Connectors Marquee */}
        <div className="matrix-databases-wrap matrix-marquee-container" aria-label="Supported database connectors marquee">
          {/* Row 1 Marquee (Moving Left) */}
          <div className="matrix-marquee-row">
            <div className="matrix-marquee-track marquee-left">
              <div className="matrix-marquee-group">
                {[...ROW_1, ...ROW_1].map((db, idx) => (
                  <div key={`r1-a-${db.name}-${idx}`} className="matrix-db-badge" title={`${db.name} — ${db.tag}`}>
                    <div className="matrix-db-icon">
                      {db.icon("currentColor")}
                    </div>
                    <span className="matrix-db-name">{db.name}</span>
                  </div>
                ))}
              </div>
              <div className="matrix-marquee-group" aria-hidden="true">
                {[...ROW_1, ...ROW_1].map((db, idx) => (
                  <div key={`r1-b-${db.name}-${idx}`} className="matrix-db-badge" title={`${db.name} — ${db.tag}`}>
                    <div className="matrix-db-icon">
                      {db.icon("currentColor")}
                    </div>
                    <span className="matrix-db-name">{db.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Row 2 Marquee (Moving Right) */}
          <div className="matrix-marquee-row">
            <div className="matrix-marquee-track marquee-right">
              <div className="matrix-marquee-group">
                {[...ROW_2, ...ROW_2].map((db, idx) => (
                  <div key={`r2-a-${db.name}-${idx}`} className="matrix-db-badge" title={`${db.name} — ${db.tag}`}>
                    <div className="matrix-db-icon">
                      {db.icon("currentColor")}
                    </div>
                    <span className="matrix-db-name">{db.name}</span>
                  </div>
                ))}
              </div>
              <div className="matrix-marquee-group" aria-hidden="true">
                {[...ROW_2, ...ROW_2].map((db, idx) => (
                  <div key={`r2-b-${db.name}-${idx}`} className="matrix-db-badge" title={`${db.name} — ${db.tag}`}>
                    <div className="matrix-db-icon">
                      {db.icon("currentColor")}
                    </div>
                    <span className="matrix-db-name">{db.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

