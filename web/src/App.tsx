import { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import { ErrorBox, Loading } from "./components/ui";
import Branches from "./pages/Branches";
import Company from "./pages/Company";
import CustomerDetail from "./pages/CustomerDetail";
import CustomerForm from "./pages/CustomerForm";
import Customers from "./pages/Customers";
import Dashboard from "./pages/Dashboard";
import FollowUpDetailPage from "./pages/FollowUpDetail";
import FollowUps from "./pages/FollowUps";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import Reports from "./pages/Reports";
import Roles from "./pages/Roles";
import Users from "./pages/Users";
import VisitDetail from "./pages/VisitDetail";
import VisitForm from "./pages/VisitForm";
import Visits from "./pages/Visits";

function RequireAuth({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Loading />;
  if (!me) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <>{children}</>;
}

/** UI-level guard only; the API enforces the same permission on the server. */
function Can({ permission, children }: { permission: string; children: ReactNode }) {
  const { can } = useAuth();
  return can(permission) ? <>{children}</> : <ErrorBox message="You do not have permission to view this page." />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Dashboard />} />
        <Route path="customers" element={<Can permission="Customer.View"><Customers /></Can>} />
        <Route path="customers/new" element={<Can permission="Customer.Create"><CustomerForm /></Can>} />
        <Route path="customers/:id" element={<Can permission="Customer.View"><CustomerDetail /></Can>} />
        <Route path="customers/:id/edit" element={<Can permission="Customer.Edit"><CustomerForm /></Can>} />
        <Route path="visits" element={<Can permission="Visit.View"><Visits /></Can>} />
        <Route path="visits/new" element={<Can permission="Visit.Create"><VisitForm /></Can>} />
        <Route path="visits/:id" element={<Can permission="Visit.View"><VisitDetail /></Can>} />
        <Route path="followups" element={<Can permission="FollowUp.View"><FollowUps /></Can>} />
        <Route path="followups/:id" element={<Can permission="FollowUp.View"><FollowUpDetailPage /></Can>} />
        <Route path="reports" element={<Can permission="Reports.View"><Reports /></Can>} />
        <Route path="users" element={<Can permission="User.View"><Users /></Can>} />
        <Route path="roles" element={<Can permission="Company.Edit"><Roles /></Can>} />
        <Route path="branches" element={<Can permission="Branch.View"><Branches /></Can>} />
        <Route path="company" element={<Can permission="Company.View"><Company /></Can>} />
        <Route path="profile" element={<Profile />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
