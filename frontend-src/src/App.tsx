import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { ArenaProvider } from './context/ArenaContext'
import ComparePage from './pages/ComparePage'
import HistoryPage from './pages/HistoryPage'
import ReportPage from './pages/ReportPage'
import ResultsPage from './pages/ResultsPage'

function App() {
  return (
    <ArenaProvider>
      <HashRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<ComparePage />} />
            <Route path="/results" element={<ResultsPage />} />
            <Route path="/results/:runId" element={<ResultsPage />} />
            <Route path="/report/:runId" element={<ReportPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </HashRouter>
    </ArenaProvider>
  )
}

export default App
