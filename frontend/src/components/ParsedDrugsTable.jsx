export default function ParsedDrugsTable({ drugs, diagnosis }) {
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
            {drugs.map((d) => (
              <tr key={d.name}>
                <td>{d.name.replace(/^\w/, (c) => c.toUpperCase())}</td>
                <td className="mono">{d.dose}</td>
                <td>{d.route}</td>
                <td>{d.frequency}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="trace-block__empty">No known drugs were detected in the prescription text.</p>
      )}
      <p className="trace-block__meta">
        Diagnosis: <strong>{diagnosis || "not detected"}</strong>
      </p>
    </div>
  );
}
