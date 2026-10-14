import React, { useState } from 'react';
import {
  Search,
  Play,
  Pause,
  Trash2,
  ExternalLink,
  Crosshair,
  GitCompare,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import { MonitorItem } from '../types/client.js';

interface DashboardProps {
  monitors: MonitorItem[];
  onTriggerCheck: (id: string) => Promise<void>;
  onTogglePause: (id: string, currentPaused: boolean) => Promise<void>;
  onDeleteMonitor: (id: string) => Promise<void>;
  onOpenDetail: (monitor: MonitorItem) => void;
  onOpenRegionPicker: (monitor: MonitorItem) => void;
  onOpenDiff: (monitor: MonitorItem) => void;
  onOpenCreate: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  monitors,
  onTriggerCheck,
  onTogglePause,
  onDeleteMonitor,
  onOpenDetail,
  onOpenRegionPicker,
  onOpenDiff,
  onOpenCreate,
}) => {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OK' | 'DOWN' | 'PAUSED' | 'NOISY'>('ALL');
  const [checkingIds, setCheckingIds] = useState<Set<string>>(new Set());

  const handleManualCheck = async (id: string) => {
    setCheckingIds(prev => new Set(prev).add(id));
    try {
      await onTriggerCheck(id);
    } finally {
      setCheckingIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const filtered = monitors.filter(m => {
    const matchesSearch =
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      m.canonical_url.toLowerCase().includes(search.toLowerCase());

    if (!matchesSearch) return false;

    if (statusFilter === 'OK') return !m.is_paused && !m.is_currently_down;
    if (statusFilter === 'DOWN') return m.is_currently_down;
    if (statusFilter === 'PAUSED') return m.is_paused;
    if (statusFilter === 'NOISY') return m.is_noisy;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Top Controls Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        {/* Search Input */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search monitors by name or URL..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-gray-900/80 border border-gray-800 rounded-lg text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 sm:pb-0">
          {(['ALL', 'OK', 'DOWN', 'PAUSED', 'NOISY'] as const).map(filter => (
            <button
              key={filter}
              onClick={() => setStatusFilter(filter)}
              className={`px-2.5 py-1 text-[11px] font-semibold rounded-md transition-all ${
                statusFilter === filter
                  ? 'bg-gray-800 text-white border border-gray-700 shadow-sm'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-900 border border-transparent'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>

      {/* High-Density Monitor Fleet Table */}
      <div className="bg-gray-900/40 border border-gray-800 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/60 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Monitor & Target</th>
                <th className="py-3 px-4">Engine</th>
                <th className="py-3 px-4">Interval</th>
                <th className="py-3 px-4">Version</th>
                <th className="py-3 px-4">Next Check</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 text-xs">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-gray-500">
                    <p className="text-sm font-medium">No monitors found</p>
                    <p className="text-xs text-gray-600 mt-1">Add your first URL or switch to a test fixture.</p>
                    <button
                      onClick={onOpenCreate}
                      className="mt-4 inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold"
                    >
                      Create Monitor
                    </button>
                  </td>
                </tr>
              ) : (
                filtered.map(m => {
                  const isChecking = checkingIds.has(m.id);
                  return (
                    <tr
                      key={m.id}
                      className="hover:bg-gray-800/30 transition-colors group"
                    >
                      {/* Health Status */}
                      <td className="py-3 px-4 whitespace-nowrap">
                        {m.is_paused ? (
                          <span className="inline-flex items-center space-x-1 text-gray-400 bg-gray-800/80 px-2 py-0.5 rounded text-[11px] font-medium border border-gray-700">
                            <span>PAUSED</span>
                          </span>
                        ) : m.is_currently_down ? (
                          <span className="inline-flex items-center space-x-1 text-rose-400 bg-rose-950/50 px-2 py-0.5 rounded text-[11px] font-medium border border-rose-800/60">
                            <XCircle className="w-3 h-3 text-rose-400" />
                            <span>DOWN ({m.consecutive_failures})</span>
                          </span>
                        ) : isChecking ? (
                          <span className="inline-flex items-center space-x-1 text-sky-400 bg-sky-950/50 px-2 py-0.5 rounded text-[11px] font-medium border border-sky-800 animate-pulse">
                            <Sparkles className="w-3 h-3 text-sky-400" />
                            <span>CHECKING</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center space-x-1 text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded text-[11px] font-medium border border-emerald-800/60">
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                            <span>OK</span>
                          </span>
                        )}
                        {m.is_noisy ? (
                          <span className="ml-1 inline-flex items-center text-amber-400 bg-amber-950/40 px-1.5 py-0.5 rounded text-[10px] font-medium border border-amber-800">
                            NOISY
                          </span>
                        ) : null}
                      </td>

                      {/* Monitor Name & URL */}
                      <td className="py-3 px-4 max-w-xs">
                        <button
                          onClick={() => onOpenDetail(m)}
                          className="font-semibold text-gray-200 hover:text-emerald-400 transition-colors truncate block text-left"
                        >
                          {m.name}
                        </button>
                        <div className="flex items-center space-x-1 text-[11px] text-gray-500 mt-0.5 font-mono truncate">
                          <span className="truncate">{m.canonical_url}</span>
                          <a
                            href={m.canonical_url.startsWith('http') ? m.canonical_url : '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-gray-500 hover:text-gray-300"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                      </td>

                      {/* Engine */}
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-300">
                          {m.required_engine === 'playwright' ? 'CHROMIUM' : 'HTTP_DOM'}
                        </span>
                      </td>

                      {/* Interval */}
                      <td className="py-3 px-4 whitespace-nowrap text-gray-300 font-mono text-[11px]">
                        {m.interval_minutes}m
                      </td>

                      {/* Version Snapshot */}
                      <td className="py-3 px-4 whitespace-nowrap font-mono text-emerald-400 text-[11px]">
                        v{m.latest_version_number || 1}
                      </td>

                      {/* Next Check Time */}
                      <td className="py-3 px-4 whitespace-nowrap text-gray-400 text-[11px] font-mono">
                        {m.is_paused ? 'Paused' : new Date(m.next_check_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-4 whitespace-nowrap text-right space-x-1">
                        <button
                          onClick={() => handleManualCheck(m.id)}
                          disabled={isChecking}
                          title="Run Immediate Check"
                          className="p-1.5 text-gray-400 hover:text-emerald-400 hover:bg-gray-800 rounded transition-colors"
                        >
                          <Play className={`w-3.5 h-3.5 ${isChecking ? 'animate-spin text-sky-400' : ''}`} />
                        </button>
                        <button
                          onClick={() => onOpenRegionPicker(m)}
                          title="Visual Region Picker"
                          className="p-1.5 text-gray-400 hover:text-sky-400 hover:bg-gray-800 rounded transition-colors"
                        >
                          <Crosshair className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => onOpenDiff(m)}
                          title="Diff & History"
                          className="p-1.5 text-gray-400 hover:text-indigo-400 hover:bg-gray-800 rounded transition-colors"
                        >
                          <GitCompare className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => onTogglePause(m.id, m.is_paused)}
                          title={m.is_paused ? 'Resume Monitor' : 'Pause Monitor'}
                          className="p-1.5 text-gray-400 hover:text-amber-400 hover:bg-gray-800 rounded transition-colors"
                        >
                          {m.is_paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                        </button>
                        <button
                          onClick={() => onDeleteMonitor(m.id)}
                          title="Delete Monitor"
                          className="p-1.5 text-gray-400 hover:text-rose-400 hover:bg-gray-800 rounded transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
