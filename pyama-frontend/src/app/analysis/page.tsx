"use client";

import { useEffect, useState, useRef, useCallback } from "react";

// =============================================================================
// TYPES
// =============================================================================

type ModelParameter = {
  name: string;
  default: number;
  bounds: [number, number];
};

type ModelInfo = {
  name: string;
  description: string;
  parameters: ModelParameter[];
};

type TraceDataPoint = {
  fov: number;
  cell: number;
  time: number;
  value: number;
  frame: number;
};

type FittingResult = {
  fov: number;
  cell: number;
  model_type: string;
  success: boolean;
  r_squared: number;
  [key: string]: number | string | boolean;
};

type JobProgress = {
  current: number;
  total: number;
  percentage: number;
};

// =============================================================================
// COMPONENT
// =============================================================================

export default function AnalysisPage() {
  // Backend config
  const backendBase = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const apiBase = `${backendBase.replace(/\/$/, "")}/api/v1`;

  // Data panel state
  const [csvPath, setCsvPath] = useState<string | null>(null);
  const [traceData, setTraceData] = useState<TraceDataPoint[]>([]);
  const [cellIds, setCellIds] = useState<string[]>([]);
  const [loadingData, setLoadingData] = useState(false);

  // Model state
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [modelParams, setModelParams] = useState<Record<string, { value: number; min: number; max: number }>>({});
  const [manualMode, setManualMode] = useState(false);

  // Fitting state
  const [fittingJobId, setFittingJobId] = useState<string | null>(null);
  const [fittingProgress, setFittingProgress] = useState<JobProgress | null>(null);
  const [isFitting, setIsFitting] = useState(false);
  const [fittingResults, setFittingResults] = useState<FittingResult[]>([]);
  const [resultsFile, setResultsFile] = useState<string | null>(null);

  // Quality panel state
  const [selectedResultIdx, setSelectedResultIdx] = useState(0);
  const [qualityFilter, setQualityFilter] = useState(false);
  const [qualityPage, setQualityPage] = useState(0);
  const resultsPerPage = 10;

  // Parameter panel state
  const [selectedHistParam, setSelectedHistParam] = useState<string>("");
  const [selectedScatterX, setSelectedScatterX] = useState<string>("");
  const [selectedScatterY, setSelectedScatterY] = useState<string>("");
  const [parameterNames, setParameterNames] = useState<string[]>([]);

  // Canvas refs
  const rawTraceCanvasRef = useRef<HTMLCanvasElement>(null);
  const fittedTraceCanvasRef = useRef<HTMLCanvasElement>(null);
  const histogramCanvasRef = useRef<HTMLCanvasElement>(null);
  const scatterCanvasRef = useRef<HTMLCanvasElement>(null);

  // File picker state
  const [showPicker, setShowPicker] = useState(false);
  const [pickerMode, setPickerMode] = useState<"csv" | "results">("csv");
  const [pickerPath, setPickerPath] = useState(process.env.NEXT_PUBLIC_DEFAULT_BROWSE_PATH || "/home");
  const [pickerItems, setPickerItems] = useState<Array<{ name: string; path: string; is_directory: boolean; is_file: boolean }>>([]);
  const [pickerLoading, setPickerLoading] = useState(false);

  // Status
  const [statusMessage, setStatusMessage] = useState("Ready");

  // Polling ref
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // =============================================================================
  // LOAD MODELS ON MOUNT
  // =============================================================================

  useEffect(() => {
    loadModels();
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  const loadModels = async () => {
    try {
      const response = await fetch(`${apiBase}/analysis/models`);
      const data = await response.json();
      if (data.models && data.models.length > 0) {
        setAvailableModels(data.models);
        setSelectedModel(data.models[0].name);
        initModelParams(data.models[0]);
      }
    } catch (err) {
      console.error("Failed to load models:", err);
    }
  };

  const initModelParams = (model: ModelInfo) => {
    const params: Record<string, { value: number; min: number; max: number }> = {};
    for (const param of model.parameters) {
      params[param.name] = {
        value: param.default,
        min: param.bounds[0],
        max: param.bounds[1],
      };
    }
    setModelParams(params);
  };

  // =============================================================================
  // FILE PICKER
  // =============================================================================

  const openPicker = (mode: "csv" | "results") => {
    setPickerMode(mode);
    setShowPicker(true);
    loadPickerDirectory(pickerPath);
  };

  const loadPickerDirectory = async (path: string) => {
    setPickerLoading(true);
    try {
      const response = await fetch(`${apiBase}/processing/list-directory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          directory_path: path,
          include_hidden: false,
          filter_extensions: [".csv"],
        }),
      });
      const data = await response.json();
      if (data.success) {
        setPickerItems(data.items || []);
        setPickerPath(data.directory_path || path);
      }
    } catch (err) {
      console.error("Failed to load directory:", err);
    } finally {
      setPickerLoading(false);
    }
  };

  const selectFile = (path: string) => {
    setShowPicker(false);
    if (pickerMode === "csv") {
      setCsvPath(path);
      loadTraceData(path);
    } else {
      loadFittedResults(path);
    }
  };

  // =============================================================================
  // DATA LOADING
  // =============================================================================

  const loadTraceData = async (path: string) => {
    setLoadingData(true);
    setStatusMessage("Loading trace data...");

    try {
      // First, get info about the file
      const infoResponse = await fetch(`${apiBase}/analysis/load-traces`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_path: path }),
      });

      const infoData = await infoResponse.json();

      if (!infoData.success) {
        throw new Error(infoData.error || "Failed to load traces");
      }

      // Read the actual CSV content
      const contentResponse = await fetch(`${apiBase}/processing/file/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: path }),
      });

      const contentData = await contentResponse.json();

      if (contentData.success && contentData.content) {
        const parsed = parseTraceCsv(contentData.content);
        setTraceData(parsed.data);
        setCellIds(parsed.cellIds);
        setStatusMessage(`Loaded ${parsed.cellIds.length} cells, ${infoData.data?.n_timepoints || 0} timepoints`);
        drawRawTraces(parsed.data);
      }
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Failed to load traces");
    } finally {
      setLoadingData(false);
    }
  };

  const parseTraceCsv = (content: string): { data: TraceDataPoint[]; cellIds: string[] } => {
    const lines = content.trim().split("\n");
    if (lines.length < 2) return { data: [], cellIds: [] };

    const header = lines[0].split(",");
    const fovIdx = header.indexOf("fov");
    const cellIdx = header.indexOf("cell");
    const timeIdx = header.indexOf("time");
    const valueIdx = header.indexOf("value");
    const frameIdx = header.indexOf("frame");

    const data: TraceDataPoint[] = [];
    const cellSet = new Set<string>();

    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      const fov = parseInt(cols[fovIdx], 10);
      const cell = parseInt(cols[cellIdx], 10);
      const time = parseFloat(cols[timeIdx]);
      const value = parseFloat(cols[valueIdx]);
      const frame = frameIdx >= 0 ? parseInt(cols[frameIdx], 10) : i - 1;

      data.push({ fov, cell, time, value, frame });
      cellSet.add(`${fov}_${cell}`);
    }

    return { data, cellIds: Array.from(cellSet) };
  };

  const loadFittedResults = async (path: string) => {
    setStatusMessage("Loading fitted results...");

    try {
      const response = await fetch(`${apiBase}/processing/file/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: path }),
      });

      const data = await response.json();

      if (data.success && data.content) {
        const results = parseFittedCsv(data.content);
        setFittingResults(results);
        setResultsFile(path);

        // Extract parameter names
        if (results.length > 0) {
          const excluded = ["fov", "cell", "model_type", "success", "r_squared", "residual_sum_squares", "message", "n_function_calls"];
          const params = Object.keys(results[0]).filter(
            (k) => !excluded.includes(k) && typeof results[0][k] === "number"
          );
          setParameterNames(params);
          if (params.length > 0) {
            setSelectedHistParam(params[0]);
            setSelectedScatterX(params[0]);
            setSelectedScatterY(params.length > 1 ? params[1] : params[0]);
          }
        }

        setStatusMessage(`Loaded ${results.length} fitted results`);
      }
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Failed to load results");
    }
  };

  const parseFittedCsv = (content: string): FittingResult[] => {
    const lines = content.trim().split("\n");
    if (lines.length < 2) return [];

    const header = lines[0].split(",");
    const results: FittingResult[] = [];

    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      const row: Record<string, number | string | boolean> = {};

      for (let j = 0; j < header.length; j++) {
        const key = header[j];
        const val = cols[j];

        if (key === "success") {
          row[key] = val.toLowerCase() === "true";
        } else if (key === "model_type") {
          row[key] = val;
        } else {
          const num = parseFloat(val);
          row[key] = isNaN(num) ? val : num;
        }
      }

      results.push(row as FittingResult);
    }

    return results;
  };

  // =============================================================================
  // FITTING
  // =============================================================================

  const startFitting = async () => {
    if (!csvPath || !selectedModel) {
      setStatusMessage("Please load CSV and select a model");
      return;
    }

    setIsFitting(true);
    setStatusMessage("Starting fitting...");

    try {
      const params: Record<string, number> = {};
      const bounds: Record<string, [number, number]> = {};

      if (manualMode) {
        for (const [name, p] of Object.entries(modelParams)) {
          params[name] = p.value;
          bounds[name] = [p.min, p.max];
        }
      }

      const response = await fetch(`${apiBase}/analysis/fitting/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          csv_path: csvPath,
          model_type: selectedModel,
          model_params: manualMode ? params : null,
          model_bounds: manualMode ? bounds : null,
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Failed to start fitting");
      }

      setFittingJobId(data.job_id);
      setStatusMessage(`Fitting started (Job: ${data.job_id})`);
      startPolling(data.job_id);
    } catch (err) {
      setIsFitting(false);
      setStatusMessage(err instanceof Error ? err.message : "Failed to start fitting");
    }
  };

  const startPolling = (jobId: string) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${apiBase}/analysis/fitting/status/${jobId}`);
        const data = await response.json();

        if (data.progress) {
          setFittingProgress(data.progress);
          setStatusMessage(`Fitting: ${data.progress.current}/${data.progress.total} (${data.progress.percentage.toFixed(1)}%)`);
        }

        if (["completed", "failed", "cancelled", "not_found"].includes(data.status)) {
          stopPolling();
          setIsFitting(false);

          if (data.status === "completed") {
            // Load results
            const resultsResponse = await fetch(`${apiBase}/analysis/fitting/results/${jobId}`);
            const resultsData = await resultsResponse.json();

            if (resultsData.success && resultsData.results_file) {
              loadFittedResults(resultsData.results_file);
              setStatusMessage(`Fitting completed! ${resultsData.summary?.successful_fits || 0} successful fits`);
            }
          } else {
            setStatusMessage(`Fitting ${data.status}: ${data.message}`);
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 1000);
  };

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  const cancelFitting = async () => {
    if (!fittingJobId) return;

    try {
      await fetch(`${apiBase}/analysis/fitting/cancel/${fittingJobId}`, { method: "POST" });
      setStatusMessage("Cancelling fitting...");
    } catch (err) {
      console.error("Failed to cancel:", err);
    }
  };

  // =============================================================================
  // DRAWING FUNCTIONS
  // =============================================================================

  const drawRawTraces = useCallback((data: TraceDataPoint[]) => {
    const canvas = rawTraceCanvasRef.current;
    if (!canvas || data.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#171717";
    ctx.fillRect(0, 0, width, height);

    // Group by cell
    const cellMap = new Map<string, TraceDataPoint[]>();
    for (const point of data) {
      const id = `${point.fov}_${point.cell}`;
      if (!cellMap.has(id)) cellMap.set(id, []);
      cellMap.get(id)!.push(point);
    }

    // Find bounds
    let minTime = Infinity, maxTime = -Infinity;
    let minVal = Infinity, maxVal = -Infinity;

    for (const point of data) {
      minTime = Math.min(minTime, point.time);
      maxTime = Math.max(maxTime, point.time);
      minVal = Math.min(minVal, point.value);
      maxVal = Math.max(maxVal, point.value);
    }

    const padding = 40;
    const plotWidth = width - padding * 2;
    const plotHeight = height - padding * 2;

    // Draw axes
    ctx.strokeStyle = "#404040";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();

    // Draw all traces in gray
    ctx.strokeStyle = "#6b7280";
    ctx.lineWidth = 0.5;
    ctx.globalAlpha = 0.3;

    for (const [, points] of cellMap) {
      points.sort((a, b) => a.time - b.time);
      ctx.beginPath();
      for (let i = 0; i < points.length; i++) {
        const x = padding + ((points[i].time - minTime) / (maxTime - minTime)) * plotWidth;
        const y = height - padding - ((points[i].value - minVal) / (maxVal - minVal)) * plotHeight;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Calculate and draw mean
    const timePoints = Array.from(new Set(data.map((d) => d.time))).sort((a, b) => a - b);
    const meanValues: number[] = [];

    for (const t of timePoints) {
      const vals = data.filter((d) => d.time === t).map((d) => d.value);
      meanValues.push(vals.reduce((a, b) => a + b, 0) / vals.length);
    }

    ctx.globalAlpha = 1;
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 2;
    ctx.beginPath();

    for (let i = 0; i < timePoints.length; i++) {
      const x = padding + ((timePoints[i] - minTime) / (maxTime - minTime)) * plotWidth;
      const y = height - padding - ((meanValues[i] - minVal) / (maxVal - minVal)) * plotHeight;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    ctx.stroke();

    // Labels
    ctx.fillStyle = "#a3a3a3";
    ctx.font = "11px sans-serif";
    ctx.fillText("Time (hours)", width / 2, height - 8);
    ctx.save();
    ctx.translate(12, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("Intensity", 0, 0);
    ctx.restore();

    // Legend
    ctx.fillStyle = "#ef4444";
    ctx.fillRect(width - 100, 10, 12, 12);
    ctx.fillStyle = "#a3a3a3";
    ctx.fillText(`Mean (n=${cellMap.size})`, width - 85, 20);
  }, []);

  useEffect(() => {
    if (traceData.length > 0) {
      drawRawTraces(traceData);
    }
  }, [traceData, drawRawTraces]);

  const drawFittedTrace = useCallback(() => {
    const canvas = fittedTraceCanvasRef.current;
    if (!canvas || fittingResults.length === 0 || traceData.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#171717";
    ctx.fillRect(0, 0, width, height);

    // Get filtered results
    const filtered = qualityFilter
      ? fittingResults.filter((r) => r.r_squared > 0.9)
      : fittingResults;

    if (filtered.length === 0) return;

    const result = filtered[selectedResultIdx % filtered.length];
    const cellId = `${result.fov}_${result.cell}`;

    // Get trace data for this cell
    const cellData = traceData.filter((d) => `${d.fov}_${d.cell}` === cellId);
    if (cellData.length === 0) return;

    cellData.sort((a, b) => a.time - b.time);

    // Find bounds
    const minTime = Math.min(...cellData.map((d) => d.time));
    const maxTime = Math.max(...cellData.map((d) => d.time));
    const minVal = Math.min(...cellData.map((d) => d.value));
    const maxVal = Math.max(...cellData.map((d) => d.value));

    const padding = 40;
    const plotWidth = width - padding * 2;
    const plotHeight = height - padding * 2;

    // Draw axes
    ctx.strokeStyle = "#404040";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();

    // Draw raw data
    ctx.strokeStyle = "#60a5fa";
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.8;
    ctx.beginPath();

    for (let i = 0; i < cellData.length; i++) {
      const x = padding + ((cellData[i].time - minTime) / (maxTime - minTime)) * plotWidth;
      const y = height - padding - ((cellData[i].value - minVal) / (maxVal - minVal)) * plotHeight;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    ctx.stroke();
    ctx.globalAlpha = 1;

    // Labels
    ctx.fillStyle = "#a3a3a3";
    ctx.font = "11px sans-serif";
    ctx.fillText(`Cell ${result.fov}_${result.cell}`, padding, 20);
    ctx.fillText(`R² = ${result.r_squared.toFixed(3)}`, padding, 35);
    ctx.fillText(result.success ? "Success" : "Failed", padding + 100, 35);
  }, [fittingResults, selectedResultIdx, qualityFilter, traceData]);

  useEffect(() => {
    drawFittedTrace();
  }, [drawFittedTrace]);

  const drawHistogram = useCallback(() => {
    const canvas = histogramCanvasRef.current;
    if (!canvas || fittingResults.length === 0 || !selectedHistParam) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#171717";
    ctx.fillRect(0, 0, width, height);

    // Get filtered data
    const filtered = qualityFilter
      ? fittingResults.filter((r) => r.r_squared > 0.9)
      : fittingResults;

    const values = filtered
      .map((r) => r[selectedHistParam])
      .filter((v): v is number => typeof v === "number" && !isNaN(v));

    if (values.length === 0) return;

    // Calculate histogram
    const min = Math.min(...values);
    const max = Math.max(...values);
    const bins = 30;
    const binWidth = (max - min) / bins;
    const counts = new Array(bins).fill(0);

    for (const v of values) {
      const idx = Math.min(Math.floor((v - min) / binWidth), bins - 1);
      counts[idx]++;
    }

    const maxCount = Math.max(...counts);
    const padding = 40;
    const plotWidth = width - padding * 2;
    const plotHeight = height - padding * 2;

    // Draw axes
    ctx.strokeStyle = "#404040";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();

    // Draw bars
    ctx.fillStyle = "#60a5fa";
    const barWidth = plotWidth / bins;

    for (let i = 0; i < bins; i++) {
      const barHeight = (counts[i] / maxCount) * plotHeight;
      ctx.fillRect(
        padding + i * barWidth + 1,
        height - padding - barHeight,
        barWidth - 2,
        barHeight
      );
    }

    // Stats
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const std = Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / values.length);

    ctx.fillStyle = "#a3a3a3";
    ctx.font = "11px sans-serif";
    ctx.fillText(selectedHistParam, width / 2, height - 8);
    ctx.fillText(`Mean: ${mean.toFixed(3)}`, width - 100, 20);
    ctx.fillText(`Std: ${std.toFixed(3)}`, width - 100, 35);
  }, [fittingResults, selectedHistParam, qualityFilter]);

  useEffect(() => {
    drawHistogram();
  }, [drawHistogram]);

  const drawScatter = useCallback(() => {
    const canvas = scatterCanvasRef.current;
    if (!canvas || fittingResults.length === 0 || !selectedScatterX || !selectedScatterY) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#171717";
    ctx.fillRect(0, 0, width, height);

    // Get filtered data
    const filtered = qualityFilter
      ? fittingResults.filter((r) => r.r_squared > 0.9)
      : fittingResults;

    const points = filtered
      .map((r) => ({
        x: r[selectedScatterX] as number,
        y: r[selectedScatterY] as number,
      }))
      .filter((p) => typeof p.x === "number" && typeof p.y === "number" && !isNaN(p.x) && !isNaN(p.y));

    if (points.length === 0) return;

    const minX = Math.min(...points.map((p) => p.x));
    const maxX = Math.max(...points.map((p) => p.x));
    const minY = Math.min(...points.map((p) => p.y));
    const maxY = Math.max(...points.map((p) => p.y));

    const padding = 40;
    const plotWidth = width - padding * 2;
    const plotHeight = height - padding * 2;

    // Draw axes
    ctx.strokeStyle = "#404040";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();

    // Draw points
    ctx.fillStyle = "#60a5fa";
    ctx.globalAlpha = 0.6;

    for (const p of points) {
      const x = padding + ((p.x - minX) / (maxX - minX || 1)) * plotWidth;
      const y = height - padding - ((p.y - minY) / (maxY - minY || 1)) * plotHeight;
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, 2 * Math.PI);
      ctx.fill();
    }

    ctx.globalAlpha = 1;

    // Labels
    ctx.fillStyle = "#a3a3a3";
    ctx.font = "11px sans-serif";
    ctx.fillText(selectedScatterX, width / 2, height - 8);
    ctx.save();
    ctx.translate(12, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(selectedScatterY, 0, 0);
    ctx.restore();
  }, [fittingResults, selectedScatterX, selectedScatterY, qualityFilter]);

  useEffect(() => {
    drawScatter();
  }, [drawScatter]);

  // =============================================================================
  // QUALITY STATS
  // =============================================================================

  const qualityStats = useCallback(() => {
    if (fittingResults.length === 0) return { good: 0, mid: 0, bad: 0 };

    const good = fittingResults.filter((r) => r.r_squared > 0.9).length;
    const mid = fittingResults.filter((r) => r.r_squared > 0.7 && r.r_squared <= 0.9).length;
    const bad = fittingResults.filter((r) => r.r_squared <= 0.7).length;
    const total = fittingResults.length;

    return {
      good: ((good / total) * 100).toFixed(1),
      mid: ((mid / total) * 100).toFixed(1),
      bad: ((bad / total) * 100).toFixed(1),
    };
  }, [fittingResults]);

  const stats = qualityStats();

  const filteredResults = qualityFilter
    ? fittingResults.filter((r) => r.r_squared > 0.9)
    : fittingResults;

  const totalQualityPages = Math.ceil(filteredResults.length / resultsPerPage);

  // =============================================================================
  // RENDER
  // =============================================================================

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-50">
      {/* File Picker Modal */}
      {showPicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowPicker(false)} />
          <div className="relative w-full max-w-2xl rounded-xl border border-neutral-800 bg-neutral-900 shadow-2xl">
            <div className="flex items-center justify-between border-b border-neutral-800 px-4 py-3">
              <div>
                <p className="text-sm font-semibold">
                  {pickerMode === "csv" ? "Select Trace CSV" : "Select Fitted Results CSV"}
                </p>
                <p className="text-xs text-neutral-400">Choose a CSV file</p>
              </div>
              <button
                className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-semibold hover:bg-neutral-700"
                onClick={() => setShowPicker(false)}
              >
                Close
              </button>
            </div>
            <div className="p-4">
              <div className="mb-3 flex items-center gap-2">
                <div className="flex-1 rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm truncate">
                  {pickerPath}
                </div>
                <button
                  className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs hover:bg-neutral-700"
                  onClick={() => {
                    const parent = pickerPath.split("/").slice(0, -1).join("/") || "/";
                    loadPickerDirectory(parent);
                  }}
                >
                  Up
                </button>
              </div>
              <div className="max-h-64 overflow-y-auto rounded-lg border border-neutral-800">
                {pickerLoading ? (
                  <div className="p-4 text-center text-neutral-400">Loading...</div>
                ) : (
                  <div className="divide-y divide-neutral-800">
                    {pickerItems.map((item) => (
                      <div
                        key={item.path}
                        className="cursor-pointer px-3 py-2 hover:bg-neutral-800"
                        onClick={() => {
                          if (item.is_directory) {
                            loadPickerDirectory(item.path);
                          } else if (item.is_file) {
                            selectFile(item.path);
                          }
                        }}
                      >
                        <span className="text-sm">
                          {item.is_directory ? "📁" : "📄"} {item.name}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <main className="mx-auto max-w-[1600px] px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-neutral-400">Analysis</p>
          <h1 className="text-3xl font-semibold text-neutral-50">Fitting Analysis</h1>
          <p className="text-sm text-neutral-400">{statusMessage}</p>
        </div>

        {/* 3-Panel Layout */}
        <div className="grid gap-4 lg:grid-cols-3">
          {/* Data Panel */}
          <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
            <h2 className="mb-4 text-lg font-semibold">Data & Fitting</h2>

            <div className="space-y-4">
              {/* Load CSV */}
              <div>
                <label className="mb-1 block text-xs text-neutral-400">Trace CSV</label>
                <div className="flex gap-2">
                  <div className="flex-1 truncate rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm">
                    {csvPath ? csvPath.split("/").pop() : "Not selected"}
                  </div>
                  <button
                    className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold hover:bg-neutral-700"
                    onClick={() => openPicker("csv")}
                  >
                    Browse
                  </button>
                </div>
              </div>

              {/* Raw trace canvas */}
              <div className="aspect-[4/3] w-full overflow-hidden rounded-lg border border-neutral-800">
                <canvas ref={rawTraceCanvasRef} width={400} height={300} className="h-full w-full" />
              </div>

              {/* Model Selection */}
              <div>
                <label className="mb-1 block text-xs text-neutral-400">Model</label>
                <select
                  className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm"
                  value={selectedModel}
                  onChange={(e) => {
                    setSelectedModel(e.target.value);
                    const model = availableModels.find((m) => m.name === e.target.value);
                    if (model) initModelParams(model);
                  }}
                >
                  {availableModels.map((m) => (
                    <option key={m.name} value={m.name}>{m.name}</option>
                  ))}
                </select>
              </div>

              {/* Parameters */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-xs text-neutral-400">Parameters</label>
                  <label className="flex items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={manualMode}
                      onChange={(e) => setManualMode(e.target.checked)}
                    />
                    Manual
                  </label>
                </div>
                <div className="max-h-40 overflow-y-auto rounded-lg border border-neutral-800">
                  <table className="w-full text-xs">
                    <thead className="bg-neutral-800 text-neutral-400">
                      <tr>
                        <th className="px-2 py-1 text-left">Name</th>
                        <th className="px-2 py-1 text-right">Value</th>
                        <th className="px-2 py-1 text-right">Min</th>
                        <th className="px-2 py-1 text-right">Max</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800">
                      {Object.entries(modelParams).map(([name, p]) => (
                        <tr key={name}>
                          <td className="px-2 py-1">{name}</td>
                          <td className="px-2 py-1">
                            <input
                              type="number"
                              step="0.01"
                              value={p.value}
                              disabled={!manualMode}
                              onChange={(e) =>
                                setModelParams((prev) => ({
                                  ...prev,
                                  [name]: { ...prev[name], value: parseFloat(e.target.value) || 0 },
                                }))
                              }
                              className="w-full rounded border border-neutral-700 bg-neutral-800 px-1 py-0.5 text-right disabled:opacity-50"
                            />
                          </td>
                          <td className="px-2 py-1">
                            <input
                              type="number"
                              step="0.01"
                              value={p.min}
                              disabled={!manualMode}
                              onChange={(e) =>
                                setModelParams((prev) => ({
                                  ...prev,
                                  [name]: { ...prev[name], min: parseFloat(e.target.value) || 0 },
                                }))
                              }
                              className="w-full rounded border border-neutral-700 bg-neutral-800 px-1 py-0.5 text-right disabled:opacity-50"
                            />
                          </td>
                          <td className="px-2 py-1">
                            <input
                              type="number"
                              step="0.01"
                              value={p.max}
                              disabled={!manualMode}
                              onChange={(e) =>
                                setModelParams((prev) => ({
                                  ...prev,
                                  [name]: { ...prev[name], max: parseFloat(e.target.value) || 0 },
                                }))
                              }
                              className="w-full rounded border border-neutral-700 bg-neutral-800 px-1 py-0.5 text-right disabled:opacity-50"
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Load Results */}
              <button
                className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-4 py-2 text-sm hover:bg-neutral-700"
                onClick={() => openPicker("results")}
              >
                Load Fitted Results
              </button>

              {/* Fitting Controls */}
              <div className="flex gap-2">
                <button
                  className="flex-1 rounded-md border border-neutral-700 bg-neutral-800 px-4 py-2 text-sm font-semibold hover:bg-neutral-700 disabled:opacity-50"
                  onClick={startFitting}
                  disabled={isFitting || !csvPath}
                >
                  {isFitting ? "Fitting..." : "Start Fitting"}
                </button>
                <button
                  className="rounded-md border border-neutral-700 bg-neutral-800 px-4 py-2 text-sm hover:bg-neutral-700 disabled:opacity-50"
                  onClick={cancelFitting}
                  disabled={!isFitting}
                >
                  Cancel
                </button>
              </div>

              {/* Progress */}
              {isFitting && (
                <div className="h-2 overflow-hidden rounded-full bg-neutral-800">
                  <div
                    className="h-full bg-blue-500 transition-all"
                    style={{ width: `${fittingProgress?.percentage || 0}%` }}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Quality Panel */}
          <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
            <h2 className="mb-4 text-lg font-semibold">Fitting Quality</h2>

            <div className="space-y-4">
              {/* Fitted trace canvas */}
              <div className="aspect-[4/3] w-full overflow-hidden rounded-lg border border-neutral-800">
                <canvas ref={fittedTraceCanvasRef} width={400} height={300} className="h-full w-full" />
              </div>

              {/* Quality Stats */}
              <div className="flex gap-2 text-xs">
                <span className="rounded bg-green-500/20 px-2 py-1 text-green-400">
                  Good: {stats.good}%
                </span>
                <span className="rounded bg-yellow-500/20 px-2 py-1 text-yellow-400">
                  Mid: {stats.mid}%
                </span>
                <span className="rounded bg-red-500/20 px-2 py-1 text-red-400">
                  Bad: {stats.bad}%
                </span>
              </div>

              {/* Results List */}
              <div className="max-h-48 overflow-y-auto rounded-lg border border-neutral-800">
                {filteredResults
                  .slice(qualityPage * resultsPerPage, (qualityPage + 1) * resultsPerPage)
                  .map((result, idx) => {
                    const globalIdx = qualityPage * resultsPerPage + idx;
                    const color =
                      result.r_squared > 0.9
                        ? "text-green-400"
                        : result.r_squared > 0.7
                          ? "text-yellow-400"
                          : "text-red-400";

                    return (
                      <div
                        key={`${result.fov}_${result.cell}`}
                        className={`cursor-pointer px-3 py-2 text-sm hover:bg-neutral-800 ${
                          globalIdx === selectedResultIdx ? "bg-neutral-800" : ""
                        }`}
                        onClick={() => setSelectedResultIdx(globalIdx)}
                      >
                        <span className={color}>
                          Cell {result.fov}_{result.cell} — R²: {result.r_squared.toFixed(3)}
                        </span>
                      </div>
                    );
                  })}
                {filteredResults.length === 0 && (
                  <div className="p-4 text-center text-sm text-neutral-500">No results loaded</div>
                )}
              </div>

              {/* Pagination */}
              {totalQualityPages > 1 && (
                <div className="flex items-center justify-between text-xs">
                  <button
                    className="rounded border border-neutral-700 bg-neutral-800 px-2 py-1 hover:bg-neutral-700 disabled:opacity-50"
                    onClick={() => setQualityPage((p) => Math.max(0, p - 1))}
                    disabled={qualityPage === 0}
                  >
                    Previous
                  </button>
                  <span className="text-neutral-400">
                    Page {qualityPage + 1} of {totalQualityPages}
                  </span>
                  <button
                    className="rounded border border-neutral-700 bg-neutral-800 px-2 py-1 hover:bg-neutral-700 disabled:opacity-50"
                    onClick={() => setQualityPage((p) => Math.min(totalQualityPages - 1, p + 1))}
                    disabled={qualityPage >= totalQualityPages - 1}
                  >
                    Next
                  </button>
                </div>
              )}

              {/* Quality Filter */}
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={qualityFilter}
                  onChange={(e) => {
                    setQualityFilter(e.target.checked);
                    setQualityPage(0);
                    setSelectedResultIdx(0);
                  }}
                />
                Good fits only (R² {">"} 0.9)
              </label>
            </div>
          </div>

          {/* Parameter Panel */}
          <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
            <h2 className="mb-4 text-lg font-semibold">Parameter Analysis</h2>

            <div className="space-y-4">
              {/* Histogram */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-xs text-neutral-400">Histogram</label>
                  <select
                    className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs"
                    value={selectedHistParam}
                    onChange={(e) => setSelectedHistParam(e.target.value)}
                  >
                    {parameterNames.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
                <div className="aspect-[4/3] w-full overflow-hidden rounded-lg border border-neutral-800">
                  <canvas ref={histogramCanvasRef} width={400} height={300} className="h-full w-full" />
                </div>
              </div>

              {/* Scatter Plot */}
              <div>
                <div className="mb-2 flex items-center gap-2">
                  <label className="text-xs text-neutral-400">Scatter</label>
                  <select
                    className="flex-1 rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs"
                    value={selectedScatterX}
                    onChange={(e) => setSelectedScatterX(e.target.value)}
                  >
                    {parameterNames.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                  <span className="text-xs text-neutral-500">vs</span>
                  <select
                    className="flex-1 rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs"
                    value={selectedScatterY}
                    onChange={(e) => setSelectedScatterY(e.target.value)}
                  >
                    {parameterNames.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
                <div className="aspect-[4/3] w-full overflow-hidden rounded-lg border border-neutral-800">
                  <canvas ref={scatterCanvasRef} width={400} height={300} className="h-full w-full" />
                </div>
              </div>

              {/* Quality Filter (shared) */}
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={qualityFilter}
                  onChange={(e) => {
                    setQualityFilter(e.target.checked);
                    setQualityPage(0);
                    setSelectedResultIdx(0);
                  }}
                />
                Good fits only (R² {">"} 0.9)
              </label>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
