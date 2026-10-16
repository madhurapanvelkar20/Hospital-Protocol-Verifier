import EcgDivider from "../components/EcgDivider.jsx";

const CAPABILITIES = [
  {
    name: "Checks against real hospital guidelines",
    body: "Every prescription is matched against actual treatment protocols — dosing, indications, and monitoring requirements — not a generic drug database.",
  },
  {
    name: "Catches dangerous combinations",
    body: "Flags drug-drug and drug-diagnosis conflicts before they become a problem, using established clinical interaction data rather than guesswork.",
  },
  {
    name: "Flags missing monitoring tests",
    body: "If a medication requires a baseline or follow-up test that hasn't been ordered yet, it's caught here — before it's overlooked.",
  },
  {
    name: "Every result is explained and sourced",
    body: "No black-box warnings. Each finding shows the exact guideline it came from, how confident the match is, and what to do about it.",
  },
  {
    name: "Works from a photo",
    body: "Don't want to type it out? Upload a photo of the prescription and the text is extracted automatically — you review and confirm it before anything is checked.",
  },
  {
    name: "Keeps a history",
    body: "Every check you run is saved to your account, so you can look back at what was flagged and when.",
  },
];

const DATA_SOURCES = [
  { label: "Hospital treatment guidelines", value: "Curated protocols across cardiology, endocrinology, rheumatology, and more" },
  { label: "Live drug labeling data", value: "Real-time lookups from the FDA's official drug label database" },
  { label: "Drug interaction records", value: "Pharmacist-curated interaction data covering severity and clinical management" },
  { label: "Your account", value: "Secured sign-in with encrypted passwords and a private verification history" },
];

export default function About() {
  return (
    <div className="page-content">
      <section className="hero hero--about">
        <span className="hero__badge">About ProtocolVerify</span>
        <h1 className="hero__title">A second check, before a prescription goes out</h1>
        <p className="hero__subtitle">
          Hospitals maintain thousands of frequently-updated treatment protocols that clinicians can't realistically
          cross-check by hand under time pressure. ProtocolVerify does that check automatically — matching a
          prescription against the relevant guideline, catching interaction risks and missing tests, and showing
          exactly why each finding matters.
        </p>
      </section>

      <EcgDivider label="What it does" />

      <section className="agent-list">
        {CAPABILITIES.map((c) => (
          <div className="agent-row" key={c.name}>
            <span className="agent-row__check" aria-hidden="true">
              ✓
            </span>
            <div>
              <h3 className="agent-row__name">{c.name}</h3>
              <p className="agent-row__body">{c.body}</p>
            </div>
          </div>
        ))}
      </section>

      <EcgDivider label="Where the information comes from" />

      <section className="stack-grid">
        {DATA_SOURCES.map((s) => (
          <div className="stack-item" key={s.label}>
            <span className="stack-item__label">{s.label}</span>
            <span className="stack-item__value">{s.value}</span>
          </div>
        ))}
      </section>

      <section className="about-note">
        <h3>A note on scope</h3>
        <p>
          This is an academic project built for demonstration. Its guideline and drug coverage is curated rather
          than exhaustive, and it&rsquo;s designed to support a clinician&rsquo;s judgment, not replace it — results
          should never be used for an actual clinical decision.
        </p>
      </section>
    </div>
  );
}
