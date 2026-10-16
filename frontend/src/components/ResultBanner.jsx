export default function ResultBanner({ violations, warnings = [] }) {
  const highCount = violations.filter((v) => v.severity === "high").length;
  const mediumCount = violations.filter((v) => v.severity === "medium").length;

  if (violations.length === 0 && warnings.length === 0) {
    return (
      <div className="banner banner--clear" role="status">
        <span className="banner__mark" aria-hidden="true" />
        <div>
          <p className="banner__title">No violations detected</p>
          <p className="banner__subtitle">
            Prescription is consistent with the retrieved protocol, with no flagged interactions or missing tests.
          </p>
        </div>
      </div>
    );
  }

  const tone = highCount > 0 ? "flag" : "warn";
  return (
    <div className={`banner banner--${tone}`} role={warnings.length > 0 ? "alert" : "status"}>
      <span className="banner__mark" aria-hidden="true" />
      <div>
        <p className="banner__title">
          {violations.length > 0
            ? `${violations.length} issue${violations.length > 1 ? "s" : ""} flagged`
            : "Verification warnings require review"}
        </p>
        <p className="banner__subtitle">
          {highCount > 0 && `${highCount} high severity`}
          {highCount > 0 && mediumCount > 0 && " \u00b7 "}
          {mediumCount > 0 && `${mediumCount} medium severity`}
          {warnings.length > 0 &&
            `${violations.length > 0 ? " · " : ""}${warnings.length} warning${warnings.length > 1 ? "s" : ""} mean this result does not confirm safety`}
          {warnings.length === 0 && highCount === 0 && mediumCount === 0 && "Review the findings below"}
        </p>
        {warnings.length > 0 && (
          <ul className="banner__warnings">
            {warnings.map((warning, index) => (
              <li key={`${warning.type}-${warning.drug || index}`}>{warning.message}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
