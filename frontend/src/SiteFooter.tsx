import { useState, type FormEvent } from "react";
import {
  X,
  Terminal,
  Shield,
  FileText,
  HelpCircle,
  Mail,
  BookOpen,
  Layers,
  Check,
  Copy,
  ExternalLink,
  Download,
} from "lucide-react";

export function SiteFooter() {
  const [email, setEmail] = useState("");
  const [subscribed, setSubscribed] = useState(false);
  const [modal, setModal] = useState<string | null>(null);
  const [copiedCli, setCopiedCli] = useState(false);

  // Contact form state inside modal
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactMsg, setContactMsg] = useState("");
  const [contactSent, setContactSent] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (email.trim()) {
      setSubscribed(true);
      setEmail("");
    }
  };

  const handleContactSubmit = (e: FormEvent) => {
    e.preventDefault();
    setContactSent(true);
    setContactName("");
    setContactEmail("");
    setContactMsg("");
  };

  const navigateTo = (hash: string) => {
    if (hash === "" || hash === "#") {
      if (location.hash === "" || location.hash === "#") {
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else {
        location.hash = "";
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    } else {
      location.hash = hash;
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <>
      <footer className="luxury-footer">
        <div className="luxury-footer-brand-wrap">
          <h1 className="luxury-footer-brand">MORPHY</h1>
        </div>

        <div className="luxury-footer-grid">
          {/* Left Column: Newsletter */}
          <div className="luxury-footer-newsletter">
            <h3 className="newsletter-title">STAY IN THE MORPHY LOOP.</h3>
            <p className="newsletter-desc">
              Receive product updates, new capabilities, engineering insights and important platform announcements directly in your inbox.
            </p>
            <form className="newsletter-form" onSubmit={handleSubmit}>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email address"
                required
              />
              <button type="submit">
                {subscribed ? "JOINED" : "SUBSCRIBE"}
              </button>
            </form>
            <p className="newsletter-legal">
              By subscribing, you agree to our{" "}
              <a
                href="#privacy"
                onClick={(e) => {
                  e.preventDefault();
                  setModal("privacy");
                }}
              >
                Privacy Policy
              </a>.
            </p>
          </div>

          {/* Vertical Divider */}
          <div className="luxury-footer-divider" aria-hidden="true" />

          {/* Right Columns: Links */}
          <div className="luxury-footer-links-grid">
            {/* 1. Navigate */}
            <div className="luxury-footer-col">
              <h4>NAVIGATE</h4>
              <ul>
                <li>
                  <a
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      navigateTo("#");
                    }}
                  >
                    Home
                  </a>
                </li>
                <li>
                  <a
                    href="#workspace"
                    onClick={(e) => {
                      e.preventDefault();
                      navigateTo("#workspace");
                    }}
                  >
                    Workspace
                  </a>
                </li>
                <li>
                  <a
                    href="#explore"
                    onClick={(e) => {
                      e.preventDefault();
                      navigateTo("#explore");
                    }}
                  >
                    Query Explorer
                  </a>
                </li>
                <li>
                  <a
                    href="#dashboards"
                    onClick={(e) => {
                      e.preventDefault();
                      navigateTo("#dashboards");
                    }}
                  >
                    Dashboards
                  </a>
                </li>
                <li>
                  <a
                    href="#philosophy"
                    onClick={(e) => {
                      e.preventDefault();
                      const el = document.getElementById("philosophy");
                      if (el) {
                        el.scrollIntoView({ behavior: "smooth" });
                      } else {
                        setModal("philosophy");
                      }
                    }}
                  >
                    Our Philosophy
                  </a>
                </li>
              </ul>
            </div>

            {/* 2. Platform */}
            <div className="luxury-footer-col">
              <h4>PLATFORM</h4>
              <ul>
                <li>
                  <a
                    href="#sources"
                    onClick={(e) => {
                      e.preventDefault();
                      const el = document.getElementById("sources");
                      if (el) {
                        el.scrollIntoView({ behavior: "smooth" });
                      } else {
                        navigateTo("#sources");
                      }
                    }}
                  >
                    Data Sources
                  </a>
                </li>
                <li>
                  <a
                    href="#governance"
                    onClick={(e) => {
                      e.preventDefault();
                      navigateTo("#governance");
                    }}
                  >
                    Governance
                  </a>
                </li>
                <li>
                  <a
                    href="#workspace"
                    onClick={(e) => {
                      e.preventDefault();
                      navigateTo("#workspace");
                    }}
                  >
                    Organizations
                  </a>
                </li>
                <li>
                  <a
                    href="#security"
                    onClick={(e) => {
                      e.preventDefault();
                      setModal("security");
                    }}
                  >
                    Security
                  </a>
                </li>
                <li>
                  <a
                    href="#changelog"
                    onClick={(e) => {
                      e.preventDefault();
                      setModal("changelog");
                    }}
                  >
                    Changelog
                  </a>
                </li>
              </ul>
            </div>

            {/* 3. Developers */}
            <div className="luxury-footer-col">
              <h4>DEVELOPERS</h4>
              <ul>
                <li>
                  <a
                    href="#cli"
                    onClick={(e) => {
                      e.preventDefault();
                      setModal("cli");
                    }}
                  >
                    CLI Installation
                  </a>
                </li>
                <li>
                  <a
                    href="#docs"
                    onClick={(e) => {
                      e.preventDefault();
                      setModal("docs");
                    }}
                  >
                    Documentation
                  </a>
                </li>
                <li>
                  <a
                    href="#api"
                    onClick={(e) => {
                      e.preventDefault();
                      setModal("api");
                    }}
                  >
                    API Reference
                  </a>
                </li>
                <li>
                  <a
                    href="https://github.com"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    GitHub Repository <ExternalLink className="w-3 h-3 ml-1 inline" />
                  </a>
                </li>
                <li>
                  <a
                    href="#releases"
                    onClick={(e) => {
                      e.preventDefault();
                      setModal("changelog");
                    }}
                  >
                    Release Notes
                  </a>
                </li>
              </ul>
            </div>

            {/* 4. Support & Trust */}
            <div className="luxury-footer-col">
              <h4>SUPPORT & TRUST</h4>
              <ul>
                <li>
                  <a
                    href="#help"
                    onClick={(e) => {
                      e.preventDefault();
                      setModal("help");
                    }}
                  >
                    Help Centre
                  </a>
                </li>
                <li>
                  <a
                    href="#privacy"
                    onClick={(e) => {
                      e.preventDefault();
                      setModal("privacy");
                    }}
                  >
                    Privacy Policy
                  </a>
                </li>
                <li>
                  <a
                    href="#terms"
                    onClick={(e) => {
                      e.preventDefault();
                      setModal("terms");
                    }}
                  >
                    Terms of Service
                  </a>
                </li>
                <li>
                  <a
                    href="#security-practices"
                    onClick={(e) => {
                      e.preventDefault();
                      setModal("security");
                    }}
                  >
                    Security Practices
                  </a>
                </li>
                <li>
                  <a
                    href="#contact"
                    onClick={(e) => {
                      e.preventDefault();
                      setContactSent(false);
                      setModal("contact");
                    }}
                  >
                    Contact Us
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Footer Bottom Bar */}
        <div className="luxury-footer-bottom">
          <p className="luxury-footer-copy">© MORPHY 2026</p>
          <p className="luxury-footer-tagline">BUILT FOR INTELLIGENT DATA ACCESS.</p>
        </div>
      </footer>

      {/* =========================================================================
          INFORMATIONAL & POLICY MODALS
          ========================================================================= */}

      {/* CLI Installation Modal */}
      {modal === "cli" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel footer-modal-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">DEVELOPER TOOLKIT</div>
                <h2 className="workspace-modal-title">MORPHY CLI Installation</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setModal(null)}
                aria-label="Close modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="cli-modal-lead">
              Query, inspect, and automate your governed data directly from Windows PowerShell, macOS Terminal, or Linux.
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
                <strong>Authenticate with your Morphy workspace:</strong>
                <pre className="cli-code-pre">morphy /login</pre>
              </div>
            </div>

            <div className="workspace-modal-actions">
              <button
                type="button"
                className="workspace-btn-secondary"
                onClick={() => {
                  navigator.clipboard.writeText("python -m pip install -e ./cli");
                  setCopiedCli(true);
                  setTimeout(() => setCopiedCli(false), 2000);
                }}
              >
                {copiedCli ? <Check className="w-4 h-4 mr-2 text-emerald-600" /> : <Copy className="w-4 h-4 mr-2" />}
                {copiedCli ? "Copied Command" : "Copy Install Command"}
              </button>
              <button
                type="button"
                className="workspace-btn-primary"
                onClick={() => setModal(null)}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Documentation Modal */}
      {modal === "docs" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel footer-modal-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">PLATFORM GUIDE</div>
                <h2 className="workspace-modal-title">Morphy Documentation</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setModal(null)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="cli-modal-lead">
              Unified polyglot data access without duplicating or extracting records into centralized silos.
            </p>

            <div className="cli-features-grid">
              <div className="cli-feature-item">
                <code>Polyglot Mesh</code>
                <p>Federated queries run across DuckDB, PostgreSQL, SQLite, and Apache Arrow with automated pushdowns.</p>
              </div>
              <div className="cli-feature-item">
                <code>Governed RBAC</code>
                <p>Enforce fine-grained row- and column-level masking rules before query execution.</p>
              </div>
              <div className="cli-feature-item">
                <code>AI Query Generation</code>
                <p>Natural language translation grounded strictly on approved schemas with pre-execution safety review.</p>
              </div>
              <div className="cli-feature-item">
                <code>Live Dashboards</code>
                <p>Pin queries, visualize metrics, and share executive dashboards across your team.</p>
              </div>
            </div>

            <div className="workspace-modal-actions">
              <button
                type="button"
                className="workspace-btn-primary"
                onClick={() => setModal(null)}
              >
                Close Documentation
              </button>
            </div>
          </div>
        </div>
      )}

      {/* API Reference Modal */}
      {modal === "api" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel footer-modal-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">DEVELOPER APIS</div>
                <h2 className="workspace-modal-title">Engine & Control Plane API</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setModal(null)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="cli-modal-lead">
              Direct HTTP & RPC endpoints for script integration and engine control.
            </p>

            <div className="cli-modal-code-block">
              <div className="cli-code-header">Core Endpoints</div>
              <pre className="cli-code-pre">
{`# Schema Introspection
GET /api/sample/schema
Accept: application/json

# Federated Query Execution (Read-Only)
POST /rpc/query
Headers: Authorization: Bearer <TOKEN>
Body: { "database": "<DB_UUID>", "sql": "SELECT * FROM orders LIMIT 5" }

# Workspace Provisioning
POST /rpc/create_workspace
Body: { "title": "Analytics Lab" }`}
              </pre>
            </div>

            <div className="workspace-modal-actions">
              <button
                type="button"
                className="workspace-btn-primary"
                onClick={() => setModal(null)}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Changelog & Releases Modal */}
      {modal === "changelog" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel footer-modal-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">PLATFORM UPDATES</div>
                <h2 className="workspace-modal-title">Changelog & Release Notes</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setModal(null)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 my-2">
              <div className="border border-gray-200 rounded-lg p-3.5 bg-slate-50">
                <div className="flex items-center justify-between mb-1">
                  <strong className="text-slate-900 font-mono text-xs">v0.2.0 — Edge-to-Edge Workspace</strong>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">LATEST</span>
                </div>
                <p className="text-xs text-slate-600 font-mono m-0">
                  Full-screen workspace redesign, collapsible vertical rail navigation, embedded profile editor, Tunnelmole remote access, and terminal CLI promotions.
                </p>
              </div>

              <div className="border border-gray-200 rounded-lg p-3.5 bg-white">
                <div className="flex items-center justify-between mb-1">
                  <strong className="text-slate-900 font-mono text-xs">v0.1.8 — Integrated Terminal CLI</strong>
                  <span className="text-[10px] font-mono text-slate-400">OCT 2026</span>
                </div>
                <p className="text-xs text-slate-600 font-mono m-0">
                  Interactive Python CLI with prompt-toolkit syntax completion, OS keyring credential storage, and natural language /ask.
                </p>
              </div>

              <div className="border border-gray-200 rounded-lg p-3.5 bg-white">
                <div className="flex items-center justify-between mb-1">
                  <strong className="text-slate-900 font-mono text-xs">v0.1.5 — Polyglot Federation Mesh</strong>
                  <span className="text-[10px] font-mono text-slate-400">SEP 2026</span>
                </div>
                <p className="text-xs text-slate-600 font-mono m-0">
                  Cross-database query routing across DuckDB, PostgreSQL, SQLite with Apache Arrow zero-copy memory transport.
                </p>
              </div>
            </div>

            <div className="workspace-modal-actions">
              <button
                type="button"
                className="workspace-btn-primary"
                onClick={() => setModal(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Help Centre Modal */}
      {modal === "help" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel footer-modal-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">SUPPORT & FAQ</div>
                <h2 className="workspace-modal-title">Morphy Help Centre</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setModal(null)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 my-2 font-mono text-xs">
              <div className="border border-gray-200 rounded-lg p-3">
                <strong className="block text-slate-900 mb-1">How do I connect external databases?</strong>
                <p className="text-slate-600 m-0">Navigate to your Workspace &gt; Query Engine or use the terminal CLI with <code>morphy /connect &lt;URI&gt;</code>.</p>
              </div>
              <div className="border border-gray-200 rounded-lg p-3">
                <strong className="block text-slate-900 mb-1">Can users alter or delete underlying data?</strong>
                <p className="text-slate-600 m-0">No. Morphy enforces strict read-only execution at the parser level. Mutation commands are rejected automatically.</p>
              </div>
              <div className="border border-gray-200 rounded-lg p-3">
                <strong className="block text-slate-900 mb-1">How are invitations accepted?</strong>
                <p className="text-slate-600 m-0">Invitations appear directly at the top of your Account bar or via <code>morphy /accept &lt;id&gt;</code> in the CLI.</p>
              </div>
            </div>

            <div className="workspace-modal-actions">
              <button
                type="button"
                className="workspace-btn-secondary"
                onClick={() => setModal("contact")}
              >
                Contact Support
              </button>
              <button
                type="button"
                className="workspace-btn-primary"
                onClick={() => setModal(null)}
              >
                Close Help
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Privacy Policy Modal */}
      {modal === "privacy" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel footer-modal-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">DATA PROTECTION</div>
                <h2 className="workspace-modal-title">Privacy Policy</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setModal(null)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 my-2 font-mono text-xs text-slate-600 leading-relaxed">
              <p>
                <strong>1. Zero Data Ingestion:</strong> Morphy acts as a federated query layer. We do not copy, replicate, or store your database records on foreign servers.
              </p>
              <p>
                <strong>2. Credential Security:</strong> Database connection strings, passwords, and tokens are encrypted with AES-256 and never logged in client telemetry.
              </p>
              <p>
                <strong>3. Query Telemetry:</strong> Only query metadata (execution duration, row counts, timestamp, actor ID) is recorded in immutable audit events.
              </p>
              <p>
                <strong>4. Account Rights:</strong> You can edit your display name, remove avatars, or delete your account at any time through the workspace settings.
              </p>
            </div>

            <div className="workspace-modal-actions">
              <button
                type="button"
                className="workspace-btn-primary"
                onClick={() => setModal(null)}
              >
                Understood
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Terms of Service Modal */}
      {modal === "terms" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel footer-modal-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">LEGAL AGREEMENT</div>
                <h2 className="workspace-modal-title">Terms of Service</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setModal(null)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 my-2 font-mono text-xs text-slate-600 leading-relaxed">
              <p>
                <strong>1. Permitted Use:</strong> Morphy is provided for internal enterprise and developer analytics, federated querying, and governed data exploration.
              </p>
              <p>
                <strong>2. Read-Only Safety:</strong> Users agree not to attempt security circumventions or SQL injection against the polyglot parser.
              </p>
              <p>
                <strong>3. RBAC Compliance:</strong> Access to specific database tables and columns is governed by organization administrators through explicit role policies.
              </p>
            </div>

            <div className="workspace-modal-actions">
              <button
                type="button"
                className="workspace-btn-primary"
                onClick={() => setModal(null)}
              >
                Accept Terms
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Security Practices Modal */}
      {modal === "security" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel footer-modal-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">SECURITY & TRUST</div>
                <h2 className="workspace-modal-title">Security Practices</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setModal(null)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 my-2 font-mono text-xs text-slate-600 leading-relaxed">
              <div className="border border-gray-200 rounded-lg p-3">
                <strong className="block text-slate-900 mb-1">🔒 Transport & At-Rest Encryption</strong>
                <p className="m-0">TLS 1.3 enforced across all web, CLI, and engine connections. Stored configuration encrypted with AES-256-GCM.</p>
              </div>
              <div className="border border-gray-200 rounded-lg p-3">
                <strong className="block text-slate-900 mb-1">🛡️ Governed Row & Column RBAC</strong>
                <p className="m-0">Fine-grained filters applied at the logical plan level before query execution. Unauthorized columns are never streamed to client.</p>
              </div>
              <div className="border border-gray-200 rounded-lg p-3">
                <strong className="block text-slate-900 mb-1">📜 Immutable Audit Logging</strong>
                <p className="m-0">Every policy update, database connection, and query event is persisted into an immutable audit event log.</p>
              </div>
            </div>

            <div className="workspace-modal-actions">
              <button
                type="button"
                className="workspace-btn-primary"
                onClick={() => setModal(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Contact Us Modal */}
      {modal === "contact" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel footer-modal-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">DIRECT CONTACT</div>
                <h2 className="workspace-modal-title">Contact Morphy Team</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setModal(null)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {contactSent ? (
              <div className="text-center py-6 font-mono">
                <Check className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                <h3 className="text-sm font-bold text-slate-900 mb-1">Message Received!</h3>
                <p className="text-xs text-slate-600 mb-4">Our team will get back to you shortly.</p>
                <button
                  type="button"
                  className="workspace-btn-primary"
                  onClick={() => setModal(null)}
                >
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={handleContactSubmit} className="space-y-3 my-2 font-mono text-xs">
                <div>
                  <label className="block text-slate-700 font-bold mb-1">Name</label>
                  <input
                    type="text"
                    required
                    value={contactName}
                    onChange={(e) => setContactName(e.target.value)}
                    placeholder="Your name"
                    className="login-input"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-bold mb-1">Email</label>
                  <input
                    type="email"
                    required
                    value={contactEmail}
                    onChange={(e) => setContactEmail(e.target.value)}
                    placeholder="you@domain.com"
                    className="login-input"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-bold mb-1">Message</label>
                  <textarea
                    required
                    rows={3}
                    value={contactMsg}
                    onChange={(e) => setContactMsg(e.target.value)}
                    placeholder="How can we assist your data workspace?"
                    className="login-input"
                    style={{ height: "auto", padding: "10px" }}
                  />
                </div>
                <div className="pt-2 flex justify-end gap-2">
                  <button
                    type="button"
                    className="workspace-btn-secondary"
                    onClick={() => setModal(null)}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="workspace-btn-primary">
                    Send Message ↗
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Our Philosophy Modal */}
      {modal === "philosophy" && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setModal(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="workspace-modal-panel footer-modal-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">OUR MANIFESTO</div>
                <h2 className="workspace-modal-title">Our Philosophy</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setModal(null)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 my-2 font-mono text-xs text-slate-600 leading-relaxed">
              <p className="text-sm font-bold text-slate-900">
                “Data takes shape. Governed access without proprietary lock-in.”
              </p>
              <p>
                We believe data should remain in its optimal storage engine — PostgreSQL for transactions, DuckDB for analytical column scans, SQLite for local speed — while your team enjoys a unified, collaborative query interface.
              </p>
              <p>
                Morphy unites governance, AI query synthesis, and interactive visualization without forcing you to move a single petabyte.
              </p>
            </div>

            <div className="workspace-modal-actions">
              <button
                type="button"
                className="workspace-btn-primary"
                onClick={() => setModal(null)}
              >
                Close Manifesto
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
