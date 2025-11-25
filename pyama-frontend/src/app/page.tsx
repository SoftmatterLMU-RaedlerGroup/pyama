"use client";

import { useEffect, useState, useCallback, useRef } from "react";

// =============================================================================
// TYPES
// =============================================================================

type PickerKey =
  | "microscopy"
  | "processingOutput"
  | "sampleYaml"
  | "processingYaml"
  | "mergeOutput"
  | "loadSamplesYaml"
  | "saveSamplesYaml";

type PickerMode = "select" | "save";

type PickerConfig = {
  key: PickerKey;
  title: string;
  description: string;
  accept?: string;
  directory?: boolean;
  filterExtensions?: string[];
  mode?: PickerMode;
  defaultFileName?: string;
};

type PickerSelections = Record<PickerKey, string | null>;

type FileItem = {
  name: string;
  path: string;
  is_directory: boolean;
  is_file: boolean;
  size_bytes?: number | null;
  extension?: string | null;
};

type MicroscopyMetadata = {
  n_fovs?: number;
  n_frames?: number;
  n_channels?: number;
  channel_names?: string[];
  time_units?: string;
  pixel_size_um?: number;
};

type WorkflowParameters = {
  fov_start: number;
  fov_end: number;
  batch_size: number;
  n_workers: number;
  background_weight: number;
};

type Sample = {
  id: string;
  name: string;
  fovs: string;
};

type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled" | "not_found";

type JobProgress = {
  current: number;
  total: number;
  percentage: number;
};

type JobState = {
  job_id: string;
  status: JobStatus;
  progress: JobProgress | null;
  message: string;
};

// =============================================================================
// COMPONENT
// =============================================================================

