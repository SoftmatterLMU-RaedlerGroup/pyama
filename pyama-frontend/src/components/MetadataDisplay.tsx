'use client';

import React from 'react';
import { FileText, Microscope, Calendar, Hash, Layers, Clock } from 'lucide-react';
import type { MicroscopyMetadataResponse } from '@/types/api';

interface MetadataDisplayProps {
  metadata: MicroscopyMetadataResponse | null;
  loading?: boolean;
  error?: string | null;
}

export default function MetadataDisplay({ metadata, loading, error }: MetadataDisplayProps) {
  if (loading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5" />
          Metadata
        </h2>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          <span className="ml-3 text-gray-600">Loading metadata...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5" />
          Metadata
        </h2>
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-700">{error}</p>
        </div>
      </div>
    );
  }

  if (!metadata) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5" />
          Metadata
        </h2>
        <div className="text-center py-8 text-gray-500">
          <Microscope className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p>No metadata loaded</p>
          <p className="text-sm">Select a microscopy file to view its metadata</p>
        </div>
      </div>
    );
  }

  // Format file size
  const formatFileSize = (bytes: number): string => {
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  };

  // Format timepoints
  const formatTimepoints = (timepoints: number[]): string => {
    if (timepoints.length === 0) return 'None';
    if (timepoints.length <= 5) return timepoints.map(t => t.toFixed(2)).join(', ');
    return `${timepoints.slice(0, 3).map(t => t.toFixed(2)).join(', ')} ... (${timepoints.length} total)`;
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
        <FileText className="w-5 h-5" />
        Metadata
      </h2>

      <div className="space-y-6">
        {/* File Information */}
        <div>
          <h3 className="text-md font-medium text-gray-700 mb-3 flex items-center gap-2">
            <FileText className="w-4 h-4" />
            File Information
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="text-sm text-gray-600">File Name</div>
              <div className="font-medium text-gray-900">{metadata.base_name}</div>
            </div>
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="text-sm text-gray-600">File Type</div>
              <div className="font-medium text-gray-900 uppercase">{metadata.file_type}</div>
            </div>
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="text-sm text-gray-600">File Path</div>
              <div className="font-mono text-sm text-gray-900 break-all">{metadata.file_path}</div>
            </div>
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="text-sm text-gray-600">Data Type</div>
              <div className="font-medium text-gray-900">{metadata.dtype}</div>
            </div>
          </div>
        </div>

        {/* Image Dimensions */}
        <div>
          <h3 className="text-md font-medium text-gray-700 mb-3 flex items-center gap-2">
            <Microscope className="w-4 h-4" />
            Image Dimensions
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="text-sm text-gray-600">Width</div>
              <div className="font-medium text-gray-900">{metadata.width} pixels</div>
            </div>
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="text-sm text-gray-600">Height</div>
              <div className="font-medium text-gray-900">{metadata.height} pixels</div>
            </div>
          </div>
        </div>

        {/* Experiment Structure */}
        <div>
          <h3 className="text-md font-medium text-gray-700 mb-3 flex items-center gap-2">
            <Layers className="w-4 h-4" />
            Experiment Structure
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="text-sm text-gray-600">Fields of View</div>
              <div className="font-medium text-gray-900">{metadata.n_fovs}</div>
            </div>
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="text-sm text-gray-600">Time Frames</div>
              <div className="font-medium text-gray-900">{metadata.n_frames}</div>
            </div>
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="text-sm text-gray-600">Channels</div>
              <div className="font-medium text-gray-900">{metadata.n_channels}</div>
            </div>
          </div>
        </div>

        {/* Channels */}
        <div>
          <h3 className="text-md font-medium text-gray-700 mb-3 flex items-center gap-2">
            <Hash className="w-4 h-4" />
            Channels
          </h3>
          <div className="bg-gray-50 p-3 rounded-md">
            <div className="text-sm text-gray-600 mb-2">Channel Names</div>
            <div className="flex flex-wrap gap-2">
              {metadata.channel_names.map((name, index) => (
                <span
                  key={index}
                  className="px-2 py-1 bg-blue-100 text-blue-800 text-sm rounded-md"
                >
                  {name}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Timepoints */}
        <div>
          <h3 className="text-md font-medium text-gray-700 mb-3 flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Timepoints
          </h3>
          <div className="bg-gray-50 p-3 rounded-md">
            <div className="text-sm text-gray-600 mb-2">Time Values</div>
            <div className="font-mono text-sm text-gray-900">
              {formatTimepoints(metadata.timepoints)}
            </div>
          </div>
        </div>

        {/* Raw Metadata JSON */}
        <div>
          <h3 className="text-md font-medium text-gray-700 mb-3">Raw Metadata</h3>
          <div className="bg-gray-900 text-gray-100 p-4 rounded-md overflow-auto">
            <pre className="text-sm whitespace-pre-wrap">
              {JSON.stringify(metadata, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}