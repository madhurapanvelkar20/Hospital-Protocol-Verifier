import { useEffect, useState } from "react";
import { fetchSamples, verifyPrescription, ocrExtractText } from "../api.js";
import { useAuth } from "../context/AuthContext.jsx";
import InputPanel from "../components/InputPanel.jsx";
import ResultBanner from "../components/ResultBanner.jsx";
import ParsedDrugsTable from "../components/ParsedDrugsTable.jsx";
import CitationList from "../components/CitationList.jsx";
import ReportPanel from "../components/ReportPanel.jsx";
import EcgDivider from "../components/EcgDivider.jsx";

export default function Verifier() {
  const { token } = useAuth();
  const [samples, setSamples] = useState([]);

  const [mode, setMode] = useState("sample");
  const [selectedLabel, setSelectedLabel] = useState("");
  const [rawText, setRawText] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [orderedTestsText, setOrderedTestsText] = useState("");

  const [ocrStatus, setOcrStatus] = useState("idle"); // idle | loading | done | error
  const [ocrError, setOcrError] = useState(null);

  const [status, setStatus] = useState("idle"); // idle | loading | done
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchSamples()
      .then((data) => {
        setSamples(data);
        if (data.length > 0) applySample(data[0]);
      })
      .catch(() => setError("Could not reach the server. Please try again shortly."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function applySample(sample) {
    setSelectedLabel(sample.label);
    setRawText(sample.raw_text);
    setDiagnosis(sample.diagnosis);
    setOrderedTestsText(sample.ordered_tests.join(", "));
  }

  function handleSelectSample(label) {
    const sample = samples.find((s) => s.label === label);
    if (sample) applySample(sample);
  }

  async function handlePhotoSelected(file) {
    setOcrStatus("loading");
    setOcrError(null);
    setRawText("");
    setDiagnosis("");
    setOrderedTestsText("");
    setResult(null);
    setStatus("idle");
    try {
      const data = await ocrExtractText(file, token);
      const { extracted_text, diagnoses, ordered_tests } = data;
      setRawText(extracted_text || "");
      // Always overwrite both fields from THIS image -- including with an empty
      // value when nothing was found -- so a previously selected sample case
      // can never leak its diagnosis/tests into a photo prescription.
      // The user reviews and edits both before verification.
      setDiagnosis((diagnoses || []).join(", "));
      setOrderedTestsText((ordered_tests || []).join(", "));
      setResult(null);
      setStatus("idle");
      setOcrStatus("done");
    } catch (err) {
      setOcrError(err.message || "Could not read this image.");
      setOcrStatus("error");
    }
  }

  async function handleRun() {
    setStatus("loading");
    setError(null);
    try {
      const orderedTests = orderedTestsText
        .split(/,(?![^()]*\))/)
        .map((t) => t.trim())
        .filter(Boolean);
      const data = await verifyPrescription({ rawText, diagnosisHint: diagnosis, orderedTests }, token);
      setResult(data);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("idle");
    }
  }

  return (
    <div className="page-content">
      <div className="hero hero--tool">
        <h1 className="hero__title">
          Check a prescription against <span className="hero__accent">hospital protocol</span>
        </h1>
        <p className="hero__subtitle">
          Enter a prescription, or upload a photo of one, and we&rsquo;ll surface interaction risks, missing
          monitoring tests, and the exact guideline behind every finding.
        </p>
      </div>

      <InputPanel
        mode={mode}
        setMode={setMode}
        samples={samples}
        selectedLabel={selectedLabel}
        onSelectSample={handleSelectSample}
        rawText={rawText}
        setRawText={setRawText}
        diagnosis={diagnosis}
        setDiagnosis={setDiagnosis}
        orderedTestsText={orderedTestsText}
        setOrderedTestsText={setOrderedTestsText}
        onRun={handleRun}
        loading={status === "loading"}
        onPhotoSelected={handlePhotoSelected}
        ocrStatus={ocrStatus}
        ocrError={ocrError}
      />

      {error && (
        <div className="banner banner--flag" role="alert">
          <span className="banner__mark" aria-hidden="true" />
          <div>
            <p className="banner__title">Something went wrong</p>
            <p className="banner__subtitle">{error}</p>
          </div>
        </div>
      )}

      {status === "done" && result && (
        <>
          <EcgDivider label="Result" />
          <ResultBanner
            violations={result.violations || []}
            parsedDrugs={result.parsed_drugs || []}
            unassessedDrugs={result.unassessed_drugs || []}
            unassessedDiagnoses={result.unassessed_diagnoses || []}
            retrievalAvailable={
              (result.retrieved_chunks || []).length > 0 && (result.retrieval_confidence || 0) >= 0.15
            }
          />

          <div className="result-grid">
            <div className="result-grid__trace">
              <ParsedDrugsTable
                drugs={result.parsed_drugs || []}
                diagnosis={result.parsed_diagnoses || result.parsed_diagnosis}
                unassessedDrugs={result.unassessed_drugs || []}
                unassessedDiagnoses={result.unassessed_diagnoses || []}
              />
              <CitationList chunks={result.retrieved_chunks || []} confidence={result.retrieval_confidence || 0} />
            </div>
            <div className="result-grid__report">
              <ReportPanel
                violations={result.violations || []}
                assessmentIncomplete={
                  !(result.parsed_drugs || []).length ||
                  (result.unassessed_drugs || []).length > 0 ||
                  (result.unassessed_diagnoses || []).length > 0 ||
                  !(result.retrieved_chunks || []).length ||
                  (result.retrieval_confidence || 0) < 0.15
                }
                hasParsedDrugs={(result.parsed_drugs || []).length > 0}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
