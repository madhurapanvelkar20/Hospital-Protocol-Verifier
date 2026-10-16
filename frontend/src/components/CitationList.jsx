export default function CitationList({ chunks, confidence }) {
  return (
    <div className="trace-block">
      <h3 className="trace-block__title">Matched guideline</h3>
      {chunks.length > 0 ? (
        <ul className="citation-list">
          {chunks.map((chunk, i) => (
            <li key={i} className="citation-card">
              <details open={i === 0}>
                <summary>
                  <span className="citation-card__title">{chunk.title}</span>
                  <span className="citation-card__meta mono">
                    {chunk.source} · v{chunk.version} · score {chunk.score?.toFixed(2)}
                  </span>
                </summary>
                <p className="citation-card__excerpt">{chunk.text}</p>
              </details>
            </li>
          ))}
        </ul>
      ) : (
        <p className="trace-block__empty">No matching protocol was found for this prescription.</p>
      )}
      {chunks.length > 0 && confidence < 0.15 && (
        <p className="trace-block__meta trace-block__meta--warn">
          This match has low confidence {"\u2014"} verify against the full guideline before relying on it.
        </p>
      )}
    </div>
  );
}
