'use client';

import React, { useState } from 'react';
import FileExplorer from '@/components/FileExplorer';
import LoadButton from '@/components/LoadButton';
import MetadataDisplay from '@/components/MetadataDisplay';
import TestingEndpoints from '@/components/TestingEndpoints';
import PyamaApiService from '@/lib/api';
import type { FileItem, MicroscopyMetadataResponse } from '@/types/api';

export default function FileInfoPage() {
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [metadata, setMetadata] = useState<MicroscopyMetadataResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleLoad = async (file: FileItem) => {
    setLoading(true);
    setError(null);
    setSuccess(false);
    setMetadata(null);

    try {
      const response = await PyamaApiService.loadMetadata({
        file_path: file.path,
      });

      if (response.success && response.metadata) {
        setMetadata(response.metadata);
        setSuccess(true);
      } else {
        setError(response.error || 'Failed to load metadata');
      }
    } catch (err) {
      console.error('Failed to load metadata', err);
      setError('Failed to connect to backend server');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <TestingEndpoints
        endpoints={[
          { method: 'POST', path: '/api/v1/processing/load-metadata' },
          { method: 'POST', path: '/api/v1/processing/file-info' },
        ]}
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 h-[72vh]">
          <FileExplorer onFileSelect={setSelectedFile} selectedFile={selectedFile} />
        </div>
        <div className="space-y-4">
          <LoadButton
            selectedFile={selectedFile}
            onLoad={handleLoad}
            loading={loading}
            error={error}
            success={success}
          />
          <MetadataDisplay metadata={metadata} loading={loading} error={error} />
        </div>
      </div>
    </div>
  );
}
