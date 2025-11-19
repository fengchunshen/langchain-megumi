import http from './http'

export interface AnalysisNodeRequest {
  nodeName: string
  parentProfile?: string
  siblingsProfiles?: string[]
}

export interface AnalysisSolutionRequest {
  solutionName: string
  description?: string
}

export interface AnalysisCompanyRequest {
  companyName: string
  businessScope?: string
}

export interface AnalysisResponse {
  [key: string]: any
}

/**
 * AI 分析 API
 */
export const analysisApi = {
  /**
   * 节点分析
   */
  analyzeNode: async (data: AnalysisNodeRequest): Promise<AnalysisResponse> => {
    return http.post('/analysis/analyze-node', data)
  },

  /**
   * 解决方案标签分析
   */
  analyzeSolution: async (
    data: AnalysisSolutionRequest
  ): Promise<AnalysisResponse> => {
    return http.post('/analysis/analyze-solution', data)
  },

  /**
   * 企业标签分析
   */
  analyzeCompany: async (
    data: AnalysisCompanyRequest
  ): Promise<AnalysisResponse> => {
    return http.post('/analysis/analyze-company-tags', data)
  },
}

