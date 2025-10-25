'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { FlaskConical, Wifi, WifiOff, AlertCircle, ArrowLeft, Play, Square, RefreshCw } from 'lucide-react';
import { PyamaApiService } from '@/lib/api';
import type { 
  StartWorkflowRequest, 
  WorkflowChannelsRequest, 
  WorkflowParametersRequest,
  ChannelSelectionRequest,
  JobStatusResponse,
  WorkflowResultsResponse 
} from '@/types/api';

export default function WorkflowPage() {
  const router = useRouter();
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  
  // Configuration state
  const [microscopyPath, setMicroscopyPath] = useState('');
  const [outputDir, setOutputDir] = useState('');
  const [phaseChannel, setPhaseChannel] = useState<string>('');
  const [phaseFeatures, setPhaseFeatures] = useState<string[]>([]);
  const [flChannels, setFlChannels] = useState<Array<{channel: string, features: string[]}>>([]);
  const [fovStart, setFovStart] = useState(0);
  const [fovEnd, setFovEnd] = useState(10);
  const [batchSize, setBatchSize] = useState(2);
  const [nWorkers, setNWorkers] = useState(2);
  
  // Job state
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string>('');
  const [jobProgress, setJobProgress] = useState<{current: number, total: number, percentage: number} | null>(null);
  const [jobMessage, setJobMessage] = useState('');
  const [workflowResults, setWorkflowResults] = useState<WorkflowResultsResponse | null>(null);
  
  // Polling state
  const [isPolling, setIsPolling] = useState(false);
  
  // Load available features
  const [availableFeatures, setAvailableFeatures] = useState<{phase: string[], fluorescence: string[]} | null>(null);

  // Check backend connection on mount
  useEffect(() => {
    const checkConnection = async () => {
      try {
        await PyamaApiService.healthCheck();
        setBackendConnected(true);
        
        // Load features
        const features = await PyamaApiService.getFeatures();
        setAvailableFeatures(features);
      } catch (err) {
        setBackendConnected(false);
        console.error('Backend connection failed:', err);
      }
    };

    checkConnection();
  }, []);

  // Poll job status
  useEffect(() => {
    if (!jobId || !isPolling) return;

    const pollInterval = setInterval(async () => {
      try {
        const status = await PyamaApiService.getWorkflowStatus(jobId);
        setJobStatus(status.status);
        setJobMessage(status.message);
        
        if (status.progress) {
          setJobProgress(status.progress);
        }
        
        // Stop polling if job is completed, failed, or cancelled
        if (['completed', 'failed', 'cancelled'].includes(status.status)) {
          setIsPolling(false);
          
          // Load results if completed
          if (status.status === 'completed') {
            const results = await PyamaApiService.getWorkflowResults(jobId);
            setWorkflowResults(results);
          }
        }
      } catch (err) {
        console.error('Error polling job status:', err);
        setIsPolling(false);
      }
    }, 1000); // Poll every second

    return () => clearInterval(pollInterval);
  }, [jobId, isPolling]);

  const handleStartWorkflow = async () => {
    // Build channels configuration
    const channels: WorkflowChannelsRequest = {
      fluorescence: []
    };
    
    if (phaseChannel && phaseFeatures.length > 0) {
      channels.phase = {
        channel: parseInt(phaseChannel),
        features: phaseFeatures
      };
    }
    
    for (const fl of flChannels) {
      if (fl.channel && fl.features.length > 0) {
        channels.fluorescence.push({
          channel: parseInt(fl.channel),
          features: fl.features
        });
      }
    }
    
    // Build request
    const request: StartWorkflowRequest = {
      microscopy_path: microscopyPath,
      output_dir: outputDir,
      channels: channels,
      parameters: {
        fov_start: fovStart,
        fov_end: fovEnd,
        batch_size: batchSize,
        n_workers: nWorkers
      }
    };
    
    try {
      const response = await PyamaApiService.startWorkflow(request);
      if (response.success && response.job_id) {
        setJobId(response.job_id);
        setJobStatus('pending');
        setJobMessage('Workflow started');
        setIsPolling(true);
        setWorkflowResults(null);
      } else {
        alert(response.error || 'Failed to start workflow');
      }
    } catch (err) {
      console.error('Error starting workflow:', err);
      alert('Failed to start workflow');
    }
  };

  const handleCancelWorkflow = async () => {
    if (!jobId) return;
    
    try {
      const response = await PyamaApiService.cancelWorkflow(jobId);
      if (response.success) {
        setIsPolling(false);
        setJobMessage('Workflow cancelled');
      }
    } catch (err) {
      console.error('Error cancelling workflow:', err);
    }
  };

  const addFluorescenceChannel = () => {
    setFlChannels([...flChannels, {channel: '', features: []}]);
  };

  const removeFluorescenceChannel = (index: number) => {
    setFlChannels(flChannels.filter((_, i) => i !== index));
  };

  const updateFluorescenceChannel = (index: number, field: 'channel' | 'features', value: string | string[]) => {
    const updated = [...flChannels];
    updated[index] = {...updated[index], [field]: value};
    setFlChannels(updated);
  };

  const toggleFeature = (type: 'phase' | 'fluorescence', feature: string, index?: number) => {
    if (type === 'phase') {
      setPhaseFeatures(
        phaseFeatures.includes(feature)
          ? phaseFeatures.filter(f => f !== feature)
          : [...phaseFeatures, feature]
      );
    } else if (type === 'fluorescence' && index !== undefined) {
      const updated = [...flChannels];
      const features = updated[index].features;
      updated[index].features = features.includes(feature)
        ? features.filter(f => f !== feature)
        : [...features, feature];
      setFlChannels(updated);
    }
  };

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
                Workflow Runner
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
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Workflow Configuration
          </h2>
          
          <div className="mb-4 p-3 bg-muted rounded-lg border">
            <div className="text-xs font-medium text-muted-foreground mb-2">Testing Endpoints:</div>
            <div className="space-y-1 text-sm">
              <div>• <code className="bg-background px-2 py-1 rounded border">POST /api/v1/processing/workflow/start</code></div>
              <div>• <code className="bg-background px-2 py-1 rounded border">GET /api/v1/processing/workflow/status/{'{job_id}'}</code></div>
              <div>• <code className="bg-background px-2 py-1 rounded border">POST /api/v1/processing/workflow/cancel/{'{job_id}'}</code></div>
              <div>• <code className="bg-background px-2 py-1 rounded border">GET /api/v1/processing/workflow/results/{'{job_id}'}</code></div>
            </div>
          </div>
          
          <div className="space-y-4">
            {/* File Paths */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Microscopy File Path
                </label>
                <input
                  type="text"
                  value={microscopyPath}
                  onChange={(e) => setMicroscopyPath(e.target.value)}
                  placeholder="/path/to/file.nd2"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Output Directory
                </label>
                <input
                  type="text"
                  value={outputDir}
                  onChange={(e) => setOutputDir(e.target.value)}
                  placeholder="/path/to/output"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                />
              </div>
            </div>

            {/* Phase Channel */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Phase Channel
              </label>
              <div className="grid grid-cols-2 gap-4">
                <input
                  type="number"
                  value={phaseChannel}
                  onChange={(e) => setPhaseChannel(e.target.value)}
                  placeholder="Channel index"
                  className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <div>
                  <div className="text-xs text-gray-600 mb-1">Features:</div>
                  <div className="flex flex-wrap gap-2">
                    {availableFeatures?.phase_features.map(feature => (
                      <button
                        key={feature}
                        onClick={() => toggleFeature('phase', feature)}
                        className={`px-2 py-1 text-xs rounded-md ${
                          phaseFeatures.includes(feature)
                            ? 'bg-blue-500 text-white'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                      >
                        {feature}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Fluorescence Channels */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700">
                  Fluorescence Channels
                </label>
                <button
                  onClick={addFluorescenceChannel}
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  + Add Channel
                </button>
              </div>
              {flChannels.map((channel, index) => (
                <div key={index} className="mb-3 p-3 bg-gray-50 rounded-md">
                  <div className="grid grid-cols-2 gap-4">
                    <input
                      type="number"
                      value={channel.channel}
                      onChange={(e) => updateFluorescenceChannel(index, 'channel', e.target.value)}
                      placeholder="Channel index"
                      className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <div className="flex items-center justify-between">
                      <div className="text-xs text-gray-600">Features:</div>
                      <button
                        onClick={() => removeFluorescenceChannel(index)}
                        className="text-xs text-red-600 hover:text-red-800"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {availableFeatures?.fluorescence_features.map(feature => (
                      <button
                        key={feature}
                        onClick={() => toggleFeature('fluorescence', feature, index)}
                        className={`px-2 py-1 text-xs rounded-md ${
                          channel.features.includes(feature)
                            ? 'bg-green-500 text-white'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                      >
                        {feature}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Parameters */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  FOV Start
                </label>
                <input
                  type="number"
                  value={fovStart}
                  onChange={(e) => setFovStart(parseInt(e.target.value) || 0)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  FOV End
                </label>
                <input
                  type="number"
                  value={fovEnd}
                  onChange={(e) => setFovEnd(parseInt(e.target.value) || 0)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Batch Size
                </label>
                <input
                  type="number"
                  value={batchSize}
                  onChange={(e) => setBatchSize(parseInt(e.target.value) || 1)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Workers
                </label>
                <input
                  type="number"
                  value={nWorkers}
                  onChange={(e) => setNWorkers(parseInt(e.target.value) || 1)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 pt-4">
              <button
                onClick={handleStartWorkflow}
                disabled={!microscopyPath || !outputDir || isPolling}
                className="flex items-center gap-2 px-6 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Play className="w-4 h-4" />
                Start Workflow
              </button>
              {isPolling && (
                <button
                  onClick={handleCancelWorkflow}
                  className="flex items-center gap-2 px-6 py-2 bg-red-500 text-white rounded-md hover:bg-red-600"
                >
                  <Square className="w-4 h-4" />
                  Cancel
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Job Status */}
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

        {/* Results */}
        {workflowResults && workflowResults.success && (
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h3 className="text-md font-semibold text-gray-900 mb-3">Results</h3>
            <div className="space-y-2 text-sm">
              <div>
                <span className="font-medium text-gray-700">Output Directory:</span>{' '}
                <span className="font-mono text-gray-900">{workflowResults.output_dir}</span>
              </div>
              {workflowResults.results_file && (
                <div>
                  <span className="font-medium text-gray-700">Results File:</span>{' '}
                  <span className="font-mono text-gray-900">{workflowResults.results_file}</span>
                </div>
              )}
              {workflowResults.traces.length > 0 && (
                <div>
                  <span className="font-medium text-gray-700">Trace Files:</span>
                  <ul className="list-disc list-inside mt-1">
                    {workflowResults.traces.map((trace, index) => (
                      <li key={index} className="font-mono text-xs text-gray-900">{trace}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
