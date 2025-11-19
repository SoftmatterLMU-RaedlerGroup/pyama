/* eslint-disable @next/next/no-img-element */
import { useState, useMemo } from 'react';
import { PyamaApiService } from '@/lib/api';
import type {
  VisualizationInitResponse,
  VisualizationFrameResponse,
} from '@/types/visualization';

export default function VisualizationTestPage() {
  const [outputDir, setOutputDir] = useState('');
  const [fovId, setFovId] = useState(0);
  const [channels, setChannels] = useState('pc');
  const [frame, setFrame] = useState(0);
  const [initResp, setInitResp] = useState<VisualizationInitResponse | null>(null);
  const [frameResp, setFrameResp] = useState<VisualizationFrameResponse | null>(null);
  const [loadingInit, setLoadingInit] = useState(false);
  const [loadingFrame, setLoadingFrame] = useState(false);

  const channelList = useMemo(
    () => channels.split(',').map((c) => c.trim()).filter(Boolean),
    [channels],
  );

  const handleInit = async () => {
    setLoadingInit(true);
    setFrameResp(null);
    try {
      const resp = await PyamaApiService.initVisualization({
        output_dir: outputDir,
        fov_id: fovId,
        channels: channelList,
        data_types: ['image', 'seg'],
        force_rebuild: false,
      });
      setInitResp(resp);
    } catch (err) {
      console.error(err);
      setInitResp({
        success: false,
        fov_id: fovId,
        channels: [],
        error: 'Failed to init visualization',
      });
    } finally {
      setLoadingInit(false);
    }
  };

  const handleLoadFrame = async (channel: string, frameIndex: number) => {
    if (!initResp) return;
    const meta = initResp.channels.find((c) => c.channel === channel);
    if (!meta) return;
    setLoadingFrame(true);
    try {
      const resp = await PyamaApiService.getVisualizationFrame({
        cached_path: meta.path,
        channel,
        frame: frameIndex,
      });
      setFrameResp(resp);
    } catch (err) {
      console.error(err);
      setFrameResp({
        success: false,
        channel,
        frames: [],
        error: 'Failed to load frame',
      });
    } finally {
      setLoadingFrame(false);
    }
  };

  const currentFrame = frameResp?.frames?.[0];

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="p-3 bg-muted rounded-lg border">
        <div className="text-xs font-medium text-muted-foreground mb-2">Testing Endpoints:</div>
        <div className="space-y-1 text-sm">
          <div>
            •{' '}
            <code className="bg-background px-2 py-1 rounded border">
              POST /api/v1/visualization/init
            </code>
          </div>
          <div>
            •{' '}
            <code className="bg-background px-2 py-1 rounded border">
              POST /api/v1/visualization/frame
            </code>
          </div>
        </div>
      </div>

      <div className="grid gap-4">
        <label className="space-y-1">
          <div className="text-sm font-medium">Output directory</div>
          <input
            className="w-full rounded border px-2 py-1 text-sm"
            value={outputDir}
            onChange={(e) => setOutputDir(e.target.value)}
            placeholder="/path/to/output"
          />
        </label>

        <label className="space-y-1">
          <div className="text-sm font-medium">FOV ID</div>
          <input
            className="w-full rounded border px-2 py-1 text-sm"
            type="number"
            value={fovId}
            onChange={(e) => setFovId(Number(e.target.value))}
          />
        </label>

        <label className="space-y-1">
          <div className="text-sm font-medium">Channels (comma separated)</div>
          <input
            className="w-full rounded border px-2 py-1 text-sm"
            value={channels}
            onChange={(e) => setChannels(e.target.value)}
            placeholder="pc,1"
          />
        </label>

        <button
          className="inline-flex items-center justify-center rounded bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
          onClick={handleInit}
          disabled={loadingInit}
        >
          {loadingInit ? 'Initializing…' : 'Init Visualization'}
        </button>
      </div>

      {initResp && (
        <div className="space-y-3">
          <div className="text-sm font-medium">Init Response</div>
          <pre className="bg-muted rounded border p-3 text-xs overflow-auto">
            {JSON.stringify(initResp, null, 2)}
          </pre>
        </div>
      )}

      {initResp && initResp.success && initResp.channels.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <select
              className="rounded border px-2 py-1 text-sm"
              onChange={(e) => handleLoadFrame(e.target.value, frame)}
              defaultValue={initResp.channels[0].channel}
            >
              {initResp.channels.map((c) => (
                <option key={c.channel} value={c.channel}>
                  {c.channel}
                </option>
              ))}
            </select>
            <input
              type="range"
              min={0}
              max={initResp.channels[0].n_frames - 1}
              value={frame}
              onChange={(e) => {
                const val = Number(e.target.value);
                setFrame(val);
                handleLoadFrame(
                  (initResp.channels[0]?.channel as string) || 'pc',
                  val,
                );
              }}
              className="flex-1"
            />
            <span className="text-xs text-muted-foreground">Frame {frame}</span>
          </div>
          <button
            className="inline-flex items-center justify-center rounded bg-secondary px-3 py-2 text-sm font-medium"
            onClick={() =>
              handleLoadFrame(
                (initResp.channels[0]?.channel as string) || 'pc',
                frame,
              )
            }
            disabled={loadingFrame}
          >
            {loadingFrame ? 'Loading frame…' : 'Load Frame'}
          </button>
        </div>
      )}

      {currentFrame && (
        <div className="space-y-3">
          <div className="text-sm font-medium">Frame Preview</div>
          <div className="border rounded overflow-hidden w-full max-w-xl">
            <img
              alt="frame"
              className="w-full h-auto"
              src={`data:image/png;base64,${arrayToPng(currentFrame)}`}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function arrayToPng(data: number[][]): string {
  // Simple grayscale PNG encoder using canvas in the browser.
  if (typeof window === 'undefined') return '';
  const height = data.length;
  const width = data[0]?.length || 0;
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';
  const imageData = ctx.createImageData(width, height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = (y * width + x) * 4;
      const v = data[y][x] ?? 0;
      imageData.data[idx] = v;
      imageData.data[idx + 1] = v;
      imageData.data[idx + 2] = v;
      imageData.data[idx + 3] = 255;
    }
  }
  ctx.putImageData(imageData, 0, 0);
  return canvas.toDataURL('image/png').split(',')[1];
}
