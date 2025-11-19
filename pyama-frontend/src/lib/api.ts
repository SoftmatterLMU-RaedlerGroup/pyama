import axios from 'axios';
import type {
  DirectoryListingRequest,
  DirectoryListingResponse,
  SearchFilesRequest,
  SearchFilesResponse,
  FileInfoRequest,
  FileInfoResponse,
  LoadMetadataRequest,
  LoadMetadataResponse,
  FeaturesResponse,
  StartWorkflowRequest,
  StartWorkflowResponse,
  JobStatusResponse,
  CancelWorkflowResponse,
  WorkflowResultsResponse,
  MergeRequest,
  MergeResponse,
  ModelsResponse,
  LoadTracesRequest,
  LoadTracesResponse,
  StartFittingRequest,
  StartFittingResponse,
  FittingStatusResponse,
  CancelFittingResponse,
  FittingResultsResponse,
} from '@/types/api';
import type {
  VisualizationInitRequest,
  VisualizationInitResponse,
  VisualizationFrameRequest,
  VisualizationFrameResponse,
} from '@/types/visualization';

// Configure axios base URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';
const BACKEND_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.replace('/api/v1', '') || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 second timeout for file operations
});

const healthApi = axios.create({
  baseURL: BACKEND_BASE_URL,
  timeout: 5000, // 5 second timeout for health check
});

// API service class
export class PyamaApiService {
  // File Explorer APIs
  static async listDirectory(request: DirectoryListingRequest): Promise<DirectoryListingResponse> {
    try {
      const response = await api.post('/processing/list-directory', request);
      return response.data;
    } catch (error) {
      console.error('Error listing directory:', error);
      throw error;
    }
  }

  static async searchFiles(request: SearchFilesRequest): Promise<SearchFilesResponse> {
    try {
      const response = await api.post('/processing/search-files', request);
      return response.data;
    } catch (error) {
      console.error('Error searching files:', error);
      throw error;
    }
  }

  static async getFileInfo(request: FileInfoRequest): Promise<FileInfoResponse> {
    try {
      const response = await api.post('/processing/file-info', request);
      return response.data;
    } catch (error) {
      console.error('Error getting file info:', error);
      throw error;
    }
  }

  // Processing APIs
  static async loadMetadata(request: LoadMetadataRequest): Promise<LoadMetadataResponse> {
    try {
      const response = await api.post('/processing/load-metadata', request);
      return response.data;
    } catch (error) {
      console.error('Error loading metadata:', error);
      throw error;
    }
  }

  static async getFeatures(): Promise<FeaturesResponse> {
    try {
      const response = await api.get('/processing/features');
      return response.data;
    } catch (error) {
      console.error('Error getting features:', error);
      throw error;
    }
  }

  // Workflow APIs
  static async startWorkflow(request: StartWorkflowRequest): Promise<StartWorkflowResponse> {
    try {
      const response = await api.post('/processing/workflow/start', request);
      return response.data;
    } catch (error) {
      console.error('Error starting workflow:', error);
      throw error;
    }
  }

  static async getWorkflowStatus(jobId: string): Promise<JobStatusResponse> {
    try {
      const response = await api.get(`/processing/workflow/status/${jobId}`);
      return response.data;
    } catch (error) {
      console.error('Error getting workflow status:', error);
      throw error;
    }
  }

  static async cancelWorkflow(jobId: string): Promise<CancelWorkflowResponse> {
    try {
      const response = await api.post(`/processing/workflow/cancel/${jobId}`);
      return response.data;
    } catch (error) {
      console.error('Error cancelling workflow:', error);
      throw error;
    }
  }

  static async getWorkflowResults(jobId: string): Promise<WorkflowResultsResponse> {
    try {
      const response = await api.get(`/processing/workflow/results/${jobId}`);
      return response.data;
    } catch (error) {
      console.error('Error getting workflow results:', error);
      throw error;
    }
  }

  static async mergeResults(request: MergeRequest): Promise<MergeResponse> {
    try {
      const response = await api.post('/processing/merge', request);
      return response.data;
    } catch (error) {
      console.error('Error merging results:', error);
      throw error;
    }
  }

  // Analysis APIs
  static async getModels(): Promise<ModelsResponse> {
    try {
      const response = await api.get('/analysis/models');
      return response.data;
    } catch (error) {
      console.error('Error getting models:', error);
      throw error;
    }
  }

  static async loadTraces(request: LoadTracesRequest): Promise<LoadTracesResponse> {
    try {
      const response = await api.post('/analysis/load-traces', request);
      return response.data;
    } catch (error) {
      console.error('Error loading traces:', error);
      throw error;
    }
  }

  static async startFitting(request: StartFittingRequest): Promise<StartFittingResponse> {
    try {
      const response = await api.post('/analysis/fitting/start', request);
      return response.data;
    } catch (error) {
      console.error('Error starting fitting:', error);
      throw error;
    }
  }

  static async getFittingStatus(jobId: string): Promise<FittingStatusResponse> {
    try {
      const response = await api.get(`/analysis/fitting/status/${jobId}`);
      return response.data;
    } catch (error) {
      console.error('Error getting fitting status:', error);
      throw error;
    }
  }

  static async cancelFitting(jobId: string): Promise<CancelFittingResponse> {
    try {
      const response = await api.post(`/analysis/fitting/cancel/${jobId}`);
      return response.data;
    } catch (error) {
      console.error('Error cancelling fitting:', error);
      throw error;
    }
  }

  static async getFittingResults(jobId: string): Promise<FittingResultsResponse> {
    try {
      const response = await api.get(`/analysis/fitting/results/${jobId}`);
      return response.data;
    } catch (error) {
      console.error('Error getting fitting results:', error);
      throw error;
    }
  }

  // Visualization APIs
  static async initVisualization(
    request: VisualizationInitRequest,
  ): Promise<VisualizationInitResponse> {
    try {
      const response = await api.post('/visualization/init', request);
      return response.data;
    } catch (error) {
      console.error('Error initializing visualization:', error);
      throw error;
    }
  }

  static async getVisualizationFrame(
    request: VisualizationFrameRequest,
  ): Promise<VisualizationFrameResponse> {
    try {
      const response = await api.post('/visualization/frame', request);
      return response.data;
    } catch (error) {
      console.error('Error loading visualization frame:', error);
      throw error;
    }
  }

  // Health check
  static async healthCheck(): Promise<{ status: string }> {
    try {
      const response = await healthApi.get('/health');
      return response.data;
    } catch (error) {
      console.error('Error checking health:', error);
      throw error;
    }
  }
}

export default PyamaApiService;
