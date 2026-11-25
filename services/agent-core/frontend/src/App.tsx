import Dashboard from './pages/Dashboard';
import ToolDrafts from './pages/ToolDrafts';
import { Route, Routes } from 'react-router-dom';

function App() {
  return <Routes>
    <Route path="/tool-drafts" element={<ToolDrafts />} />
    <Route path="*" element={<Dashboard />} />
  </Routes>;
}

export default App;
