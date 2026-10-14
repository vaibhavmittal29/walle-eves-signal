import React, { useState } from 'react';
import { X, GitCompare, Code, Columns, Split } from 'lucide-react';
import { MyersDiffResult, DiffChunk } from '../types/client.js';

interface DiffViewerProps {
  isOpen: boolean;
  onClose: () => void;
  diffData: {
    previousVersion?: any;
    currentVersion?: any;
    diff: MyersDiffResult;
  } | null;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  isOpen,
  onClose,
  diffData,
}) => {
  const [viewMode, setViewMode] = useState<'line' | 'patch'>('line');

  if (!isOpen || !diffData) return null;

  const { previousVersion, currentVersion, diff } = diffData;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-[#111827] border border-gray-800 rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gray-900/80">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
              <GitCompare className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white flex items-center space-x-2">
                <span>Version Diff Comparison</span>
                <span className="text-xs font-mono text-emerald-400">
                  v{previousVersion?.version_number || 1} → v{currentVersion?.version_number}
                </span>
              </h2>
              <div className="flex items-center space-x-2 text-[11px] text-gray-400 mt-0.5">
                <span className="text-emerald-400">+{diff.additions} additions</span>
                <span>•</span>
                <span className="text-rose-400">-{diff.deletions} deletions</span>
              </div>
            </div>
          </div>

          {/* Toggle View Mode */}
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1 bg-gray-900 p-1 rounded-lg border border-gray-800">
              <button
                onClick={() => setViewMode('line')}
                className={`px-2.5 py-1 text-xs font-semibold rounded ${
                  viewMode === 'line' ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                Line Diff
              </button>
              <button
                onClick={() => setViewMode('patch')}
                className={`px-2.5 py-1 text-xs font-semibold rounded ${
                  viewMode === 'patch' ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                Unified Patch
              </button>
            </div>

            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white p-1.5 rounded-lg hover:bg-gray-800"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Diff Container */}
        <div className="flex-1 overflow-y-auto p-6 font-mono text-xs">
          {viewMode === 'line' ? (
            <div className="divide-y divide-gray-800/60 rounded-lg overflow-hidden border border-gray-800 bg-gray-950">
              {diff.lineChanges.map((chunk: DiffChunk, idx: number) => {
                const isAdded = chunk.type === 'added';
                const isRemoved = chunk.type === 'removed';

                return (
                  <div
                    key={idx}
                    className={`px-4 py-1.5 flex items-start space-x-3 whitespace-pre-wrap ${
                      isAdded
                        ? 'bg-emerald-950/40 text-emerald-300 border-l-2 border-emerald-500'
                        : isRemoved
                        ? 'bg-rose-950/40 text-rose-300 border-l-2 border-rose-500 line-through opacity-80'
                        : 'text-gray-300 hover:bg-gray-900/50'
                    }`}
                  >
                    <span className="w-5 text-gray-600 select-none font-bold">
                      {isAdded ? '+' : isRemoved ? '-' : ' '}
                    </span>
                    <span className="flex-1">{chunk.value}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <pre className="p-4 rounded-lg bg-gray-950 border border-gray-800 text-gray-300 whitespace-pre-wrap leading-relaxed">
              {diff.unifiedPatch}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
};
