export default function InputPanel({
  mode,
  setMode,
  samples,
  selectedLabel,
  onSelectSample,
  rawText,
  setRawText,
  diagnosis,
  setDiagnosis,
  orderedTestsText,
  setOrderedTestsText,
  onRun,
  loading,
}) {
  return (
    <section className="panel input-panel" aria-labelledby="input-panel-heading">
      <div className="input-panel__mode" role="tablist" aria-label="Input mode">
        <button
          role="tab"
          aria-selected={mode === "sample"}
          className={`mode-toggle ${mode === "sample" ? "mode-toggle--active" : ""}`}
          onClick={() => setMode("sample")}
          type="button"
        >
          Sample case
        </button>
        <button
          role="tab"
          aria-selected={mode === "custom"}
          className={`mode-toggle ${mode === "custom" ? "mode-toggle--active" : ""}`}
          onClick={() => setMode("custom")}
          type="button"
        >
          Write my own
        </button>
      </div>

      <h2 id="input-panel-heading" className="input-panel__heading">
        {mode === "sample" ? "Choose a prescription to verify" : "Enter a prescription"}
      </h2>

      {mode === "sample" && (
        <label className="field">
          <span className="field__label">Sample case</span>
          <select
            className="field__select"
            value={selectedLabel}
            onChange={(e) => onSelectSample(e.target.value)}
          >
            {samples.map((s) => (
              <option key={s.label} value={s.label}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      )}

      <label className="field">
        <span className="field__label">Prescription text</span>
        <textarea
          className="field__textarea"
          rows={3}
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          placeholder="e.g. Prescribe Metformin 500mg oral twice daily for type 2 diabetes."
        />
      </label>

      <div className="field-row">
        <label className="field">
          <span className="field__label">Diagnosis</span>
          <input
            className="field__input"
            type="text"
            value={diagnosis}
            onChange={(e) => setDiagnosis(e.target.value)}
            placeholder="e.g. type 2 diabetes"
          />
        </label>
        <label className="field">
          <span className="field__label">Tests already ordered</span>
          <input
            className="field__input"
            type="text"
            value={orderedTestsText}
            onChange={(e) => setOrderedTestsText(e.target.value)}
            placeholder="comma-separated, e.g. eGFR, INR"
          />
        </label>
      </div>

      <button className="run-button" onClick={onRun} disabled={loading || !rawText.trim()} type="button">
        {loading ? "Running pipeline\u2026" : "Run verification"}
      </button>
    </section>
  );
}
