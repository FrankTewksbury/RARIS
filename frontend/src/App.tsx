import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { AcquisitionMonitor } from "./pages/AcquisitionMonitor";
import { CurationDashboard } from "./pages/CurationDashboard";
import "./App.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: 1 },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <nav className="top-nav">
          <NavLink to="/" end>Discovery</NavLink>
          <NavLink to="/acquisition">Acquisition</NavLink>
          <NavLink to="/curation">Curation</NavLink>
        </nav>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/acquisition" element={<AcquisitionMonitor />} />
          <Route path="/curation" element={<CurationDashboard />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
