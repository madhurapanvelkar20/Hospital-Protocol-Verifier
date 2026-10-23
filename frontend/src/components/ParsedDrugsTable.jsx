export default function ParsedDrugsTable({ drugs, diagnosis, unassessedDrugs = [], unassessedDiagnoses = [] }) {
  const diagnosisText = Array.isArray(diagnosis) ? diagnosis.join(", ") : diagnosis;

  return (
    <div className="trace-block">
      <h3 className="trace-block__title">Prescription details</h3>
      {drugs.length > 0 ? (
        <table className="drugs-table">
          <thead>
            <tr>
              <th>Drug</th>
              <th>Dose</th>
              <th>Route</th>
              <th>Frequency</th>
            </tr>
          </thead>
          <tbody>
            {drugs.map((d, i) => (
              <tr key={`${d.name}-${i}`}>
                <td>
                  {d.name.replace(/^\w/, (c) => c.toUpperCase())}
                  {(d.recognized === false || unassessedDrugs.includes(d.name)) && (
                    <span
                      className="trace-block__meta"
                      title="This medicine was read from the prescription, but the configured rules do not assess it."
                    >
                      {" "}(not assessed)
                    </span>
                  )}
                </td>
                <td className="mono">{d.dose}</td>
                <td>{d.route}</td>
                <td>{d.frequency}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="trace-block__empty">
          No medicines could be extracted. Correct the prescription text before relying on any result.
        </p>
      )}
      <p className="trace-block__meta">
        Diagnosis: <strong>{diagnosisText || "not detected"}</strong>
        {unassessedDiagnoses.length > 0 && (
          <>{" "}(not assessed: {unassessedDiagnoses.join(", ")})</>
        )}
      </p>
    </div>
  );
}
