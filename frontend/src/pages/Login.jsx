import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      const redirectTo = location.state?.from || "/verify";
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err.message || "Login failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-content page-content--narrow">
      <section className="panel auth-panel">
        <h1 className="auth-panel__heading">Log in</h1>
        <p className="auth-panel__subtitle">Access the verifier and your verification history.</p>

        <form onSubmit={handleSubmit}>
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
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>

          {error && <p className="auth-panel__error">{error}</p>}

          <button className="run-button" type="submit" disabled={loading}>
            {loading ? "Logging in…" : "Log in"}
          </button>
        </form>

        <p className="auth-panel__switch">
          Don&rsquo;t have an account? <Link to="/signup">Sign up</Link>
        </p>
      </section>
    </div>
  );
}
