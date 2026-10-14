import React from 'react';
import { X, Clock, GitCommit, CheckCircle2, AlertOctagon, ShieldAlert, GitCompare, Activity } from 'lucide-react';
import { MonitorItem, VersionItem, CheckRunItem } from '../types/client.js';

interface MonitorDetailProps {
  monitor: MonitorItem | null;
  versions: VersionItem[];
  runs: CheckRunItem[];
  onClose: () => void;
  onOpenDiff: (v1Id?: string, v2Id?: string) => void;
}

export const MonitorDetail: React.FC<MonitorDetailProps> = ({
  monitor,
  versions,
  runs,
  onClose,
  onOpenDiff,
}) => {
  if (!monitor) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-xl h-full bg-[#111827] border-l border-gray-800 flex flex-col shadow-2xl">
        {/* Drawer Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-gray-900/80">
          <div>
            <h2 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>{monitor.name}</span>
            </h2>
            <p className="text-[11px] text-gray-400 font-mono truncate max-w-md mt-0.5">{monitor.canonical_url}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-gray-400 hover:text-white hover:bg-gray-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Tabs / Scrollable Container */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6 text-xs">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-gray-900/60 border border-gray-800">
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">Engine</span>
              <span className="font-mono text-gray-200 mt-0.5 block">{monitor.required_engine}</span>
            </div>
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">Interval</span>
              <span className="font-mono text-gray-200 mt-0.5 block">{monitor.interval_minutes} minutes</span>
            </div>
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">Sensitivity</span>
              <span className="capitalize text-gray-200 mt-0.5 block">{monitor.sensitivity}</span>
            </div>
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">Active Baseline</span>
              <span className="font-mono text-emerald-400 mt-0.5 block">v{monitor.latest_version_number || 1}</span>
            </div>
          </div>

          {/* Version Snapshot History */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-gray-200 flex items-center space-x-1.5">
                <GitCommit className="w-4 h-4 text-emerald-400" />
                <span>Version Snapshots ({versions.length})</span>
              </h3>
              {versions.length >= 2 && (
                <button
                  onClick={() => onOpenDiff(versions[1].id, versions[0].id)}
                  className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/40 text-[11px] font-semibold"
                >
                  <GitCompare className="w-3 h-3" />
                  <span>Compare Recent</span>
                </button>
              )}
            </div>

            <div className="space-y-2">
              {versions.map((v, i) => (
                <div
                  key={v.id}
                  className="p-3 rounded-lg bg-gray-900/70 border border-gray-800 flex items-start justify-between"
                >
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-mono font-bold text-emerald-400">v{v.version_number}</span>
                      <span className="text-gray-300 font-medium">{v.change_summary || 'Snapshot'}</span>
                    </div>
                    <p className="text-[11px] text-gray-500 font-mono mt-1">Hash: {v.content_hash.slice(0, 16)}...</p>
                    <p className="text-[10px] text-gray-500 mt-0.5">{new Date(v.created_at).toLocaleString()}</p>
                  </div>
                  {i < versions.length - 1 && (
                    <button
                      onClick={() => onOpenDiff(versions[i + 1].id, v.id)}
                      className="text-[10px] font-semibold text-gray-400 hover:text-white px-2 py-1 rounded bg-gray-800 hover:bg-gray-700"
                    >
                      Diff
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Operational Check Runs Log */}
          <div className="space-y-3 pt-3 border-t border-gray-800">
            <h3 className="font-bold text-gray-200 flex items-center space-x-1.5">
              <Activity className="w-4 h-4 text-sky-400" />
              <span>Recent Check Runs (Audit Log)</span>
            </h3>

            <div className="space-y-1.5">
              {runs.map(r => (
                <div
                  key={r.id}
                  className="flex items-center justify-between p-2 rounded bg-gray-900/40 border border-gray-800/80 text-[11px]"
                >
                  <div className="flex items-center space-x-2">
                    {r.outcome === 'OK' ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : r.outcome === 'BLOCKED' ? (
                      <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                    ) : (
                      <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
                    )}
                    <span className="font-semibold text-gray-300">{r.outcome}</span>
                    <span className="text-gray-500 font-mono">({r.duration_ms}ms)</span>
                    {r.was_deduplicated ? (
                      <span className="text-[10px] px-1 rounded bg-sky-950 text-sky-400 border border-sky-800">DEDUP</span>
                    ) : null}
                  </div>
                  <span className="text-gray-500">{new Date(r.created_at).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
