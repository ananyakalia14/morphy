import { useId, useRef, useState } from "react";
import { Check, Copy, Download, Terminal, X } from "lucide-react";

const INSTALL = "python -m pip install morphy-cli";
const HOSTED = "morphy --url https://morphy-engine.vercel.app";
const STEPS = [
  {
    name: "Open",
    prompt: "$",
    command: HOSTED,
    detail: "Open the public sample workspace from any terminal with MORPHY installed.",
    output: "morphy (sample) >",
  },
  {
    name: "Explore",
    prompt: ">",
    command: "/examples",
    detail: "List the questions available for this sample dataset.",
    output: "• Revenue by product\n• Monthly revenue\n• Top customers\n• Recent orders",
  },
  {
    name: "Query",
    prompt: ">",
    command: "/ask Revenue by product",
    detail: "The sample shows the SQL and results. For a live database, /ask shows the draft and asks before executing it.",
    output: "SELECT product, ROUND(SUM(amount), 2) AS revenue\nFROM orders WHERE status = 'paid'\nGROUP BY product ORDER BY revenue DESC\n\nproduct    │ revenue\nAnalytics  │ 6900.0\nWorkspace  │ 3020.0\nConnectors │ 1730.0",
  },
  {
    name: "Export",
    prompt: ">",
    command: "/export revenue.csv",
    detail: "Write the last query result to a CSV in your current directory.",
    output: "Saved 3 rows to revenue.csv.",
  },
] as const;

export function CliPromoSection() {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [view, setView] = useState<"explore" | "install">("explore");
  const [step, setStep] = useState(0);
  const [copyStatus, setCopyStatus] = useState("");
  const current = STEPS[step]!;

  function open(next: typeof view) {
    setView(next);
    setStep(0);
    setCopyStatus("");
    dialog.current?.showModal();
  }

  async function copy(command: string) {
    try {
      await navigator.clipboard.writeText(command);
      setCopyStatus("Command copied.");
    } catch {
      setCopyStatus("Select the command text to copy it.");
    }
  }

  return (
    <>
      <div className="cli-promo-card">
        <div className="cli-promo-content">
          <div className="cli-promo-badge"><Terminal className="w-3.5 h-3.5" /> DEVELOPER TOOLKIT</div>
          <h2 className="cli-promo-heading">MORPHY, beyond the browser.</h2>
          <p className="cli-promo-description">Inspect schemas, review SQL, and export results from your terminal using the same MORPHY engine.</p>
          <div className="cli-promo-buttons">
            <button type="button" className="cli-cta-primary" onClick={() => open("explore")}>
              <Terminal className="w-4 h-4 mr-2" /> Explore CLI
            </button>
            <button type="button" className="cli-cta-secondary" onClick={() => open("install")}>
              <Download className="w-4 h-4 mr-2" /> View installation guide
            </button>
          </div>
        </div>
        <div className="cli-promo-terminal-box">
          <div className="cli-terminal-top">
            <div className="cli-window-dots" aria-hidden="true"><span className="window-dot red" /><span className="window-dot yellow" /><span className="window-dot green" /></div>
            <span className="cli-window-title">terminal · synthetic sample</span>
          </div>
          <div className="cli-terminal-screen">
            <div className="cli-term-line"><span className="cli-term-prompt">$</span><code className="cli-term-text">{INSTALL}</code></div>
            <div className="cli-term-line"><span className="cli-term-prompt">$</span><code className="cli-term-text">{HOSTED}</code></div>
            <div className="cli-term-line"><span className="cli-term-prompt">&gt;</span><code className="cli-term-text">/ask Revenue by product</code></div>
            <div className="cli-term-feedback"><Check size={14} aria-hidden="true" /> Three products in the sample result</div>
          </div>
        </div>
      </div>

      <dialog ref={dialog} className="workspace-modal-panel cli-walkthrough" aria-labelledby={titleId}>
        <div className="workspace-modal-header">
          <div>
            <div className="workspace-modal-eyebrow">TERMINAL WORKSPACE</div>
            <h2 id={titleId} className="workspace-modal-title">{view === "explore" ? "Run a query in the CLI" : "Install MORPHY CLI"}</h2>
          </div>
          <button type="button" className="workspace-modal-close-btn" aria-label="Close dialog" onClick={() => dialog.current?.close()} autoFocus><X size={20} /></button>
        </div>

        {view === "explore" ? (
          <>
            <p className="cli-modal-lead">Step through a recorded example using synthetic commerce data.</p>
            <div className="cli-walkthrough-steps" role="group" aria-label="CLI walkthrough steps">
              {STEPS.map(({ name }, index) => (
                <button type="button" key={name} aria-pressed={index === step} onClick={() => { setStep(index); setCopyStatus(""); }}>{index + 1}. {name}</button>
              ))}
            </div>
            <div className="cli-walkthrough-console" aria-live="polite">
              <pre><code><span aria-hidden="true">{current.prompt} </span>{current.command}</code>{"\n\n"}{current.output}</pre>
            </div>
            <p className="cli-modal-lead">{current.detail}</p>
          </>
        ) : (
          <>
            <p className="cli-modal-lead">Use Python 3.11 or later. These commands install the published package and open the sample workspace.</p>
            <div className="cli-walkthrough-console"><pre><code>{INSTALL}{"\n"}{HOSTED}</code></pre></div>
            <p className="cli-modal-lead">For an organization database, configure the CLI for your MORPHY Supabase project, then use <code>/login</code>, <code>/orgs</code>, <code>/use-org</code>, <code>/dbs</code>, and <code>/use-db</code> inside the shell. <a href="https://github.com/ananyakalia14/morphy/tree/main/cli#installation--setup">Read the CLI setup guide</a>.</p>
          </>
        )}

        <div className="workspace-modal-actions cli-walkthrough-actions">
          <button type="button" className="workspace-btn-secondary" onClick={() => void copy(view === "explore" ? current.command : INSTALL)}><Copy size={15} /> {view === "explore" ? "Copy command" : "Copy install command"}</button>
          {view === "explore" ? (
            <button type="button" className="workspace-btn-primary" onClick={() => { setView("install"); setCopyStatus(""); }}>Installation guide</button>
          ) : (
            <button type="button" className="workspace-btn-primary" onClick={() => { setView("explore"); setCopyStatus(""); }}>Explore CLI</button>
          )}
        </div>
        <p className="cli-walkthrough-status" role="status">{copyStatus}</p>
      </dialog>
    </>
  );
}
