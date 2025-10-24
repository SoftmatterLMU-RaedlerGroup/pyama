'use client';

import React from 'react';
import { Loader2, FileText, AlertCircle, CheckCircle } from 'lucide-react';
import type { FileItem } from '@/types/api';

interface LoadButtonProps {
  selectedFile: FileItem | null;
  onLoad: (file: FileItem) => void;
  loading?: boolean;
  error?: string | null;
  success?: boolean;
}

export default function LoadButton({ 
  selectedFile, 
  onLoad, 
  loading = false, 
  error = null, 
  success = false 
}: LoadButtonProps) {
  const isMicroscopyFile = selectedFile?.extension?.toLowerCase() === '.nd2' || 
                          selectedFile?.extension?.toLowerCase() === '.czi';

  const handleLoad = () => {
    if (selectedFile && !loading) {
      onLoad(selectedFile);
    }
  };

  const getButtonText = () => {
    if (loading) return 'Loading...';
    if (success) return 'Loaded Successfully';
    if (error) return 'Load Failed';
    if (!selectedFile) return 'No File Selected';
    if (!isMicroscopyFile) return 'Not a Microscopy File';
    return 'Load Metadata';
  };

  const getButtonIcon = () => {
    if (loading) return <Loader2 className="w-4 h-4 animate-spin" />;
    if (success) return <CheckCircle className="w-4 h-4" />;
    if (error) return <AlertCircle className="w-4 h-4" />;
    return <FileText className="w-4 h-4" />;
  };

  const getButtonStyle = () => {
    if (loading) return 'bg-blue-500 hover:bg-blue-600 text-white';
    if (success) return 'bg-green-500 hover:bg-green-600 text-white';
    if (error) return 'bg-red-500 hover:bg-red-600 text-white';
    if (!selectedFile || !isMicroscopyFile) return 'bg-gray-300 text-gray-500 cursor-not-allowed';
    return 'bg-blue-500 hover:bg-blue-600 text-white';
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">Load File</h2>
      
      {/* Selected File Info */}
      {selectedFile && (
        <div className="mb-4 p-3 bg-gray-50 rounded-md">
          <div className="text-sm text-gray-600">Selected File:</div>
          <div className="font-medium text-gray-900 truncate">{selectedFile.name}</div>
          <div className="text-sm text-gray-500">
            {selectedFile.size_bytes ? `${(selectedFile.size_bytes / 1024 / 1024).toFixed(1)} MB` : 'Unknown size'}
            {selectedFile.extension && ` • ${selectedFile.extension.toUpperCase()}`}
          </div>
        </div>
      )}

      {/* Load Button */}
      <button
        onClick={handleLoad}
        disabled={!selectedFile || !isMicroscopyFile || loading}
        className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-md font-medium transition-colors ${getButtonStyle()}`}
      >
        {getButtonIcon()}
        {getButtonText()}
      </button>

      {/* Status Messages */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-500" />
            <span className="text-red-700 text-sm">{error}</span>
          </div>
        </div>
      )}

      {success && (
        <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-green-500" />
            <span className="text-green-700 text-sm">Metadata loaded successfully!</span>
          </div>
        </div>
      )}

      {/* Help Text */}
      {!selectedFile && (
        <div className="mt-4 text-center text-gray-500 text-sm">
          Select a microscopy file (.nd2 or .czi) from the file explorer to load its metadata
        </div>
      )}

      {selectedFile && !isMicroscopyFile && (
        <div className="mt-4 text-center text-amber-600 text-sm">
          Selected file is not a supported microscopy format. Please select a .nd2 or .czi file.
        </div>
      )}
    </div>
  );
}