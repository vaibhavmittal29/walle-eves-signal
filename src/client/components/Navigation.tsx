import React from 'react';
import { Eye, Activity, ShieldCheck, Inbox, Plus, LogOut } from 'lucide-react';

interface NavigationProps {
  currentTab: 'monitors' | 'fixtures' | 'outbox';
  onSelectTab: (tab: 'monitors' | 'fixtures' | 'outbox') => void;
  onOpenCreateModal: () => void;
  userEmail: string;
  onLogout: () => void;
}

export const Navigation: React.FC<NavigationProps> = ({
  currentTab,
  onSelectTab,
  onOpenCreateModal,
  userEmail,
  onLogout,
}) => {
  return (
    <header className="sticky top-0 z-40 bg-[#0E131F]/90 backdrop-blur border-b border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Eye className="w-5 h-5" />
          </div>
          <div>
            <span className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
              ChangeWatch
              <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                PROD
              </span>
            </span>
            <p className="text-[11px] text-gray-400 leading-none">Intelligent Change Detector</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center space-x-1 bg-gray-900/60 p-1 rounded-lg border border-gray-800">
          <button
            onClick={() => onSelectTab('monitors')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center space-x-1.5 ${
              currentTab === 'monitors'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Monitors Fleet</span>
          </button>
          <button
            onClick={() => onSelectTab('fixtures')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center space-x-1.5 ${
              currentTab === 'fixtures'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Testbed Fixtures</span>
          </button>
          <button
            onClick={() => onSelectTab('outbox')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center space-x-1.5 ${
              currentTab === 'outbox'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
            }`}
          >
            <Inbox className="w-3.5 h-3.5" />
            <span>Outbox Audit</span>
          </button>
        </nav>

        {/* Action Controls & User */}
        <div className="flex items-center space-x-3">
          <button
            onClick={onOpenCreateModal}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold rounded-md bg-emerald-500 hover:bg-emerald-400 text-gray-950 transition-colors shadow"
          >
            <Plus className="w-4 h-4" />
            <span>New Monitor</span>
          </button>

          <div className="h-4 w-px bg-gray-800" />

          <div className="flex items-center space-x-2 text-xs text-gray-400">
            <span className="hidden sm:inline-block max-w-[120px] truncate">{userEmail}</span>
            <button
              onClick={onLogout}
              title="Sign Out"
              className="p-1.5 text-gray-400 hover:text-rose-400 hover:bg-gray-800/50 rounded transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
