/**
 * Surfaces retrieval confidence prominently, rather than leaving it
 * buried inside an expandable citation card. Alert fatigue -- clinicians
 * ignoring/disabling CDS tools because every flag looks equally certain
 * -- is a documented failure mode in the literature this project is
 * built on; showing how sure the system is, up front, is a direct
 * response to that.
 */
export default function ConfidenceIndicator({ confidence, attempts, chunkCount }) {
  if (chunkCount === 0) {
    return (
      <div className="confidence-indicator confidence-indicator--none">
        <span className="confidence-indicator__dot" aria-hidden="true" />
        <span>No matching guideline found — findings below are not backed by a citation.</span>
      </div>
    );
  }

  let tier = "low";
  let label = "Low confidence";
  let hint = "Verify against the full guideline before relying on this.";
  if (confidence >= 0.5) {
    tier = "high";
    label = "High confidence match";
    hint = "Strong match to the retrieved guideline.";
  } else if (confidence >= 0.2) {
    tier = "medium";
    label = "Moderate confidence match";
    hint = "Reasonable match — worth a quick sanity check.";
  }

  return (
    <div className={`confidence-indicator confidence-indicator--${tier}`}>
      <span className="confidence-indicator__dot" aria-hidden="true" />
      <div>
        <span className="confidence-indicator__label">{label}</span>
        <span className="confidence-indicator__hint">{hint}</span>
      </div>
      {attempts > 1 && <span className="confidence-indicator__badge">query reformulated once</span>}
    </div>
  );
}
