'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { FileText, Loader2, AlertCircle, CheckCircle, Wifi, WifiOff, ArrowLeft, Microscope, Hash, Layers, Clock, Sparkles } from 'lucide-react';
import { PyamaApiService } from '@/lib/api';
import type { MicroscopyMetadataResponse, FeaturesResponse } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function FileInfoPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [filePath, setFilePath] = useState('');
  const [metadata, setMetadata] = useState<MicroscopyMetadataResponse | null>(null);
  const [features, setFeatures] = useState<FeaturesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingFeatures, setLoadingFeatures] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        await PyamaApiService.healthCheck();
        setBackendConnected(true);
        loadFeatures();
      } catch (err) {
        setBackendConnected(false);
        console.error('Backend connection failed:', err);
      }
    };

    checkConnection();
  }, []);

  // Read file path from URL and auto-load
  useEffect(() => {
    const fileParam = searchParams.get('file');
    if (fileParam) {
      setFilePath(fileParam);
      const timer = setTimeout(() => {
        if (backendConnected) {
          handleLoadInternal(fileParam);
        }
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [searchParams, backendConnected]);

  const loadFeatures = async () => {
    setLoadingFeatures(true);
    try {
      const response = await PyamaApiService.getFeatures();
      setFeatures(response);
    } catch (err) {
      console.error('Error loading features:', err);
    } finally {
      setLoadingFeatures(false);
    }
  };

  const handleLoadInternal = async (path: string) => {
    setLoading(true);
    setError(null);
    setSuccess(false);
    setMetadata(null);

    try {
      const response = await PyamaApiService.loadMetadata({
        file_path: path.trim()
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

  const handleLoad = async () => {
    if (!filePath.trim()) {
      setError('Please enter a file path');
      return;
    }
    await handleLoadInternal(filePath);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => router.back()}>
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <h1 className="text-xl font-semibold text-gray-900">File Information</h1>
            </div>
            
            <div className="flex items-center gap-2">
              {backendConnected === null ? (
                <div className="flex items-center gap-2 text-gray-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Checking connection...</span>
                </div>
              ) : backendConnected ? (
                <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                  <Wifi className="h-3 w-3 mr-1" />
                  Backend Connected
                </Badge>
              ) : (
                <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                  <WifiOff className="h-3 w-3 mr-1" />
                  Backend Disconnected
                </Badge>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>File Information & Features</CardTitle>
            <CardDescription>Load microscopy metadata and view available features</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="mb-4 p-3 bg-muted rounded-lg border">
              <div className="text-xs font-medium text-muted-foreground mb-2">Testing Endpoints:</div>
              <div className="space-y-1 text-sm">
                <div>• <code className="bg-background px-2 py-1 rounded border">POST /api/v1/processing/load-metadata</code></div>
                <div>• <code className="bg-background px-2 py-1 rounded border">GET /api/v1/processing/features</code></div>
              </div>
            </div>
            <Separator className="mb-4" />

            <Tabs defaultValue="metadata" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="metadata">Load Metadata</TabsTrigger>
                <TabsTrigger value="features">Available Features</TabsTrigger>
              </TabsList>

              <TabsContent value="metadata" className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label htmlFor="file-path">File Path</Label>
                  <div className="flex gap-2">
                    <Input
                      id="file-path"
                      value={filePath}
                      onChange={(e) => setFilePath(e.target.value)}
                      placeholder="/path/to/file.nd2 or /path/to/file.czi"
                      disabled={loading}
                      className="font-mono"
                    />
                    <Button onClick={handleLoad} disabled={loading || !filePath.trim()}>
                      {loading ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Loading...
                        </>
                      ) : (
                        <>
                          <FileText className="mr-2 h-4 w-4" />
                          Load Metadata
                        </>
                      )}
                    </Button>
                  </div>
                </div>

                {error && (
                  <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <AlertCircle className="h-4 w-4 text-red-500" />
                    <span className="text-red-700 text-sm">{error}</span>
                  </div>
                )}

                {success && (
                  <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    <span className="text-green-700 text-sm">Metadata loaded successfully!</span>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="features" className="mt-4">
                {loadingFeatures ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  </div>
                ) : features ? (
                  <div className="space-y-6">
                    {/* Phase Features */}
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <Sparkles className="h-5 w-5 text-blue-500" />
                        <h3 className="text-lg font-semibold text-gray-900">Phase Contrast Features</h3>
                        <Badge variant="secondary">{features.phase_features.length}</Badge>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {features.phase_features.map((feature, index) => (
                          <div key={index} className="p-4 bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg border border-blue-200 hover:shadow-md transition-shadow">
                            <div className="flex items-center justify-between">
                              <div className="text-sm font-medium text-blue-900">{feature}</div>
                              <Badge variant="outline" className="bg-white">Phase</Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <Separator />

                    {/* Fluorescence Features */}
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <Sparkles className="h-5 w-5 text-green-500" />
                        <h3 className="text-lg font-semibold text-gray-900">Fluorescence Features</h3>
                        <Badge variant="secondary">{features.fluorescence_features.length}</Badge>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {features.fluorescence_features.map((feature, index) => (
                          <div key={index} className="p-4 bg-gradient-to-br from-green-50 to-green-100 rounded-lg border border-green-200 hover:shadow-md transition-shadow">
                            <div className="flex items-center justify-between">
                              <div className="text-sm font-medium text-green-900">{feature}</div>
                              <Badge variant="outline" className="bg-white">Fluorescence</Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Summary */}
                    <div className="p-4 bg-gradient-to-r from-green-50 to-blue-50 border border-green-200 rounded-lg">
                      <h4 className="text-sm font-medium text-gray-900 mb-2">Summary</h4>
                      <div className="flex items-center gap-4 text-sm text-gray-700">
                        <span><strong>{features.phase_features.length + features.fluorescence_features.length}</strong> total features</span>
                        <span>•</span>
                        <span><strong>{features.phase_features.length}</strong> phase</span>
                        <span>•</span>
                        <span><strong>{features.fluorescence_features.length}</strong> fluorescence</span>
                      </div>
                    </div>
                  </div>
                ) : null}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Metadata Display */}
        {metadata && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Microscope className="h-5 w-5" />
                Metadata
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* File Information */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  File Information
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-3 bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg border border-blue-200">
                    <div className="text-xs text-blue-600 font-medium">File Name</div>
                    <div className="font-semibold text-blue-900">{metadata.base_name}</div>
                  </div>
                  <div className="p-3 bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg border border-purple-200">
                    <div className="text-xs text-purple-600 font-medium">File Type</div>
                    <div className="font-semibold text-purple-900 uppercase">{metadata.file_type}</div>
                  </div>
                  <div className="p-3 bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg border border-gray-200">
                    <div className="text-xs text-gray-600 font-medium">Data Type</div>
                    <div className="font-semibold text-gray-900">{metadata.dtype}</div>
                  </div>
                  <div className="p-3 bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg border border-gray-200 md:col-span-2">
                    <div className="text-xs text-gray-600 font-medium">File Path</div>
                    <div className="font-mono text-xs text-gray-900 break-all">{metadata.file_path}</div>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Image Dimensions */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                  <Microscope className="h-4 w-4" />
                  Image Dimensions
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-gradient-to-br from-green-50 to-green-100 rounded-lg border border-green-200">
                    <div className="text-xs text-green-600 font-medium">Width</div>
                    <div className="font-semibold text-green-900">{metadata.width} pixels</div>
                  </div>
                  <div className="p-3 bg-gradient-to-br from-green-50 to-green-100 rounded-lg border border-green-200">
                    <div className="text-xs text-green-600 font-medium">Height</div>
                    <div className="font-semibold text-green-900">{metadata.height} pixels</div>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Experiment Structure */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                  <Layers className="h-4 w-4" />
                  Experiment Structure
                </h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-3 bg-gradient-to-br from-orange-50 to-orange-100 rounded-lg border border-orange-200">
                    <div className="text-xs text-orange-600 font-medium">Fields of View</div>
                    <div className="font-semibold text-orange-900">{metadata.n_fovs}</div>
                  </div>
                  <div className="p-3 bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg border border-blue-200">
                    <div className="text-xs text-blue-600 font-medium">Time Frames</div>
                    <div className="font-semibold text-blue-900">{metadata.n_frames}</div>
                  </div>
                  <div className="p-3 bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg border border-purple-200">
                    <div className="text-xs text-purple-600 font-medium">Channels</div>
                    <div className="font-semibold text-purple-900">{metadata.n_channels}</div>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Channels */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                  <Hash className="h-4 w-4" />
                  Channels
                </h3>
                <div className="p-3 bg-gradient-to-br from-indigo-50 to-indigo-100 rounded-lg border border-indigo-200">
                  <div className="flex flex-wrap gap-2">
                    {metadata.channel_names.map((name, index) => (
                      <Badge key={index} variant="secondary" className="bg-white">
                        {name}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>

              <Separator />

              {/* Timepoints */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Timepoints
                </h3>
                <div className="p-3 bg-gradient-to-br from-pink-50 to-pink-100 rounded-lg border border-pink-200">
                  <div className="font-mono text-sm text-pink-900">
                    {metadata.timepoints.length <= 5
                      ? metadata.timepoints.map(t => t.toFixed(2)).join(', ')
                      : `${metadata.timepoints.slice(0, 3).map(t => t.toFixed(2)).join(', ')} ... (${metadata.timepoints.length} total)`
                    }
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}

