"use client";

import { useEffect, useState } from "react";

type PickerKey =
  | "microscopy"
  | "processingOutput"
  | "sampleYaml"
  | "processingYaml"
  | "mergeOutput";

type PickerConfig = {
  key: PickerKey;
  title: string;
  description: string;
  accept?: string;
  directory?: boolean;
  filterExtensions?: string[];
};

type PickerSelections = Record<PickerKey, string | null>;

export default function Home() {
  const [activePicker, setActivePicker] = useState<PickerConfig | null>(null);
  const [selections, setSelections] = useState<PickerSelections>({
    microscopy: null,
    processingOutput: null,
    sampleYaml: null,
    processingYaml: null,
    mergeOutput: null,
  });

  const [statusMessage, setStatusMessage] = useState("Ready for wiring");
  const [metadata, setMetadata] = useState<{
    n_fovs?: number;
    n_frames?: number;
    n_channels?: number;
    channel_names?: string[];
    time_units?: string;
    pixel_size_um?: number;
  } | null>(null);
  const [loadingMetadata, setLoadingMetadata] = useState(false);
  const [channelNames, setChannelNames] = useState<string[]>([]);
  const [availablePhaseFeatures, setAvailablePhaseFeatures] = useState<string[]>([]);
  const [availableFlFeatures, setAvailableFlFeatures] = useState<string[]>([]);
  const [phaseFeatures, setPhaseFeatures] = useState<string[]>([]);
  const [phaseChannel, setPhaseChannel] = useState<number | null>(null);
  const [pcFeaturesSelected, setPcFeaturesSelected] = useState<string[]>([]);
  const [flChannelSelection, setFlChannelSelection] = useState<number | null>(null);
  const [flFeatureSelection, setFlFeatureSelection] = useState<string | null>(null);
  const [flMapping, setFlMapping] = useState<Record<number, string[]>>({});
  const [splitMode, setSplitMode] = useState(false);

  const [currentPath, setCurrentPath] = useState(
    process.env.NEXT_PUBLIC_DEFAULT_BROWSE_PATH || "/home"
  );
  const [items, setItems] = useState<
    {
      name: string;
      path: string;
      is_directory: boolean;
      is_file: boolean;
      size_bytes?: number | null;
      extension?: string | null;
    }[]
  >([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openPicker = (config: PickerConfig) => setActivePicker(config);
  const closePicker = () => setActivePicker(null);
  const backendBase =
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const apiBase = `${backendBase.replace(/\/$/, "")}/api/v1`;

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

  const loadDirectory = async (
    path: string,
    pickerOverride?: PickerConfig | null
  ) => {
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

  useEffect(() => {
    if (!activePicker) return;
    const startPath = getStartPath(activePicker);
    setCurrentPath(startPath);
    loadDirectory(startPath, activePicker);
  }, [activePicker]);

  useEffect(() => {
    (async () => {
      const { phase, fl } = await loadFeatures();
      if (!phaseFeatures.length && phase.length) {
        setPhaseFeatures(phase.slice(0, Math.min(3, phase.length)));
      }
      if (!availableFlFeatures.length && fl.length) {
        setAvailableFlFeatures(fl);
      }
    })();
  }, []); // load features once on mount for display readiness

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
      if (
        Array.isArray(data.fluorescence_features) &&
        data.fluorescence_features.length
      ) {
        fl = data.fluorescence_features;
        setAvailableFlFeatures(data.fluorescence_features);
      }
    } catch {
      // Keep defaults on failure
    }
    return { phase, fl };
  };

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
      const names: string[] = Array.isArray(meta.channel_names)
        ? meta.channel_names
        : [];
      setMetadata(meta);
      setChannelNames(names);

      const phaseDefaults = phase.length
        ? phase.slice(0, Math.min(3, phase.length))
        : phaseFeatures;
      setPhaseFeatures(phaseDefaults);
      setPhaseChannel(names.length ? 0 : null);
      setPcFeaturesSelected(phaseDefaults);

      // Do not auto-populate fluorescence mappings; user will add them manually.
      setFlMapping({});
      setFlChannelSelection(names.length ? 0 : null);
      setFlFeatureSelection(fl.length ? fl[0] : null);

      const fovsText =
        typeof meta.n_fovs === "number" ? `${meta.n_fovs} FOVs` : "FOVs unknown";
      setStatusMessage(
        `Loaded metadata for ${filePath} (${fovsText})${split ? " [split]" : ""}`
      );
    } catch (err) {
      setStatusMessage(
        err instanceof Error ? err.message : "Failed to load metadata"
      );
    } finally {
      setLoadingMetadata(false);
    }
  };

  const handleSelect = (path: string) => {
    if (!activePicker) return;
    const key = activePicker.key;
    setSelections((prev) => ({
      ...prev,
      [key]: path,
    }));
    setActivePicker(null);
    if (key === "microscopy") {
      // Reset channel selections when a new file is chosen
      setPhaseChannel(null);
      setPcFeaturesSelected([]);
      setFlChannelSelection(null);
      setFlFeatureSelection(null);
      setFlMapping({});
      loadMicroscopyMetadata(path);
    }
  };

  const goUp = () => {
    if (!currentPath || !activePicker) return;
    const normalized = currentPath.replace(/\\/g, "/");
    const parent = normalized.split("/").slice(0, -1).join("/") || "/";
    setCurrentPath(parent);
    loadDirectory(parent);
  };

  const selectionLabel = (key: PickerKey, fallback: string) =>
    formatName(selections[key]) || fallback;

  const handlePhaseChange = (value: string) => {
    const parsed = Number(value);
    setPhaseChannel(Number.isNaN(parsed) ? null : parsed);
  };

  const togglePcFeature = (feature: string) => {
    setPcFeaturesSelected((prev) =>
      prev.includes(feature)
        ? prev.filter((f) => f !== feature)
        : [...prev, feature]
    );
    setPhaseFeatures((prev) =>
      prev.includes(feature)
        ? prev.filter((f) => f !== feature)
        : [...prev, feature]
    );
  };

  const toggleSplitMode = () => {
    const next = !splitMode;
    setSplitMode(next);
    if (selections.microscopy) {
      loadMicroscopyMetadata(selections.microscopy, next);
    }
  };

  const addFlMapping = () => {
    if (flChannelSelection === null || !flFeatureSelection) return;
    setFlMapping((prev) => {
      const existing = prev[flChannelSelection] || [];
      if (existing.includes(flFeatureSelection)) {
        return prev;
      }
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

  const parameterRows = [
    { key: "fov_start", value: "0" },
    { key: "fov_end", value: "-1" },
    { key: "batch_size", value: "2" },
    { key: "n_workers", value: "2" },
    { key: "background_weight", value: "1.0" },
  ];
  const sampleRows = [
    { name: "control", fovs: "0-5" },
    { name: "drug_a", fovs: "6-11" },
    { name: "rescue", fovs: "12-17" },
  ];

  return (
    <div className="relative min-h-screen bg-neutral-950 text-neutral-50">
      {activePicker ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <div className="w-full max-w-3xl overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-900 shadow-2xl">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-neutral-800 px-5 py-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-neutral-50">
                  {activePicker.title}
                </p>
                <p className="text-xs text-neutral-400">
                  {activePicker.description}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {activePicker.directory ? (
                  <button
                    className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:bg-neutral-700"
                    onClick={() => handleSelect(currentPath)}
                    disabled={loading}
                  >
                    Use this folder
                  </button>
                ) : null}
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
                  <div className="truncate text-sm text-neutral-100">
                    {currentPath}
                  </div>
                </div>
                <button
                  className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:border-neutral-500"
                  onClick={goUp}
                  disabled={!currentPath || currentPath === "/"}
                >
                  Up one level
                </button>
                <button
                  className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:border-neutral-500"
                  onClick={() => loadDirectory(currentPath)}
                  disabled={loading}
                >
                  Refresh
                </button>
              </div>

              {error ? (
                <div className="rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
                  {error}
                </div>
              ) : null}

              <div className="max-h-[24rem] overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900">
                <table className="w-full text-sm text-neutral-100">
                  <thead className="border-b border-neutral-800 bg-neutral-800 text-left text-xs uppercase tracking-wide text-neutral-400">
                    <tr>
                      <th className="px-3 py-2 font-semibold">Name</th>
                      <th className="px-3 py-2 font-semibold">Type</th>
                      <th className="px-3 py-2 text-right font-semibold">
                        Size
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-800">
                    {loading ? (
                      <tr>
                        <td
                          colSpan={3}
                          className="px-3 py-8 text-center text-sm text-neutral-400"
                        >
                          Loading directory...
                        </td>
                      </tr>
                    ) : items.length === 0 ? (
                      <tr>
                        <td
                          colSpan={3}
                          className="px-3 py-8 text-center text-sm text-neutral-400"
                        >
                          No items found in this location.
                        </td>
                      </tr>
                    ) : (
                      items.map((item) => (
                        <tr
                          key={item.path}
                          className="cursor-pointer hover:bg-neutral-800/70"
                          onDoubleClick={() => {
                            if (item.is_directory) {
                              setCurrentPath(item.path);
                              loadDirectory(item.path);
                            } else if (!activePicker?.directory) {
                              handleSelect(item.path);
                            }
                          }}
                          onClick={() => {
                            if (item.is_directory) {
                              setCurrentPath(item.path);
                              loadDirectory(item.path);
                            } else if (!activePicker?.directory) {
                              handleSelect(item.path);
                            }
                          }}
                        >
                          <td className="px-3 py-2 font-medium text-neutral-50">
                            {item.name}
                          </td>
                          <td className="px-3 py-2 text-neutral-300">
                            {item.is_directory
                              ? "Folder"
                              : item.extension || "File"}
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

              {!activePicker?.directory ? (
                <p className="text-xs text-neutral-400">
                  Double-click a file to select it. Directories open to navigate.
                </p>
              ) : (
                <p className="text-xs text-neutral-400">
                  Navigate to your target folder and click "Use this folder" to
                  confirm.
                </p>
              )}
            </div>
          </div>
        </div>
      ) : null}

      <main className="relative mx-auto max-w-7xl px-6 py-12">
        <div className="mb-10 flex flex-wrap items-start justify-between gap-6">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-neutral-400">
              Processing
            </p>
            <h1 className="text-4xl font-semibold leading-tight text-neutral-50">
              PyAMA Processing Workspace
            </h1>
            <p className="max-w-3xl text-sm text-neutral-300">
              One-to-one layout from the PyAMA-Pro Processing tab, now in the
              frontend. Controls are scaffolded with placeholder content so we
              can wire data and actions next.
            </p>
          </div>
          <div className="rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-3 text-sm text-neutral-200 shadow-sm">
            <p className="font-semibold text-neutral-50">Status</p>
            <p className="text-xs text-neutral-400">{statusMessage}</p>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <section className="rounded-2xl border border-neutral-900 bg-neutral-900 p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-2xl font-semibold uppercase tracking-[0.12em] text-neutral-50">
                Workflow
              </h2>
              <span className="rounded-full border border-neutral-700 bg-neutral-800 px-3 py-1 text-xs font-semibold text-neutral-200">
                Placeholder UI
              </span>
            </div>

            <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
              <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-5 space-y-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-neutral-50">Input</p>
                    <p className="text-xs text-neutral-400">
                      Microscopy file and channel selection
                    </p>
                  </div>
                  <button
                    type="button"
                    className="group inline-flex items-center gap-2 rounded-full border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:border-neutral-500"
                    onClick={toggleSplitMode}
                  >
                    <span>Split files</span>
                    <div
                      className={`h-5 w-9 rounded-full border transition ${
                        splitMode
                          ? "border-neutral-500 bg-neutral-700"
                          : "border-neutral-700 bg-neutral-800"
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

                <div className="space-y-4">
                  <div className="rounded-lg border border-dashed border-neutral-700 bg-neutral-900 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-neutral-400">
                          Microscopy File
                        </p>
                        <p className="text-sm font-semibold text-neutral-50">
                          {selectionLabel("microscopy", "No file selected")}
                        </p>
                        <p className="text-xs text-neutral-400">
                          {selections.microscopy || ""}
                        </p>
                        <p className="text-xs text-neutral-400">
                          Supports ND2 / CZI / OME-TIFF
                        </p>
                        {loadingMetadata ? (
                          <p className="text-xs text-neutral-500">
                            Loading metadata...
                          </p>
                        ) : metadata ? (
                          <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-neutral-300">
                            <span>Channels: {metadata.n_channels ?? channelNames.length}</span>
                            <span>FOVs: {metadata.n_fovs ?? "?"}</span>
                            <span>Frames: {metadata.n_frames ?? "?"}</span>
                            <span>
                              Time units: {metadata.time_units || "unknown"}
                            </span>
                          </div>
                        ) : null}
                      </div>
                      <button
                        className="rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:bg-neutral-700"
                        onClick={() =>
                          openPicker({
                            key: "microscopy",
                            title: "Choose microscopy file",
                            description: "Select an ND2 / CZI / OME-TIFF file",
                            filterExtensions: [
                              ".nd2",
                              ".czi",
                              ".ome.tif",
                              ".ome.tiff",
                              ".tif",
                              ".tiff",
                            ],
                          })
                        }
                      >
                        Browse
                      </button>
                    </div>
                  </div>

                  <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-neutral-50">
                        Channels
                      </h3>
                      {channelNames.length ? (
                        <span className="text-xs text-neutral-400">
                          {channelNames.length} channels
                        </span>
                      ) : null}
                    </div>

                    {channelNames.length ? (
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-neutral-300">
                        {channelNames.map((name, idx) => (
                          <span
                            key={`${name}-${idx}`}
                            className="rounded-full border border-neutral-700 bg-neutral-800 px-3 py-1"
                          >
                            {idx}: {name || "Channel"}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    <div className="mt-3 space-y-3">
                      <div className="rounded-md border border-neutral-800 bg-neutral-900 p-3">
                        <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-400">
                          <span className="text-sm font-semibold text-neutral-50">
                            Phase Contrast
                          </span>
                          <select
                            className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] text-neutral-100"
                            value={phaseChannel ?? ""}
                            onChange={(e) => handlePhaseChange(e.target.value)}
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
                          {availablePhaseFeatures.length ? (
                            availablePhaseFeatures.map((feature) => {
                              const active = pcFeaturesSelected.includes(feature);
                              return (
                                <button
                                  type="button"
                                  key={feature}
                                  onClick={() => {
                                    togglePcFeature(feature);
                                    setPhaseFeatures((prev) =>
                                      prev.includes(feature)
                                        ? prev.filter((f) => f !== feature)
                                        : [...prev, feature]
                                    );
                                  }}
                                  className={`rounded-full border px-3 py-1 text-[11px] font-semibold transition ${
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

                      <div className="space-y-3 rounded-md border border-neutral-800 bg-neutral-900 p-3">
                        <div className="flex items-center justify-between text-xs text-neutral-400">
                          <span className="text-sm font-semibold text-neutral-50">
                            Fluorescence
                          </span>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <select
                            className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs text-neutral-100"
                            value={flChannelSelection ?? ""}
                            onChange={(e) => {
                              const v = e.target.value;
                              setFlChannelSelection(v === "" ? null : Number(v));
                            }}
                          >
                            <option value="">Select channel</option>
                            {channelNames.map((name, idx) => (
                              <option key={`${name}-${idx}`} value={idx}>
                                {idx}: {name || "Channel"}
                              </option>
                            ))}
                          </select>
                          <select
                            className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs text-neutral-100"
                            value={flFeatureSelection ?? ""}
                            onChange={(e) =>
                              setFlFeatureSelection(e.target.value || null)
                            }
                          >
                            <option value="">Select feature</option>
                            {availableFlFeatures.map((feature) => (
                              <option key={feature} value={feature}>
                                {feature}
                              </option>
                            ))}
                          </select>
                          <button
                            className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1 text-xs font-semibold text-neutral-100 hover:bg-neutral-700"
                            onClick={addFlMapping}
                          >
                            Add
                          </button>
                        </div>

                        {Object.keys(flMapping).length ? (
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
                                      {channel}:{" "}
                                      {channelNames[Number(channel)] ||
                                        "Channel"}{" "}
                                      <span className="mx-1 text-neutral-400">
                                        -&gt;
                                      </span>
                                      <span className="font-semibold">
                                        {feature}
                                      </span>
                                    </div>
                                    <button
                                      className="rounded-full border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] text-neutral-200"
                                      onClick={() =>
                                        removeFlMapping(Number(channel), feature)
                                      }
                                    >
                                      Remove
                                    </button>
                                  </div>
                                ))
                              )}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-neutral-50">Output</p>
                    <p className="text-xs text-neutral-400">
                      Destination, parameters, and actions
                    </p>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  <div className="rounded-lg border border-dashed border-neutral-700 bg-neutral-900 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-neutral-400">
                          Save Directory
                        </p>
                        <p className="text-sm font-semibold text-neutral-50">
                          {selectionLabel("processingOutput", "No directory selected")}
                        </p>
                        <p className="text-xs text-neutral-400">
                          {selections.processingOutput || ""}
                        </p>
                        <p className="text-xs text-neutral-400">
                          Processing results will be saved here
                        </p>
                      </div>
                      <button
                        className="rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-50 transition hover:bg-neutral-700"
                        onClick={() =>
                          openPicker({
                            key: "processingOutput",
                            title: "Choose output directory",
                            description: "Select the processing output folder",
                            directory: true,
                          })
                        }
                      >
                        Browse
                      </button>
                    </div>
                  </div>

                  <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-neutral-50">
                        Parameters
                      </h3>
                      <span className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] text-neutral-200">
                        ParameterTable placeholder
                      </span>
                    </div>
                    <div className="divide-y divide-neutral-800">
                      {parameterRows.map((row) => (
                        <div
                          key={row.key}
                          className="grid grid-cols-[1.2fr_1fr] items-center gap-3 py-2 text-sm"
                        >
                          <span className="text-neutral-200">{row.key}</span>
                          <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-right text-neutral-200">
                            {row.value}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex flex-col gap-3 rounded-lg border border-neutral-800 bg-neutral-900 p-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <button className="flex-1 rounded-lg border border-neutral-700 bg-neutral-800 px-4 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-neutral-700">
                        Start Complete Workflow
                      </button>
                      <button className="rounded-lg border border-neutral-700 bg-neutral-800 px-4 py-3 text-sm font-semibold text-neutral-200 hover:border-neutral-500">
                        Cancel
                      </button>
                    </div>
                    <div className="h-2 rounded-full bg-neutral-800">
                      <div className="h-full w-1/3 rounded-full bg-neutral-200 transition-all" />
                    </div>
                    <p className="text-xs text-neutral-400">
                      Progress bar placeholder -- indeterminate while running.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-neutral-900 bg-neutral-900 p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-2xl font-semibold uppercase tracking-[0.12em] text-neutral-50">
                Merge
              </h2>
              <span className="rounded-full border border-neutral-700 bg-neutral-800 px-3 py-1 text-xs text-neutral-200">
                Static scaffold
              </span>
            </div>

            <div className="space-y-4">
              <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-neutral-50">
                      Assign FOVs
                    </p>
                    <p className="text-xs text-neutral-400">
                      Table mirrors PyAMA-Pro layout
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-[11px]">
                    <span className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-neutral-200">
                      Add Sample
                    </span>
                    <span className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-neutral-200">
                      Remove Selected
                    </span>
                  </div>
                </div>

                <div className="overflow-hidden rounded-lg border border-neutral-800">
                  <table className="w-full text-sm text-neutral-100">
                    <thead className="bg-neutral-800 text-left text-[13px] text-neutral-300">
                      <tr>
                        <th className="px-3 py-2 font-semibold">Sample Name</th>
                        <th className="px-3 py-2 font-semibold">
                          FOVs (e.g., 0-5, 7, 9-11)
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800 bg-neutral-900">
                      {sampleRows.map((row) => (
                        <tr key={row.name} className="hover:bg-neutral-800/60">
                          <td className="px-3 py-2 font-semibold text-neutral-50">
                            {row.name}
                          </td>
                          <td className="px-3 py-2 text-neutral-300">
                            {row.fovs}
                          </td>
                        </tr>
                      ))}
                      <tr className="bg-neutral-900">
                        <td className="px-3 py-2 text-neutral-400">
                          New sample...
                        </td>
                        <td className="px-3 py-2 text-neutral-400">
                          Enter FOV ranges here
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-neutral-300">
                  <span className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1">
                    Load from YAML
                  </span>
                  <span className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1">
                    Save to YAML
                  </span>
                </div>
              </div>

              <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
                <div className="mb-3 space-y-1">
                  <p className="text-sm font-semibold text-neutral-50">
                    Merge Samples
                  </p>
                  <p className="text-xs text-neutral-400">
                    File selectors and run button (placeholder)
                  </p>
                </div>

                <div className="space-y-3 text-sm text-neutral-200">
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span>Sample YAML</span>
                      <button
                        className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px]"
                        onClick={() =>
                          openPicker({
                            key: "sampleYaml",
                            title: "Choose sample.yaml",
                            description:
                              "Select a samples YAML that defines FOV assignments",
                            accept: ".yaml,.yml",
                          })
                        }
                      >
                        Browse
                      </button>
                    </div>
                    <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-neutral-300">
                      {selections.sampleYaml || "sample.yaml (unselected)"}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span>Processing Results YAML</span>
                      <button
                        className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px]"
                        onClick={() =>
                          openPicker({
                            key: "processingYaml",
                            title: "Choose processing_results.yaml",
                            description:
                              "Select the processing results YAML generated by workflow",
                            accept: ".yaml,.yml",
                          })
                        }
                      >
                        Browse
                      </button>
                    </div>
                    <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-neutral-300">
                      {selections.processingYaml ||
                        "processing_results.yaml (unselected)"}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span>Output Folder</span>
                      <button
                        className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px]"
                        onClick={() =>
                          openPicker({
                            key: "mergeOutput",
                            title: "Choose merge output folder",
                            description:
                              "Select where merged CSVs should be written",
                            directory: true,
                          })
                        }
                      >
                        Browse
                      </button>
                    </div>
                    <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-neutral-300">
                      {selections.mergeOutput || "/output/path (unselected)"}
                    </div>
                  </div>

                  <button className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-800 px-4 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-neutral-700">
                    Run Merge
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
