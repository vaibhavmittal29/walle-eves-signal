import React, { useState } from 'react';
import { X, ShieldCheck, Camera, Layers, Sliders } from 'lucide-react';
import { CaptureConfig } from '../../shared/types.js';

interface MonitorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: any) => Promise<void>;
  initialData?: any;
}

export const MonitorModal: React.FC<MonitorModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  initialData,
}) => {
  const [url, setUrl] = useState(initialData?.canonical_url || '');
  const [name, setName] = useState(initialData?.name || '');
  const [intervalMinutes, setIntervalMinutes] = useState(initialData?.interval_minutes || 60);
  const [engine, setEngine] = useState<'http_dom' | 'playwright'>(initialData?.capture_config?.engine || 'http_dom');
  const [screenshotRequired, setScreenshotRequired] = useState(initialData?.capture_config?.screenshotRequired || false);
  const [sensitivity, setSensitivity] = useState<'low' | 'balanced' | 'high'>(initialData?.sensitivity || 'balanced');
  const [timestampsFilter, setTimestampsFilter] = useState(initialData?.noise_filters?.timestamps ?? true);
  const [countersFilter, setCountersFilter] = useState(initialData?.noise_filters?.counters ?? true);
  const [tokensFilter, setTokensFilter] = useState(initialData?.noise_filters?.tokens ?? true);
  const [includeSelectors, setIncludeSelectors] = useState<string>(
    (initialData?.include_selectors || []).join(', ')
  );
  const [ignoreSelectors, setIgnoreSelectors] = useState<string>(
    (initialData?.ignore_selectors || []).join(', ')
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const capture_config: Partial<CaptureConfig> = {
        engine,
        screenshotRequired: engine === 'playwright' ? screenshotRequired : false,
      };

      const includes = includeSelectors
        .split(',')
        .map(s => s.trim())
        .filter(s => s.length > 0);

      const ignores = ignoreSelectors
        .split(',')
        .map(s => s.trim())
        .filter(s => s.length > 0);

      await onSubmit({
        url,
        name,
        interval_minutes: parseInt(String(intervalMinutes), 10),
        sensitivity,
        capture_config,
        include_selectors: includes,
        ignore_selectors: ignores,
        noise_filters: {
          timestamps: timestampsFilter,
          counters: countersFilter,
          tokens: tokensFilter,
        },
      });

      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save monitor');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-[#111827] border border-gray-800 rounded-xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gray-900/60">
          <h2 className="text-sm font-bold text-white flex items-center space-x-2">
            <span>{initialData ? 'Edit Monitor' : 'Create New Monitor'}</span>
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-1 rounded-md hover:bg-gray-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {error && (
            <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
              {error}
            </div>
          )}

          {/* Target URL */}
          <div>
            <label className="block text-gray-300 font-semibold mb-1">Target Webpage URL</label>
            <input
              type="text"
              required
              placeholder="https://example.com/announcements or fixture://stable-clean"
              value={url}
              onChange={e => setUrl(e.target.value)}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:border-emerald-500 font-mono text-xs"
            />
          </div>

          {/* Monitor Name */}
          <div>
            <label className="block text-gray-300 font-semibold mb-1">Monitor Name</label>
            <input
              type="text"
              required
              placeholder="e.g. University Portal Updates"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:border-emerald-500 text-xs"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            {/* Interval */}
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Check Interval (Minutes)</label>
              <input
                type="number"
                min={15}
                max={1440}
                required
                value={intervalMinutes}
                onChange={e => setIntervalMinutes(parseInt(e.target.value, 10))}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-gray-200 focus:outline-none focus:border-emerald-500 text-xs font-mono"
              />
            </div>

            {/* Sensitivity */}
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Sensitivity Policy</label>
              <select
                value={sensitivity}
                onChange={e => setSensitivity(e.target.value as any)}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-gray-200 focus:outline-none focus:border-emerald-500 text-xs"
              >
                <option value="low">Low (2-Check Confirmation)</option>
                <option value="balanced">Balanced (Standard)</option>
                <option value="high">High (Instant Alert)</option>
              </select>
            </div>
          </div>

          {/* Capture Engine Selection */}
          <div className="pt-2 border-t border-gray-800/80">
            <label className="block text-gray-300 font-semibold mb-2">Capture Engine</label>
            <div className="grid grid-cols-2 gap-3">
              <label className={`flex items-start p-3 rounded-lg border cursor-pointer transition-all ${
                engine === 'http_dom' ? 'bg-emerald-950/30 border-emerald-500/60' : 'bg-gray-900 border-gray-800'
              }`}>
                <input
                  type="radio"
                  name="engine"
                  value="http_dom"
                  checked={engine === 'http_dom'}
                  onChange={() => {
                    setEngine('http_dom');
                    setScreenshotRequired(false);
                  }}
                  className="mt-0.5 text-emerald-500 focus:ring-emerald-500"
                />
                <div className="ml-2.5">
                  <span className="block font-semibold text-gray-200">HTTP DOM (Fast)</span>
                  <span className="block text-[11px] text-gray-400 mt-0.5">Socket-pinned Cheerio parser. Low overhead, ideal for static text.</span>
                </div>
              </label>

              <label className={`flex items-start p-3 rounded-lg border cursor-pointer transition-all ${
                engine === 'playwright' ? 'bg-emerald-950/30 border-emerald-500/60' : 'bg-gray-900 border-gray-800'
              }`}>
                <input
                  type="radio"
                  name="engine"
                  value="playwright"
                  checked={engine === 'playwright'}
                  onChange={() => setEngine('playwright')}
                  className="mt-0.5 text-emerald-500 focus:ring-emerald-500"
                />
                <div className="ml-2.5">
                  <span className="block font-semibold text-gray-200">Chromium Browser</span>
                  <span className="block text-[11px] text-gray-400 mt-0.5">Full JS execution, SPA support, visual screenshot captures.</span>
                </div>
              </label>
            </div>
          </div>

          {/* Screenshot Option (Guarded by engine) */}
          <div className="flex items-center justify-between p-3 rounded-lg bg-gray-900 border border-gray-800">
            <div className="flex items-center space-x-2">
              <Camera className="w-4 h-4 text-gray-400" />
              <div>
                <span className="text-gray-200 font-semibold">Visual Screenshots</span>
                <span className="block text-[10px] text-gray-500">
                  {engine === 'playwright'
                    ? 'Captures full-page PNG and enables pixel-diff visual comparison.'
                    : 'Requires Chromium Browser engine (disabled for HTTP DOM).'}
                </span>
              </div>
            </div>
            <input
              type="checkbox"
              disabled={engine !== 'playwright'}
              checked={screenshotRequired && engine === 'playwright'}
              onChange={e => setScreenshotRequired(e.target.checked)}
              className="rounded bg-gray-800 border-gray-700 text-emerald-500 focus:ring-emerald-500 h-4 w-4 disabled:opacity-30"
            />
          </div>

          {/* Noise Filters Toggles */}
          <div className="pt-2 border-t border-gray-800/80">
            <label className="block text-gray-300 font-semibold mb-2">Deterministic Noise Filters</label>
            <div className="flex items-center space-x-4">
              <label className="flex items-center space-x-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={timestampsFilter}
                  onChange={e => setTimestampsFilter(e.target.checked)}
                  className="rounded bg-gray-800 border-gray-700 text-emerald-500 focus:ring-emerald-500"
                />
                <span className="text-gray-300">Timestamps</span>
              </label>
              <label className="flex items-center space-x-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={countersFilter}
                  onChange={e => setCountersFilter(e.target.checked)}
                  className="rounded bg-gray-800 border-gray-700 text-emerald-500 focus:ring-emerald-500"
                />
                <span className="text-gray-300">Counters</span>
              </label>
              <label className="flex items-center space-x-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={tokensFilter}
                  onChange={e => setTokensFilter(e.target.checked)}
                  className="rounded bg-gray-800 border-gray-700 text-emerald-500 focus:ring-emerald-500"
                />
                <span className="text-gray-300">Tokens</span>
              </label>
            </div>
          </div>

          {/* Slicing Selectors */}
          <div className="grid grid-cols-2 gap-3 pt-2">
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Watch Selectors</label>
              <input
                type="text"
                placeholder="#content, .main-article"
                value={includeSelectors}
                onChange={e => setIncludeSelectors(e.target.value)}
                className="w-full px-3 py-1.5 bg-gray-900 border border-gray-800 rounded-lg text-gray-200 placeholder-gray-600 focus:outline-none focus:border-emerald-500 text-xs font-mono"
              />
            </div>
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Ignore Selectors</label>
              <input
                type="text"
                placeholder=".banner, #sidebar, footer"
                value={ignoreSelectors}
                onChange={e => setIgnoreSelectors(e.target.value)}
                className="w-full px-3 py-1.5 bg-gray-900 border border-gray-800 rounded-lg text-gray-200 placeholder-gray-600 focus:outline-none focus:border-emerald-500 text-xs font-mono"
              />
            </div>
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end space-x-2 pt-4 border-t border-gray-800">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:bg-gray-800 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold flex items-center space-x-1.5"
            >
              <span>{loading ? 'Saving...' : 'Save Monitor'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
