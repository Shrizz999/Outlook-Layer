import React, { useState } from 'react';
import { Mail, CheckCircle2, AlertCircle, Sparkles, ChevronDown, ChevronRight, FileText, User, Plus, X } from 'lucide-react';
import { EmailAnalysis, SourceMessage } from '../types';
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-8rem)]">
      {/* Left Column: Email List */}
      <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl overflow-hidden flex flex-col shadow-xs">
        <div className="p-3.5 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Mail className="w-4 h-4 text-blue-600" />
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Ingested Messages ({emails.length})
            </h3>
          </div>
          <button
            onClick={() => setShowCompose(true)}
            className="flex items-center space-x-1 bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-semibold px-2.5 py-1 rounded-lg transition shadow-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Simulate Inbound Email</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
          {emails.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400">No emails ingested yet.</div>
          ) : (
            emails.map((msg) => {
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
                <button
                  onClick={handleTriggerAnalysis}
                  disabled={loadingAnalysis}
                  className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold px-3 py-1.5 rounded-lg flex items-center space-x-1.5 transition"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{loadingAnalysis ? 'Analysing...' : 'Re-run AI Analysis'}</span>
                </button>
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
    </div>
  );
};
