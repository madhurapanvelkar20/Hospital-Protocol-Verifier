import ViolationCard from "./ViolationCard.jsx";

const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 };

export default function ReportPanel({ violations, assessmentIncomplete = false, hasParsedDrugs = true }) {
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
          {hasParsedDrugs
            ? assessmentIncomplete
              ? "No configured findings were produced for assessed items. Some items were not assessed."
              : "No configured interaction or monitoring findings were produced. This does not establish safety."
            : "No medications were identified, so medication checks were not performed."}
        </p>
      )}
    </div>
  );
}
