'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { GitMerge, Wifi, WifiOff, ArrowLeft, Play, CheckCircle, AlertCircle } from 'lucide-react';
import { PyamaApiService } from '@/lib/api';
import type { MergeResponse } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';

export default function MergePage() {
  const router = useRouter();
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  
  // Form state
  const [sampleYaml, setSampleYaml] = useState('');
  const [processingResultsYaml, setProcessingResultsYaml] = useState('');
  const [outputDir, setOutputDir] = useState('');
  
  // Result state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [mergeResult, setMergeResult] = useState<MergeResponse | null>(null);

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

  const handleMerge = async () => {
    if (!sampleYaml || !processingResultsYaml || !outputDir) {
      setError('Please fill in all fields');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);
    setMergeResult(null);

    try {
      const response = await PyamaApiService.mergeResults({
        sample_yaml: sampleYaml,
        processing_results_yaml: processingResultsYaml,
        output_dir: outputDir
      });

      if (response.success) {
        setMergeResult(response);
        setSuccess(true);
      } else {
        setError(response.error || 'Failed to merge results');
      }
    } catch (err) {
      setError('Failed to connect to backend server');
      console.error('Error merging results:', err);
    } finally {
      setLoading(false);
    }
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
              <h1 className="text-xl font-semibold text-gray-900">Merge Results</h1>
            </div>
            
            <div className="flex items-center gap-2">
              {backendConnected === null ? (
                <div className="flex items-center gap-2 text-gray-500">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-500"></div>
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
            <CardTitle>Merge Processing Results</CardTitle>
            <CardDescription>Combine FOVs from multiple fields of view into samples</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-3 bg-muted rounded-lg border">
              <div className="text-xs font-medium text-muted-foreground mb-2">Testing Endpoint:</div>
              <code className="text-sm bg-background px-2 py-1 rounded border">POST /api/v1/processing/merge</code>
            </div>
            <Separator />

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="sample-yaml">Sample YAML Path</Label>
                <Input
                  id="sample-yaml"
                  value={sampleYaml}
                  onChange={(e) => setSampleYaml(e.target.value)}
                  placeholder="/path/to/samples.yaml"
                  disabled={loading}
                  className="font-mono"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="processing-results-yaml">Processing Results YAML Path</Label>
                <Input
                  id="processing-results-yaml"
                  value={processingResultsYaml}
                  onChange={(e) => setProcessingResultsYaml(e.target.value)}
                  placeholder="/path/to/processing_results.yaml"
                  disabled={loading}
                  className="font-mono"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="output-dir">Output Directory</Label>
                <Input
                  id="output-dir"
                  value={outputDir}
                  onChange={(e) => setOutputDir(e.target.value)}
                  placeholder="/path/to/output"
                  disabled={loading}
                  className="font-mono"
                />
              </div>

              <Button 
                onClick={handleMerge} 
                disabled={loading || !sampleYaml || !processingResultsYaml || !outputDir}
                className="w-full"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Merging...
                  </>
                ) : (
                  <>
                    <GitMerge className="mr-2 h-4 w-4" />
                    Merge Results
                  </>
                )}
              </Button>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                <AlertCircle className="h-4 w-4 text-red-500" />
                <span className="text-red-700 text-sm">{error}</span>
              </div>
            )}

            {success && mergeResult && (
              <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span className="text-green-700 text-sm">{mergeResult.message}</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Results */}
        {mergeResult && mergeResult.success && (
          <Card>
            <CardHeader>
              <CardTitle>Merge Results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2 text-sm">
                {mergeResult.output_dir && (
                  <div>
                    <span className="font-medium text-gray-700">Output Directory:</span>{' '}
                    <span className="font-mono text-gray-900">{mergeResult.output_dir}</span>
                  </div>
                )}
                
                {mergeResult.merged_files.length > 0 && (
                  <div>
                    <span className="font-medium text-gray-700">Merged Files ({mergeResult.merged_files.length}):</span>
                    <div className="mt-2 space-y-1">
                      {mergeResult.merged_files.map((file, index) => (
                        <div key={index} className="text-xs font-mono text-gray-600 bg-gray-50 p-2 rounded border">
                          {file}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}

