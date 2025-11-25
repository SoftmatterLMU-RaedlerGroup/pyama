"use client";

import { useEffect, useState, useRef, useCallback } from "react";

// =============================================================================
// TYPES
// =============================================================================

type ChannelMeta = {
  channel: string;
  dtype: string;
  shape: number[];
  n_frames: number;
  vmin: number;
  vmax: number;
  path: string;
};

type TraceData = {
  cell_id: string;
  fov: number;
  cell: number;
  frames: number[];
  values: number[];
  x_positions: number[];
  y_positions: number[];
  good: boolean;
};

type OverlayPosition = {
  id: string;
  x: number;
  y: number;
  color: string;
};

// =============================================================================
// COMPONENT
// =============================================================================

export default function VisualizationPage() {
  // Backend config
  const backendBase = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const apiBase = `${backendBase.replace(/\/$/, "")}/api/v1`;

  // Load panel state
  const [outputDir, setOutputDir] = useState<string | null>(null);
  const [availableFovs, setAvailableFovs] = useState<number[]>([]);
  const [selectedFov, setSelectedFov] = useState<number>(0);
  const [availableChannels, setAvailableChannels] = useState<string[]>([]);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [loadingProject, setLoadingProject] = useState(false);

  // Visualization state
  const [channelsMeta, setChannelsMeta] = useState<ChannelMeta[]>([]);
  const [currentChannel, setCurrentChannel] = useState<string>("");
  const [currentFrame, setCurrentFrame] = useState(0);
  const [maxFrames, setMaxFrames] = useState(0);
  const [imageData, setImageData] = useState<number[][] | null>(null);
  const [loadingFrame, setLoadingFrame] = useState(false);

  // Trace panel state
  const [traces, setTraces] = useState<TraceData[]>([]);
  const [activeTraceId, setActiveTraceId] = useState<string | null>(null);
  const [traceFeature, setTraceFeature] = useState<string>("value");
  const [tracePage, setTracePage] = useState(0);
  const tracesPerPage = 10;

  // Overlays
  const [overlayPositions, setOverlayPositions] = useState<OverlayPosition[]>([]);

  // Canvas refs
  const imageCanvasRef = useRef<HTMLCanvasElement>(null);
  const traceCanvasRef = useRef<HTMLCanvasElement>(null);

  // Status
  const [statusMessage, setStatusMessage] = useState("Ready");

  // File picker state
  const [showPicker, setShowPicker] = useState(false);
  const [pickerPath, setPickerPath] = useState(process.env.NEXT_PUBLIC_DEFAULT_BROWSE_PATH || "/home");
  const [pickerItems, setPickerItems] = useState<Array<{ name: string; path: string; is_directory: boolean }>>([]);
  const [pickerLoading, setPickerLoading] = useState(false);

  // =============================================================================
  // FILE PICKER
  // =============================================================================

  const openPicker = () => {
    setShowPicker(true);
    loadPickerDirectory(pickerPath);
  };

  const loadPickerDirectory = async (path: string) => {
    setPickerLoading(true);
    try {
      const response = await fetch(`${apiBase}/processing/list-directory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ directory_path: path, include_hidden: false }),
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

  const selectOutputDir = (path: string) => {
    setOutputDir(path);
    setShowPicker(false);
    discoverFovs(path);
  };

  // =============================================================================
  // PROJECT LOADING
  // =============================================================================

  const discoverFovs = async (dir: string) => {
    setLoadingProject(true);
    setStatusMessage("Discovering FOVs...");
    try {
      const response = await fetch(`${apiBase}/processing/list-directory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ directory_path: dir, include_hidden: false }),
      });
      const data = await response.json();
      if (data.success) {
        const fovDirs = (data.items || [])
          .filter((item: { name: string; is_directory: boolean }) =>
            item.is_directory && item.name.startsWith("fov_"))
          .map((item: { name: string }) => parseInt(item.name.replace("fov_", ""), 10))
          .filter((n: number) => !isNaN(n))
          .sort((a: number, b: number) => a - b);

        setAvailableFovs(fovDirs);
        if (fovDirs.length > 0) {
          setSelectedFov(fovDirs[0]);
          discoverChannels(dir, fovDirs[0]);
        }
        setStatusMessage(`Found ${fovDirs.length} FOVs`);
      }
    } catch (err) {
      setStatusMessage("Failed to discover FOVs");
    } finally {
      setLoadingProject(false);
    }
  };

  const discoverChannels = async (dir: string, fov: number) => {
    try {
      const fovDir = `${dir}/fov_${fov.toString().padStart(3, "0")}`;
      const response = await fetch(`${apiBase}/processing/list-directory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ directory_path: fovDir, include_hidden: false }),
      });
      const data = await response.json();
      if (data.success) {
        const channels: string[] = [];
        for (const item of data.items || []) {
          if (item.name === "pc.npy") channels.push("pc");
          else if (item.name === "seg.npy") channels.push("seg");
          else if (item.name.startsWith("fl_") && item.name.endsWith(".npy")) {
            const ch = item.name.replace("fl_", "").replace(".npy", "");
            channels.push(ch);
          }
        }
        setAvailableChannels(channels);
        if (channels.length > 0) {
          setSelectedChannels([channels[0]]);
        }
      }
    } catch (err) {
      console.error("Failed to discover channels:", err);
    }
  };

  // =============================================================================
  // VISUALIZATION INITIALIZATION
  // =============================================================================

  const startVisualization = async () => {
    if (!outputDir || selectedChannels.length === 0) {
      setStatusMessage("Please select output directory and channels");
      return;
    }

    setLoadingProject(true);
    setStatusMessage("Initializing visualization...");

    try {
      const response = await fetch(`${apiBase}/visualization/init`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          output_dir: outputDir,
          fov_id: selectedFov,
          channels: selectedChannels,
          data_types: ["image", "seg"],
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Failed to initialize visualization");
      }

      setChannelsMeta(data.channels);
      if (data.channels.length > 0) {
        const firstChannel = data.channels[0];
        setCurrentChannel(firstChannel.channel);
        setMaxFrames(firstChannel.n_frames);
        setCurrentFrame(0);
        loadFrame(firstChannel.path, firstChannel.channel, 0);
      }

      // Load traces if available
      if (data.traces_csv) {
        loadTraces(data.traces_csv);
      }

      setStatusMessage(`Loaded FOV ${selectedFov} with ${data.channels.length} channels`);
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Failed to initialize");
    } finally {
      setLoadingProject(false);
    }
  };

  // =============================================================================
  // FRAME LOADING
  // =============================================================================

  const loadFrame = async (cachedPath: string, channel: string, frame: number) => {
    setLoadingFrame(true);
    try {
      const response = await fetch(`${apiBase}/visualization/frame`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cached_path: cachedPath,
          channel,
          frame,
        }),
      });

      const data = await response.json();

      if (data.success && data.frames.length > 0) {
        setImageData(data.frames[0]);
        drawImage(data.frames[0]);
      }
    } catch (err) {
      console.error("Failed to load frame:", err);
    } finally {
      setLoadingFrame(false);
    }
  };

  const changeFrame = (delta: number) => {
    const newFrame = Math.max(0, Math.min(maxFrames - 1, currentFrame + delta));
    if (newFrame !== currentFrame) {
      setCurrentFrame(newFrame);
      const meta = channelsMeta.find((c) => c.channel === currentChannel);
      if (meta) {
        loadFrame(meta.path, meta.channel, newFrame);
      }
      updateOverlaysForFrame(newFrame);
    }
  };

  const changeChannel = (channel: string) => {
    setCurrentChannel(channel);
    const meta = channelsMeta.find((c) => c.channel === channel);
    if (meta) {
      setMaxFrames(meta.n_frames);
      const frame = Math.min(currentFrame, meta.n_frames - 1);
      setCurrentFrame(frame);
      loadFrame(meta.path, channel, frame);
    }
  };

  // =============================================================================
  // IMAGE RENDERING
  // =============================================================================

  const drawImage = useCallback((data: number[][]) => {
    const canvas = imageCanvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const height = data.length;
    const width = data[0]?.length || 0;

    canvas.width = width;
    canvas.height = height;

    const imageData = ctx.createImageData(width, height);

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4;
        const value = data[y][x] || 0;
        imageData.data[idx] = value;
        imageData.data[idx + 1] = value;
        imageData.data[idx + 2] = value;
        imageData.data[idx + 3] = 255;
      }
    }

    ctx.putImageData(imageData, 0, 0);

    // Draw overlays
    drawOverlays(ctx);
  }, [overlayPositions, activeTraceId]);

  const drawOverlays = (ctx: CanvasRenderingContext2D) => {
    for (const overlay of overlayPositions) {
      ctx.beginPath();
      ctx.arc(overlay.x, overlay.y, 20, 0, 2 * Math.PI);
      ctx.strokeStyle = overlay.id === activeTraceId ? "red" : overlay.color;
      ctx.lineWidth = overlay.id === activeTraceId ? 3 : 2;
      ctx.stroke();
    }
  };

  // =============================================================================
  // TRACE LOADING & RENDERING
  // =============================================================================

  const loadTraces = async (csvPath: string) => {
    try {
      // For now, parse traces from the server
      // In a full implementation, we'd have a dedicated endpoint
      const response = await fetch(`${apiBase}/processing/file/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: csvPath }),
      });

      const data = await response.json();
      if (data.success && data.content) {
        const parsed = parseTracesCsv(data.content);
        setTraces(parsed);
        if (parsed.length > 0) {
          setActiveTraceId(parsed[0].cell_id);
          updateOverlaysFromTraces(parsed, 0);
        }
      }
    } catch (err) {
      console.error("Failed to load traces:", err);
    }
  };

  const parseTracesCsv = (content: string): TraceData[] => {
    const lines = content.trim().split("\n");
    if (lines.length < 2) return [];

    const header = lines[0].split(",");
    const fovIdx = header.indexOf("fov");
    const cellIdx = header.indexOf("cell");
    const frameIdx = header.indexOf("frame");
    const valueIdx = header.indexOf("value");
    const xIdx = header.indexOf("x");
    const yIdx = header.indexOf("y");
    const goodIdx = header.indexOf("good");

    if (fovIdx < 0 || cellIdx < 0 || frameIdx < 0 || valueIdx < 0) {
      return [];
    }

    const traceMap = new Map<string, TraceData>();

    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      const fov = parseInt(cols[fovIdx], 10);
      const cell = parseInt(cols[cellIdx], 10);
      const frame = parseInt(cols[frameIdx], 10);
      const value = parseFloat(cols[valueIdx]);
      const x = xIdx >= 0 ? parseFloat(cols[xIdx]) : 0;
      const y = yIdx >= 0 ? parseFloat(cols[yIdx]) : 0;
      const good = goodIdx >= 0 ? cols[goodIdx].toLowerCase() === "true" : true;

      const cellId = `${fov}_${cell}`;

      if (!traceMap.has(cellId)) {
        traceMap.set(cellId, {
          cell_id: cellId,
          fov,
          cell,
          frames: [],
          values: [],
          x_positions: [],
          y_positions: [],
          good,
        });
      }

      const trace = traceMap.get(cellId)!;
      trace.frames.push(frame);
      trace.values.push(value);
      trace.x_positions.push(x);
      trace.y_positions.push(y);
    }

    return Array.from(traceMap.values());
  };

  const updateOverlaysFromTraces = (traceData: TraceData[], frame: number) => {
    const positions: OverlayPosition[] = [];

    for (const trace of traceData) {
      const frameIdx = trace.frames.indexOf(frame);
      if (frameIdx >= 0) {
        positions.push({
          id: trace.cell_id,
          x: trace.x_positions[frameIdx] || 0,
          y: trace.y_positions[frameIdx] || 0,
          color: trace.good ? "blue" : "green",
        });
      }
    }

    setOverlayPositions(positions);
  };

  const updateOverlaysForFrame = (frame: number) => {
    updateOverlaysFromTraces(traces, frame);
  };

  useEffect(() => {
    if (imageData) {
      drawImage(imageData);
    }
  }, [overlayPositions, activeTraceId, imageData, drawImage]);

  const drawTraces = useCallback(() => {
    const canvas = traceCanvasRef.current;
    if (!canvas || traces.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#171717";
    ctx.fillRect(0, 0, width, height);

    // Get visible traces
    const startIdx = tracePage * tracesPerPage;
    const visibleTraces = traces.slice(startIdx, startIdx + tracesPerPage);

    if (visibleTraces.length === 0) return;

    // Find data bounds
    let minVal = Infinity;
    let maxVal = -Infinity;
    let maxFrame = 0;

    for (const trace of visibleTraces) {
      for (const v of trace.values) {
        minVal = Math.min(minVal, v);
        maxVal = Math.max(maxVal, v);
      }
      maxFrame = Math.max(maxFrame, ...trace.frames);
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

    // Draw traces
    const colors = ["#60a5fa", "#f87171", "#4ade80", "#fbbf24", "#a78bfa", "#f472b6", "#22d3d8", "#fb923c"];

    for (let i = 0; i < visibleTraces.length; i++) {
      const trace = visibleTraces[i];
      const color = trace.cell_id === activeTraceId ? "#ef4444" : colors[i % colors.length];
      const lineWidth = trace.cell_id === activeTraceId ? 2 : 1;
      const alpha = trace.cell_id === activeTraceId ? 1 : 0.6;

      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.globalAlpha = alpha;
      ctx.beginPath();

      for (let j = 0; j < trace.frames.length; j++) {
        const x = padding + (trace.frames[j] / maxFrame) * plotWidth;
        const y = height - padding - ((trace.values[j] - minVal) / (maxVal - minVal)) * plotHeight;

        if (j === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }

      ctx.stroke();
    }

    ctx.globalAlpha = 1;

    // Draw current frame indicator
    const frameX = padding + (currentFrame / maxFrame) * plotWidth;
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(frameX, padding);
    ctx.lineTo(frameX, height - padding);
    ctx.stroke();
    ctx.setLineDash([]);

    // Labels
    ctx.fillStyle = "#a3a3a3";
    ctx.font = "11px sans-serif";
    ctx.fillText("Frame", width / 2, height - 10);
    ctx.save();
    ctx.translate(12, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("Value", 0, 0);
    ctx.restore();
  }, [traces, tracePage, activeTraceId, currentFrame]);

  useEffect(() => {
    drawTraces();
  }, [drawTraces]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = imageCanvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    // Find closest overlay
    let closest: OverlayPosition | null = null;
    let minDist = 30;

    for (const overlay of overlayPositions) {
      const dist = Math.sqrt((overlay.x - x) ** 2 + (overlay.y - y) ** 2);
      if (dist < minDist) {
        minDist = dist;
        closest = overlay;
      }
    }

    if (closest) {
      setActiveTraceId(closest.id);
      // Find trace page
      const traceIdx = traces.findIndex((t) => t.cell_id === closest!.id);
      if (traceIdx >= 0) {
        setTracePage(Math.floor(traceIdx / tracesPerPage));
      }
    }
  };

  const toggleTraceQuality = (traceId: string) => {
    setTraces((prev) =>
      prev.map((t) => (t.cell_id === traceId ? { ...t, good: !t.good } : t))
    );
  };

  const totalTracePages = Math.ceil(traces.length / tracesPerPage);

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
                <p className="text-sm font-semibold">Select Output Directory</p>
                <p className="text-xs text-neutral-400">Choose the workflow output folder</p>
              </div>
              <div className="flex gap-2">
                <button
                  className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-semibold hover:bg-neutral-700"
                  onClick={() => selectOutputDir(pickerPath)}
                >
                  Use this folder
                </button>
                <button
                  className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-semibold hover:bg-neutral-700"
                  onClick={() => setShowPicker(false)}
                >
                  Close
                </button>
              </div>
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
                          }
                        }}
                      >
                        <span className="text-sm">{item.is_directory ? "📁" : "📄"} {item.name}</span>
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
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-neutral-400">Visualization</p>
          <h1 className="text-3xl font-semibold text-neutral-50">FOV Visualization</h1>
          <p className="text-sm text-neutral-400">{statusMessage}</p>
        </div>

        {/* 3-Panel Layout */}
        <div className="grid gap-4 lg:grid-cols-[1fr_2fr_1fr]">
          {/* Load Panel */}
          <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
            <h2 className="mb-4 text-lg font-semibold">Load Project</h2>

            <div className="space-y-4">
              {/* Output Directory */}
              <div>
                <label className="mb-1 block text-xs text-neutral-400">Output Directory</label>
                <div className="flex gap-2">
                  <div className="flex-1 truncate rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm">
                    {outputDir || "Not selected"}
                  </div>
                  <button
                    className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold hover:bg-neutral-700"
                    onClick={openPicker}
                  >
                    Browse
                  </button>
                </div>
              </div>

              {/* FOV Selection */}
              {availableFovs.length > 0 && (
                <div>
                  <label className="mb-1 block text-xs text-neutral-400">FOV</label>
                  <select
                    className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm"
                    value={selectedFov}
                    onChange={(e) => {
                      const fov = parseInt(e.target.value, 10);
                      setSelectedFov(fov);
                      if (outputDir) discoverChannels(outputDir, fov);
                    }}
                  >
                    {availableFovs.map((fov) => (
                      <option key={fov} value={fov}>FOV {fov}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Channel Selection */}
              {availableChannels.length > 0 && (
                <div>
                  <label className="mb-1 block text-xs text-neutral-400">Channels</label>
                  <div className="space-y-1">
                    {availableChannels.map((ch) => (
                      <label key={ch} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={selectedChannels.includes(ch)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedChannels((prev) => [...prev, ch]);
                            } else {
                              setSelectedChannels((prev) => prev.filter((c) => c !== ch));
                            }
                          }}
                          className="rounded border-neutral-700"
                        />
                        {ch === "pc" ? "Phase Contrast" : ch === "seg" ? "Segmentation" : `FL ${ch}`}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Start Button */}
              <button
                className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-4 py-2 text-sm font-semibold hover:bg-neutral-700 disabled:opacity-50"
                onClick={startVisualization}
                disabled={loadingProject || !outputDir || selectedChannels.length === 0}
              >
                {loadingProject ? "Loading..." : "Start Visualization"}
              </button>
            </div>
          </div>

          {/* Image Panel */}
          <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Image</h2>
              {channelsMeta.length > 0 && (
                <select
                  className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-sm"
                  value={currentChannel}
                  onChange={(e) => changeChannel(e.target.value)}
                >
                  {channelsMeta.map((ch) => (
                    <option key={ch.channel} value={ch.channel}>
                      {ch.channel === "pc" ? "Phase Contrast" : ch.channel === "seg" ? "Segmentation" : `FL ${ch.channel}`}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Canvas */}
            <div className="relative aspect-square w-full overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950">
              <canvas
                ref={imageCanvasRef}
                className="h-full w-full object-contain"
                onClick={handleCanvasClick}
              />
              {loadingFrame && (
                <div className="absolute inset-0 flex items-center justify-center bg-neutral-950/50">
                  <span className="text-sm text-neutral-400">Loading...</span>
                </div>
              )}
            </div>

            {/* Frame Controls */}
            <div className="mt-3 flex items-center justify-center gap-2">
              <button
                className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1 text-sm hover:bg-neutral-700 disabled:opacity-50"
                onClick={() => changeFrame(-10)}
                disabled={currentFrame < 10}
              >
                {"<<"}
              </button>
              <button
                className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1 text-sm hover:bg-neutral-700 disabled:opacity-50"
                onClick={() => changeFrame(-1)}
                disabled={currentFrame === 0}
              >
                {"<"}
              </button>
              <span className="min-w-[100px] text-center text-sm">
                Frame {currentFrame + 1} / {maxFrames || 1}
              </span>
              <button
                className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1 text-sm hover:bg-neutral-700 disabled:opacity-50"
                onClick={() => changeFrame(1)}
                disabled={currentFrame >= maxFrames - 1}
              >
                {">"}
              </button>
              <button
                className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1 text-sm hover:bg-neutral-700 disabled:opacity-50"
                onClick={() => changeFrame(10)}
                disabled={currentFrame >= maxFrames - 10}
              >
                {">>"}
              </button>
            </div>
          </div>

          {/* Trace Panel */}
          <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Traces</h2>
              <span className="text-xs text-neutral-400">{traces.length} cells</span>
            </div>

            {/* Trace Canvas */}
            <div className="mb-3 aspect-[4/3] w-full overflow-hidden rounded-lg border border-neutral-800">
              <canvas ref={traceCanvasRef} width={400} height={300} className="h-full w-full" />
            </div>

            {/* Trace List */}
            <div className="mb-3 max-h-48 overflow-y-auto rounded-lg border border-neutral-800">
              {traces.slice(tracePage * tracesPerPage, (tracePage + 1) * tracesPerPage).map((trace) => (
                <div
                  key={trace.cell_id}
                  className={`flex cursor-pointer items-center justify-between px-3 py-2 text-sm hover:bg-neutral-800 ${
                    trace.cell_id === activeTraceId ? "bg-neutral-800" : ""
                  }`}
                  onClick={() => setActiveTraceId(trace.cell_id)}
                >
                  <span className={trace.good ? "text-blue-400" : "text-green-400"}>
                    Cell {trace.cell}
                  </span>
                  <button
                    className="text-xs text-neutral-500 hover:text-neutral-300"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleTraceQuality(trace.cell_id);
                    }}
                  >
                    {trace.good ? "Good" : "Bad"}
                  </button>
                </div>
              ))}
              {traces.length === 0 && (
                <div className="p-4 text-center text-sm text-neutral-500">No traces loaded</div>
              )}
            </div>

            {/* Pagination */}
            {totalTracePages > 1 && (
              <div className="flex items-center justify-between text-xs">
                <button
                  className="rounded border border-neutral-700 bg-neutral-800 px-2 py-1 hover:bg-neutral-700 disabled:opacity-50"
                  onClick={() => setTracePage((p) => Math.max(0, p - 1))}
                  disabled={tracePage === 0}
                >
                  Previous
                </button>
                <span className="text-neutral-400">
                  Page {tracePage + 1} of {totalTracePages}
                </span>
                <button
                  className="rounded border border-neutral-700 bg-neutral-800 px-2 py-1 hover:bg-neutral-700 disabled:opacity-50"
                  onClick={() => setTracePage((p) => Math.min(totalTracePages - 1, p + 1))}
                  disabled={tracePage >= totalTracePages - 1}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
