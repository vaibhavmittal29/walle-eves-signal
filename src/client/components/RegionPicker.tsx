import React, { useState, useEffect } from 'react';
import { X, Crosshair, Check, AlertTriangle, ShieldCheck, PlusCircle, MinusCircle } from 'lucide-react';
import { MonitorItem } from '../types/client.js';

interface RegionPickerProps {
  monitor: MonitorItem | null;
  isOpen: boolean;
  onClose: () => void;
  onSaveSelectors: (monitorId: string, includes: string[], ignores: string[]) => Promise<void>;
}

export const RegionPicker: React.FC<RegionPickerProps> = ({
  monitor,
  isOpen,
  onClose,
  onSaveSelectors,
}) => {
  const [selectedSelector, setSelectedSelector] = useState<string>('');
  const [hoveredElement, setHoveredElement] = useState<string | null>(null);
  const [includes, setIncludes] = useState<string[]>([]);
  const [ignores, setIgnores] = useState<string[]>([]);
  const [htmlContent, setHtmlContent] = useState<string>('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (monitor) {
      setIncludes(monitor.include_selectors || []);
      setIgnores(monitor.ignore_selectors || []);
      // Fetch preview fixture HTML if fixture://, otherwise sample DOM
      if (monitor.canonical_url.startsWith('fixture://')) {
        const id = monitor.canonical_url.replace('fixture://', '').split('/')[0];
        fetch(`/api/fixtures/${id}`)
          .then(res => res.json())
          .then(data => {
            if (data.fixture) setHtmlContent(data.fixture.html);
          })
          .catch(() => {});
      } else {
        setHtmlContent(`
          <div id="page-wrapper">
            <header class="site-header">
              <h1 id="brand-title">${monitor.name}</h1>
            </header>
            <main id="main-content" class="content-body">
              <article class="primary-announcement">
                <h2 class="headline">Sample Tracked Element</h2>
                <p class="description">Click anywhere inside this container to inspect and isolate its CSS selector.</p>
              </article>
            </main>
          </div>
        `);
      }
    }
  }, [monitor]);

  if (!isOpen || !monitor) return null;

  // Stability evaluation for CSS selectors
  const evaluateStability = (sel: string): { isStable: boolean; warning?: string } => {
    if (!sel) return { isStable: true };
    if (/(:nth-child\(\d+\)){2,}/.test(sel)) {
      return { isStable: false, warning: 'Deep nth-child chaining is fragile to minor DOM shifts' };
    }
    if (/\b(?:css-|sc-|_)[a-z0-9]{5,}\b/i.test(sel)) {
      return { isStable: false, warning: 'Detected hashed/generated class name that may change on rebuild' };
    }
    return { isStable: true };
  };

  const stability = evaluateStability(selectedSelector);

  const addInclude = (sel: string) => {
    if (sel && !includes.includes(sel)) setIncludes([...includes, sel]);
  };

  const addIgnore = (sel: string) => {
    if (sel && !ignores.includes(sel)) setIgnores([...ignores, sel]);
  };

  const removeInclude = (sel: string) => setIncludes(includes.filter(s => s !== sel));
  const removeIgnore = (sel: string) => setIgnores(ignores.filter(s => s !== sel));

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSaveSelectors(monitor.id, includes, ignores);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-[#111827] border border-gray-800 rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gray-900/80">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/30">
              <Crosshair className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white flex items-center space-x-2">
                <span>Visual Region Picker & CSS Selector Generator</span>
              </h2>
              <p className="text-[11px] text-gray-400 font-mono mt-0.5">{monitor.canonical_url}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-gray-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Interactive Selector Preview & Control Strip */}
        <div className="p-4 bg-gray-900/50 border-b border-gray-800 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center space-x-2 flex-1 min-w-[280px]">
            <span className="font-semibold text-gray-400">Selected:</span>
            <input
              type="text"
              value={selectedSelector}
              onChange={e => setSelectedSelector(e.target.value)}
              placeholder="Click a preview element below or type selector..."
              className="flex-1 px-3 py-1.5 bg-gray-950 border border-gray-700 rounded text-gray-200 font-mono text-xs focus:outline-none focus:border-sky-500"
            />
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => addInclude(selectedSelector)}
              disabled={!selectedSelector}
              className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-semibold disabled:opacity-40 flex items-center space-x-1"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              <span>+ Watch Selector</span>
            </button>
            <button
              onClick={() => addIgnore(selectedSelector)}
              disabled={!selectedSelector}
              className="px-3 py-1.5 rounded bg-rose-600 hover:bg-rose-500 text-white font-semibold disabled:opacity-40 flex items-center space-x-1"
            >
              <MinusCircle className="w-3.5 h-3.5" />
              <span>+ Ignore Selector</span>
            </button>
          </div>
        </div>

        {/* Stability Warning */}
        {selectedSelector && (
          <div className={`px-6 py-2 text-xs flex items-center space-x-2 ${
            stability.isStable ? 'bg-emerald-950/20 text-emerald-300' : 'bg-amber-950/30 text-amber-300'
          }`}>
            {stability.isStable ? (
              <>
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Selector appears stable and resilient to layout shifts.</span>
              </>
            ) : (
              <>
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>Stability Warning: {stability.warning}</span>
              </>
            )}
          </div>
        )}

        {/* Visual Inspection Area */}
        <div className="flex-1 grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-gray-800 overflow-hidden">
          {/* HTML Canvas Preview (Clickable Elements) */}
          <div className="md:col-span-2 p-6 overflow-y-auto bg-gray-950 text-gray-300 font-sans text-xs">
            <p className="text-gray-500 font-mono mb-4 text-[11px]">
              Tip: Click on any element below to isolate its CSS selector.
            </p>

            <div
              className="p-4 rounded-lg bg-gray-900 border border-gray-800 space-y-4"
              onClick={(e) => {
                const target = e.target as HTMLElement;
                if (!target) return;
                let sel = target.id ? `#${target.id}` : target.className ? `.${target.className.split(' ')[0]}` : target.tagName.toLowerCase();
                setSelectedSelector(sel);
              }}
            >
              <div
                id="content"
                className="p-3 border border-dashed border-gray-700 rounded hover:border-sky-400 hover:bg-sky-950/20 transition-all cursor-pointer"
              >
                <h2 className="text-sm font-bold text-white mb-1">#content (Main Content Region)</h2>
                <p className="text-gray-400">All announcements, assignments, and schedule updates reside inside this block.</p>
                <div className="announcement mt-3 p-2 bg-gray-800/80 rounded border border-gray-700 hover:border-emerald-400 hover:bg-emerald-950/20 transition-all cursor-pointer">
                  <span className="font-semibold text-emerald-400">.announcement</span>
                  <p className="text-gray-300 mt-0.5">Laboratory session dates and urgent notifications.</p>
                </div>
              </div>

              <footer className="footer p-2 text-gray-500 border border-dashed border-gray-800 rounded hover:border-rose-400 hover:bg-rose-950/20 cursor-pointer">
                <span>footer (Static Copyright Block)</span>
              </footer>
            </div>
          </div>

          {/* Slices Config Sidebar */}
          <div className="p-5 bg-[#111827] overflow-y-auto space-y-5 text-xs">
            {/* Watch Selectors List */}
            <div>
              <span className="font-bold text-emerald-400 block mb-2">Watch Selectors ({includes.length})</span>
              {includes.length === 0 ? (
                <p className="text-gray-500 italic text-[11px]">Watching entire page body</p>
              ) : (
                <div className="space-y-1.5">
                  {includes.map(sel => (
                    <div key={sel} className="flex items-center justify-between p-1.5 rounded bg-emerald-950/30 border border-emerald-800/60 font-mono text-[11px] text-emerald-300">
                      <span className="truncate">{sel}</span>
                      <button onClick={() => removeInclude(sel)} className="text-gray-500 hover:text-rose-400">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Ignore Selectors List */}
            <div>
              <span className="font-bold text-rose-400 block mb-2">Ignore Selectors ({ignores.length})</span>
              {ignores.length === 0 ? (
                <p className="text-gray-500 italic text-[11px]">No elements ignored</p>
              ) : (
                <div className="space-y-1.5">
                  {ignores.map(sel => (
                    <div key={sel} className="flex items-center justify-between p-1.5 rounded bg-rose-950/30 border border-rose-800/60 font-mono text-[11px] text-rose-300">
                      <span className="truncate">{sel}</span>
                      <button onClick={() => removeIgnore(sel)} className="text-gray-500 hover:text-rose-400">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-2 px-6 py-3 border-t border-gray-800 bg-gray-900/80">
          <button onClick={onClose} className="px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:bg-gray-800 font-medium text-xs">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold text-xs flex items-center space-x-1.5"
          >
            <span>{saving ? 'Saving...' : 'Save Region Rules'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
