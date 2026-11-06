import React, { useEffect, useState } from 'react';
import { Activity, ShieldCheck, Cpu, HardDrive, Lock, Server } from 'lucide-react';
import { api } from '../api/client';

export const DiagnosticsView: React.FC = () => {
  const [aiUsage, setAiUsage] = useState<any>(null);
  const [systemStatus, setSystemStatus] = useState<any>(null);

  useEffect(() => {
    api.getAiUsage().then(setAiUsage).catch(console.error);
    api.getSystemStatus().then(setSystemStatus).catch(console.error);
  }, []);

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h2 className="text-lg font-bold text-slate-900">AI Gateway & System Diagnostics</h2>
        <p className="text-xs text-slate-500">
          Inference provider quota management, backend health metrics, and tenant security status.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Card 1: AI Provider */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-slate-800 font-bold text-xs">
            <Cpu className="w-4 h-4 text-blue-600" />
            <span>Inference Gateway Status</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between border-b border-slate-100 pb-1.5">
              <span className="text-slate-500">Configured Provider:</span>
              <span className="font-mono font-bold text-slate-800 uppercase">
                {aiUsage?.provider || 'MOCK'}
              </span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-1.5">
              <span className="text-slate-500">Selected Model:</span>
              <span className="font-mono text-slate-800">{aiUsage?.model || 'mock-deterministic-v1'}</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-1.5">
              <span className="text-slate-500">Daily Request Budget:</span>
              <span className="font-semibold text-slate-800">{aiUsage?.max_requests_per_day || 40}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Per-Minute Rate Limit:</span>
              <span className="font-semibold text-slate-800">{aiUsage?.max_requests_per_minute || 15}</span>
            </div>
          </div>
        </div>

        {/* Card 2: Database Protection */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-slate-800 font-bold text-xs">
            <HardDrive className="w-4 h-4 text-emerald-600" />
            <span>Database Integrity</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between border-b border-slate-100 pb-1.5">
              <span className="text-slate-500">Modification Policy:</span>
              <span className="font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                ADDITIVE ONLY
              </span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-1.5">
              <span className="text-slate-500">Legacy Tables:</span>
              <span className="font-semibold text-slate-800">16 Protected Tables</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-1.5">
              <span className="text-slate-500">Extension Tables:</span>
              <span className="font-semibold text-slate-800">V001 to V005 Migrations</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Destructive Migrations:</span>
              <span className="font-bold text-rose-700">Blocked (0 Allowed)</span>
            </div>
          </div>
        </div>

        {/* Card 3: Security & Secrets */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-slate-800 font-bold text-xs">
            <Lock className="w-4 h-4 text-amber-600" />
            <span>Security & Secrets Guard</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between border-b border-slate-100 pb-1.5">
              <span className="text-slate-500">API Key Privacy:</span>
              <span className="font-semibold text-emerald-700">Backend Secured</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-1.5">
              <span className="text-slate-500">Customer Mailbox Access:</span>
              <span className="font-semibold text-slate-600">Disabled (Fixtures Mode)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Auto Email Sending:</span>
              <span className="font-semibold text-rose-700">Strictly Disabled</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
