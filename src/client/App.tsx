import React, { useState, useEffect } from 'react';
import { Navigation } from './components/Navigation.js';
import { Dashboard } from './components/Dashboard.js';
import { MonitorModal } from './components/MonitorModal.js';
import { MonitorDetail } from './components/MonitorDetail.js';
import { DiffViewer } from './components/DiffViewer.js';
import { RegionPicker } from './components/RegionPicker.js';
import { FixtureSwitcher } from './components/FixtureSwitcher.js';
import { OutboxAudit } from './components/OutboxAudit.js';
import { MonitorItem, VersionItem, CheckRunItem } from './types/client.js';
import { Eye, Lock, Mail, User, ShieldAlert } from 'lucide-react';

export const App: React.FC = () => {
  // Authentication State
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);

  // App Navigation & Data
  const [currentTab, setCurrentTab] = useState<'monitors' | 'fixtures' | 'outbox'>('monitors');
  const [monitors, setMonitors] = useState<MonitorItem[]>([]);
  const [loadingMonitors, setLoadingMonitors] = useState(false);

  // Modals & Panels State
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedMonitor, setSelectedMonitor] = useState<MonitorItem | null>(null);
  const [monitorDetail, setMonitorDetail] = useState<{
    monitor: MonitorItem;
    versions: VersionItem[];
    runs: CheckRunItem[];
  } | null>(null);

  const [diffModal, setDiffModal] = useState<{
    isOpen: boolean;
    data: any;
  }>({ isOpen: false, data: null });

  const [regionPickerMonitor, setRegionPickerMonitor] = useState<MonitorItem | null>(null);

  // Check initial user authentication
  useEffect(() => {
    fetch('/api/auth/me')
      .then(res => {
        if (res.ok) return res.json();
        throw new Error('Not authenticated');
      })
      .then(data => {
        setCurrentUser(data.user);
      })
      .catch(() => {
        setCurrentUser(null);
      })
      .finally(() => {
        setAuthLoading(false);
      });
  }, []);

  // Fetch monitors when logged in
  const fetchMonitors = () => {
    if (!currentUser) return;
    setLoadingMonitors(true);
    fetch('/api/monitors')
      .then(res => res.json())
      .then(data => {
        setMonitors(data.monitors || []);
      })
      .catch(console.error)
      .finally(() => setLoadingMonitors(false));
  };

  useEffect(() => {
    fetchMonitors();
  }, [currentUser]);

  // Auth Handlers
  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);

    const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register';
    const body = authMode === 'login' ? { email, password } : { email, password, displayName };

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Authentication failed');
      }

      setCurrentUser(data.user);
    } catch (err: any) {
      setAuthError(err.message);
    }
  };

  const handleLogout = async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    setCurrentUser(null);
  };

  // Monitor Actions
  const handleCreateMonitor = async (formData: any) => {
    const res = await fetch('/api/monitors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Could not create monitor');

    fetchMonitors();
  };

  const handleTriggerCheck = async (id: string) => {
    const res = await fetch(`/api/monitors/${id}/check`, { method: 'POST' });
    if (res.ok) {
      fetchMonitors();
    }
  };

  const handleTogglePause = async (id: string, currentPaused: boolean) => {
    await fetch(`/api/monitors/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_paused: !currentPaused }),
    });
    fetchMonitors();
  };

  const handleDeleteMonitor = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this monitor? All versions and screenshot artifacts will be permanently purged.')) {
      return;
    }
    await fetch(`/api/monitors/${id}`, { method: 'DELETE' });
    fetchMonitors();
    if (monitorDetail?.monitor.id === id) setMonitorDetail(null);
  };

  const handleOpenDetail = async (monitor: MonitorItem) => {
    const res = await fetch(`/api/monitors/${monitor.id}`);
    const data = await res.json();
    if (res.ok) {
      setMonitorDetail({
        monitor: data.monitor,
        versions: data.versions || [],
        runs: data.recentRuns || [],
      });
    }
  };

  const handleOpenDiff = async (monitor: MonitorItem, v1Id?: string, v2Id?: string) => {
    const query = v1Id && v2Id ? `?v1=${v1Id}&v2=${v2Id}` : '';
    const res = await fetch(`/api/monitors/${monitor.id}/diff${query}`);
    const data = await res.json();
    if (res.ok) {
      setDiffModal({ isOpen: true, data });
    } else {
      alert(data.error || 'Cannot fetch diff for this monitor yet.');
    }
  };

  const handleSaveSelectors = async (monitorId: string, includes: string[], ignores: string[]) => {
    await fetch(`/api/monitors/${monitorId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        include_selectors: includes,
        ignore_selectors: ignores,
      }),
    });
    fetchMonitors();
  };

  // Auth Screen if not logged in
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0B0F17] text-gray-400">
        <div className="animate-pulse">Loading ChangeWatch...</div>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0B0F17] p-4">
        <div className="w-full max-w-sm bg-gray-900/80 border border-gray-800 rounded-2xl p-8 shadow-2xl backdrop-blur">
          <div className="flex items-center space-x-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Eye className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">ChangeWatch</h1>
              <p className="text-xs text-gray-400">Website Change Detection</p>
            </div>
          </div>

          <form onSubmit={handleAuthSubmit} className="space-y-4 text-xs">
            {authError && (
              <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300">
                {authError}
              </div>
            )}

            {authMode === 'register' && (
              <div>
                <label className="block text-gray-300 font-semibold mb-1">Display Name</label>
                <div className="relative">
                  <User className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    required
                    placeholder="Alice Cooper"
                    value={displayName}
                    onChange={e => setDisplayName(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-gray-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-gray-300 font-semibold mb-1">Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-gray-200 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-gray-300 font-semibold mb-1">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  placeholder="••••••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-gray-200 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-bold transition-colors mt-2"
            >
              {authMode === 'login' ? 'Sign In to Dashboard' : 'Create Account'}
            </button>
          </form>

          <div className="mt-6 text-center text-xs text-gray-500">
            {authMode === 'login' ? (
              <p>
                Don't have an account?{' '}
                <button
                  onClick={() => setAuthMode('register')}
                  className="text-emerald-400 font-semibold hover:underline"
                >
                  Register
                </button>
              </p>
            ) : (
              <p>
                Already registered?{' '}
                <button
                  onClick={() => setAuthMode('login')}
                  className="text-emerald-400 font-semibold hover:underline"
                >
                  Sign In
                </button>
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0B0F17] text-gray-200 flex flex-col">
      <Navigation
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        onOpenCreateModal={() => setIsCreateOpen(true)}
        userEmail={currentUser.email}
        onLogout={handleLogout}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentTab === 'monitors' && (
          <Dashboard
            monitors={monitors}
            onTriggerCheck={handleTriggerCheck}
            onTogglePause={handleTogglePause}
            onDeleteMonitor={handleDeleteMonitor}
            onOpenDetail={handleOpenDetail}
            onOpenRegionPicker={setRegionPickerMonitor}
            onOpenDiff={handleOpenDiff}
            onOpenCreate={() => setIsCreateOpen(true)}
          />
        )}

        {currentTab === 'fixtures' && (
          <FixtureSwitcher
            onCreateMonitorFromFixture={(url, name) => {
              handleCreateMonitor({
                url,
                name: `Monitor: ${name}`,
                interval_minutes: 60,
                sensitivity: 'balanced',
                capture_config: { engine: 'http_dom' },
              });
              setCurrentTab('monitors');
            }}
          />
        )}

        {currentTab === 'outbox' && <OutboxAudit />}
      </main>

      {/* Monitor Create Modal */}
      <MonitorModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={handleCreateMonitor}
      />

      {/* Monitor Detail Drawer */}
      <MonitorDetail
        monitor={monitorDetail?.monitor || null}
        versions={monitorDetail?.versions || []}
        runs={monitorDetail?.runs || []}
        onClose={() => setMonitorDetail(null)}
        onOpenDiff={(v1, v2) => {
          if (monitorDetail?.monitor) {
            handleOpenDiff(monitorDetail.monitor, v1, v2);
          }
        }}
      />

      {/* Diff Viewer Modal */}
      <DiffViewer
        isOpen={diffModal.isOpen}
        diffData={diffModal.data}
        onClose={() => setDiffModal({ isOpen: false, data: null })}
      />

      {/* Visual Region Picker Overlay */}
      <RegionPicker
        isOpen={Boolean(regionPickerMonitor)}
        monitor={regionPickerMonitor}
        onClose={() => setRegionPickerMonitor(null)}
        onSaveSelectors={handleSaveSelectors}
      />
    </div>
  );
};
