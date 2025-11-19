export interface VisualizationInitRequest {
  output_dir: string;
  fov_id: number;
  channels: string[];
  data_types?: Array<"image" | "seg">;
  force_rebuild?: boolean;
}

export interface VisualizationChannelMeta {
  channel: string;
  dtype: string;
  shape: number[];
  n_frames: number;
  vmin: number;
  vmax: number;
  path: string;
}

export interface VisualizationInitResponse {
  success: boolean;
  fov_id: number;
  channels: VisualizationChannelMeta[];
  traces_csv?: string;
  error?: string;
}

export interface VisualizationFrameRequest {
  cached_path: string;
  channel: string;
  frame?: number;
  frame_start?: number;
  frame_end?: number;
}

export interface VisualizationFrameResponse {
  success: boolean;
  channel: string;
  frames: number[][][];
  error?: string;
}
