import ViolationCard from "./ViolationCard.jsx";

const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 };

export default function ReportPanel({ violations }) {
  const sorted = [...violations].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3)
  );

  return (
    <div className="report-panel">
      <h3 className="trace-block__title">Findings</h3>
      {sorted.length > 0 ? (
        <ul className="violation-list">
          {sorted.map((v, i) => (
            <ViolationCard violation={v} key={i} />
          ))}
        </ul>
      ) : (
        <p className="trace-block__empty">
          No interaction or monitoring issues were found for this prescription.
        </p>
      )}
    </div>
  );
}
