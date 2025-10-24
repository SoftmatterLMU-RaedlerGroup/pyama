// API response types for PyAMA Backend

export interface FileItem {
  name: string;
  path: string;
  is_directory: boolean;
  is_file: boolean;
  size_bytes?: number;
  modified_time?: string;
  extension?: string;
}

export interface DirectoryListingRequest {
  directory_path: string;
  include_hidden?: boolean;
  filter_extensions?: string[];
}

export interface DirectoryListingResponse {
  success: boolean;
  directory_path: string;
  items: FileItem[];
  error?: string;
}

export interface SearchFilesRequest {
  search_path: string;
  pattern?: string;
  extensions?: string[];
  max_depth?: number;
  include_hidden?: boolean;
}

export interface SearchFilesResponse {
  success: boolean;
  search_path: string;
  files: FileItem[];
  total_found: number;
  error?: string;
}

export interface FileInfoRequest {
  file_path: string;
}

export interface MicroscopyMetadataResponse {
  file_path: string;
  base_name: string;
  file_type: string;
  height: number;
  width: number;
  n_frames: number;
  n_fovs: number;
  n_channels: number;
  timepoints: number[];
  channel_names: string[];
  dtype: string;
}

export interface FileInfoResponse {
  success: boolean;
  file_info?: FileItem;
  is_microscopy_file: boolean;
  metadata_preview?: MicroscopyMetadataResponse;
  error?: string;
}

export interface LoadMetadataRequest {
  file_path: string;
}

export interface LoadMetadataResponse {
  success: boolean;
  metadata?: MicroscopyMetadataResponse;
  error?: string;
}