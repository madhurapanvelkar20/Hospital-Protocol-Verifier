import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      await signup(email, password, displayName);
      navigate("/verify", { replace: true });
    } catch (err) {
      setError(err.message || "Sign up failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-content page-content--narrow">
      <section className="panel auth-panel">
        <h1 className="auth-panel__heading">Create an account</h1>
        <p className="auth-panel__subtitle">Free — used to save your verification history.</p>

        <form onSubmit={handleSubmit}>
          <label className="field">
            <span className="field__label">Name</span>
            <input
              className="field__input"
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              autoComplete="name"
            />
          </label>
          <label className="field">
            <span className="field__label">Email</span>
            <input
              className="field__input"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </label>
          <label className="field">
            <span className="field__label">Password</span>
            <input
              className="field__input"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
          </label>

          {error && <p className="auth-panel__error">{error}</p>}

          <button className="run-button" type="submit" disabled={loading}>
            {loading ? "Creating account…" : "Sign up"}
          </button>
        </form>

        <p className="auth-panel__switch">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </section>
    </div>
  );
}
