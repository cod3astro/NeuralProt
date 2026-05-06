import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Nav            from './components/Nav';
import PredictPage    from './pages/PredictPage';
import ComparePage    from './pages/ComparePage';
import DocsPage       from './pages/DocsPage';
import AboutPage      from './pages/AboutPage';
import EvaluatePage   from './pages/EvaluatePage';

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/"           element={<PredictPage />} />
        <Route path="/compare"    element={<ComparePage />} />
        <Route path="/docs"       element={<DocsPage />}    />
        <Route path="/about"      element={<AboutPage />}   />
        <Route path="/evaluate"   element={<EvaluatePage />}   />
      </Routes>
    </BrowserRouter>
  );
}