import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LoginPage } from './pages/LoginPage';
import { HomePage } from './pages/HomePage';
import { LandingPage } from './pages/LandingPage';
import { QueryHistoryPage } from './pages/QueryHistoryPage';
import { PaperDetailPage } from './pages/PaperDetailPage';
import { PaperComparePage } from './pages/PaperComparePage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/landing" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/landing" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
      <Route path="/history" element={<ProtectedRoute><QueryHistoryPage /></ProtectedRoute>} />
      <Route path="/paper/:pmid" element={<ProtectedRoute><PaperDetailPage /></ProtectedRoute>} />
      <Route path="/compare" element={<ProtectedRoute><PaperComparePage /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Router>
          <AppRoutes />
        </Router>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
