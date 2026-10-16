import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import EcgDivider from "../components/EcgDivider.jsx";

const FEATURES = [
  {
    title: "Guideline retrieval",
    body: "Matches a prescription against a real hospital protocol corpus, with hybrid semantic + keyword search and a live openFDA drug-label lookup layered on top.",
  },
  {
    title: "Interaction checking",
    body: "Flags drug-drug and drug-diagnosis conflicts using a structured interaction knowledge base, not model guesswork.",
  },
  {
    title: "Missing-test detection",
    body: "Checks required monitoring tests against what's already been ordered, and flags anything missing before it's overlooked.",
  },
  {
    title: "Cited explanations",
    body: "Every finding comes with the exact guideline excerpt, source, version, and confidence behind it — never a bare warning.",
  },
];

export default function Home() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="page-content">
      <section className="hero hero--home">
        <span className="hero__badge">Agentic RAG · Clinical decision support</span>
        <h1 className="hero__title">
          Check a prescription against <span className="hero__accent">hospital protocol</span> in seconds
        </h1>
        <p className="hero__subtitle">
          A five-agent pipeline that retrieves the right guideline, checks for interactions, flags missing
          monitoring tests, and explains every finding with a citation back to its source.
        </p>
        <div className="hero__cta-row">
          <Link to={isAuthenticated ? "/verify" : "/signup"} className="cta-button cta-button--primary">
            {isAuthenticated ? "Open the verifier" : "Get started free"}
          </Link>
          <Link to="/about" className="cta-button cta-button--ghost">
            How it works
          </Link>
        </div>
      </section>

      <EcgDivider label="Capabilities" />

      <section className="feature-grid">
        {FEATURES.map((f) => (
          <div className="feature-card" key={f.title}>
            <h3 className="feature-card__title">{f.title}</h3>
            <p className="feature-card__body">{f.body}</p>
          </div>
        ))}
      </section>

      <section className="disclaimer-band">
        <p>ProtocolVerify is a decision-support prototype built for academic demonstration and does not replace clinical judgment.</p>
      </section>
    </div>
  );
}
