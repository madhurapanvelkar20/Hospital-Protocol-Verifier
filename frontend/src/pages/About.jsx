import EcgDivider from "../components/EcgDivider.jsx";

const AGENTS = [
  { name: "Prescription Parser Agent", body: "Extracts drug, dose, route, frequency, and diagnosis from the prescription text (regex-based by default, with an LLM-based mode available)." },
  { name: "Retriever Agent", body: "Matches the prescription against the guideline corpus using hybrid dense (bge-large) + BM25 keyword retrieval, re-querying once if confidence is low, and optionally merges in a live openFDA drug-label citation." },
  { name: "Cross-Check Agent", body: "Checks the parsed drug(s) against a structured drug-drug and drug-diagnosis interaction knowledge base." },
  { name: "Missing-Test Detector Agent", body: "Compares prescribed drugs against a monitoring-requirement table and flags any required test not yet ordered." },
  { name: "Violation & Explanation Agent", body: "Combines every finding into a clinician-readable report, citing the exact guideline excerpt, source, version, and confidence behind each one." },
];

const STACK = [
  { label: "Orchestration", value: "LangGraph (multi-agent state graph)" },
  { label: "Retrieval", value: "bge-large embeddings + BM25, via ChromaDB" },
  { label: "Live data", value: "openFDA drug labels; PubMed literature (supporting evidence)" },
  { label: "Knowledge base", value: "Structured interaction & monitoring data (JSON)" },
  { label: "Backend", value: "FastAPI, SQLite (auth + verification history)" },
  { label: "Frontend", value: "React (Vite)" },
];

export default function About() {
  return (
    <div className="page-content">
      <section className="hero hero--about">
        <span className="hero__badge">About the project</span>
        <h1 className="hero__title">An agentic RAG system for prescription compliance</h1>
        <p className="hero__subtitle">
          Hospitals maintain thousands of frequently-updated treatment protocols that clinicians can't
          realistically cross-check by hand under time pressure. ProtocolVerify automates that check — retrieving
          the relevant guideline, verifying the prescription against it, and explaining every flagged issue with a
          traceable citation.
        </p>
      </section>

      <EcgDivider label="The five agents" />

      <section className="agent-list">
        {AGENTS.map((a, i) => (
          <div className="agent-row" key={a.name}>
            <span className="agent-row__index">{i + 1}</span>
            <div>
              <h3 className="agent-row__name">{a.name}</h3>
              <p className="agent-row__body">{a.body}</p>
            </div>
          </div>
        ))}
      </section>

      <EcgDivider label="Tech stack" />

      <section className="stack-grid">
        {STACK.map((s) => (
          <div className="stack-item" key={s.label}>
            <span className="stack-item__label">{s.label}</span>
            <span className="stack-item__value">{s.value}</span>
          </div>
        ))}
      </section>

      <section className="about-note">
        <h3>A note on scope</h3>
        <p>
          This is an academic prototype. The guideline corpus, interaction rules, and monitoring requirements are
          curated for demonstration rather than sourced from a live clinical system, and results should never be
          used for an actual clinical decision.
        </p>
      </section>
    </div>
  );
}
