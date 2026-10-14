import React, { useState, useEffect } from 'react';
import { ShieldCheck, Plus, Sparkles, AlertOctagon, ShieldAlert, Cpu } from 'lucide-react';

interface FixtureItem {
  id: string;
  name: string;
  description: string;
  statusCode: number;
  url: string;
}

interface FixtureSwitcherProps {
  onCreateMonitorFromFixture: (fixtureUrl: string, name: string) => void;
}

export const FixtureSwitcher: React.FC<FixtureSwitcherProps> = ({
  onCreateMonitorFromFixture,
}) => {
  const [fixtures, setFixtures] = useState<FixtureItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [mutatingId, setMutatingId] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/fixtures')
      .then(res => res.json())
      .then(data => {
        setFixtures(data.fixtures || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleSimulateChange = async (fixtureId: string) => {
    setMutatingId(fixtureId);
    try {
      await fetch(`/api/fixtures/${fixtureId}/mutate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          html: `<!DOCTYPE html><html><body><h1>Simulated Update!</h1><p class="announcement">New update triggered at ${new Date().toLocaleTimeString()}!</p></body></html>`,
        }),
      });
      alert(`Fixture "${fixtureId}" content mutated successfully! Trigger a manual check on any monitor watching this fixture to observe version diffing.`);
    } finally {
      setMutatingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-sm font-bold text-white flex items-center space-x-2">
          <ShieldCheck className="w-5 h-5 text-emerald-400" />
          <span>Deterministic Testbed Fixtures (14+ Edge Cases)</span>
        </h2>
        <p className="text-xs text-gray-400 mt-1">
          Use these in-memory test fixtures to safely verify diff algorithms, noise filters, anti-bot handling, and outage resilience without external internet dependencies.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {fixtures.map(f => {
          const isError = f.statusCode >= 500;
          const isBlocked = f.statusCode === 403 || f.id.includes('challenge') || f.id.includes('robots');

          return (
            <div
              key={f.id}
              className="p-4 rounded-xl bg-gray-900/60 border border-gray-800 flex flex-col justify-between hover:border-gray-700 transition-all shadow-sm"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-bold ${
                    isError
                      ? 'bg-rose-950 text-rose-300 border border-rose-800'
                      : isBlocked
                      ? 'bg-amber-950 text-amber-300 border border-amber-800'
                      : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                  }`}>
                    HTTP {f.statusCode}
                  </span>
                  <span className="text-[10px] font-mono text-gray-500 truncate max-w-[150px]">{f.url}</span>
                </div>

                <h3 className="font-bold text-gray-200 mt-2.5 text-xs">{f.name}</h3>
                <p className="text-[11px] text-gray-400 mt-1 leading-relaxed">{f.description}</p>
              </div>

              <div className="flex items-center space-x-2 pt-4 mt-3 border-t border-gray-800/80">
                <button
                  onClick={() => onCreateMonitorFromFixture(f.url, f.name)}
                  className="flex-1 py-1.5 px-2 rounded-md bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-300 border border-emerald-500/40 text-[11px] font-semibold flex items-center justify-center space-x-1"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Track URL</span>
                </button>
                <button
                  onClick={() => handleSimulateChange(f.id)}
                  disabled={mutatingId === f.id}
                  title="Simulate Content Change"
                  className="py-1.5 px-2.5 rounded-md bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/40 text-[11px] font-semibold flex items-center justify-center space-x-1 disabled:opacity-40"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Mutate</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
