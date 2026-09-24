const TYPE_LABEL = {
  "drug-drug interaction": "Drug \u2013 Drug",
  "drug-diagnosis contraindication": "Drug \u2013 Diagnosis",
  "missing monitoring test": "Missing Test",
};

export default function ViolationCard({ violation }) {
  return (
    <li className={`violation-card violation-card--${violation.severity}`}>
      <div className="violation-card__head">
        <span className={`severity-chip severity-chip--${violation.severity}`}>{violation.severity}</span>
        <span className="violation-card__type">{TYPE_LABEL[violation.type] || violation.type}</span>
      </div>
      <p className="violation-card__desc">{violation.description}</p>
      <p className="violation-card__rec">
        <span className="violation-card__rec-label">Recommendation</span>
        {violation.recommendation}
      </p>
      <p className="violation-card__source mono">Source: {violation.source}</p>
    </li>
  );
}
