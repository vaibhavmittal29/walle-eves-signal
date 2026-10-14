import React, { useState, useEffect } from 'react';
import { Inbox, CheckCircle2, AlertTriangle, Send, Settings, ShieldCheck, Clock } from 'lucide-react';
import { OutboxItem } from '../types/client.js';

export const OutboxAudit: React.FC = () => {
  const [items, setItems] = useState<OutboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [discordWebhook, setDiscordWebhook] = useState('');
  const [savingWebhook, setSavingWebhook] = useState(false);
  const [showConfig, setShowConfig] = useState(false);

  const fetchOutbox = () => {
    fetch('/api/outbox')
      .then(res => res.json())
      .then(data => setItems(data.outbox || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchOutbox();
  }, []);

  const handleSaveDiscord = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingWebhook(true);
    try {
      await fetch('/api/outbox/destinations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel: 'discord',
          destination_config: { webhookUrl: discordWebhook },
          enabled: true,
        }),
      });
      setShowConfig(false);
      alert('Discord webhook destination configured successfully!');
    } finally {
      setSavingWebhook(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center space-x-2">
            <Inbox className="w-5 h-5 text-emerald-400" />
            <span>Multi-Channel Notification Outbox (Audit Journal)</span>
          </h2>
          <p className="text-xs text-gray-400 mt-1">
            Channel-independent deliveries with idempotency keys (<code className="font-mono text-emerald-400">event_channel_dest</code>).
          </p>
        </div>

        <button
          onClick={() => setShowConfig(!showConfig)}
          className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-semibold border border-gray-700"
        >
          <Settings className="w-3.5 h-3.5" />
          <span>Webhook Settings</span>
        </button>
      </div>

      {/* Webhook Configuration Modal/Drawer */}
      {showConfig && (
        <div className="p-4 rounded-xl bg-gray-900 border border-gray-800 space-y-3">
          <h3 className="font-bold text-gray-200 text-xs">Configure Discord Alert Webhook</h3>
          <form onSubmit={handleSaveDiscord} className="flex gap-2">
            <input
              type="url"
              required
              placeholder="https://discord.com/api/webhooks/..."
              value={discordWebhook}
              onChange={e => setDiscordWebhook(e.target.value)}
              className="flex-1 px-3 py-1.5 bg-gray-950 border border-gray-700 rounded-lg text-xs font-mono text-gray-200 focus:outline-none focus:border-emerald-500"
            />
            <button
              type="submit"
              disabled={savingWebhook}
              className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs"
            >
              {savingWebhook ? 'Saving...' : 'Save Webhook'}
            </button>
          </form>
        </div>
      )}

      {/* Outbox Table */}
      <div className="bg-gray-900/40 border border-gray-800 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/60 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Channel</th>
                <th className="py-3 px-4">Monitor & Event</th>
                <th className="py-3 px-4">Idempotency Key</th>
                <th className="py-3 px-4">Attempts</th>
                <th className="py-3 px-4 text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 font-mono text-[11px]">
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-gray-500">
                    No outbox notifications dispatched yet.
                  </td>
                </tr>
              ) : (
                items.map(item => {
                  const isSent = item.status === 'SENT_EXTERNAL' || item.status === 'RECORDED_IN_APP';
                  const isPending = item.status === 'PENDING_CONFIG';
                  const isRetrying = item.status === 'RETRYING';
                  const isFailed = item.status === 'FAILED';

                  return (
                    <tr key={item.id} className="hover:bg-gray-800/30">
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                          isSent
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : isPending
                            ? 'bg-amber-950 text-amber-300 border border-amber-800'
                            : isRetrying
                            ? 'bg-sky-950 text-sky-300 border border-sky-800'
                            : 'bg-rose-950 text-rose-300 border border-rose-800'
                        }`}>
                          {item.status}
                        </span>
                      </td>

                      <td className="py-3 px-4 font-semibold uppercase text-gray-300">
                        {item.channel}
                      </td>

                      <td className="py-3 px-4 font-sans text-xs">
                        <span className="font-semibold text-gray-200 block">{item.monitor_name}</span>
                        <span className="text-[11px] text-gray-400">{item.summary}</span>
                      </td>

                      <td className="py-3 px-4 text-gray-500 truncate max-w-[180px]">
                        {item.idempotency_key}
                      </td>

                      <td className="py-3 px-4 text-gray-300">
                        {item.attempts}
                      </td>

                      <td className="py-3 px-4 text-right text-gray-500">
                        {new Date(item.created_at).toLocaleTimeString()}
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
