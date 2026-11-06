import React, { useState } from 'react';
import { FileEdit, Copy, Check, AlertTriangle, ShieldCheck, Send } from 'lucide-react';
import { BusinessCase } from '../types';

interface SmartDraftsViewProps {
  cases: BusinessCase[];
}

export const SmartDraftsView: React.FC<SmartDraftsViewProps> = ({ cases }) => {
  const [template, setTemplate] = useState('SUPPLIER_DELIVERY_FOLLOWUP');
  const [selectedCaseId, setSelectedCaseId] = useState(cases[0]?.id || '');
  const [copied, setCopied] = useState(false);

  const selectedCase = cases.find((c) => c.id === selectedCaseId) || cases[0];

  const draftSubject = `Delivery Status Clarification — Part HT-2045 (Ref: SO-1025)`;
  const draftBody = `Dear Apex Tube Mills Team,

We are following up regarding the delivery schedule for our purchase of:
- Part Number: HT-2045 (Hydraulic Tube 20x4.5mm)
- Quantity: 40 MTR (Balance for SO-1025)

Could you please confirm the scheduled dispatch date and share the airway bill or dispatch tracking reference once released?

Thank you for your assistance.

Kind regards,
Procurement & Supply Chain Team
Balbird Intelligence Integration`;

  const handleCopy = () => {
    navigator.clipboard.writeText(`Subject: ${draftSubject}\n\n${draftBody}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Smart Response Drafts</h2>
          <p className="text-xs text-slate-500">
            Assisted correspondence generation based on verified case context. Automatic email transmission is strictly disabled.
          </p>
        </div>

        <div className="flex items-center space-x-1.5 text-xs text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          <span>Zero Hallucination Policy: Unconfirmed values must be validated by employee</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Template & Case Selector */}
        <div className="lg:col-span-4 bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Draft Parameters</h3>

          <div className="space-y-1.5 text-xs">
            <label className="font-semibold text-slate-700">Select Template Category</label>
            <select
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 font-medium text-slate-800"
            >
              <option value="SUPPLIER_DELIVERY_FOLLOWUP">Supplier Delivery Follow-up</option>
              <option value="CUSTOMER_ENQUIRY_ACK">Customer Order Acknowledgement</option>
              <option value="PPC_SCHEDULE_REQUEST">Internal PPC Schedule Clarification</option>
            </select>
          </div>

          <div className="space-y-1.5 text-xs">
            <label className="font-semibold text-slate-700">Target Business Case</label>
            <select
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 font-mono text-slate-800"
            >
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.case_number} - {c.title.slice(0, 30)}...
                </option>
              ))}
            </select>
          </div>

          <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-800 space-y-1">
            <div className="flex items-center space-x-1 font-bold text-amber-900">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
              <span>Safety Enforcement</span>
            </div>
            <p className="text-[11px] leading-relaxed">
              Smart Drafts never invent prices, quantities, or promise dates not backed by operational evidence.
            </p>
          </div>
        </div>

        {/* Right Column: Draft Editor & Preview */}
        <div className="lg:col-span-8 bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <h3 className="text-sm font-bold text-slate-900">Generated Email Draft Preview</h3>
              <button
                onClick={handleCopy}
                className="bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold px-3 py-1.5 rounded-lg flex items-center space-x-1.5 transition"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied to Clipboard!' : 'Copy to Outlook'}</span>
              </button>
            </div>

            <div className="space-y-2 text-xs">
              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400">Subject</label>
                <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg font-semibold text-slate-800">
                  {draftSubject}
                </div>
              </div>

              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400">Body</label>
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg whitespace-pre-line text-slate-800 leading-relaxed font-sans min-h-[220px]">
                  {draftBody}
                </div>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-200 flex items-center justify-between text-xs text-slate-400">
            <span>Recipient: sales@apextubes.invalid</span>
            <span className="font-semibold text-slate-500">Human Approval Required</span>
          </div>
        </div>
      </div>
    </div>
  );
};
