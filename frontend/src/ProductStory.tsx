import { useEffect, useRef, useState } from "react";

const STEPS = [
  {
    label: "Connect",
    title: "Bring your data into view.",
    text: "Start with a read-only connection or a CSV import. MORPHY shows the tables and fields your role can use.",
  },
  {
    label: "Ask",
    title: "Ask the question you came for.",
    text: "Use plain language to draft SQL. Read and edit the draft before you decide to run it.",
  },
  {
    label: "Enforce",
    title: "Apply access before the math.",
    text: "The engine applies row filters before the aggregation and limits which columns the SQL can reference. In this example, the viewer can see only APAC orders.",
  },
  {
    label: "Answer",
    title: "See what you can act on.",
    text: "The result totals paid APAC orders by product. The query workspace lets you inspect the executed SQL alongside the result.",
  },
] as const;

const REVENUE = [
  ["Analytics", "6,900", 100],
  ["Workspace", "3,020", 44],
  ["Connectors", "1,730", 25],
] as const;

function StoryPanel({ step }: { step: number }) {
  if (step === 0) {
    return (
      <div className="story-panel-inner story-schema">
        <div className="story-schema-chip"><span aria-hidden="true">▦</span><div><small>SAMPLE DATABASE</small><strong>Commerce</strong></div></div>
        <div className="story-schema-tables">
          <div><strong>orders</strong><span>product</span><span>amount</span><span>region</span><span>status</span></div>
          <div><strong>customers</strong><span>name</span><span>region</span><span>plan</span></div>
        </div>
      </div>
    );
  }
  if (step === 1) {
    return (
      <div className="story-panel-inner story-prompt">
        <small>QUESTION</small>
        <p>How much paid revenue did each product generate?</p>
        <div className="story-prompt-status"><i /> SQL DRAFT READY FOR REVIEW</div>
      </div>
    );
  }
  if (step === 2) {
    return (
      <div className="story-panel-inner story-query">
        <small>ILLUSTRATIVE REWRITE · SQLITE</small>
        <pre><code><span>SELECT</span>{" product, SUM(amount) AS revenue\n"}<span>FROM</span>{" (\n  "}<span>SELECT</span>{" product, amount, status\n  "}<span>FROM</span>{" orders\n  "}<mark>WHERE region = 'APAC'</mark>{"\n) AS permitted_orders\n"}<span>WHERE</span>{" status = 'paid'\n"}<span>GROUP BY</span>{" product\n"}<span>ORDER BY</span>{" revenue DESC;"}</code></pre>
      </div>
    );
  }
  return (
    <div className="story-panel-inner story-results">
      <small>PAID REVENUE · APAC</small>
      <table>
        <thead><tr><th scope="col">Product</th><th scope="col">Revenue</th></tr></thead>
        <tbody>{REVENUE.map(([name, amount, width]) => (
          <tr key={name}><th scope="row">{name}<span aria-hidden="true" className="story-result-bar" style={{ width: `${width}%` }} /></th><td>{amount}</td></tr>
        ))}</tbody>
      </table>
    </div>
  );
}

export function ProductStory() {
  const [active, setActive] = useState(0);
  const articles = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    let observer: IntersectionObserver | undefined;
    function observeSteps() {
      observer?.disconnect();
      const inset = Math.max(0, Math.floor(window.innerHeight / 2) - 1);
      const next = new IntersectionObserver((entries) => {
        const current = entries.find((entry) => entry.isIntersecting);
        if (current) setActive(articles.current.indexOf(current.target as HTMLElement));
      }, { rootMargin: `-${inset}px 0px` });
      articles.current.forEach((article) => { if (article) next.observe(article); });
      observer = next;
    }
    observeSteps();
    window.addEventListener("resize", observeSteps);
    return () => {
      window.removeEventListener("resize", observeSteps);
      observer?.disconnect();
    };
  }, []);

  function goToStep(index: number) {
    setActive(index);
    articles.current[index]?.scrollIntoView({ behavior: "instant", block: "center" });
  }

  return (
    <section id="workflow" className="motion-story" aria-labelledby="motion-story-title">
      <div className="motion-wrap">
        <div className="motion-section-heading">
          <p className="motion-kicker"><i /> 01 / THE QUERY FLOW</p>
          <h2 id="motion-story-title">From a question to an answer you can use.</h2>
          <p>Follow one question through the workspace, from the source to the permitted result.</p>
        </div>
        <div className="motion-story-grid">
          <div className="motion-story-console">
            <div className="story-console-header"><span><i /> QUERY WORKSPACE</span><span>SYNTHETIC DATA</span></div>
            <div key={active} className="story-console-screen"><StoryPanel step={active} /></div>
            <div className="story-controls" aria-label="Query flow steps">
              {STEPS.map(({ label }, index) => <button type="button" key={label} aria-label={`Show step ${index + 1}: ${label}`} aria-pressed={active === index} onClick={() => goToStep(index)}><span>0{index + 1}</span><b>{label}</b></button>)}
            </div>
          </div>
          <div className="motion-story-steps">
            {STEPS.map(({ label, title, text }, index) => (
              <article key={label} ref={(node) => { articles.current[index] = node; }} className={active === index ? "is-current" : undefined}>
                <span className="story-step-label">0{index + 1} / {label.toUpperCase()}</span>
                <h3>{title}</h3><p>{text}</p>
                {index === STEPS.length - 1 && <a href="#explore" className="motion-text-link">Run a sample query <span aria-hidden="true">↗</span></a>}
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
