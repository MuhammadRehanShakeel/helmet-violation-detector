/**
 * App.jsx - Which page is shown for which address, and who may open it.
 */
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useSelector } from 'react-redux';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Analyze from './pages/Analyze';
import LiveCamera from './pages/LiveCamera';
import Violations from './pages/Violations';
import PlateSearch from './pages/PlateSearch';
import Cameras from './pages/Cameras';
import Users from './pages/Users';
import AuditLog from './pages/AuditLog';
import Verify from './pages/Verify';
import Profile from './pages/Profile';
import RequestAccess from './pages/RequestAccess';
import Citizen from './pages/Citizen';
import Appeals from './pages/Appeals';
import HotspotMap from './pages/HotspotMap';
import CctvWall from './pages/CctvWall';

function Protected({ roles, children }) {
  const user = useSelector((s) => s.auth.user);
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password && location.pathname !== '/profile') return <Navigate to="/profile" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}

const OFFICERS = ['admin', 'officer'];

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/verify/:code" element={<Verify />} />
      <Route path="/request-access" element={<RequestAccess />} />
      <Route path="/citizen" element={<Citizen />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/violations" element={<Violations />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/map" element={<HotspotMap />} />
        <Route path="/appeals" element={<Protected roles={OFFICERS}><Appeals /></Protected>} />
        <Route path="/cctv" element={<Protected roles={OFFICERS}><CctvWall /></Protected>} />
        <Route path="/analyze" element={<Protected roles={OFFICERS}><Analyze /></Protected>} />
        <Route path="/live" element={<Protected roles={OFFICERS}><LiveCamera /></Protected>} />
        <Route path="/plates" element={<Protected roles={OFFICERS}><PlateSearch /></Protected>} />
        <Route path="/cameras" element={<Protected roles={['admin']}><Cameras /></Protected>} />
        <Route path="/users" element={<Protected roles={['admin']}><Users /></Protected>} />
        <Route path="/audit" element={<Protected roles={['admin']}><AuditLog /></Protected>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
