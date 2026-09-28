import { BarChart3, Bot, BrainCircuit, LayoutDashboard, Target, Users } from "lucide-react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { CopilotPage } from "./pages/CopilotPage";
import { CustomerPage, CustomersPage } from "./pages/CustomersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ModelsPage } from "./pages/ModelsPage";
import { OpportunitiesPage } from "./pages/OpportunitiesPage";
import { SegmentsPage } from "./pages/SegmentsPage";

const links = [
  ["/dashboard", "Overview", LayoutDashboard], ["/customers", "Customers", Users], ["/segments", "Segments", BarChart3],
  ["/opportunities", "Opportunities", Target], ["/copilot", "AI Copilot", Bot], ["/models", "Model health", BrainCircuit],
] as const;

export function App() {
  return <div className="shell">
    <aside className="sidebar"><div className="brand"><span>G</span><div>GrowthPilot<small>AI command center</small></div></div><nav>{links.map(([to, label, Icon]) => <NavLink key={to} to={to}><Icon size={18}/>{label}</NavLink>)}</nav><div className="sidebar-foot"><i/>Models online<br/><small>Last sync: demo dataset</small></div></aside>
    <main><header><div><p className="eyebrow">DEMO RETAIL / CUSTOMER INTELLIGENCE</p><h1>Decide what to do next.</h1></div><div className="avatar">GP</div></header>
      <Routes><Route path="/" element={<Navigate to="/dashboard" replace/>}/><Route path="/dashboard" element={<DashboardPage/>}/><Route path="/customers" element={<CustomersPage/>}/><Route path="/customers/:id" element={<CustomerPage/>}/><Route path="/segments" element={<SegmentsPage/>}/><Route path="/opportunities" element={<OpportunitiesPage/>}/><Route path="/copilot" element={<CopilotPage/>}/><Route path="/models" element={<ModelsPage/>}/></Routes>
    </main>
  </div>;
}
