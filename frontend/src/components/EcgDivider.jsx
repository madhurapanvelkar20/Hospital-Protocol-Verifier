/**
 * Signature element: a thin "vital line" divider, styled after a cardiac
 * monitor trace. Used between major sections so the page itself reads like
 * a chart being monitored -- echoing what the tool does to a prescription.
 */
export default function EcgDivider({ label }) {
  return (
    <div className="ecg-divider" role="separator" aria-label={label || "section divider"}>
      <svg
        className="ecg-divider__line"
        viewBox="0 0 600 32"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          d="M0,16 L210,16 L226,16 L236,3 L246,29 L256,16 L270,16 L600,16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
      {label && <span className="ecg-divider__label">{label}</span>}
    </div>
  );
}
