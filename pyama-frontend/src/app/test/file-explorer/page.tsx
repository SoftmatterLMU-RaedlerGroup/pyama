'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Wifi, WifiOff, AlertCircle, ArrowLeft } from 'lucide-react';
import FileExplorer from '@/components/FileExplorer';
import { PyamaApiService } from '@/lib/api';
import type { FileItem } from '@/types/api';

export default function FileExplorerPage() {
  const router = useRouter();
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
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

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <button
                onClick={() => router.back()}
                className="p-2 hover:bg-gray-100 rounded-md transition-colors"
                title="Go back"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600" />
              </button>
              <h1 className="text-xl font-semibold text-gray-900">
                File Explorer
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

        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            File Explorer
          </h2>
          
          <div className="mb-4 p-3 bg-muted rounded-lg border">
            <div className="text-xs font-medium text-muted-foreground mb-2">Testing Endpoints:</div>
            <div className="space-y-1 text-sm">
              <div>• <code className="bg-background px-2 py-1 rounded border">POST /api/v1/processing/list-directory</code></div>
              <div>• <code className="bg-background px-2 py-1 rounded border">POST /api/v1/processing/search-files</code></div>
              <div>• <code className="bg-background px-2 py-1 rounded border">POST /api/v1/processing/file-info</code></div>
            </div>
          </div>

          <FileExplorer
            onFileSelect={setSelectedFile}
            selectedFile={selectedFile}
          />
        </div>

        {/* Selected File Info */}
        {selectedFile && (
          <div className="mt-6 bg-white rounded-lg shadow-sm p-6">
            <h3 className="text-md font-semibold text-gray-900 mb-3">Selected File</h3>
            <div className="space-y-3">
              <div className="space-y-2 text-sm">
                <div>
                  <span className="font-medium text-gray-700">Name:</span>{' '}
                  <span className="text-gray-900">{selectedFile.name}</span>
                </div>
                <div>
                  <span className="font-medium text-gray-700">Path:</span>{' '}
                  <span className="text-gray-900 font-mono text-xs">{selectedFile.path}</span>
                </div>
                {selectedFile.size_bytes && (
                  <div>
                    <span className="font-medium text-gray-700">Size:</span>{' '}
                    <span className="text-gray-900">
                      {(selectedFile.size_bytes / 1024 / 1024).toFixed(2)} MB
                    </span>
                  </div>
                )}
              </div>
              
              {/* Load Metadata Button for microscopy files */}
              {(selectedFile.extension?.toLowerCase() === '.nd2' || selectedFile.extension?.toLowerCase() === '.czi') && (
                <button
                  onClick={() => router.push(`/test/file-info?file=${encodeURIComponent(selectedFile.path)}`)}
                  className="w-full px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors"
                >
                  Load Metadata
                </button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

