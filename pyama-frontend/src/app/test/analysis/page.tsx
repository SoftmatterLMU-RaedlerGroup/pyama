'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { TrendingUp, Wifi, WifiOff, ArrowLeft, Play, Square } from 'lucide-react';
import { PyamaApiService } from '@/lib/api';
import type { 
  ModelInfo,
  StartFittingRequest,
  FittingStatusResponse,
  FittingResultsResponse 
} from '@/types/api';

export default function AnalysisPage() {
  const router = useRouter();
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  
  // Configuration
  const [csvPath, setCsvPath] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  
  // Job state
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState('');
  const [jobProgress, setJobProgress] = useState<{current: number, total: number, percentage: number} | null>(null);
  const [jobMessage, setJobMessage] = useState('');
  const [fittingResults, setFittingResults] = useState<FittingResultsResponse | null>(null);
  
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        await PyamaApiService.healthCheck();
        setBackendConnected(true);
        
        const modelsResponse = await PyamaApiService.getModels();
        setAvailableModels(modelsResponse.models);
        if (modelsResponse.models.length > 0) {
          setSelectedModel(modelsResponse.models[0].name);
        }
      } catch (err) {
        setBackendConnected(false);
        console.error('Backend connection failed:', err);
      }
    };

    checkConnection();
  }, []);

  useEffect(() => {
    if (!jobId || !isPolling) return;

    const pollInterval = setInterval(async () => {
      try {
        const status = await PyamaApiService.getFittingStatus(jobId);
        setJobStatus(status.status);
        setJobMessage(status.message);
        
        if (status.progress) {
          setJobProgress(status.progress);
        }
        
        if (['completed', 'failed', 'cancelled'].includes(status.status)) {
          setIsPolling(false);
          
          if (status.status === 'completed') {
            const results = await PyamaApiService.getFittingResults(jobId);
            setFittingResults(results);
          }
        }
      } catch (err) {
        console.error('Error polling job status:', err);
        setIsPolling(false);
      }
    }, 1000);

    return () => clearInterval(pollInterval);
  }, [jobId, isPolling]);

  const handleStartFitting = async () => {
    if (!csvPath || !selectedModel) {
      alert('Please select CSV file and model');
      return;
    }
    
    const request: StartFittingRequest = {
      csv_path: csvPath,
      model_type: selectedModel
    };
    
    try {
      const response = await PyamaApiService.startFitting(request);
      if (response.success && response.job_id) {
        setJobId(response.job_id);
        setJobStatus('pending');
        setJobMessage('Fitting started');
        setIsPolling(true);
        setFittingResults(null);
      } else {
        alert(response.error || 'Failed to start fitting');
      }
    } catch (err) {
      console.error('Error starting fitting:', err);
      alert('Failed to start fitting');
    }
  };

  const handleCancelFitting = async () => {
    if (!jobId) return;
    
    try {
      const response = await PyamaApiService.cancelFitting(jobId);
      if (response.success) {
        setIsPolling(false);
        setJobMessage('Fitting cancelled');
      }
    } catch (err) {
      console.error('Error cancelling fitting:', err);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
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
              <h1 className="text-xl font-semibold text-gray-900">Analysis</h1>
            </div>
            
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

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Fitting Configuration</h2>
          
          <div className="mb-4 p-3 bg-muted rounded-lg border">
            <div className="text-xs font-medium text-muted-foreground mb-2">Testing Endpoints:</div>
            <div className="space-y-1 text-sm">
              <div>• <code className="bg-background px-2 py-1 rounded border">GET /api/v1/analysis/models</code></div>
              <div>• <code className="bg-background px-2 py-1 rounded border">POST /api/v1/analysis/load-traces</code></div>
              <div>• <code className="bg-background px-2 py-1 rounded border">POST /api/v1/analysis/fitting/start</code></div>
              <div>• <code className="bg-background px-2 py-1 rounded border">GET /api/v1/analysis/fitting/status/{'{job_id}'}</code></div>
              <div>• <code className="bg-background px-2 py-1 rounded border">POST /api/v1/analysis/fitting/cancel/{'{job_id}'}</code></div>
              <div>• <code className="bg-background px-2 py-1 rounded border">GET /api/v1/analysis/fitting/results/{'{job_id}'}</code></div>
            </div>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                CSV File Path
              </label>
              <input
                type="text"
                value={csvPath}
                onChange={(e) => setCsvPath(e.target.value)}
                placeholder="/path/to/traces.csv"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Model
              </label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {availableModels.map(model => (
                  <option key={model.name} value={model.name}>
                    {model.name} - {model.description}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex gap-3 pt-4">
              <button
                onClick={handleStartFitting}
                disabled={!csvPath || !selectedModel || isPolling}
                className="flex items-center gap-2 px-6 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Play className="w-4 h-4" />
                Start Fitting
              </button>
              {isPolling && (
                <button
                  onClick={handleCancelFitting}
                  className="flex items-center gap-2 px-6 py-2 bg-red-500 text-white rounded-md hover:bg-red-600"
                >
                  <Square className="w-4 h-4" />
                  Cancel
                </button>
              )}
            </div>
          </div>
        </div>

        {jobId && (
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h3 className="text-md font-semibold text-gray-900 mb-3">Job Status</h3>
            <div className="space-y-3">
              <div>
                <span className="text-sm text-gray-600">Job ID:</span>{' '}
                <span className="font-mono text-sm text-gray-900">{jobId}</span>
              </div>
              <div>
                <span className="text-sm text-gray-600">Status:</span>{' '}
                <span className={`px-2 py-1 text-xs rounded-md ${
                  jobStatus === 'completed' ? 'bg-green-100 text-green-800' :
                  jobStatus === 'failed' ? 'bg-red-100 text-red-800' :
                  jobStatus === 'running' ? 'bg-blue-100 text-blue-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {jobStatus}
                </span>
              </div>
              {jobProgress && (
                <div>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-gray-600">Progress</span>
                    <span className="text-gray-900">{jobProgress.current}/{jobProgress.total} ({jobProgress.percentage.toFixed(1)}%)</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all"
                      style={{ width: `${jobProgress.percentage}%` }}
                    />
                  </div>
                </div>
              )}
              <div>
                <span className="text-sm text-gray-600">Message:</span>{' '}
                <span className="text-sm text-gray-900">{jobMessage}</span>
              </div>
            </div>
          </div>
        )}

        {fittingResults && fittingResults.success && (
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h3 className="text-md font-semibold text-gray-900 mb-3">Results</h3>
            <div className="space-y-2 text-sm">
              {fittingResults.results_file && (
                <div>
                  <span className="font-medium text-gray-700">Results File:</span>{' '}
                  <span className="font-mono text-gray-900">{fittingResults.results_file}</span>
                </div>
              )}
              {fittingResults.summary && (
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div className="bg-gray-50 p-3 rounded-md">
                    <div className="text-xs text-gray-600">Total Cells</div>
                    <div className="font-medium text-gray-900">{fittingResults.summary.total_cells}</div>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-md">
                    <div className="text-xs text-gray-600">Successful Fits</div>
                    <div className="font-medium text-gray-900">{fittingResults.summary.successful_fits}</div>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-md">
                    <div className="text-xs text-gray-600">Failed Fits</div>
                    <div className="font-medium text-gray-900">{fittingResults.summary.failed_fits}</div>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-md">
                    <div className="text-xs text-gray-600">Mean R²</div>
                    <div className="font-medium text-gray-900">{fittingResults.summary.mean_r_squared.toFixed(3)}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