export default function Home() {
  // File picker state
  const [activePicker, setActivePicker] = useState<PickerConfig | null>(null);
  const [selections, setSelections] = useState<PickerSelections>({
    microscopy: null,
    processingOutput: null,
    sampleYaml: null,
    processingYaml: null,
    mergeOutput: null,
    loadSamplesYaml: null,
    saveSamplesYaml: null,
  });
  const [currentPath, setCurrentPath] = useState(
    process.env.NEXT_PUBLIC_DEFAULT_BROWSE_PATH || "/home"
  );
  const [items, setItems] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveFileName, setSaveFileName] = useState("samples.yaml");

  // Status and metadata
  const [statusMessage, setStatusMessage] = useState("Ready");
  const [metadata, setMetadata] = useState<MicroscopyMetadata | null>(null);
  const [loadingMetadata, setLoadingMetadata] = useState(false);
  const [channelNames, setChannelNames] = useState<string[]>([]);

  // Features
  const [availablePhaseFeatures, setAvailablePhaseFeatures] = useState<string[]>([]);
  const [availableFlFeatures, setAvailableFlFeatures] = useState<string[]>([]);

  // Phase contrast selection
  const [phaseChannel, setPhaseChannel] = useState<number | null>(null);
  const [pcFeaturesSelected, setPcFeaturesSelected] = useState<string[]>([]);

  // Fluorescence selection
  const [flChannelSelection, setFlChannelSelection] = useState<number | null>(null);
  const [flFeatureSelection, setFlFeatureSelection] = useState<string | null>(null);
  const [flMapping, setFlMapping] = useState<Record<number, string[]>>({});

  // Parameters
  const [parameters, setParameters] = useState<WorkflowParameters>({
    fov_start: 0,
    fov_end: -1,
    batch_size: 2,
    n_workers: 2,
    background_weight: 1.0,
  });
  const [manualMode, setManualMode] = useState(false);

  // Split mode
  const [splitMode, setSplitMode] = useState(false);

  // Job state
  const [currentJob, setCurrentJob] = useState<JobState | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Samples for merge
  const [samples, setSamples] = useState<Sample[]>([
    { id: "1", name: "control", fovs: "0-5" },
    { id: "2", name: "drug_a", fovs: "6-11" },
    { id: "3", name: "rescue", fovs: "12-17" },
  ]);
  const [editingSampleId, setEditingSampleId] = useState<string | null>(null);

  // Merge state
  const [isMerging, setIsMerging] = useState(false);

  // Backend configuration
  const backendBase = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const apiBase = `${backendBase.replace(/\/$/, "")}/api/v1`;

  // =============================================================================
  // UTILITY FUNCTIONS
  // =============================================================================

  const formatName = (fullPath: string | null) => {
    if (!fullPath) return null;
    const normalized = fullPath.replace(/\\/g, "/");
    const parts = normalized.split("/").filter(Boolean);
    return parts[parts.length - 1] || fullPath;
  };

  const getStartPath = (config: PickerConfig) => {
    const prior = selections[config.key];
    if (prior) {
      const normalized = prior.replace(/\\/g, "/");
      if (config.directory) return normalized;
      const parent = normalized.split("/").slice(0, -1).join("/") || "/";
      return parent;
    }
    return process.env.NEXT_PUBLIC_DEFAULT_BROWSE_PATH || "/home";
  };

  const selectionLabel = (key: PickerKey, fallback: string) =>
    formatName(selections[key]) || fallback;

  const generateSampleId = () => `sample_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

  // =============================================================================
  // FILE PICKER
  // =============================================================================

  const openPicker = (config: PickerConfig) => setActivePicker(config);
  const closePicker = () => setActivePicker(null);

  const loadDirectory = async (path: string, pickerOverride?: PickerConfig | null) => {
    const picker = pickerOverride ?? activePicker;
    if (!picker) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/processing/list-directory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          directory_path: path,
          include_hidden: false,
          filter_extensions: picker.filterExtensions ?? null,
        }),
      });
      if (!response.ok) {
        throw new Error(`Backend responded with ${response.status}`);
      }
      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error || "Failed to list directory");
      }
      setItems(data.items || []);
      setCurrentPath(data.directory_path || path);
    } catch (err) {
      setItems([]);
      setError(err instanceof Error ? err.message : "Failed to list directory");
    } finally {
      setLoading(false);
    }
  };

  const goUp = () => {
    if (!currentPath || !activePicker) return;
    const normalized = currentPath.replace(/\\/g, "/");
    const parent = normalized.split("/").slice(0, -1).join("/") || "/";
    setCurrentPath(parent);
    loadDirectory(parent);
  };

  const handleSelect = async (path: string) => {
    if (!activePicker) return;
    const key = activePicker.key;

    // Handle save mode - path is a directory, append filename
    if (activePicker.mode === "save") {
      const fullPath = `${path.replace(/\/$/, "")}/${saveFileName}`;
      setSelections((prev) => ({ ...prev, [key]: fullPath }));
      setActivePicker(null);

      if (key === "saveSamplesYaml") {
        await saveSamplesToServer(fullPath);
      }
      return;
    }

    setSelections((prev) => ({ ...prev, [key]: path }));
    setActivePicker(null);

    if (key === "microscopy") {
      setPhaseChannel(null);
      setPcFeaturesSelected([]);
      setFlChannelSelection(null);
      setFlFeatureSelection(null);
      setFlMapping({});
      loadMicroscopyMetadata(path);
    } else if (key === "loadSamplesYaml") {
      await loadSamplesFromServer(path);
    }
  };

  useEffect(() => {
    if (!activePicker) return;
    const startPath = getStartPath(activePicker);
    setCurrentPath(startPath);
    loadDirectory(startPath, activePicker);
  }, [activePicker]);

  // =============================================================================
  // FEATURES LOADING
  // =============================================================================

  const loadFeatures = async () => {
    let phase = availablePhaseFeatures;
    let fl = availableFlFeatures;
    try {
      const response = await fetch(`${apiBase}/processing/features`);
      if (!response.ok) return { phase, fl };
      const data = await response.json();
      if (Array.isArray(data.phase_features) && data.phase_features.length) {
        phase = data.phase_features;
        setAvailablePhaseFeatures(data.phase_features);
      }
      if (Array.isArray(data.fluorescence_features) && data.fluorescence_features.length) {
        fl = data.fluorescence_features;
        setAvailableFlFeatures(data.fluorescence_features);
      }
    } catch {
      // Keep defaults on failure
    }
    return { phase, fl };
  };

  useEffect(() => {
    (async () => {
      const { phase, fl } = await loadFeatures();
      if (!pcFeaturesSelected.length && phase.length) {
        setPcFeaturesSelected(phase.slice(0, Math.min(3, phase.length)));
      }
      if (!availableFlFeatures.length && fl.length) {
        setAvailableFlFeatures(fl);
      }
    })();
  }, []);

  // =============================================================================
  // MICROSCOPY METADATA
  // =============================================================================

  const loadMicroscopyMetadata = async (filePath: string, split = splitMode) => {
    setLoadingMetadata(true);
    setStatusMessage("Loading microscopy metadata...");
    setMetadata(null);
    setChannelNames([]);
    try {
      const { phase, fl } = await loadFeatures();
      const response = await fetch(`${apiBase}/processing/load-metadata`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: filePath, split_mode: split }),
      });
      if (!response.ok) {
        throw new Error(`Backend responded with ${response.status}`);
      }
      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error || "Failed to load metadata");
      }
      const meta = data.metadata || {};
      const names: string[] = Array.isArray(meta.channel_names) ? meta.channel_names : [];
      setMetadata(meta);
      setChannelNames(names);

      const phaseDefaults = phase.length ? phase.slice(0, Math.min(3, phase.length)) : [];
      setPcFeaturesSelected(phaseDefaults);
      setPhaseChannel(names.length ? 0 : null);

      setFlMapping({});
      setFlChannelSelection(names.length ? 0 : null);
      setFlFeatureSelection(fl.length ? fl[0] : null);

      // Update fov_end based on metadata
      if (typeof meta.n_fovs === "number") {
        setParameters((prev) => ({
          ...prev,
          fov_end: meta.n_fovs - 1,
        }));
      }

      const fovsText = typeof meta.n_fovs === "number" ? `${meta.n_fovs} FOVs` : "FOVs unknown";
      setStatusMessage(`Loaded metadata for ${formatName(filePath)} (${fovsText})${split ? " [split]" : ""}`);
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Failed to load metadata");
    } finally {
      setLoadingMetadata(false);
    }
  };

  const toggleSplitMode = () => {
    const next = !splitMode;
    setSplitMode(next);
    if (selections.microscopy) {
      loadMicroscopyMetadata(selections.microscopy, next);
    }
  };

  // =============================================================================
  // CHANNEL SELECTION
  // =============================================================================

  const handlePhaseChange = (value: string) => {
    const parsed = Number(value);
    setPhaseChannel(Number.isNaN(parsed) ? null : parsed);
  };

  const togglePcFeature = (feature: string) => {
    setPcFeaturesSelected((prev) =>
      prev.includes(feature) ? prev.filter((f) => f !== feature) : [...prev, feature]
    );
  };

  const addFlMapping = () => {
    if (flChannelSelection === null || !flFeatureSelection) return;
    setFlMapping((prev) => {
      const existing = prev[flChannelSelection] || [];
      if (existing.includes(flFeatureSelection)) return prev;
      return {
        ...prev,
        [flChannelSelection]: [...existing, flFeatureSelection],
      };
    });
  };

  const removeFlMapping = (channel: number, feature: string) => {
    setFlMapping((prev) => {
      const current = prev[channel] || [];
      const updated = current.filter((f) => f !== feature);
      const next = { ...prev };
      if (updated.length) {
        next[channel] = updated;
      } else {
        delete next[channel];
      }
      return next;
    });
  };

  // =============================================================================
  // PARAMETERS
  // =============================================================================

  const handleParameterChange = (key: keyof WorkflowParameters, value: string) => {
    const numValue = key === "background_weight" ? parseFloat(value) : parseInt(value, 10);
    if (!isNaN(numValue)) {
      setParameters((prev) => ({ ...prev, [key]: numValue }));
    }
  };

  const parameterConfig: { key: keyof WorkflowParameters; label: string; type: "int" | "float" }[] = [
    { key: "fov_start", label: "FOV Start", type: "int" },
    { key: "fov_end", label: "FOV End (-1 for all)", type: "int" },
    { key: "batch_size", label: "Batch Size", type: "int" },
    { key: "n_workers", label: "Workers", type: "int" },
    { key: "background_weight", label: "Background Weight", type: "float" },
  ];

  // =============================================================================
  // WORKFLOW EXECUTION
  // =============================================================================

  const validateWorkflow = (): string | null => {
    if (!selections.microscopy) return "Please select a microscopy file";
    if (!selections.processingOutput) return "Please select an output directory";
    if (phaseChannel === null && Object.keys(flMapping).length === 0) {
      return "Please configure at least one channel (phase or fluorescence)";
    }
    if (phaseChannel !== null && pcFeaturesSelected.length === 0) {
      return "Please select at least one phase feature";
    }
    if (parameters.batch_size < 1) return "Batch size must be at least 1";
    if (parameters.n_workers < 1) return "Number of workers must be at least 1";
    return null;
  };

  const startWorkflow = async () => {
    const validationError = validateWorkflow();
    if (validationError) {
      setStatusMessage(`Error: ${validationError}`);
      return;
    }

    setIsProcessing(true);
    setStatusMessage("Starting workflow...");

    try {
      // Build channel configuration
      const phaseConfig = phaseChannel !== null && pcFeaturesSelected.length > 0
        ? { channel: phaseChannel, features: pcFeaturesSelected }
        : null;

      const flConfigs = Object.entries(flMapping).map(([channel, features]) => ({
        channel: parseInt(channel, 10),
        features,
      }));

      const response = await fetch(`${apiBase}/processing/workflow/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          microscopy_path: selections.microscopy,
          output_dir: selections.processingOutput,
          channels: {
            phase: phaseConfig,
            fluorescence: flConfigs,
          },
          parameters: {
            fov_start: parameters.fov_start,
            fov_end: parameters.fov_end,
            batch_size: parameters.batch_size,
            n_workers: parameters.n_workers,
          },
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Failed to start workflow");
      }

      setCurrentJob({
        job_id: data.job_id,
        status: "pending",
        progress: null,
        message: data.message || "Workflow started",
      });
      setStatusMessage(`Workflow started (Job: ${data.job_id})`);

      // Start polling for status
      startPolling(data.job_id);
    } catch (err) {
      setIsProcessing(false);
      setStatusMessage(err instanceof Error ? err.message : "Failed to start workflow");
    }
  };

  const startPolling = (jobId: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${apiBase}/processing/workflow/status/${jobId}`);
        const data = await response.json();

        setCurrentJob({
          job_id: data.job_id,
          status: data.status,
          progress: data.progress,
          message: data.message,
        });

        // Update status message with progress
        if (data.progress) {
          setStatusMessage(
            `Processing: ${data.progress.current}/${data.progress.total} FOVs (${data.progress.percentage.toFixed(1)}%)`
          );
        } else {
          setStatusMessage(data.message || `Status: ${data.status}`);
        }

        // Stop polling if job is done
        if (["completed", "failed", "cancelled", "not_found"].includes(data.status)) {
          stopPolling();
          setIsProcessing(false);
          if (data.status === "completed") {
            setStatusMessage("Workflow completed successfully!");
          } else if (data.status === "cancelled") {
            setStatusMessage("Workflow was cancelled");
          } else if (data.status === "failed") {
            setStatusMessage(`Workflow failed: ${data.message}`);
          }
        }
      } catch (err) {
        console.error("Failed to poll job status:", err);
      }
    }, 1000);
  };

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  const cancelWorkflow = async () => {
    if (!currentJob) return;

    try {
      const response = await fetch(`${apiBase}/processing/workflow/cancel/${currentJob.job_id}`, {
        method: "POST",
      });
      const data = await response.json();

      if (data.success) {
        setStatusMessage("Cancelling workflow...");
      } else {
        setStatusMessage(`Failed to cancel: ${data.message}`);
      }
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Failed to cancel workflow");
    }
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => stopPolling();
  }, []);

  // =============================================================================
  // SAMPLES MANAGEMENT
  // =============================================================================

  const addSample = () => {
    const newSample: Sample = {
      id: generateSampleId(),
      name: "",
      fovs: "",
    };
    setSamples((prev) => [...prev, newSample]);
    setEditingSampleId(newSample.id);
  };

  const removeSample = (id: string) => {
    setSamples((prev) => prev.filter((s) => s.id !== id));
    if (editingSampleId === id) {
      setEditingSampleId(null);
    }
  };

  const updateSample = (id: string, field: "name" | "fovs", value: string) => {
    setSamples((prev) =>
      prev.map((s) => (s.id === id ? { ...s, [field]: value } : s))
    );
  };

  const saveSamplesToServer = async (filePath: string) => {
    const validSamples = samples.filter((s) => s.name && s.fovs);
    if (validSamples.length === 0) {
      setStatusMessage("No valid samples to save");
      return;
    }

    setStatusMessage("Saving samples...");

    try {
      const response = await fetch(`${apiBase}/processing/samples/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_path: filePath,
          samples: validSamples.map((s) => ({ name: s.name, fovs: s.fovs })),
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Failed to save samples");
      }

      setStatusMessage(data.message || `Saved ${validSamples.length} samples to ${formatName(filePath)}`);
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Failed to save samples");
    }
  };

  const loadSamplesFromServer = async (filePath: string) => {
    setStatusMessage("Loading samples...");

    try {
      const response = await fetch(`${apiBase}/processing/samples/load`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: filePath }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Failed to load samples");
      }

      if (data.samples && data.samples.length > 0) {
        const loadedSamples: Sample[] = data.samples.map((s: { name: string; fovs: string }) => ({
          id: generateSampleId(),
          name: s.name,
          fovs: s.fovs,
        }));
        setSamples(loadedSamples);
        setStatusMessage(`Loaded ${loadedSamples.length} samples from ${formatName(filePath)}`);
      } else {
        setStatusMessage("No samples found in YAML file");
      }
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Failed to load samples");
    }
  };

  const openSaveYamlPicker = () => {
    setSaveFileName("samples.yaml");
    openPicker({
      key: "saveSamplesYaml",
      title: "Save Samples YAML",
      description: "Choose a directory to save the samples configuration",
      directory: true,
      mode: "save",
      defaultFileName: "samples.yaml",
    });
  };

  const openLoadYamlPicker = () => {
    openPicker({
      key: "loadSamplesYaml",
      title: "Load Samples YAML",
      description: "Select a samples YAML file to load",
      filterExtensions: [".yaml", ".yml"],
    });
  };

  // =============================================================================
  // MERGE EXECUTION
  // =============================================================================

  const validateMerge = (): string | null => {
    if (!selections.sampleYaml) return "Please select a sample YAML file";
    if (!selections.processingYaml) return "Please select a processing results YAML file";
    if (!selections.mergeOutput) return "Please select an output directory";
    return null;
  };

  const runMerge = async () => {
    const validationError = validateMerge();
    if (validationError) {
      setStatusMessage(`Error: ${validationError}`);
      return;
    }

    setIsMerging(true);
    setStatusMessage("Running merge...");

    try {
      const response = await fetch(`${apiBase}/processing/merge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sample_yaml: selections.sampleYaml,
          processing_results_yaml: selections.processingYaml,
          output_dir: selections.mergeOutput,
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Failed to merge results");
      }

      setStatusMessage(`Merge completed: ${data.merged_files?.length || 0} files created`);
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Failed to merge results");
    } finally {
      setIsMerging(false);
    }
  };

  // =============================================================================
  // RENDER
  // =============================================================================

  return (
    <div className="relative min-h-screen bg-neutral-950 text-neutral-50">
      {/* File Picker Modal */}
      {activePicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={closePicker}
          />
          <div className="relative w-full max-w-3xl overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-900 shadow-2xl">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-neutral-800 px-5 py-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-neutral-50">{activePicker.title}</p>
                <p className="text-xs text-neutral-400">{activePicker.description}</p>
              </div>
              <div className="flex items-center gap-2">
                {activePicker.directory && (
                  <button
                    className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:bg-neutral-700"
                    onClick={() => handleSelect(currentPath)}
                    disabled={loading || (activePicker.mode === "save" && !saveFileName.trim())}
                  >
                    {activePicker.mode === "save" ? "Save here" : "Use this folder"}
                  </button>
                )}
                <button
                  className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:border-neutral-500"
                  onClick={closePicker}
                >
                  Close
                </button>
              </div>
            </div>

            <div className="space-y-3 px-5 py-4">
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2">
                  <span className="text-xs font-medium text-neutral-400">Path</span>
                  <div className="truncate text-sm text-neutral-100">{currentPath}</div>
                </div>
                <button
                  className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:border-neutral-500"
                  onClick={goUp}
                  disabled={!currentPath || currentPath === "/"}
                >
                  Up
                </button>
                <button
                  className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:border-neutral-500"
                  onClick={() => loadDirectory(currentPath)}
                  disabled={loading}
                >
                  Refresh
                </button>
              </div>

              {error && (
                <div className="rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
                  {error}
                </div>
              )}

              <div className="max-h-[24rem] overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900">
                <table className="w-full text-sm text-neutral-100">
                  <thead className="border-b border-neutral-800 bg-neutral-800 text-left text-xs uppercase tracking-wide text-neutral-400">
                    <tr>
                      <th className="px-3 py-2 font-semibold">Name</th>
                      <th className="px-3 py-2 font-semibold">Type</th>
                      <th className="px-3 py-2 text-right font-semibold">Size</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-800">
                    {loading ? (
                      <tr>
                        <td colSpan={3} className="px-3 py-8 text-center text-sm text-neutral-400">
                          Loading directory...
                        </td>
                      </tr>
                    ) : items.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="px-3 py-8 text-center text-sm text-neutral-400">
                          No items found in this location.
                        </td>
                      </tr>
                    ) : (
                      items.map((item) => (
                        <tr
                          key={item.path}
                          className="cursor-pointer hover:bg-neutral-800/70"
                          onClick={() => {
                            if (item.is_directory) {
                              setCurrentPath(item.path);
                              loadDirectory(item.path);
                            } else if (!activePicker?.directory) {
                              handleSelect(item.path);
                            }
                          }}
                        >
                          <td className="px-3 py-2 font-medium text-neutral-50">{item.name}</td>
                          <td className="px-3 py-2 text-neutral-300">
                            {item.is_directory ? "Folder" : item.extension || "File"}
                          </td>
                          <td className="px-3 py-2 text-right text-neutral-300">
                            {item.is_directory
                              ? "-"
                              : typeof item.size_bytes === "number"
                                ? `${(item.size_bytes / 1024 / 1024).toFixed(2)} MB`
                                : ""}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Save mode: filename input */}
              {activePicker?.mode === "save" && (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-neutral-400">Filename:</span>
                  <input
                    type="text"
                    value={saveFileName}
                    onChange={(e) => setSaveFileName(e.target.value)}
                    className="flex-1 rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm text-neutral-100 focus:border-neutral-500 focus:outline-none"
                    placeholder="samples.yaml"
                  />
                </div>
              )}

              <p className="text-xs text-neutral-400">
                {activePicker?.mode === "save"
                  ? 'Navigate to your target folder, enter filename, and click "Use this folder" to save.'
                  : activePicker?.directory
                    ? 'Navigate to your target folder and click "Use this folder" to confirm.'
                    : "Click a file to select it. Click folders to navigate."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="relative mx-auto max-w-7xl px-6 py-12">
        {/* Header */}
        <div className="mb-10 flex flex-wrap items-start justify-between gap-6">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-neutral-400">
              Processing
            </p>
            <h1 className="text-4xl font-semibold leading-tight text-neutral-50">
              PyAMA Processing Workspace
            </h1>
            <p className="max-w-3xl text-sm text-neutral-300">
              Configure and run microscopy image processing workflows with real-time progress tracking.
            </p>
          </div>
          <div className="rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-3 text-sm text-neutral-200 shadow-sm">
            <p className="font-semibold text-neutral-50">Status</p>
            <p className="text-xs text-neutral-400">{statusMessage}</p>
          </div>
        </div>

        {/* Main Grid */}
        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          {/* Workflow Section */}
          <section className="rounded-2xl border border-neutral-900 bg-neutral-900 p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-2xl font-semibold uppercase tracking-[0.12em] text-neutral-50">
                Workflow
              </h2>
              {isProcessing && (
                <span className="animate-pulse rounded-full border border-blue-500/50 bg-blue-500/20 px-3 py-1 text-xs font-semibold text-blue-200">
                  Processing...
                </span>
              )}
            </div>

            <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
              {/* Input Section */}
              <div className="space-y-5 rounded-xl border border-neutral-800 bg-neutral-900 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-neutral-50">Input</p>
                    <p className="text-xs text-neutral-400">Microscopy file and channel selection</p>
                  </div>
                  <button
                    type="button"
                    className="group inline-flex items-center gap-2 rounded-full border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:border-neutral-500"
                    onClick={toggleSplitMode}
                  >
                    <span>Split files</span>
                    <div
                      className={`h-5 w-9 rounded-full border transition ${
                        splitMode ? "border-neutral-500 bg-neutral-700" : "border-neutral-700 bg-neutral-800"
                      }`}
                    >
                      <div
                        className={`h-4 w-4 rounded-full bg-neutral-50 transition ${
                          splitMode ? "translate-x-4" : "translate-x-0.5"
                        }`}
                      />
                    </div>
                  </button>
                </div>

                {/* Microscopy File Selection */}
                <div className="rounded-lg border border-dashed border-neutral-700 bg-neutral-900 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-neutral-400">
                        Microscopy File
                      </p>
                      <p className="text-sm font-semibold text-neutral-50">
                        {selectionLabel("microscopy", "No file selected")}
                      </p>
                      {selections.microscopy && (
                        <p className="text-xs text-neutral-500 truncate max-w-xs">{selections.microscopy}</p>
                      )}
                      <p className="text-xs text-neutral-400">Supports ND2 / CZI / OME-TIFF</p>
                      {loadingMetadata && (
                        <p className="text-xs text-neutral-500">Loading metadata...</p>
                      )}
                      {metadata && (
                        <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-neutral-300">
                          <span>Channels: {metadata.n_channels ?? channelNames.length}</span>
                          <span>FOVs: {metadata.n_fovs ?? "?"}</span>
                          <span>Frames: {metadata.n_frames ?? "?"}</span>
                          <span>Time: {metadata.time_units || "unknown"}</span>
                        </div>
                      )}
                    </div>
                    <button
                      className="rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:bg-neutral-700 disabled:opacity-50"
                      onClick={() =>
                        openPicker({
                          key: "microscopy",
                          title: "Choose microscopy file",
                          description: "Select an ND2 / CZI / OME-TIFF file",
                          filterExtensions: [".nd2", ".czi", ".ome.tif", ".ome.tiff", ".tif", ".tiff"],
                        })
                      }
                      disabled={isProcessing}
                    >
                      Browse
                    </button>
                  </div>
                </div>

                {/* Channel Configuration */}
                <div className="space-y-3 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-neutral-50">Channels</h3>
                    {channelNames.length > 0 && (
                      <span className="text-xs text-neutral-400">{channelNames.length} available</span>
                    )}
                  </div>

                  {channelNames.length > 0 && (
                    <div className="flex flex-wrap gap-2 text-[11px] text-neutral-300">
                      {channelNames.map((name, idx) => (
                        <span
                          key={`${name}-${idx}`}
                          className="rounded-full border border-neutral-700 bg-neutral-800 px-3 py-1"
                        >
                          {idx}: {name || "Channel"}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Phase Contrast */}
                  <div className="rounded-md border border-neutral-800 bg-neutral-900 p-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-400">
                      <span className="text-sm font-semibold text-neutral-50">Phase Contrast</span>
                      <select
                        className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] text-neutral-100 disabled:opacity-50"
                        value={phaseChannel ?? ""}
                        onChange={(e) => handlePhaseChange(e.target.value)}
                        disabled={isProcessing || channelNames.length === 0}
                      >
                        <option value="">Select channel</option>
                        {channelNames.map((name, idx) => (
                          <option key={`${name}-${idx}`} value={idx}>
                            {idx}: {name || "Channel"}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {availablePhaseFeatures.length > 0 ? (
                        availablePhaseFeatures.map((feature) => {
                          const active = pcFeaturesSelected.includes(feature);
                          return (
                            <button
                              type="button"
                              key={feature}
                              onClick={() => togglePcFeature(feature)}
                              disabled={isProcessing}
                              className={`rounded-full border px-3 py-1 text-[11px] font-semibold transition disabled:opacity-50 ${
                                active
                                  ? "border-neutral-500 bg-neutral-700 text-neutral-50"
                                  : "border-neutral-800 bg-neutral-900 text-neutral-400 hover:border-neutral-700"
                              }`}
                            >
                              {feature}
                            </button>
                          );
                        })
                      ) : (
                        <span className="text-[11px] text-neutral-500">
                          Load a microscopy file to choose phase features.
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Fluorescence */}
                  <div className="space-y-3 rounded-md border border-neutral-800 bg-neutral-900 p-3">
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span className="text-sm font-semibold text-neutral-50">Fluorescence</span>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <select
                        className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs text-neutral-100 disabled:opacity-50"
                        value={flChannelSelection ?? ""}
                        onChange={(e) => setFlChannelSelection(e.target.value === "" ? null : Number(e.target.value))}
                        disabled={isProcessing || channelNames.length === 0}
                      >
                        <option value="">Select channel</option>
                        {channelNames.map((name, idx) => (
                          <option key={`${name}-${idx}`} value={idx}>
                            {idx}: {name || "Channel"}
                          </option>
                        ))}
                      </select>
                      <select
                        className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs text-neutral-100 disabled:opacity-50"
                        value={flFeatureSelection ?? ""}
                        onChange={(e) => setFlFeatureSelection(e.target.value || null)}
                        disabled={isProcessing || availableFlFeatures.length === 0}
                      >
                        <option value="">Select feature</option>
                        {availableFlFeatures.map((feature) => (
                          <option key={feature} value={feature}>
                            {feature}
                          </option>
                        ))}
                      </select>
                      <button
                        className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1 text-xs font-semibold text-neutral-100 hover:bg-neutral-700 disabled:opacity-50"
                        onClick={addFlMapping}
                        disabled={isProcessing || flChannelSelection === null || !flFeatureSelection}
                      >
                        Add
                      </button>
                    </div>

                    {Object.keys(flMapping).length > 0 && (
                      <div className="space-y-2">
                        {Object.entries(flMapping)
                          .sort(([a], [b]) => Number(a) - Number(b))
                          .map(([channel, features]) =>
                            features.map((feature) => (
                              <div
                                key={`${channel}-${feature}`}
                                className="flex items-center justify-between rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2"
                              >
                                <div className="text-[13px] text-neutral-50">
                                  {channel}: {channelNames[Number(channel)] || "Channel"}{" "}
                                  <span className="mx-1 text-neutral-400">→</span>
                                  <span className="font-semibold">{feature}</span>
                                </div>
                                <button
                                  className="rounded-full border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] text-neutral-200 hover:bg-neutral-700 disabled:opacity-50"
                                  onClick={() => removeFlMapping(Number(channel), feature)}
                                  disabled={isProcessing}
                                >
                                  Remove
                                </button>
                              </div>
                            ))
                          )}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Output Section */}
              <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-neutral-50">Output</p>
                    <p className="text-xs text-neutral-400">Destination, parameters, and actions</p>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  {/* Output Directory */}
                  <div className="rounded-lg border border-dashed border-neutral-700 bg-neutral-900 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-neutral-400">
                          Save Directory
                        </p>
                        <p className="text-sm font-semibold text-neutral-50">
                          {selectionLabel("processingOutput", "No directory selected")}
                        </p>
                        {selections.processingOutput && (
                          <p className="text-xs text-neutral-500 truncate max-w-[180px]">
                            {selections.processingOutput}
                          </p>
                        )}
                      </div>
                      <button
                        className="rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:bg-neutral-700 disabled:opacity-50"
                        onClick={() =>
                          openPicker({
                            key: "processingOutput",
                            title: "Choose output directory",
                            description: "Select the processing output folder",
                            directory: true,
                          })
                        }
                        disabled={isProcessing}
                      >
                        Browse
                      </button>
                    </div>
                  </div>

                  {/* Parameters */}
                  <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-neutral-50">Parameters</h3>
                      <button
                        className={`rounded-md border px-2 py-1 text-[11px] transition ${
                          manualMode
                            ? "border-blue-500/50 bg-blue-500/20 text-blue-200"
                            : "border-neutral-700 bg-neutral-800 text-neutral-200"
                        }`}
                        onClick={() => setManualMode(!manualMode)}
                        disabled={isProcessing}
                      >
                        {manualMode ? "Manual Mode" : "Auto Mode"}
                      </button>
                    </div>
                    <div className="divide-y divide-neutral-800">
                      {parameterConfig.map(({ key, label, type }) => (
                        <div
                          key={key}
                          className="grid grid-cols-[1.2fr_1fr] items-center gap-3 py-2 text-sm"
                        >
                          <span className="text-neutral-200">{label}</span>
                          {manualMode ? (
                            <input
                              type="number"
                              step={type === "float" ? "0.1" : "1"}
                              value={parameters[key]}
                              onChange={(e) => handleParameterChange(key, e.target.value)}
                              disabled={isProcessing}
                              className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-right text-neutral-200 focus:border-neutral-500 focus:outline-none disabled:opacity-50"
                            />
                          ) : (
                            <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-right text-neutral-200">
                              {parameters[key]}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Workflow Controls */}
                  <div className="flex flex-col gap-3 rounded-lg border border-neutral-800 bg-neutral-900 p-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        className="flex-1 rounded-lg border border-neutral-700 bg-neutral-800 px-4 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        onClick={startWorkflow}
                        disabled={isProcessing}
                      >
                        {isProcessing ? "Processing..." : "Start Complete Workflow"}
                      </button>
                      <button
                        className="rounded-lg border border-neutral-700 bg-neutral-800 px-4 py-3 text-sm font-semibold text-neutral-200 hover:border-red-500/50 hover:text-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        onClick={cancelWorkflow}
                        disabled={!isProcessing}
                      >
                        Cancel
                      </button>
                    </div>

                    {/* Progress Bar */}
                    <div className="h-2 rounded-full bg-neutral-800 overflow-hidden">
                      {currentJob?.progress ? (
                        <div
                          className="h-full rounded-full bg-blue-500 transition-all duration-300"
                          style={{ width: `${currentJob.progress.percentage}%` }}
                        />
                      ) : isProcessing ? (
                        <div className="h-full w-full bg-gradient-to-r from-neutral-800 via-blue-500/50 to-neutral-800 animate-pulse" />
                      ) : (
                        <div className="h-full w-0 rounded-full bg-neutral-200" />
                      )}
                    </div>

                    <p className="text-xs text-neutral-400">
                      {currentJob?.progress
                        ? `${currentJob.progress.current}/${currentJob.progress.total} FOVs (${currentJob.progress.percentage.toFixed(1)}%)`
                        : isProcessing
                          ? "Processing in progress..."
                          : "Ready to start workflow"}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Merge Section */}
          <section className="rounded-2xl border border-neutral-900 bg-neutral-900 p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-2xl font-semibold uppercase tracking-[0.12em] text-neutral-50">
                Merge
              </h2>
              {isMerging && (
                <span className="animate-pulse rounded-full border border-green-500/50 bg-green-500/20 px-3 py-1 text-xs font-semibold text-green-200">
                  Merging...
                </span>
              )}
            </div>

            <div className="space-y-4">
              {/* Assign FOVs */}
              <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-neutral-50">Assign FOVs</p>
                    <p className="text-xs text-neutral-400">Map samples to FOV ranges</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-[11px]">
                    <button
                      className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-neutral-200 hover:bg-neutral-700"
                      onClick={addSample}
                    >
                      Add Sample
                    </button>
                  </div>
                </div>

                <div className="overflow-hidden rounded-lg border border-neutral-800">
                  <table className="w-full text-sm text-neutral-100">
                    <thead className="bg-neutral-800 text-left text-[13px] text-neutral-300">
                      <tr>
                        <th className="px-3 py-2 font-semibold">Sample Name</th>
                        <th className="px-3 py-2 font-semibold">FOVs (e.g., 0-5, 7, 9-11)</th>
                        <th className="w-16 px-3 py-2"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800 bg-neutral-900">
                      {samples.map((sample) => (
                        <tr key={sample.id} className="hover:bg-neutral-800/60">
                          <td className="px-3 py-2">
                            <input
                              type="text"
                              value={sample.name}
                              onChange={(e) => updateSample(sample.id, "name", e.target.value)}
                              placeholder="Sample name"
                              className="w-full rounded border border-transparent bg-transparent px-1 py-0.5 font-semibold text-neutral-50 placeholder-neutral-500 focus:border-neutral-700 focus:outline-none"
                            />
                          </td>
                          <td className="px-3 py-2">
                            <input
                              type="text"
                              value={sample.fovs}
                              onChange={(e) => updateSample(sample.id, "fovs", e.target.value)}
                              placeholder="0-5, 7, 9-11"
                              className="w-full rounded border border-transparent bg-transparent px-1 py-0.5 text-neutral-300 placeholder-neutral-500 focus:border-neutral-700 focus:outline-none"
                            />
                          </td>
                          <td className="px-3 py-2">
                            <button
                              onClick={() => removeSample(sample.id)}
                              className="rounded px-2 py-1 text-[11px] text-neutral-400 hover:bg-neutral-700 hover:text-red-300"
                            >
                              ×
                            </button>
                          </td>
                        </tr>
                      ))}
                      {samples.length === 0 && (
                        <tr>
                          <td colSpan={3} className="px-3 py-4 text-center text-neutral-500">
                            No samples defined. Click "Add Sample" to create one.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-neutral-300">
                  <button
                    className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 hover:bg-neutral-700"
                    onClick={openLoadYamlPicker}
                  >
                    Load from YAML
                  </button>
                  <button
                    className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 hover:bg-neutral-700"
                    onClick={openSaveYamlPicker}
                  >
                    Save to YAML
                  </button>
                </div>
              </div>

              {/* Merge Samples */}
              <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
                <div className="mb-3 space-y-1">
                  <p className="text-sm font-semibold text-neutral-50">Merge Samples</p>
                  <p className="text-xs text-neutral-400">Combine processing results with sample definitions</p>
                </div>

                <div className="space-y-3 text-sm text-neutral-200">
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span>Sample YAML</span>
                      <button
                        className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] hover:bg-neutral-700 disabled:opacity-50"
                        onClick={() =>
                          openPicker({
                            key: "sampleYaml",
                            title: "Choose sample.yaml",
                            description: "Select a samples YAML that defines FOV assignments",
                            filterExtensions: [".yaml", ".yml"],
                          })
                        }
                        disabled={isMerging}
                      >
                        Browse
                      </button>
                    </div>
                    <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-neutral-300 truncate">
                      {selections.sampleYaml || "sample.yaml (unselected)"}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span>Processing Results YAML</span>
                      <button
                        className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] hover:bg-neutral-700 disabled:opacity-50"
                        onClick={() =>
                          openPicker({
                            key: "processingYaml",
                            title: "Choose processing_results.yaml",
                            description: "Select the processing results YAML generated by workflow",
                            filterExtensions: [".yaml", ".yml"],
                          })
                        }
                        disabled={isMerging}
                      >
                        Browse
                      </button>
                    </div>
                    <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-neutral-300 truncate">
                      {selections.processingYaml || "processing_results.yaml (unselected)"}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span>Output Folder</span>
                      <button
                        className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] hover:bg-neutral-700 disabled:opacity-50"
                        onClick={() =>
                          openPicker({
                            key: "mergeOutput",
                            title: "Choose merge output folder",
                            description: "Select where merged CSVs should be written",
                            directory: true,
                          })
                        }
                        disabled={isMerging}
                      >
                        Browse
                      </button>
                    </div>
                    <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-neutral-300 truncate">
                      {selections.mergeOutput || "/output/path (unselected)"}
                    </div>
                  </div>

                  <button
                    className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-800 px-4 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={runMerge}
                    disabled={isMerging}
                  >
                    {isMerging ? "Merging..." : "Run Merge"}
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
