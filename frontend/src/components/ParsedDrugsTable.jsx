export default function ParsedDrugsTable({ drugs, diagnoses }) {
  const diagnosisList = diagnoses || [];
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
              <th>Local recognition</th>
            </tr>
          </thead>
          <tbody>
            {drugs.map((d) => (
              <tr key={d.name}>
                <td>{d.name.replace(/^\w/, (c) => c.toUpperCase())}</td>
                <td className="mono">{d.dose}</td>
                <td>{d.route}</td>
                <td>{d.frequency}</td>
                <td>
                  <span
                    className={`drug-status drug-status--${d.recognition_status || "unknown"}`}
                    title={
                      d.recognition_status === "recognized"
                        ? "The name is in the local vocabulary; clinical rule coverage is not exhaustive."
                        : "No interaction or monitoring rules were evaluated for this name."
                    }
                  >
                    {d.recognition_status === "recognized" ? "Recognized" : "Unsupported"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="trace-block__empty">
          No drug name was reliably extracted. Review the prescription and warnings before relying on this result.
        </p>
      )}
      <p className="trace-block__meta">
        {diagnosisList.length > 1 ? "Diagnoses" : "Diagnosis"}:{" "}
        <strong>
          {diagnosisList.length > 0
            ? diagnosisList.map((d) => d.replace(/^\w/, (c) => c.toUpperCase())).join(", ")
            : "not detected"}
        </strong>
      </p>
    </div>
  );
}
