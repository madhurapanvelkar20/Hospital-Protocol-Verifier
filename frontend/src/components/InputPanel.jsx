import { useRef } from "react";

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
  onPhotoSelected,
  ocrStatus, // "idle" | "loading" | "done" | "error"
  ocrError,
}) {
  const fileInputRef = useRef(null);

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (file) onPhotoSelected(file);
    e.target.value = ""; // allow re-selecting the same file later
  }

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
        <button
          role="tab"
          aria-selected={mode === "photo"}
          className={`mode-toggle ${mode === "photo" ? "mode-toggle--active" : ""}`}
          onClick={() => setMode("photo")}
          type="button"
        >
          Upload photo
        </button>
      </div>

      <h2 id="input-panel-heading" className="input-panel__heading">
        {mode === "sample" && "Choose a prescription to verify"}
        {mode === "custom" && "Enter a prescription"}
        {mode === "photo" && "Upload a prescription photo"}
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

      {mode === "photo" && (
        <div className="photo-upload">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg"
            onChange={handleFileChange}
            className="photo-upload__input"
            id="prescription-photo"
          />
          <label htmlFor="prescription-photo" className="photo-upload__button">
            {ocrStatus === "loading" ? "Reading photo…" : "Choose a photo"}
          </label>
          <p className="photo-upload__hint">PNG or JPEG, up to 8MB. The extracted text appears below for you to review before verifying.</p>
          {ocrStatus === "error" && <p className="auth-panel__error">{ocrError}</p>}
          {ocrStatus === "done" && <p className="photo-upload__success">Text extracted — diagnosis and tests were auto-filled where found. Review everything below before running verification.</p>}
        </div>
      )}

      <label className="field">
        <span className="field__label">
          {mode === "photo" ? "Extracted prescription text (review and edit if needed)" : "Prescription text"}
        </span>
        <textarea
          className="field__textarea"
          rows={mode === "photo" ? 5 : 3}
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          placeholder="e.g. Prescribe Metformin 500mg oral twice daily for type 2 diabetes."
        />
      </label>

      <div className="field-row">
        <label className="field">
          <span className="field__label">Diagnosis (comma-separated if more than one)</span>
          <input
            className="field__input"
            type="text"
            value={diagnosis}
            onChange={(e) => setDiagnosis(e.target.value)}
            placeholder="e.g. hypertension, type 2 diabetes"
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
