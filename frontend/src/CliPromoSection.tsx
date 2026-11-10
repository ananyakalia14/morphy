import { useState } from "react";
import { Terminal, Download, Check, Copy, X } from "lucide-react";

export function CliPromoSection() {
  const [cliModal, setCliModal] = useState<"explore" | "install" | null>(null);
  const [copiedSnippet, setCopiedSnippet] = useState(false);

  const copyInstall = () => {
    navigator.clipboard.writeText("python -m pip install -e ./cli && morphy --help");
    setCopiedSnippet(true);
    setTimeout(() => setCopiedSnippet(false), 2000);
  };

  return (
    <>
      <div className="cli-promo-card">
        <div className="cli-promo-content">
          <div className="cli-promo-badge">
            <Terminal className="w-3.5 h-3.5" />
            <span>DEVELOPER TOOLKIT</span>
          </div>
          <h2 className="cli-promo-heading">MORPHY, beyond the browser.</h2>
          <p className="cli-promo-description">
            Take your database workspace to the terminal. Query, inspect and interact with your data using MORPHY CLI — powered by the same governed engine.
          </p>
          <div className="cli-promo-buttons">
            <button
              type="button"
              className="cli-cta-primary"
              onClick={() => setCliModal("explore")}
            >
              <Terminal className="w-4 h-4 mr-2" />
              Explore CLI
            </button>
            <button
              type="button"
              className="cli-cta-secondary"
              onClick={() => setCliModal("install")}
            >
              <Download className="w-4 h-4 mr-2" />
              View installation guide
            </button>
          </div>
        </div>

        <div className="cli-promo-terminal-box">
          <div className="cli-terminal-top">
            <div className="cli-window-dots">
              <span className="window-dot red" />
              <span className="window-dot yellow" />
              <span className="window-dot green" />
            </div>
            <span className="cli-window-title">terminal — morphy</span>
            <button
              type="button"
              className="cli-copy-btn"
              onClick={copyInstall}
              title="Copy install snippet"
            >
              {copiedSnippet ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>
          <div className="cli-terminal-screen">
            <div className="cli-term-line">
              <span className="cli-term-prompt">$</span>
              <span className="cli-term-text">python -m pip install -e ./cli</span>
            </div>
            <div className="cli-term-line">
              <span className="cli-term-prompt">$</span>
              <span className="cli-term-text">morphy /ask "Revenue trends by region"</span>
            </div>
            <div className="cli-term-feedback">
              <span className="cli-term-check">✔</span>
              <span>Federated SQL generated & executed across 3 engines</span>
            </div>
          </div>
        </div>
      </div>

      {/* Explore CLI Modal */}
      {cliModal === "explore" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setCliModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel cli-detail-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">TERMINAL WORKSPACE</div>
                <h2 className="workspace-modal-title">MORPHY CLI Features</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setCliModal(null)}
                aria-label="Close dialog"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="cli-modal-lead">
              A full-featured terminal companion powered by the exact same engine, RBAC, and DuckDB/PostgreSQL federation as the browser workspace.
            </p>

            <div className="cli-features-grid">
              <div className="cli-feature-item">
                <code>/ask &lt;query&gt;</code>
                <p>Natural language AI query generation with pre-execution safety review.</p>
              </div>
              <div className="cli-feature-item">
                <code>/sql &lt;SELECT&gt;</code>
                <p>Run governed read-only SQL queries with syntax highlighting and schema hints.</p>
              </div>
              <div className="cli-feature-item">
                <code>/dashboard</code>
                <p>Render interactive terminal dashboards directly inside your console.</p>
              </div>
              <div className="cli-feature-item">
                <code>/export &lt;file.csv&gt;</code>
                <p>Stream query results to RFC-4180 CSV or formatted JSON for shell pipelines.</p>
              </div>
            </div>

            <div className="cli-modal-code-block">
              <div className="cli-code-header">One-Shot Scripting & Automation</div>
              <pre className="cli-code-pre">
{`# Run non-interactive queries directly in scripts
morphy --sql "SELECT * FROM orders LIMIT 5" --json

# Both 'morphy' and 'sq' aliases supported
sq --database db-1 --sql "SELECT count(*) FROM analytics" --csv`}
              </pre>
            </div>

            <div className="workspace-modal-actions">
              <button
                type="button"
                className="workspace-btn-secondary"
                onClick={() => setCliModal("install")}
              >
                <Download className="w-4 h-4 mr-2" />
                View installation guide
              </button>
              <button
                type="button"
                className="workspace-btn-primary"
                onClick={() => setCliModal(null)}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Installation Guide Modal */}
      {cliModal === "install" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setCliModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel cli-detail-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">GETTING STARTED</div>
                <h2 className="workspace-modal-title">MORPHY CLI Installation Guide</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setCliModal(null)}
                aria-label="Close dialog"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="cli-modal-lead">
              Works seamlessly on <strong>Windows</strong>, <strong>macOS</strong>, and <strong>Linux</strong> with Python 3.11+.
            </p>

            <div className="cli-install-step">
              <span className="cli-step-num">1</span>
              <div>
                <strong>Install via pip from repository root:</strong>
                <pre className="cli-code-pre">python -m pip install -e ./cli</pre>
              </div>
            </div>

            <div className="cli-install-step">
              <span className="cli-step-num">2</span>
              <div>
                <strong>Verify installation (both console aliases):</strong>
                <pre className="cli-code-pre">morphy --help&#10;sq --help</pre>
              </div>
            </div>

            <div className="cli-install-step">
              <span className="cli-step-num">3</span>
              <div>
                <strong>Authenticate with your Morphy account:</strong>
                <pre className="cli-code-pre">morphy /login</pre>
              </div>
            </div>

            <div className="workspace-modal-actions">
              <button
                type="button"
                className="workspace-btn-secondary"
                onClick={() => setCliModal("explore")}
              >
                <Terminal className="w-4 h-4 mr-2" />
                Explore CLI
              </button>
              <button
                type="button"
                className="workspace-btn-primary"
                onClick={() => setCliModal(null)}
              >
                Close Guide
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

