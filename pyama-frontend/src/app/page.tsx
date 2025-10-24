'use client';

import React, { useState, useEffect } from 'react';
import { AlertCircle, Wifi, WifiOff } from 'lucide-react';
import FileExplorer from '@/components/FileExplorer';
import MetadataDisplay from '@/components/MetadataDisplay';
import LoadButton from '@/components/LoadButton';
import { PyamaApiService } from '@/lib/api';
import type { FileItem, MicroscopyMetadataResponse } from '@/types/api';

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [metadata, setMetadata] = useState<MicroscopyMetadataResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);

  // Check backend connection on mount
  useEffect(() => {
    const checkConnection = async () => {
      try {
        await PyamaApiService.healthCheck();
        setBackendConnected(true);
      } catch (err) {
        setBackendConnected(false);
        console.error('Backend connection failed:', err);
      }
    };

    checkConnection();
  }, []);

  // Handle file selection
  const handleFileSelect = (file: FileItem) => {
    setSelectedFile(file);
    setMetadata(null);
    setError(null);
    setSuccess(false);
  };

  // Handle file loading
  const handleLoad = async (file: FileItem) => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await PyamaApiService.loadMetadata({
        file_path: file.path
      });

      if (response.success && response.metadata) {
        setMetadata(response.metadata);
        setSuccess(true);
      } else {
        setError(response.error || 'Failed to load metadata');
      }
    } catch (err) {
      setError('Failed to connect to backend server');
      console.error('Error loading metadata:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">
                PyAMA File Explorer
              </h1>
            </div>
            
            {/* Backend Status */}
            <div className="flex items-center gap-2">
              {backendConnected === null ? (
                <div className="flex items-center gap-2 text-gray-500">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-500"></div>
                  <span className="text-sm">Checking connection...</span>
                </div>
              ) : backendConnected ? (
                <div className="flex items-center gap-2 text-green-600">
                  <Wifi className="w-4 h-4" />
                  <span className="text-sm">Backend Connected</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-red-600">
                  <WifiOff className="w-4 h-4" />
                  <span className="text-sm">Backend Disconnected</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {backendConnected === false && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-red-500" />
              <div>
                <h3 className="text-sm font-medium text-red-800">
                  Backend Server Not Available
                </h3>
                <p className="text-sm text-red-700 mt-1">
                  Please make sure the PyAMA backend server is running on{' '}
                  <code className="bg-red-100 px-1 rounded">http://localhost:8000</code>
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* File Explorer */}
          <div className="lg:col-span-1">
            <FileExplorer
              onFileSelect={handleFileSelect}
              selectedFile={selectedFile}
            />
          </div>

          {/* Load Button and Metadata */}
          <div className="lg:col-span-2 space-y-6">
            {/* Load Button */}
            <LoadButton
              selectedFile={selectedFile}
              onLoad={handleLoad}
              loading={loading}
              error={error}
              success={success}
            />

            {/* Metadata Display */}
            <MetadataDisplay
              metadata={metadata}
              loading={loading}
              error={error}
            />
          </div>
        </div>

        {/* Instructions */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="text-lg font-medium text-blue-900 mb-3">How to Use</h3>
          <div className="space-y-2 text-sm text-blue-800">
            <p>1. <strong>Browse Files:</strong> Use the file explorer on the left to navigate directories and find your microscopy files (.nd2 or .czi)</p>
            <p>2. <strong>Select File:</strong> Click on a microscopy file to select it</p>
            <p>3. <strong>Load Metadata:</strong> Click the "Load Metadata" button to extract and display the file's metadata</p>
            <p>4. <strong>View Details:</strong> The metadata will be displayed below, including image dimensions, channels, timepoints, and more</p>
          </div>
        </div>
      </main>
    </div>
  );
}