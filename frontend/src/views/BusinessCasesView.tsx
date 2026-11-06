import React, { useState } from 'react';
import { Briefcase, Link2, Clock, CheckCircle2, User, Layers, ArrowRight } from 'lucide-react';
import { BusinessCase } from '../types';

interface BusinessCasesViewProps {
  cases: BusinessCase[];
  onSelectCase?: (c: BusinessCase) => void;
}

export const BusinessCasesView: React.FC<BusinessCasesViewProps> = ({ cases }) => {
  const [selectedCase, setSelectedCase] = useState<BusinessCase | null>(cases[0] || null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const filteredCases = cases.filter(
    (c) => statusFilter === 'ALL' || c.status === statusFilter
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-8rem)]">
      {/* Left Column: Cases List */}
      <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl overflow-hidden flex flex-col shadow-xs">
        <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Briefcase className="w-4 h-4 text-blue-600" />
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Business Cases ({filteredCases.length})
            </h3>
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-[11px] font-semibold bg-white border border-slate-300 rounded px-2 py-1 text-slate-700"
          >
            <option value="ALL">All Statuses</option>
            <option value="NEW">New</option>
            <option value="ACTIVE">Active</option>
            <option value="ORDER">Order</option>
            <option value="COMPLETED">Completed</option>
          </select>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
          {filteredCases.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400">No matching business cases.</div>
          ) : (
            filteredCases.map((c) => {
              const isSelected = selectedCase?.id === c.id;
              return (
                <div
                  key={c.id}
                  onClick={() => setSelectedCase(c)}
                  className={`p-4 cursor-pointer transition ${
                    isSelected ? 'bg-blue-50/60 border-l-4 border-blue-600' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-mono font-bold text-blue-600">{c.case_number}</span>
                    <span className="text-[10px] text-slate-400">{c.opened_at?.slice(0, 10)}</span>
                  </div>
                  <h4 className="text-xs font-bold text-slate-900 mb-1">{c.title}</h4>
                  <p className="text-[11px] text-slate-500 line-clamp-2 mb-2">{c.summary}</p>
                  <div className="flex items-center space-x-2">
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800">
                      {c.case_type}
                    </span>
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                      {c.status}
                    </span>
                    <span
                      className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                        c.priority === 'HIGH' || c.priority === 'CRITICAL'
                          ? 'bg-rose-100 text-rose-800'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {c.priority}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Right Column: Case Deep Context */}
      <div className="lg:col-span-7 bg-white border border-slate-200 rounded-xl overflow-y-auto p-6 shadow-xs space-y-6">
        {selectedCase ? (
          <>
            {/* Header */}
            <div className="border-b border-slate-200 pb-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-md border border-blue-200">
                  {selectedCase.case_number}
                </span>
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
                  Status: {selectedCase.status}
                </span>
              </div>
              <h2 className="text-lg font-bold text-slate-900">{selectedCase.title}</h2>
              <p className="text-xs text-slate-600 leading-relaxed">{selectedCase.summary}</p>
            </div>

            {/* Linked Operational Records */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center">
                <Link2 className="w-4 h-4 mr-1.5 text-blue-600" />
                Linked Operational Objects ({selectedCase.links?.length || 0})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {selectedCase.links && selectedCase.links.length > 0 ? (
                  selectedCase.links.map((link) => (
                    <div
                      key={link.id}
                      className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-800 uppercase tracking-wider text-[10px]">
                          {link.linked_object_type}
                        </span>
                        <span className="text-[10px] text-emerald-700 font-semibold bg-emerald-50 px-1.5 py-0.5 rounded">
                          {link.relationship_type}
                        </span>
                      </div>
                      <p className="font-mono text-slate-900 font-semibold truncate">
                        ID: {link.linked_object_id}
                      </p>
                      {link.match_method && (
                        <p className="text-[10px] text-slate-400">
                          Method: <strong>{link.match_method}</strong> ({Math.round((link.match_confidence || 0) * 100)}% conf)
                        </p>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-400 py-2">No linked objects recorded.</p>
                )}
              </div>
            </div>

            {/* Case Parties */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center">
                <User className="w-4 h-4 mr-1.5 text-slate-500" />
                Involved Parties
              </h3>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-2">
                <div className="flex justify-between items-center text-slate-700">
                  <span className="font-medium">Primary Customer:</span>
                  <span className="font-semibold text-slate-900">Acme Engineering Ltd</span>
                </div>
                <div className="flex justify-between items-center text-slate-700">
                  <span className="font-medium">Primary Material Supplier:</span>
                  <span className="font-semibold text-slate-900">Apex Tube Mills</span>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="p-12 text-center text-xs text-slate-400">Select a business case to view details.</div>
        )}
      </div>
    </div>
  );
};
