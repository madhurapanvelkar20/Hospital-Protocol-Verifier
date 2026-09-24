import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext.jsx";
import Navbar from "./components/Navbar.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import Home from "./pages/Home.jsx";
import About from "./pages/About.jsx";
import Login from "./pages/Login.jsx";
import Signup from "./pages/Signup.jsx";
import Verifier from "./pages/Verifier.jsx";
import History from "./pages/History.jsx";

function Layout({ children }) {
  return (
    <div className="page">
      <div className="page__glow" aria-hidden="true" />
      <Navbar />
      <main className="layout">{children}</main>
      <footer className="page__footer">
        <p>ProtocolVerify is a decision-support aid and does not replace clinical judgment.</p>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/about" element={<About />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route
              path="/verify"
              element={
                <ProtectedRoute>
                  <Verifier />
                </ProtectedRoute>
              }
            />
            <Route
              path="/history"
              element={
                <ProtectedRoute>
                  <History />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Layout>
      </BrowserRouter>
    </AuthProvider>
  );
}
