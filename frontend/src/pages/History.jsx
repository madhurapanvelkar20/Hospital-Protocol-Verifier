import { useEffect, useState } from "react";
import { fetchHistory } from "../api.js";
import { useAuth } from "../context/AuthContext.jsx";
import ResultBanner from "../components/ResultBanner.jsx";
import ConfidenceIndicator from "../components/ConfidenceIndicator.jsx";
import ParsedDrugsTable from "../components/ParsedDrugsTable.jsx";
import CitationList from "../components/CitationList.jsx";
import ReportPanel from "../components/ReportPanel.jsx";

const SEVERITY_LABEL = { high: "High severity", medium: "Medium severity", low: "Low severity" };

function HistoryEntry({ entry }) {
  const [expanded, setExpanded] = useState(false);
  const date = new Date(entry.created_at).toLocaleString();

  return (
    <div className="history-entry">
      <button
        className="history-entry__summary"
        onClick={() => setExpanded((v) => !v)}
        type="button"
        aria-expanded={expanded}
      >
        <div className="history-entry__summary-left">
          <span className={`history-dot history-dot--${entry.highest_severity || "clear"}`} aria-hidden="true" />
          <div>
            <p className="history-entry__text">{entry.raw_text}</p>
            <p className="history-entry__meta">
              {date}
              {entry.diagnosis_hint ? ` · ${entry.diagnosis_hint}` : ""}
            </p>
          </div>
        </div>
        <span className="history-entry__badge">
          {entry.violation_count === 0
            ? "No issues"
            : `${entry.violation_count} issue${entry.violation_count > 1 ? "s" : ""}${
                entry.highest_severity ? ` · ${SEVERITY_LABEL[entry.highest_severity]}` : ""
              }`}
        </span>
      </button>

      {expanded && (
        <div className="history-entry__detail">
          <ResultBanner
            violations={entry.result.violations || []}
            warnings={entry.result.warnings || []}
          />
          <ConfidenceIndicator
            confidence={entry.result.retrieval_confidence || 0}
            attempts={entry.result.retrieval_attempts || 1}
            chunkCount={(entry.result.retrieved_chunks || []).length}
          />
          <div className="result-grid">
            <div className="result-grid__trace">
              <ParsedDrugsTable drugs={entry.result.parsed_drugs || []} diagnoses={entry.result.parsed_diagnoses} />
              <CitationList
                chunks={entry.result.retrieved_chunks || []}
                confidence={entry.result.retrieval_confidence || 0}
              />
            </div>
            <div className="result-grid__report">
              <ReportPanel violations={entry.result.violations || []} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function History() {
  const { token } = useAuth();
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchHistory(token)
      .then(setEntries)
      .catch((err) => setError(err.message));
  }, [token]);

  return (
    <div className="page-content">
      <div className="hero hero--tool">
        <h1 className="hero__title">Verification history</h1>
        <p className="hero__subtitle">Your past prescription checks, most recent first.</p>
      </div>

      {error && (
        <div className="banner banner--flag" role="alert">
          <span className="banner__mark" aria-hidden="true" />
          <div>
            <p className="banner__title">Couldn&rsquo;t load history</p>
            <p className="banner__subtitle">{error}</p>
          </div>
        </div>
      )}

      {entries === null && !error && <p className="trace-block__empty">Loading…</p>}

      {entries && entries.length === 0 && (
        <div className="panel history-empty">
          <p>No verifications yet — run one from the Verifier page and it&rsquo;ll show up here.</p>
        </div>
      )}

      {entries && entries.length > 0 && (
        <div className="history-list">
          {entries.map((entry) => (
            <HistoryEntry entry={entry} key={entry.id} />
          ))}
        </div>
      )}
    </div>
  );
}
