import React, { useState, useRef, useMemo, useEffect } from 'react';
import { Mail, CheckCircle2, AlertCircle, Sparkles, ChevronDown, ChevronRight, FileText, User, Plus, X, UploadCloud, FileCheck, Search, Filter, ArrowUpDown, Archive, FolderInput, CloudOff, Info, RefreshCw, Trash2, Layers } from 'lucide-react';
import { EmailAnalysis, EmailDashboardSummary, GraphConnectorStatus, SourceMessage } from '../types';
import { api } from '../api/client';

interface InboxViewProps {
  emails: SourceMessage[];
  onRefresh: () => void;
}

export const InboxView: React.FC<InboxViewProps> = ({ emails, onRefresh }) => {
  const [selectedEmail, setSelectedEmail] = useState<SourceMessage | null>(emails[0] || null);
  const [analysis, setAnalysis] = useState<EmailAnalysis | null>(emails[0]?.latest_analysis || null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [showQuoted, setShowQuoted] = useState(false);
  const [showCompose, setShowCompose] = useState(false);

  // Train Data & Reset state
  const [showTrainModal, setShowTrainModal] = useState(false);
  const [trainBatch, setTrainBatch] = useState<string>('all');
  const [trainLimit, setTrainLimit] = useState<number>(5);
  const [isImportingTrain, setIsImportingTrain] = useState(false);
  const [trainResult, setTrainResult] = useState<any | null>(null);
  const [isResetting, setIsResetting] = useState(false);

  // Search, Filter, Sort State
  const [searchQuery, setSearchQuery] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('ALL');
  const [priorityFilter, setPriorityFilter] = useState('ALL');
  const [sortBy, setSortBy] = useState<'NEWEST' | 'OLDEST' | 'PRIORITY'>('NEWEST');

  // Compose Form State
  const [composeSubject, setComposeSubject] = useState('');
  const [composeSenderName, setComposeSenderName] = useState('');
  const [composeSenderEmail, setComposeSenderEmail] = useState('');
  const [composeBody, setComposeBody] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If emails list updates and selected email exists, sync latest analysis
  React.useEffect(() => {
    if (emails.length > 0 && !selectedEmail) {
      setSelectedEmail(emails[0]);
      setAnalysis(emails[0].latest_analysis || null);
    } else if (selectedEmail) {
      const updated = emails.find((e) => e.id === selectedEmail.id);
      if (updated && updated.latest_analysis && !analysis) {
        setAnalysis(updated.latest_analysis);
      }
    }
  }, [emails]);

  const handleSelectEmail = async (msg: SourceMessage) => {
    setSelectedEmail(msg);
    if (msg.latest_analysis) {
      setAnalysis(msg.latest_analysis);
    }
    setLoadingAnalysis(true);
    try {
      const res = await api.getEmailAnalysis(msg.id);
      setAnalysis(res);
    } catch {
      if (!msg.latest_analysis) {
        setAnalysis(null);
      }
    } finally {
      setLoadingAnalysis(false);
    }
  };

  const handleTriggerAnalysis = async () => {
    if (!selectedEmail) return;
    setLoadingAnalysis(true);
    try {
      const res = await api.triggerAnalysis(selectedEmail.id);
      setAnalysis(res);
      onRefresh();
    } catch (err: any) {
      alert(`Analysis failed: ${err.message}`);
    } finally {
      setLoadingAnalysis(false);
    }
  };

  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const batchInputRef = useRef<HTMLInputElement>(null);
  const zipInputRef = useRef<HTMLInputElement>(null);
  const [dashboardSummary, setDashboardSummary] = useState<EmailDashboardSummary | null>(null);
  const [graphStatus, setGraphStatus] = useState<GraphConnectorStatus | null>(null);
  const [showGraphModal, setShowGraphModal] = useState(false);

  const loadEmailDashboard = async () => {
    try {
      const [sum, grp] = await Promise.all([
        api.getEmailDashboardSummary(),
        api.getGraphStatus(),
      ]);
      setDashboardSummary(sum);
      setGraphStatus(grp);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadEmailDashboard();
  }, [emails]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const newMsg = await api.uploadEml(file);
      onRefresh();
      setSelectedEmail(newMsg);
      if (newMsg.latest_analysis) {
        setAnalysis(newMsg.latest_analysis);
      }
      loadEmailDashboard();
    } catch (err: any) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleImportTrainData = async () => {
    setIsImportingTrain(true);
    try {
      const res = await api.importTrainData(trainBatch, trainLimit || undefined);
      setTrainResult(res);
      onRefresh();
      loadEmailDashboard();
    } catch (err: any) {
      alert(`Train Data import failed: ${err.message}`);
    } finally {
      setIsImportingTrain(false);
    }
  };

  const handleResetData = async () => {
    if (!window.confirm("Are you sure you want to clear all emails, tasks, proposals, and business cases to start completely fresh?")) {
      return;
    }
    setIsResetting(true);
    try {
      await api.resetOperationalData();
      alert("All operational data cleared successfully! System is fresh.");
      setSelectedEmail(null);
      setAnalysis(null);
      onRefresh();
      loadEmailDashboard();
    } catch (err: any) {
      alert(`Reset failed: ${err.message}`);
    } finally {
      setIsResetting(false);
    }
  };

  const handleBatchUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    try {
      const res = await api.uploadBatchEml(Array.from(files));
      alert(`Batch upload: ${res.ingested.length} messages ingested, ${res.failed.length} failed.`);
      onRefresh();
      loadEmailDashboard();
    } catch (err: any) {
      alert(`Batch upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
      if (batchInputRef.current) {
        batchInputRef.current.value = '';
      }
    }
  };

  const handleZipUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const res = await api.uploadZipEml(file);
      alert(`ZIP archive: ${res.ingested.length} messages extracted, ${res.failed.length} failed.`);
      onRefresh();
      loadEmailDashboard();
    } catch (err: any) {
      alert(`ZIP upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
      if (zipInputRef.current) {
        zipInputRef.current.value = '';
      }
    }
  };

  const handleImportFixtures = async () => {
    setIsUploading(true);
    try {
      const res = await api.importFixtures();
      alert(`Synthetic Fixtures Ingested: ${res.successfully_ingested} messages, ${res.skipped_duplicates} duplicates skipped.`);
      onRefresh();
      loadEmailDashboard();
    } catch (err: any) {
      alert(`Fixture import failed: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleReprocessEmail = async () => {
    if (!selectedEmail) return;
    setLoadingAnalysis(true);
    try {
      const updated = await api.reprocessEmail(selectedEmail.id);
      setSelectedEmail(updated);
      alert('Email reprocessed successfully through pipeline.');
      onRefresh();
      loadEmailDashboard();
    } catch (err: any) {
      alert(`Reprocessing failed: ${err.message}`);
    } finally {
      setLoadingAnalysis(false);
    }
  };

  const handleCreateEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!composeSubject || !composeBody || !composeSenderEmail) {
      alert('Please fill in Subject, Sender Email, and Body.');
      return;
    }

    setIsSubmitting(true);
    try {
      const newMsg = await api.ingestEmail({
        subject: composeSubject,
        sender_name: composeSenderName || composeSenderEmail.split('@')[0],
        sender_email: composeSenderEmail,
        body: composeBody,
      });
      setShowCompose(false);
      setComposeSubject('');
      setComposeSenderName('');
      setComposeSenderEmail('');
      setComposeBody('');
      onRefresh();
      setSelectedEmail(newMsg);
      if (newMsg.latest_analysis) {
        setAnalysis(newMsg.latest_analysis);
      }
    } catch (err: any) {
      alert(`Failed to ingest email: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Filtered and sorted emails
  const filteredEmails = useMemo(() => {
    let result = [...emails];

    // Search query filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter((msg: SourceMessage) => {
        const subjectMatch = msg.subject?.toLowerCase().includes(q);
        const senderMatch =
          msg.sender_display_name?.toLowerCase().includes(q) ||
          msg.sender_address?.toLowerCase().includes(q);
        const bodyMatch =
          msg.body_preprocessed?.toLowerCase().includes(q) ||
          msg.body_text?.toLowerCase().includes(q);
        const refMatch = msg.latest_analysis?.raw_structured_output?.references?.some((r: any) =>
          r.value?.toLowerCase().includes(q) || r.type?.toLowerCase().includes(q)
        );
        return Boolean(subjectMatch || senderMatch || bodyMatch || refMatch);
      });
    }

    // Department filter
    if (departmentFilter !== 'ALL') {
      result = result.filter(
        (msg: SourceMessage) =>
          msg.latest_analysis?.department?.toUpperCase() === departmentFilter.toUpperCase()
      );
    }

    // Priority filter
    if (priorityFilter !== 'ALL') {
      result = result.filter(
        (msg: SourceMessage) =>
          msg.latest_analysis?.priority?.toUpperCase() === priorityFilter.toUpperCase()
      );
    }

    // Sorting
    const priorityWeight: Record<string, number> = {
      CRITICAL: 4,
      HIGH: 3,
      NORMAL: 2,
      LOW: 1,
    };

    result.sort((a: SourceMessage, b: SourceMessage) => {
      if (sortBy === 'PRIORITY') {
        const pA = priorityWeight[a.latest_analysis?.priority?.toUpperCase() || ''] || 0;
        const pB = priorityWeight[b.latest_analysis?.priority?.toUpperCase() || ''] || 0;
        if (pA !== pB) return pB - pA;
      }

      const dateA = a.sent_at ? new Date(a.sent_at).getTime() : 0;
      const dateB = b.sent_at ? new Date(b.sent_at).getTime() : 0;

      if (sortBy === 'OLDEST') {
        return dateA - dateB;
      }
      return dateB - dateA; // Default NEWEST
    });

    return result;
  }, [emails, searchQuery, departmentFilter, priorityFilter, sortBy]);

  return (
    <div className="space-y-4">
      {/* Top Email Dashboard & Multi-Source Ingestion Bar */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-4">
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400">Total Ingested</span>
              <div className="text-base font-bold text-slate-900">{dashboardSummary?.total_ingested ?? emails.length}</div>
            </div>
            <div className="h-7 w-px bg-slate-200" />
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400">Processed</span>
              <div className="text-base font-bold text-emerald-600">{dashboardSummary?.successfully_processed ?? emails.length}</div>
            </div>
            <div className="h-7 w-px bg-slate-200" />
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400">Duplicates Filtered</span>
              <div className="text-base font-bold text-slate-600">{dashboardSummary?.duplicate_detected ?? 0}</div>
            </div>
            <div className="h-7 w-px bg-slate-200" />
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400">Linked to Cases</span>
              <div className="text-base font-bold text-blue-600">{dashboardSummary?.linked_to_business_cases ?? 0}</div>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {/* Graph Connector Status Button */}
            <button
              onClick={() => setShowGraphModal(true)}
              className="flex items-center space-x-1.5 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition"
            >
              <CloudOff className="w-3.5 h-3.5 text-slate-500" />
              <span>Graph: Offline</span>
            </button>

            {/* Import Local Fixtures Button */}
            <button
              onClick={handleImportFixtures}
              disabled={isUploading}
              className="flex items-center space-x-1.5 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition disabled:opacity-50"
              title="Batch import local synthetic EML fixtures"
            >
              <FolderInput className="w-3.5 h-3.5 text-indigo-600" />
              <span>Import Fixtures</span>
            </button>

            {/* Batch Upload .eml */}
            <input
              type="file"
              ref={batchInputRef}
              onChange={handleBatchUpload}
              accept=".eml"
              multiple
              className="hidden"
            />
            <button
              onClick={() => batchInputRef.current?.click()}
              disabled={isUploading}
              className="flex items-center space-x-1.5 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition disabled:opacity-50"
            >
              <UploadCloud className="w-3.5 h-3.5 text-blue-600" />
              <span>Batch .eml</span>
            </button>

            {/* ZIP Upload */}
            <input
              type="file"
              ref={zipInputRef}
              onChange={handleZipUpload}
              accept=".zip"
              className="hidden"
            />
            <button
              onClick={() => zipInputRef.current?.click()}
              disabled={isUploading}
              className="flex items-center space-x-1.5 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition disabled:opacity-50"
            >
              <Archive className="w-3.5 h-3.5 text-amber-600" />
              <span>Upload ZIP</span>
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-14rem)]">
      {/* Left Column: Email List */}
      <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl overflow-hidden flex flex-col shadow-xs">
        <div className="p-3 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <Mail className="w-4 h-4 text-blue-600" />
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Messages ({emails.length})
            </h3>
          </div>
          <div className="flex items-center space-x-1.5">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".eml,.msg"
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="flex items-center space-x-1 bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 text-[11px] font-semibold px-2.5 py-1 rounded-lg transition shadow-2xs disabled:opacity-50"
              title="Upload an .eml or .msg email file"
            >
              <UploadCloud className="w-3.5 h-3.5 text-blue-600" />
              <span>{isUploading ? 'Uploading...' : 'Upload .eml'}</span>
            </button>
            <button
              onClick={() => setShowTrainModal(true)}
              className="flex items-center space-x-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-[11px] font-semibold px-2.5 py-1 rounded-lg transition shadow-2xs"
              title="Batch import Swapnali, Ganesh, or Vaibhav test datasets from Train Data"
            >
              <FolderInput className="w-3.5 h-3.5 text-indigo-600" />
              <span>Train Data</span>
            </button>
            <button
              onClick={handleResetData}
              disabled={isResetting}
              className="flex items-center space-x-1 bg-white hover:bg-rose-50 border border-rose-200 text-rose-700 text-[11px] font-semibold px-2 py-1 rounded-lg transition shadow-2xs disabled:opacity-50"
              title="Reset all system operational data for a fresh start"
            >
              <Trash2 className="w-3.5 h-3.5 text-rose-600" />
              <span>{isResetting ? 'Resetting...' : 'Reset'}</span>
            </button>
            <button
              onClick={() => setShowCompose(true)}
              className="flex items-center space-x-1 bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-semibold px-2.5 py-1 rounded-lg transition shadow-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Compose</span>
            </button>
          </div>
        </div>

        {/* Filter and Search Bar */}
        <div className="p-2.5 border-b border-slate-200 bg-white space-y-2">
          {/* Search Box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search by SO, Part, sender, subject..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-xs pl-8 pr-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-2 text-slate-400 hover:text-slate-600 text-xs"
              >
                ✕
              </button>
            )}
          </div>

          {/* Filter Pills / Dropdowns */}
          <div className="grid grid-cols-3 gap-1.5 text-[11px]">
            <select
              value={departmentFilter}
              onChange={(e) => setDepartmentFilter(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded px-1.5 py-1 text-slate-700 font-medium focus:outline-none"
            >
              <option value="ALL">All Depts</option>
              <option value="SALES">Sales</option>
              <option value="PURCHASE">Purchase</option>
              <option value="PPC">PPC</option>
              <option value="PRODUCTION">Production</option>
              <option value="QUALITY">Quality</option>
              <option value="DISPATCH">Dispatch</option>
            </select>

            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded px-1.5 py-1 text-slate-700 font-medium focus:outline-none"
            >
              <option value="ALL">All Priority</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="NORMAL">Normal</option>
              <option value="LOW">Low</option>
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-slate-50 border border-slate-200 rounded px-1.5 py-1 text-slate-700 font-medium focus:outline-none"
            >
              <option value="NEWEST">Newest</option>
              <option value="OLDEST">Oldest</option>
              <option value="PRIORITY">By Priority</option>
            </select>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
          {filteredEmails.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400">{emails.length === 0 ? 'No emails ingested yet.' : 'No emails match your search or filter criteria.'}</div>
          ) : (
            filteredEmails.map((msg) => {
              const isSelected = selectedEmail?.id === msg.id;
              return (
                <div
                  key={msg.id}
                  onClick={() => handleSelectEmail(msg)}
                  className={`p-3.5 cursor-pointer transition ${
                    isSelected ? 'bg-blue-50/60 border-l-4 border-blue-600' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-semibold text-slate-800 truncate">
                      {msg.sender_display_name || msg.sender_address}
                    </span>
                    <span className="text-[10px] text-slate-400 whitespace-nowrap ml-2">
                      {msg.sent_at?.slice(0, 10)}
                    </span>
                  </div>
                  <div className="text-xs font-medium text-slate-900 truncate mb-1">
                    {msg.subject || '(No subject)'}
                  </div>
                  <p className="text-[11px] text-slate-500 line-clamp-2">
                    {msg.body_preprocessed || msg.body_text}
                  </p>
                  {/* Findings chips badge row right where analysed was */}
                  {msg.latest_analysis ? (
                    <div className="mt-2.5 pt-2 border-t border-slate-100/80 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200/60 uppercase">
                          {msg.latest_analysis.department || 'GENERAL'}
                        </span>
                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200/60">
                          {msg.latest_analysis.intent || 'INQUIRY'}
                        </span>
                        <span
                          className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                            msg.latest_analysis.priority === 'CRITICAL' || msg.latest_analysis.priority === 'HIGH'
                              ? 'bg-red-50 text-red-700 border border-red-200/60'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {msg.latest_analysis.priority}
                        </span>
                        {msg.latest_analysis.confidence !== undefined && msg.latest_analysis.confidence !== null && (
                          <span className="text-[9px] font-semibold text-slate-400 ml-auto">
                            {Math.round(msg.latest_analysis.confidence * 100)}% conf
                          </span>
                        )}
                      </div>

                      {/* Extracted References (SO / Part numbers) */}
                      {msg.latest_analysis.raw_structured_output?.references &&
                        msg.latest_analysis.raw_structured_output.references.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {msg.latest_analysis.raw_structured_output.references.slice(0, 3).map((ref, idx) => (
                              <span
                                key={idx}
                                className="text-[9px] font-mono font-semibold px-1.5 py-0.2 rounded bg-slate-100 text-slate-800 border border-slate-200/80"
                              >
                                {ref.type}: {ref.value}
                              </span>
                            ))}
                          </div>
                        )}
                    </div>
                  ) : (
                    <div className="mt-2 flex items-center space-x-1.5">
                      <span
                        className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                          msg.processing_status === 'ANALYSED'
                            ? 'bg-emerald-50 text-emerald-700'
                            : msg.processing_status === 'NEEDS_REVIEW'
                            ? 'bg-amber-50 text-amber-700'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {msg.processing_status}
                      </span>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Right Column: Email Detail & AI Extraction */}
      <div className="lg:col-span-7 bg-white border border-slate-200 rounded-xl overflow-y-auto p-6 shadow-xs space-y-6">
        {selectedEmail ? (
          <>
            {/* Header */}
            <div className="border-b border-slate-200 pb-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-slate-400">ID: {selectedEmail.id}</span>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleReprocessEmail}
                    disabled={loadingAnalysis}
                    className="bg-slate-100 hover:bg-slate-200 text-slate-700 disabled:opacity-50 text-xs font-semibold px-2.5 py-1.5 rounded-lg flex items-center space-x-1.5 transition"
                    title="Reprocess email through normalisation, deduplication, thread linking, and context engine"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Reprocess Pipeline</span>
                  </button>
                  <button
                    onClick={handleTriggerAnalysis}
                    disabled={loadingAnalysis}
                    className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold px-3 py-1.5 rounded-lg flex items-center space-x-1.5 transition"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>{loadingAnalysis ? 'Analysing...' : 'Re-run AI Analysis'}</span>
                  </button>
                </div>
              </div>
              <h2 className="text-base font-bold text-slate-900">{selectedEmail.subject}</h2>
              <div className="text-xs text-slate-500 flex items-center space-x-4">
                <span>
                  <strong>From:</strong> {selectedEmail.sender_display_name} &lt;{selectedEmail.sender_address}&gt;
                </span>
                <span>
                  <strong>Date:</strong> {selectedEmail.sent_at}
                </span>
              </div>
            </div>

            {/* AI Intelligence Extraction Card */}
            {analysis && (
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3.5">
                <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                  <div className="flex items-center space-x-1.5 text-xs font-bold text-slate-800 uppercase tracking-wide">
                    <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                    <span>AI Intelligence Findings</span>
                  </div>
                  <span className="text-[11px] text-slate-500">
                    Confidence: <strong>{Math.round((analysis.confidence || 0) * 100)}%</strong>
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold">Department</span>
                    <p className="font-bold text-slate-800">{analysis.department || 'GENERAL'}</p>
                  </div>
                  <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold">Intent</span>
                    <p className="font-bold text-slate-800">{analysis.intent || 'INQUIRY'}</p>
                  </div>
                  <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold">Priority</span>
                    <p className="font-bold text-slate-800">{analysis.priority}</p>
                  </div>
                </div>

                {/* Summary */}
                {analysis.summary && (
                  <div className="text-xs text-slate-700 bg-white p-2.5 rounded-lg border border-slate-200">
                    <strong className="text-slate-900">Summary:</strong> {analysis.summary}
                  </div>
                )}

                {/* Extracted References */}
                {analysis.raw_structured_output?.references && analysis.raw_structured_output.references.length > 0 && (
                  <div className="space-y-1.5">
                    <span className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">
                      Extracted References:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {analysis.raw_structured_output.references.map((r, i) => (
                        <span
                          key={i}
                          className="bg-blue-100 text-blue-800 font-mono text-[11px] font-semibold px-2.5 py-0.5 rounded-md"
                        >
                          {r.type}: {r.value}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Email Cleaned Body */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center">
                <FileText className="w-3.5 h-3.5 mr-1 text-slate-400" />
                Authored Content (Preprocessed)
              </h4>
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 font-sans text-xs text-slate-800 leading-relaxed whitespace-pre-line">
                {selectedEmail.body_preprocessed || selectedEmail.body_text}
              </div>
            </div>

            {/* Extracted Attachments & Technical Line Items */}
            {selectedEmail.has_attachments && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center">
                  <FileCheck className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                  Extracted Attachments & Technical Line Items
                </h4>
                <div className="bg-emerald-50/40 border border-emerald-200 rounded-lg p-3 space-y-2">
                  {selectedEmail.attachments_metadata && selectedEmail.attachments_metadata.length > 0 ? (
                    selectedEmail.attachments_metadata.map((att: any, idx: number) => (
                      <div key={idx} className="bg-white border border-emerald-200 rounded-md p-2.5 flex items-center justify-between text-xs shadow-2xs">
                        <div className="flex items-center space-x-2">
                          <span className="font-bold text-slate-800">{att.filename}</span>
                          <span className="text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded font-mono">
                            {att.content_type || 'document'}
                          </span>
                          {att.size_bytes ? (
                            <span className="text-[10px] text-slate-400">({Math.round(att.size_bytes / 1024)} KB)</span>
                          ) : null}
                        </div>
                        {att.parsed_data?.line_items && (
                          <span className="text-[10px] font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                            {att.parsed_data.line_items.length} Line Items Extracted
                          </span>
                        )}
                        {att.parsed_data?.ocr_status === 'EXCLUDED' && (
                          <span className="text-[10px] font-bold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                            Image Document (OCR Excluded)
                          </span>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-slate-500">Attachment metadata registered for this email.</div>
                  )}
                </div>
              </div>
            )}

            {/* Quoted History Toggle */}
            {selectedEmail.quoted_history_text && (
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <button
                  onClick={() => setShowQuoted(!showQuoted)}
                  className="w-full text-left p-3 bg-slate-50 text-xs font-semibold text-slate-600 flex items-center justify-between hover:bg-slate-100 transition"
                >
                  <span>Separated Quoted Thread History</span>
                  {showQuoted ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                </button>
                {showQuoted && (
                  <div className="p-3 bg-white text-[11px] text-slate-500 whitespace-pre-line border-t border-slate-200 font-mono">
                    {selectedEmail.quoted_history_text}
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="p-12 text-center text-xs text-slate-400">Select an email to view details.</div>
        )}
      </div>
    </div>

      {/* Modal: Simulate / Inject Inbound Email */}
      {showCompose && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 rounded-lg bg-blue-100 text-blue-700">
                  <Mail className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-800">Simulate Incoming Inbound Email</h3>
                  <p className="text-[11px] text-slate-500">Injects email into ingestion pipeline & runs instant AI analysis</p>
                </div>
              </div>
              <button
                onClick={() => setShowCompose(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateEmail} className="p-5 space-y-3.5">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-600">Sender Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Vikram Sharma"
                    value={composeSenderName}
                    onChange={(e) => setComposeSenderName(e.target.value)}
                    className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-600">Sender Email</label>
                  <input
                    type="email"
                    required
                    placeholder="e.g. v.sharma@acme-eng.com"
                    value={composeSenderEmail}
                    onChange={(e) => setComposeSenderEmail(e.target.value)}
                    className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-600">Email Subject</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Request for urgent delivery of 50 units for SO-1025"
                  value={composeSubject}
                  onChange={(e) => setComposeSubject(e.target.value)}
                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-600">Email Body</label>
                <textarea
                  rows={4}
                  required
                  placeholder="Paste or type raw email content mentioning order references (e.g. SO-1025, HT-2045, delivery dates)..."
                  value={composeBody}
                  onChange={(e) => setComposeBody(e.target.value)}
                  className="w-full text-xs p-3 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 resize-none font-sans"
                />
              </div>

              <div className="pt-2 flex items-center justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowCompose(false)}
                  className="px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition flex items-center space-x-1.5 disabled:opacity-50"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{isSubmitting ? 'Ingesting & Analysing...' : 'Ingest & Run AI'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Microsoft Graph Connector Diagnostics & Status */}
      {showGraphModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-5 border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <CloudOff className="w-5 h-5 text-amber-500" />
                <h3 className="text-sm font-bold text-slate-800">Microsoft Graph Connector Status</h3>
              </div>
              <button onClick={() => setShowGraphModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-4 space-y-4">
              <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                <div className="text-xs font-bold text-amber-800">
                  Status: {graphStatus?.status || 'DISABLED_OFFLINE'}
                </div>
                <p className="text-[11px] text-amber-700 mt-0.5">
                  {graphStatus?.message ||
                    'Microsoft Graph live sync is disabled. Balbird Intelligence operates in offline-first mode using EML, ZIP archives, CSV/table extractions, and local synthetic fixtures.'}
                </p>
              </div>

              <div>
                <h4 className="text-xs font-semibold text-slate-700">Missing Configuration Variables:</h4>
                <div className="mt-1 flex flex-wrap gap-1">
                  {(graphStatus?.missing_configurations || [
                    'GRAPH_CLIENT_ID',
                    'GRAPH_CLIENT_SECRET',
                    'GRAPH_TENANT_ID',
                  ]).map((cfg) => (
                    <span
                      key={cfg}
                      className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-100 text-slate-700 border border-slate-200"
                    >
                      {cfg}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold text-slate-700">
                  Required Azure AD Permissions (when enabling):
                </h4>
                <ul className="mt-1 space-y-1 text-xs text-slate-600 list-disc list-inside">
                  {(graphStatus?.required_azure_permissions || [
                    'Mail.Read (Application / Delegated)',
                    'Mail.ReadBasic.All',
                    'MailboxSettings.Read',
                    'User.Read.All',
                  ]).map((perm) => (
                    <li key={perm}>{perm}</li>
                  ))}
                </ul>
              </div>

              <p className="text-[11px] text-slate-500 italic">
                Note: Offline EML/ZIP/Fixture ingestion uses the exact same parsing and AI analysis pipeline as Microsoft Graph.
              </p>

              <div className="pt-2 flex justify-end">
                <button
                  onClick={() => setShowGraphModal(false)}
                  className="px-4 py-1.5 text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Train Data Ingestion & Orchestration */}
      {showTrainModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-5 border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <FolderInput className="w-5 h-5 text-indigo-600" />
                <h3 className="text-sm font-bold text-slate-800">Import Dummy Train Data</h3>
              </div>
              <button
                onClick={() => {
                  setShowTrainModal(false);
                  setTrainResult(null);
                }}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-4 space-y-4">
              <p className="text-xs text-slate-600">
                Batch ingest emails and technical attachments from the <code className="font-mono bg-slate-100 px-1 py-0.5 rounded text-indigo-700">Train Data</code> repository.
                The system will automatically parse technical documents (.csv, .xlsx, .pdf), attribute employees, and auto-instantiate the 13-stage manufacturing workflow with sequential blocking dependencies.
              </p>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-600">Employee Dataset</label>
                  <select
                    value={trainBatch}
                    onChange={(e) => setTrainBatch(e.target.value)}
                    className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:outline-none"
                  >
                    <option value="all">All (Swapnali + Ganesh + Vaibhav)</option>
                    <option value="swapnali">Swapnali (Enquiries & Quotes)</option>
                    <option value="ganesh">Ganesh (Part Checks & POs)</option>
                    <option value="vaibhav">Vaibhav (SO Booking & Orders)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-600">Limit (Per Employee)</label>
                  <select
                    value={trainLimit}
                    onChange={(e) => setTrainLimit(Number(e.target.value))}
                    className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:outline-none"
                  >
                    <option value={5}>5 emails (Quick test)</option>
                    <option value={10}>10 emails</option>
                    <option value={25}>25 emails</option>
                    <option value={0}>All available emails</option>
                  </select>
                </div>
              </div>

              {/* Automatic Processing Features Badge List */}
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-1.5 text-[11px] text-slate-600">
                <div className="font-semibold text-slate-700 flex items-center space-x-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                  <span>Autonomous Ingestion Pipeline Actions:</span>
                </div>
                <ul className="list-disc list-inside space-y-0.5 pl-1 text-[11px]">
                  <li>Extracts line items from attached CSV, XLSX, and text PDF files</li>
                  <li>Attributes sender & recipient to canonical employee roster</li>
                  <li>Generates 13-stage workflow (<code className="text-slate-700 font-mono">Enquiry → PO → SO → Dispatch</code>)</li>
                  <li>Assigns sequential blocking dependencies & highlights active bottleneck</li>
                </ul>
              </div>

              {/* Results box if completed */}
              {trainResult && (
                <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200 space-y-2">
                  <div className="flex items-center space-x-1.5 text-xs font-bold text-emerald-800">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Import Completed Successfully!</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="bg-white p-2 rounded border border-emerald-100">
                      <div className="text-[10px] text-slate-500 uppercase font-semibold">Emails</div>
                      <div className="text-sm font-bold text-slate-800">{trainResult.total_ingested}</div>
                    </div>
                    <div className="bg-white p-2 rounded border border-emerald-100">
                      <div className="text-[10px] text-slate-500 uppercase font-semibold">Tasks Created</div>
                      <div className="text-sm font-bold text-indigo-600">{trainResult.total_tasks_created}</div>
                    </div>
                    <div className="bg-white p-2 rounded border border-emerald-100">
                      <div className="text-[10px] text-slate-500 uppercase font-semibold">Dependencies</div>
                      <div className="text-sm font-bold text-purple-600">{trainResult.total_dependencies_created}</div>
                    </div>
                  </div>
                  {trainResult.active_bottlenecks && trainResult.active_bottlenecks.length > 0 && (
                    <div className="text-[11px] text-emerald-900 pt-1">
                      <span className="font-semibold">Identified Bottlenecks: </span>
                      {trainResult.active_bottlenecks.map((b: any, i: number) => (
                        <span key={i} className="inline-block bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded mr-1 font-mono text-[10px]">
                          {b.assignee_name || 'Unassigned'} ({b.title})
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="pt-2 flex items-center justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowTrainModal(false);
                    setTrainResult(null);
                  }}
                  className="px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition"
                >
                  Close
                </button>
                <button
                  type="button"
                  onClick={handleImportTrainData}
                  disabled={isImportingTrain}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg transition flex items-center space-x-1.5 disabled:opacity-50 shadow-xs"
                >
                  <FolderInput className="w-3.5 h-3.5" />
                  <span>{isImportingTrain ? 'Processing Train Data...' : 'Import & Orchestrate'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
