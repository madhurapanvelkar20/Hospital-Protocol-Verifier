const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

async function request(path, options = {}, token = null) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* non-JSON error body, keep statusText */
    }
    const error = new Error(detail);
    error.status = res.status;
    throw error;
  }
  if (res.status === 204) return null;
  return res.json();
}

// ---- public ----
export function fetchSamples() {
  return request("/samples");
}

export function fetchMeta() {
  return request("/meta");
}

export function fetchHealth() {
  return request("/health");
}

// ---- auth ----
export function signup({ email, password, displayName }) {
  return request("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
}

export function login({ email, password }) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function fetchMe(token) {
  return request("/auth/me", {}, token);
}

// ---- protected ----
export function verifyPrescription({ rawText, diagnosisHint, orderedTests }, token) {
  return request(
    "/verify",
    {
      method: "POST",
      body: JSON.stringify({
        raw_text: rawText,
        diagnosis_hint: diagnosisHint || null,
        ordered_tests: orderedTests,
      }),
    },
    token
  );
}

export function fetchHistory(token) {
  return request("/history", {}, token);
}
