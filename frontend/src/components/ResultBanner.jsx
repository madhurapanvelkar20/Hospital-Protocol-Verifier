export default function ResultBanner({
  violations,
  parsedDrugs = [],
  unassessedDrugs = [],
  unassessedDiagnoses = [],
  retrievalAvailable = false,
}) {
  const highCount = violations.filter((v) => v.severity === "high").length;
  const mediumCount = violations.filter((v) => v.severity === "medium").length;
  const notAssessedDrugs = [
    ...new Set([
      ...unassessedDrugs,
      ...parsedDrugs.filter((drug) => drug.recognized === false).map((drug) => drug.name),
    ]),
  ];
  const assessmentIncomplete =
    parsedDrugs.length === 0 ||
    notAssessedDrugs.length > 0 ||
    unassessedDiagnoses.length > 0 ||
    !retrievalAvailable;

  if (violations.length === 0) {
    return (
      <div className={`banner banner--${assessmentIncomplete ? "warn" : "clear"}`} role="status">
        <span className="banner__mark" aria-hidden="true" />
        <div>
          <p className="banner__title">
            {parsedDrugs.length === 0
              ? "Assessment incomplete"
              : assessmentIncomplete
                ? "No configured violations detected — assessment incomplete"
                : "No configured violations detected"}
          </p>
          <p className="banner__subtitle">
            {parsedDrugs.length === 0
              ? "No medicines were extracted. Correct the prescription text before relying on a result."
              : assessmentIncomplete
                ? `${retrievalAvailable ? "" : "No relevant protocol guideline was retrieved. "}` +
                  `Only configured rules were evaluated. Not assessed: ${[
                    ...notAssessedDrugs,
                    ...unassessedDiagnoses,
                  ].join(", ") || "guideline coverage"}. This is not proof that the prescription is safe.`
                : "Only configured interaction and monitoring rules were evaluated. This is not proof that the prescription is safe."}
          </p>
        </div>
      </div>
    );
  }

  const tone = highCount > 0 ? "flag" : "warn";
  return (
    <div className={`banner banner--${tone}`} role="status">
      <span className="banner__mark" aria-hidden="true" />
      <div>
        <p className="banner__title">
          {violations.length} issue{violations.length > 1 ? "s" : ""} flagged
        </p>
        <p className="banner__subtitle">
          {highCount > 0 && `${highCount} high severity`}
          {highCount > 0 && mediumCount > 0 && " \u00b7 "}
          {mediumCount > 0 && `${mediumCount} medium severity`}
          {highCount === 0 && mediumCount === 0 && "Review the findings below"}
          {assessmentIncomplete && " \u00b7 assessment incomplete for some items"}
        </p>
      </div>
    </div>
  );
}
