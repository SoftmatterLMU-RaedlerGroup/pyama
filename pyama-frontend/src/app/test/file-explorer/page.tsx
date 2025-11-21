'use client';

import React, { useState } from 'react';
import FileExplorer from '@/components/FileExplorer';
import TestingEndpoints from '@/components/TestingEndpoints';
import type { FileItem } from '@/types/api';

export default function FileExplorerPage() {
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);

  return (
    <div className="p-6 space-y-6">
      <TestingEndpoints
        endpoints={[
          { method: 'POST', path: '/api/v1/processing/list-directory' },
          { method: 'POST', path: '/api/v1/processing/search-files' },
        ]}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 h-[70vh]">
          <FileExplorer onFileSelect={setSelectedFile} selectedFile={selectedFile} />
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
          <h2 className="text-lg font-semibold text-gray-900">Selection</h2>
          {selectedFile ? (
            <div className="space-y-2">
              <div className="text-sm text-gray-700">
                <span className="font-medium">Name:</span>{' '}
                <span className="font-mono break-all">{selectedFile.name}</span>
              </div>
              <div className="text-sm text-gray-700">
                <span className="font-medium">Path:</span>{' '}
                <span className="font-mono break-all">{selectedFile.path}</span>
              </div>
              <div className="text-sm text-gray-700">
                <span className="font-medium">Type:</span>{' '}
                {selectedFile.is_directory ? 'Directory' : 'File'}
              </div>
              {selectedFile.extension && !selectedFile.is_directory && (
                <div className="text-sm text-gray-700">
                  <span className="font-medium">Extension:</span>{' '}
                  {selectedFile.extension}
                </div>
              )}
              {selectedFile.size_bytes && !selectedFile.is_directory && (
                <div className="text-sm text-gray-700">
                  <span className="font-medium">Size:</span>{' '}
                  {(selectedFile.size_bytes / 1024 / 1024).toFixed(2)} MB
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-500">
              Browse on the left to pick a microscopy file or folder. Selection details will
              appear here.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
