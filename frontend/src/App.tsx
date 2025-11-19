import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import AppStore from './pages/AppStore'
import FastGPT from './pages/apps/FastGPT'
import DeepSearch from './pages/apps/DeepSearch'
import Agent from './pages/apps/Agent'
import Drawing from './pages/apps/Drawing'
import OCR from './pages/apps/OCR'
import Tianyancha from './pages/apps/Tianyancha'
import AnalysisNode from './pages/apps/AnalysisNode'
import AnalysisSolution from './pages/apps/AnalysisSolution'
import AnalysisCompany from './pages/apps/AnalysisCompany'
import Monitor from './pages/apps/Monitor'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/apps" replace />} />
        <Route path="/apps" element={<AppStore />} />
        <Route path="/apps/fastgpt" element={<FastGPT />} />
        <Route path="/apps/deepsearch" element={<DeepSearch />} />
        <Route path="/apps/agent" element={<Agent />} />
        <Route path="/apps/drawing" element={<Drawing />} />
        <Route path="/apps/ocr" element={<OCR />} />
        <Route path="/apps/tianyancha-batch" element={<Tianyancha />} />
        <Route path="/apps/analysis-node" element={<AnalysisNode />} />
        <Route path="/apps/analysis-solution" element={<AnalysisSolution />} />
        <Route path="/apps/analysis-company" element={<AnalysisCompany />} />
        <Route path="/apps/monitor" element={<Monitor />} />
      </Routes>
    </Layout>
  )
}

export default App

