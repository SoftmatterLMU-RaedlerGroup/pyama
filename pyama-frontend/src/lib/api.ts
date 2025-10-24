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
} from '@/types/api';

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