import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Navbar() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/");
  }

  return (
    <header className="navbar">
      <div className="navbar__inner">
        <Link to="/" className="navbar__brand">
          <span className="navbar__mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
              <path
                d="M3 12h4l2-7 4 14 2-7h6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span className="navbar__name">ProtocolVerify</span>
        </Link>

        <nav className="navbar__links" aria-label="Main navigation">
          <NavLink to="/" end className={({ isActive }) => `navbar__link ${isActive ? "navbar__link--active" : ""}`}>
            Home
          </NavLink>
          <NavLink to="/about" className={({ isActive }) => `navbar__link ${isActive ? "navbar__link--active" : ""}`}>
            About
          </NavLink>
          {isAuthenticated && (
            <>
              <NavLink to="/verify" className={({ isActive }) => `navbar__link ${isActive ? "navbar__link--active" : ""}`}>
                Verifier
              </NavLink>
              <NavLink to="/history" className={({ isActive }) => `navbar__link ${isActive ? "navbar__link--active" : ""}`}>
                History
              </NavLink>
            </>
          )}
        </nav>

        <div className="navbar__auth">
          {isAuthenticated ? (
            <>
              <span className="navbar__user">{user?.display_name}</span>
              <button className="navbar__logout" onClick={handleLogout} type="button">
                Log out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="navbar__login">
                Log in
              </Link>
              <Link to="/signup" className="navbar__signup">
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
