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

export interface FeaturesResponse {
  phase_features: string[];
  fluorescence_features: string[];
}

// Workflow Types
export interface ChannelSelectionRequest {
  channel: number;
  features: string[];
}

export interface WorkflowChannelsRequest {
  phase?: ChannelSelectionRequest;
  fluorescence: ChannelSelectionRequest[];
}

export interface WorkflowParametersRequest {
  fov_start: number;
  fov_end: number;
  batch_size: number;
  n_workers: number;
}

export interface StartWorkflowRequest {
  microscopy_path: string;
  output_dir: string;
  channels: WorkflowChannelsRequest;
  parameters: WorkflowParametersRequest;
}

export interface StartWorkflowResponse {
  success: boolean;
  job_id?: string;
  message: string;
  error?: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  progress?: {
    current: number;
    total: number;
    percentage: number;
  };
  message: string;
}

export interface CancelWorkflowResponse {
  success: boolean;
  message: string;
}

export interface WorkflowResultsResponse {
  success: boolean;
  output_dir?: string;
  results_file?: string;
  traces: string[];
  error?: string;
}

export interface MergeRequest {
  sample_yaml: string;
  processing_results_yaml: string;
  output_dir: string;
}

export interface MergeResponse {
  success: boolean;
  message: string;
  output_dir?: string;
  merged_files: string[];
  error?: string;
}

// Analysis Types
export interface ModelParameter {
  name: string;
  default: number;
  bounds: number[];
}

export interface ModelInfo {
  name: string;
  description: string;
  parameters: ModelParameter[];
}

export interface ModelsResponse {
  models: ModelInfo[];
}

export interface LoadTracesRequest {
  csv_path: string;
}

export interface TraceDataInfo {
  n_cells: number;
  n_timepoints: number;
  time_units: string;
  columns: string[];
}

export interface LoadTracesResponse {
  success: boolean;
  data?: TraceDataInfo;
  error?: string;
}

export interface StartFittingRequest {
  csv_path: string;
  model_type: string;
  model_params?: Record<string, number>;
  model_bounds?: Record<string, number[]>;
}

export interface StartFittingResponse {
  success: boolean;
  job_id?: string;
  message: string;
  error?: string;
}

export interface FittingStatusResponse {
  job_id: string;
  status: string;
  progress?: {
    current: number;
    total: number;
    percentage: number;
  };
  message: string;
}

export interface CancelFittingResponse {
  success: boolean;
  message: string;
}

export interface FittingResultsResponse {
  success: boolean;
  results_file?: string;
  summary?: {
    total_cells: number;
    successful_fits: number;
    failed_fits: number;
    mean_r_squared: number;
  };
  error?: string;
}