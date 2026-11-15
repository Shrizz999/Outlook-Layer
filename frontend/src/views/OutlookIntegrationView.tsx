import React, { useState, useEffect, useRef } from 'react';
import {
  Mail,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Folder,
  Layers,
  Search,
  ExternalLink,
  ShieldCheck,
  ShieldAlert,
  Clock,
  Inbox,
  Send,
  Archive,
  Trash2,
  Calendar,
  User,
  Users,
  Paperclip,
  Activity,
  LogOut,
  Power,
  ChevronRight,
  Info,
  Reply,
  ReplyAll,
  Forward,
  Flag,
  CheckSquare,
  Plus,
  X,
  Sparkles,
  Network,
  Tag,
  Bold,
  Italic,
  List,
  MessageSquare,
  AlertCircle,
  Eye,
  EyeOff,
  Building,
} from 'lucide-react';
import {
  EmailFolder,
  EmailMessage,
  EmailDraft,
  ConversationThread,
  TodoTaskMapping,
  MicrosoftConnection,
  MicrosoftConnectionStatus,
  OutlookAdminOverview,
  SyncRun,
  UserAccount,
} from '../types';
import { api } from '../api/client';

interface OutlookIntegrationViewProps {
  currentUser: UserAccount;
}

export const OutlookIntegrationView: React.FC<OutlookIntegrationViewProps> = ({ currentUser }) => {
  const [activeTab, setActiveTab] = useState<'mailbox' | 'folders' | 'history' | 'admin'>('mailbox');
  const [status, setStatus] = useState<MicrosoftConnectionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [connecting, setConnecting] = useState(false);

  // Mailbox explorer state
  const [folders, setFolders] = useState<EmailFolder[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [emails, setEmails] = useState<EmailMessage[]>([]);
  const [drafts, setDrafts] = useState<EmailDraft[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<EmailMessage | null>(null);
  const [loadingEmails, setLoadingEmails] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'unread' | 'flagged' | 'high_priority'>('all');

  // Thread view
  const [threadMessages, setThreadMessages] = useState<EmailMessage[]>([]);
  const [loadingThread, setLoadingThread] = useState(false);

  // Sidecar intelligence panel
  const [showIntelligence, setShowIntelligence] = useState(true);
  const [emailAnalysis, setEmailAnalysis] = useState<any | null>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);

  // Composer Modal state
  const [isComposerOpen, setIsComposerOpen] = useState(false);
  const [composerMode, setComposerMode] = useState<'new' | 'reply' | 'reply_all' | 'forward'>('new');
  const [draftId, setDraftId] = useState<string | null>(null);
  const [composerTo, setComposerTo] = useState('');
  const [composerCc, setComposerCc] = useState('');
  const [composerBcc, setComposerBcc] = useState('');
  const [composerSubject, setComposerSubject] = useState('');
  const [composerBody, setComposerBody] = useState('');
  const [composerImportance, setComposerImportance] = useState<'low' | 'normal' | 'high'>('normal');
  const [showCc, setShowCc] = useState(false);
  const [showBcc, setShowBcc] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [autoSaveStatus, setAutoSaveStatus] = useState<string | null>(null);
  const autoSaveTimerRef = useRef<any>(null);

  // Microsoft To Do Modal
  const [isTodoModalOpen, setIsTodoModalOpen] = useState(false);
  const [todoTitle, setTodoTitle] = useState('');
  const [todoNotes, setTodoNotes] = useState('');
  const [todoDueDate, setTodoDueDate] = useState('');
  const [todoImportance, setTodoImportance] = useState<'low' | 'normal' | 'high'>('normal');
  const [creatingTodo, setCreatingTodo] = useState(false);

  // Sync runs & admin overview
  const [syncRuns, setSyncRuns] = useState<SyncRun[]>([]);
  const [adminOverview, setAdminOverview] = useState<OutlookAdminOverview | null>(null);
  const isAdmin = currentUser.approved_position === 'SYSADMIN';

  const isDraftsFolder = () => {
    const folder = folders.find((f) => f.id === selectedFolderId);
    return folder?.well_known_name === 'drafts';
  };

  const fetchStatusAndData = async () => {
    setLoading(true);
    try {
      const statusRes = await api.getOutlookStatus();
      setStatus(statusRes);

      if (statusRes.is_connected) {
        const [foldersRes, runsRes, draftsRes] = await Promise.all([
          api.listOutlookFolders(),
          api.listOutlookSyncRuns(10),
          api.listOutlookDrafts(),
        ]);
        setFolders(foldersRes);
        setSyncRuns(runsRes);
        setDrafts(draftsRes);

        if (!selectedFolderId && foldersRes.length > 0) {
          const inbox = foldersRes.find((f) => f.well_known_name === 'inbox');
          setSelectedFolderId(inbox ? inbox.id : foldersRes[0].id);
        }
      }

      if (isAdmin) {
        try {
          const adm = await api.getOutlookAdminOverview();
          setAdminOverview(adm);
        } catch {
          // ignore
        }
      }
    } catch (err: any) {
      console.error('Failed to load Outlook status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatusAndData();
  }, []);

  // Fetch emails when selected folder or search query changes
  const loadEmails = async () => {
    if (!status?.is_connected) return;
    setLoadingEmails(true);
    try {
      if (isDraftsFolder()) {
        const d = await api.listOutlookDrafts();
        setDrafts(d);
        setEmails([]);
        setSelectedEmail(null);
      } else {
        const msgs = await api.listOutlookEmails({
          folderId: selectedFolderId || undefined,
          search: searchQuery || undefined,
          limit: 50,
        });
        setEmails(msgs);
        if (msgs.length > 0 && !selectedEmail) {
          setSelectedEmail(msgs[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load emails:', err);
    } finally {
      setLoadingEmails(false);
    }
  };

  useEffect(() => {
    loadEmails();
  }, [selectedFolderId, status?.is_connected, searchQuery]);

  // Load conversation thread and analysis when selected email changes
  useEffect(() => {
    if (!selectedEmail) {
      setThreadMessages([]);
      setEmailAnalysis(null);
      return;
    }

    if (selectedEmail.conversation_id) {
      setLoadingThread(true);
      api
        .getConversationThread(selectedEmail.conversation_id)
        .then((thread) => {
          setThreadMessages(thread.messages || []);
        })
        .catch(() => {
          setThreadMessages([selectedEmail]);
        })
        .finally(() => setLoadingThread(false));
    } else {
      setThreadMessages([selectedEmail]);
    }

    // Load AI Analysis for email
    setLoadingAnalysis(true);
    api
      .getOutlookEmailAnalysis(selectedEmail.id)
      .then((res: any) => {
        setEmailAnalysis(res);
      })
      .catch(() => {
        setEmailAnalysis(null);
      })
      .finally(() => setLoadingAnalysis(false));
  }, [selectedEmail]);

  // Auto-save draft timer
  useEffect(() => {
    if (!isComposerOpen || !status?.is_connected) return;

    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }

    if (!composerSubject && !composerBody && !composerTo) return;

    autoSaveTimerRef.current = setTimeout(async () => {
      try {
        setAutoSaveStatus('Saving draft...');
        const toRecips = composerTo
          .split(/[,;]/)
          .map((s) => s.trim())
          .filter(Boolean)
          .map((email) => ({ email }));
        const ccRecips = composerCc
          .split(/[,;]/)
          .map((s) => s.trim())
          .filter(Boolean)
          .map((email) => ({ email }));
        const bccRecips = composerBcc
          .split(/[,;]/)
          .map((s) => s.trim())
          .filter(Boolean)
          .map((email) => ({ email }));

        const saved = await api.saveOutlookDraft({
          id: draftId || undefined,
          reply_mode: composerMode,
          reply_to_message_id: selectedEmail?.id,
          subject: composerSubject,
          body_content: composerBody,
          to_recipients: toRecips,
          cc_recipients: ccRecips,
          bcc_recipients: bccRecips,
          importance: composerImportance,
        });
        setDraftId(saved.id);
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        setAutoSaveStatus(`Saved at ${timeStr}`);
        const freshDrafts = await api.listOutlookDrafts();
        setDrafts(freshDrafts);
      } catch {
        setAutoSaveStatus('Failed to auto-save');
      }
    }, 2500);

    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    };
  }, [composerTo, composerCc, composerBcc, composerSubject, composerBody, composerImportance, isComposerOpen]);

  // Account Connections
  const handleConnectLive = async () => {
    setConnecting(true);
    try {
      const init = await api.getOutlookConnectUrl();
      const popup = window.open(init.authorization_url, 'MicrosoftLogin', 'width=600,height=700,left=200,top=100');
      const handleMessage = (e: MessageEvent) => {
        if (e.data?.type === 'OUTLOOK_CONNECTED_SUCCESS') {
          window.removeEventListener('message', handleMessage);
          fetchStatusAndData();
        }
      };
      window.addEventListener('message', handleMessage);
    } catch (err: any) {
      alert(`OAuth initialization failed: ${err.message}`);
    } finally {
      setConnecting(false);
    }
  };

  const handleMockConnect = async (type: 'organizational' | 'personal') => {
    setConnecting(true);
    try {
      await api.mockConnectOutlook(type);
      await fetchStatusAndData();
    } catch (err: any) {
      alert(`Mock connect failed: ${err.message}`);
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    if (
      !confirm(
        'Are you sure you want to disconnect your Microsoft Outlook account? Your credentials cache will be securely purged from the server.'
      )
    ) {
      return;
    }
    try {
      await api.disconnectOutlook();
      await fetchStatusAndData();
      setEmails([]);
      setSelectedEmail(null);
    } catch (err: any) {
      alert(`Disconnect failed: ${err.message}`);
    }
  };

  const handleSyncNow = async () => {
    setSyncing(true);
    try {
      const res = await api.triggerOutlookSync();
      alert(res.message);
      await fetchStatusAndData();
      await loadEmails();
    } catch (err: any) {
      alert(`Synchronization failed: ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  // Message Operations
  const handleToggleRead = async (email: EmailMessage) => {
    try {
      const updated = await api.markOutlookEmailRead(email.id, !email.is_read);
      setEmails((prev) => prev.map((m) => (m.id === email.id ? updated : m)));
      if (selectedEmail?.id === email.id) setSelectedEmail(updated);
    } catch (err: any) {
      alert(`Failed to update read status: ${err.message}`);
    }
  };

  const handleToggleFlag = async (email: EmailMessage, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const updated = await api.updateOutlookEmailFlag(email.id, !email.is_flagged);
      setEmails((prev) => prev.map((m) => (m.id === email.id ? updated : m)));
      if (selectedEmail?.id === email.id) setSelectedEmail(updated);
    } catch (err: any) {
      alert(`Failed to update flag: ${err.message}`);
    }
  };

  const handleMoveToFolder = async (folderId: string) => {
    if (!selectedEmail) return;
    try {
      const updated = await api.moveOutlookEmail(selectedEmail.id, folderId);
      setEmails((prev) => prev.filter((m) => m.id !== selectedEmail.id));
      setSelectedEmail(null);
      alert('Email moved successfully');
    } catch (err: any) {
      alert(`Failed to move email: ${err.message}`);
    }
  };

  const handleDeleteEmail = async () => {
    if (!selectedEmail) return;
    if (!confirm('Move this email to Deleted Items?')) return;
    try {
      await api.deleteOutlookEmail(selectedEmail.id);
      setEmails((prev) => prev.filter((m) => m.id !== selectedEmail.id));
      setSelectedEmail(null);
    } catch (err: any) {
      alert(`Failed to delete email: ${err.message}`);
    }
  };

  // Composer openers
  const openNewComposer = () => {
    setComposerMode('new');
    setDraftId(null);
    setComposerTo('');
    setComposerCc('');
    setComposerBcc('');
    setComposerSubject('');
    setComposerBody('');
    setComposerImportance('normal');
    setAutoSaveStatus(null);
    setIsComposerOpen(true);
  };

  const openReplyComposer = (replyAll = false) => {
    if (!selectedEmail) return;
    setComposerMode(replyAll ? 'reply_all' : 'reply');
    setDraftId(null);
    setComposerTo(selectedEmail.sender_email || '');
    if (replyAll) {
      const ccList = (selectedEmail.recipients || [])
        .map((r) => r.email)
        .concat((selectedEmail.cc_recipients || []).map((r) => r.email))
        .filter((e) => e !== selectedEmail.sender_email && e !== status?.connection?.email_address);
      setComposerCc(ccList.join(', '));
      setShowCc(ccList.length > 0);
    } else {
      setComposerCc('');
    }
    const subj = selectedEmail.subject || '';
    setComposerSubject(subj.toLowerCase().startsWith('re:') ? subj : `Re: ${subj}`);
    setComposerBody(
      `<br/><br/><hr/><p><strong>From:</strong> ${selectedEmail.sender_name} &lt;${selectedEmail.sender_email}&gt;<br/><strong>Date:</strong> ${selectedEmail.received_at}<br/><strong>Subject:</strong> ${selectedEmail.subject}</p>${selectedEmail.body_content || ''}`
    );
    setAutoSaveStatus(null);
    setIsComposerOpen(true);
  };

  const openForwardComposer = () => {
    if (!selectedEmail) return;
    setComposerMode('forward');
    setDraftId(null);
    setComposerTo('');
    setComposerCc('');
    const subj = selectedEmail.subject || '';
    setComposerSubject(subj.toLowerCase().startsWith('fwd:') ? subj : `Fwd: ${subj}`);
    setComposerBody(
      `<br/><br/><p>---------- Forwarded message ---------<br/><strong>From:</strong> ${selectedEmail.sender_name} &lt;${selectedEmail.sender_email}&gt;<br/><strong>Subject:</strong> ${selectedEmail.subject}</p>${selectedEmail.body_content || ''}`
    );
    setAutoSaveStatus(null);
    setIsComposerOpen(true);
  };

  const openDraftInComposer = (draft: EmailDraft) => {
    setComposerMode(draft.reply_mode || 'new');
    setDraftId(draft.id);
    setComposerTo((draft.to_recipients || []).map((r) => r.email).join(', '));
    setComposerCc((draft.cc_recipients || []).map((r) => r.email).join(', '));
    setComposerBcc((draft.bcc_recipients || []).map((r) => r.email).join(', '));
    setComposerSubject(draft.subject || '');
    setComposerBody(draft.body_content || '');
    setComposerImportance(draft.importance || 'normal');
    setAutoSaveStatus('Draft restored');
    setIsComposerOpen(true);
  };

  const handleSendEmail = async () => {
    if (!composerTo.trim()) {
      alert('Please specify at least one recipient in the To field.');
      return;
    }
    if (!composerSubject.trim()) {
      alert('Please enter a subject.');
      return;
    }

    setIsSending(true);
    try {
      const toRecips = composerTo
        .split(/[,;]/)
        .map((s) => s.trim())
        .filter(Boolean)
        .map((email) => ({ email }));
      const ccRecips = composerCc
        .split(/[,;]/)
        .map((s) => s.trim())
        .filter(Boolean)
        .map((email) => ({ email }));
      const bccRecips = composerBcc
        .split(/[,;]/)
        .map((s) => s.trim())
        .filter(Boolean)
        .map((email) => ({ email }));

      const sentMsg = await api.sendOutlookEmail({
        subject: composerSubject,
        body_content: composerBody,
        body_type: 'html',
        to_recipients: toRecips,
        cc_recipients: ccRecips,
        bcc_recipients: bccRecips,
        importance: composerImportance,
        draft_id: draftId || undefined,
      });

      alert(`Email sent successfully! (ID: ${sentMsg.graph_message_id.slice(0, 16)}...)`);
      setIsComposerOpen(false);
      setDraftId(null);
      await loadEmails();
    } catch (err: any) {
      alert(`Send failed: ${err.message}`);
    } finally {
      setIsSending(false);
    }
  };

  const handleDiscardDraft = async () => {
    if (draftId) {
      try {
        await api.deleteOutlookDraft(draftId);
      } catch {
        // ignore
      }
    }
    setIsComposerOpen(false);
    setDraftId(null);
    if (isDraftsFolder()) {
      const d = await api.listOutlookDrafts();
      setDrafts(d);
    }
  };

  // Microsoft To Do Modal opener
  const openTodoModal = () => {
    if (!selectedEmail) return;
    setTodoTitle(selectedEmail.subject || 'Review Email');
    setTodoNotes(`From: ${selectedEmail.sender_name} (${selectedEmail.sender_email})\n\n${selectedEmail.body_preview || ''}`);
    setTodoDueDate('');
    setTodoImportance(selectedEmail.importance || 'normal');
    setIsTodoModalOpen(true);
  };

  const handleCreateTodoTask = async () => {
    if (!selectedEmail || !todoTitle.trim()) return;
    setCreatingTodo(true);
    try {
      await api.createTodoFromEmail(selectedEmail.id, {
        title: todoTitle,
        notes: todoNotes,
        importance: todoImportance,
        due_date: todoDueDate ? new Date(todoDueDate).toISOString() : undefined,
      });
      alert('Task successfully synchronized to Microsoft To Do!');
      setIsTodoModalOpen(false);
    } catch (err: any) {
      alert(`Failed to create To Do task: ${err.message}`);
    } finally {
      setCreatingTodo(false);
    }
  };

  // Filter emails list
  const filteredEmails = emails.filter((msg) => {
    if (filterType === 'unread') return !msg.is_read;
    if (filterType === 'flagged') return msg.is_flagged;
    if (filterType === 'high_priority') return msg.importance === 'high';
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mr-2" />
        <span className="text-sm font-medium">Loading Email Workspace...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Header Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">Balbird Email Workspace</h1>
              <span className="text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full uppercase tracking-wider">
                Full Native Client
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Read, send, reply, flag, and coordinate company communication without opening Outlook.
            </p>
          </div>

          <div className="flex items-center space-x-2 flex-wrap">
            {status?.is_connected ? (
              <>
                <button
                  onClick={openNewComposer}
                  className="inline-flex items-center px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition shadow-xs cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5 mr-1.5" />
                  Compose
                </button>
                <button
                  onClick={handleSyncNow}
                  disabled={syncing}
                  className="inline-flex items-center px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 disabled:opacity-50 transition cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${syncing ? 'animate-spin' : ''}`} />
                  {syncing ? 'Syncing...' : 'Sync'}
                </button>
                <button
                  onClick={handleDisconnect}
                  className="inline-flex items-center px-3 py-1.5 text-xs font-semibold rounded-lg bg-white border border-rose-200 text-rose-600 hover:bg-rose-50 transition cursor-pointer"
                >
                  <Power className="w-3.5 h-3.5 mr-1.5" />
                  Disconnect
                </button>
              </>
            ) : (
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleConnectLive}
                  disabled={connecting}
                  className="inline-flex items-center px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition shadow-xs cursor-pointer"
                >
                  <Mail className="w-3.5 h-3.5 mr-1.5" />
                  Connect Outlook Account
                </button>
                <button
                  onClick={() => handleMockConnect('organizational')}
                  disabled={connecting}
                  className="inline-flex items-center px-3 py-2 text-xs font-semibold rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 transition cursor-pointer"
                  title="Connect offline synthetic pilot account for testing without Microsoft Azure app credentials"
                >
                  Connect Pilot Mock Account
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Mailbox Status Bar */}
        {status?.is_connected && status.connection && (
          <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between text-xs text-slate-500 gap-2">
            <div className="flex items-center space-x-3">
              <span className="flex items-center text-slate-800 font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-500 mr-1.5" />
                {status.connection.email_address} ({status.connection.account_type.toUpperCase()})
              </span>
              <span className="text-slate-300">|</span>
              <span>Folders: {status.folder_count}</span>
              <span className="text-slate-300">|</span>
              <span>Synced Messages: {status.message_count}</span>
            </div>
            <div className="text-[11px] text-slate-400">
              Delegated Graph scopes: <code>Mail.ReadWrite</code>, <code>Mail.Send</code>, <code>Tasks.ReadWrite</code>
            </div>
          </div>
        )}
      </div>

      {/* Navigation Sub-Tabs */}
      {status?.is_connected && (
        <div className="flex items-center space-x-1 border-b border-slate-200 text-xs font-medium">
          <button
            onClick={() => setActiveTab('mailbox')}
            className={`px-4 py-2 border-b-2 font-semibold transition cursor-pointer ${
              activeTab === 'mailbox' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Mailbox Workspace
          </button>
          <button
            onClick={() => setActiveTab('folders')}
            className={`px-4 py-2 border-b-2 font-semibold transition cursor-pointer ${
              activeTab === 'folders' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Folders ({folders.length})
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`px-4 py-2 border-b-2 font-semibold transition cursor-pointer ${
              activeTab === 'history' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Sync History
          </button>
          {isAdmin && (
            <button
              onClick={() => setActiveTab('admin')}
              className={`px-4 py-2 border-b-2 font-semibold transition cursor-pointer ${
                activeTab === 'admin' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Admin System Overview
            </button>
          )}
        </div>
      )}

      {/* Main Mailbox Workspace (Responsive 3-Column + Sidecar Intelligence) */}
      {status?.is_connected && activeTab === 'mailbox' && (
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs min-h-[640px]">
          {/* Column 1: Folders & Compose (2.5 Cols) */}
          <div className="md:col-span-2 border-r border-slate-200 p-3 space-y-3 bg-slate-50/50 flex flex-col justify-between">
            <div className="space-y-1">
              <button
                onClick={openNewComposer}
                className="w-full flex items-center justify-center space-x-1.5 py-2 px-3 mb-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs transition cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>New Message</span>
              </button>

              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-2 pb-1">Mailbox Folders</div>

              {folders.map((f) => {
                const isSelected = selectedFolderId === f.id;
                const isDraft = f.well_known_name === 'drafts';
                const count = isDraft ? drafts.length : f.total_item_count;

                return (
                  <button
                    key={f.id}
                    onClick={() => {
                      setSelectedFolderId(f.id);
                      setSelectedEmail(null);
                    }}
                    className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs transition cursor-pointer ${
                      isSelected ? 'bg-blue-600 text-white font-semibold' : 'text-slate-700 hover:bg-slate-200/60'
                    }`}
                  >
                    <div className="flex items-center space-x-2 truncate">
                      {f.well_known_name === 'inbox' ? (
                        <Inbox className="w-3.5 h-3.5 shrink-0" />
                      ) : f.well_known_name === 'sentitems' ? (
                        <Send className="w-3.5 h-3.5 shrink-0" />
                      ) : f.well_known_name === 'archive' ? (
                        <Archive className="w-3.5 h-3.5 shrink-0" />
                      ) : f.well_known_name === 'deleteditems' ? (
                        <Trash2 className="w-3.5 h-3.5 shrink-0" />
                      ) : (
                        <Folder className="w-3.5 h-3.5 shrink-0" />
                      )}
                      <span className="truncate">{f.display_name}</span>
                    </div>
                    {count > 0 && (
                      <span
                        className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                          isSelected ? 'bg-blue-700 text-white' : 'bg-slate-200 text-slate-600'
                        }`}
                      >
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            <div className="p-2 bg-white rounded-xl border border-slate-200 text-[10px] text-slate-500 space-y-1">
              <div className="font-semibold text-slate-700 flex items-center">
                <ShieldCheck className="w-3 h-3 text-emerald-600 mr-1" /> Delegated Identity
              </div>
              <p>Sent emails genuinely originate from your authorized Microsoft account.</p>
            </div>
          </div>

          {/* Column 2: Email & Drafts List (3.5 Cols) */}
          <div className="md:col-span-4 border-r border-slate-200 flex flex-col">
            {/* Search & Filters */}
            <div className="p-3 border-b border-slate-200 space-y-2 bg-white">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search sender, subject, or content..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-100 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              {!isDraftsFolder() && (
                <div className="flex items-center space-x-1 text-[11px]">
                  {(['all', 'unread', 'flagged', 'high_priority'] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setFilterType(t)}
                      className={`px-2 py-0.5 rounded-md font-medium transition cursor-pointer ${
                        filterType === t ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
                      }`}
                    >
                      {t === 'all'
                        ? 'All'
                        : t === 'unread'
                        ? 'Unread'
                        : t === 'flagged'
                        ? 'Flagged'
                        : 'High Priority'}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto divide-y divide-slate-100 max-h-[580px]">
              {loadingEmails ? (
                <div className="p-8 text-center text-xs text-slate-400">Loading messages...</div>
              ) : isDraftsFolder() ? (
                drafts.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-400">No saved drafts.</div>
                ) : (
                  drafts.map((d) => (
                    <div
                      key={d.id}
                      onClick={() => openDraftInComposer(d)}
                      className="p-3 hover:bg-slate-50 cursor-pointer transition border-l-4 border-transparent hover:border-blue-400"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-slate-800 text-xs">
                          {d.to_recipients && d.to_recipients.length > 0
                            ? `To: ${d.to_recipients.map((r) => r.email).join(', ')}`
                            : '(No recipients)'}
                        </span>
                        <span className="text-[10px] text-slate-400">
                          {new Date(d.last_saved_at || d.updated_at).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="text-xs font-medium text-slate-900 truncate">
                        {d.subject || '(Draft with no subject)'}
                      </div>
                      <div className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                        {d.body_content ? d.body_content.replace(/<[^>]+>/g, '') : 'Empty draft'}
                      </div>
                    </div>
                  ))
                )
              ) : filteredEmails.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-400">No messages match your criteria.</div>
              ) : (
                filteredEmails.map((msg) => {
                  const isSel = selectedEmail?.id === msg.id;
                  return (
                    <div
                      key={msg.id}
                      onClick={() => setSelectedEmail(msg)}
                      className={`p-3 cursor-pointer text-xs transition border-l-4 ${
                        isSel
                          ? 'bg-blue-50/70 border-blue-600'
                          : msg.is_read
                          ? 'border-transparent hover:bg-slate-50'
                          : 'border-blue-400 bg-slate-50/40 hover:bg-blue-50/40 font-semibold'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center space-x-1.5 truncate">
                          {!msg.is_read && <span className="w-1.5 h-1.5 rounded-full bg-blue-600 shrink-0" />}
                          <span className="truncate max-w-[150px] text-slate-900">
                            {msg.sender_name || msg.sender_email || 'Unknown'}
                          </span>
                        </div>
                        <div className="flex items-center space-x-1.5 shrink-0">
                          <button
                            onClick={(e) => handleToggleFlag(msg, e)}
                            className={`p-0.5 rounded hover:bg-slate-200 transition ${
                              msg.is_flagged ? 'text-amber-500' : 'text-slate-300 hover:text-slate-500'
                            }`}
                            title={msg.is_flagged ? 'Unflag' : 'Flag'}
                          >
                            <Flag className="w-3.5 h-3.5 fill-current" />
                          </button>
                          <span className="text-[10px] text-slate-400">
                            {msg.received_at ? new Date(msg.received_at).toLocaleDateString([], { month: 'short', day: 'numeric' }) : ''}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center justify-between gap-1 mb-1">
                        <span className="font-medium text-slate-800 truncate">{msg.subject || '(No Subject)'}</span>
                        {msg.importance === 'high' && (
                          <span className="text-[9px] bg-rose-50 text-rose-600 border border-rose-200 px-1 py-0.2 rounded font-bold uppercase shrink-0">
                            High
                          </span>
                        )}
                      </div>

                      <p className="text-[11px] text-slate-500 line-clamp-2">{msg.body_preview || 'No preview available'}</p>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Column 3: Message Reading & Thread Pane (4.5 Cols if intelligence open, 6 Cols if closed) */}
          <div className={`${showIntelligence ? 'md:col-span-4' : 'md:col-span-6'} flex flex-col justify-between border-r border-slate-200 overflow-y-auto max-h-[640px]`}>
            {selectedEmail ? (
              <div className="flex-1 flex flex-col">
                {/* Action Bar */}
                <div className="p-3 border-b border-slate-200 bg-white flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center space-x-1">
                    <button
                      onClick={() => openReplyComposer(false)}
                      className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-700 font-medium text-xs flex items-center space-x-1 cursor-pointer"
                      title="Reply"
                    >
                      <Reply className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Reply</span>
                    </button>
                    <button
                      onClick={() => openReplyComposer(true)}
                      className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-700 font-medium text-xs flex items-center space-x-1 cursor-pointer"
                      title="Reply All"
                    >
                      <ReplyAll className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Reply All</span>
                    </button>
                    <button
                      onClick={openForwardComposer}
                      className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-700 font-medium text-xs flex items-center space-x-1 cursor-pointer"
                      title="Forward"
                    >
                      <Forward className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Forward</span>
                    </button>
                  </div>

                  <div className="flex items-center space-x-1">
                    <button
                      onClick={() => handleToggleFlag(selectedEmail)}
                      className={`p-1.5 rounded-lg hover:bg-slate-100 cursor-pointer ${
                        selectedEmail.is_flagged ? 'text-amber-500' : 'text-slate-400 hover:text-slate-700'
                      }`}
                      title={selectedEmail.is_flagged ? 'Remove flag' : 'Flag message'}
                    >
                      <Flag className="w-4 h-4 fill-current" />
                    </button>
                    <button
                      onClick={() => handleToggleRead(selectedEmail)}
                      className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 cursor-pointer"
                      title={selectedEmail.is_read ? 'Mark unread' : 'Mark read'}
                    >
                      {selectedEmail.is_read ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={openTodoModal}
                      className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-600 hover:text-blue-600 cursor-pointer flex items-center space-x-1 text-xs"
                      title="Add to Microsoft To Do"
                    >
                      <CheckSquare className="w-4 h-4" />
                      <span className="hidden lg:inline text-[11px]">To Do</span>
                    </button>
                    <button
                      onClick={handleDeleteEmail}
                      className="p-1.5 rounded-lg hover:bg-rose-50 text-slate-400 hover:text-rose-600 cursor-pointer"
                      title="Delete email"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setShowIntelligence(!showIntelligence)}
                      className={`p-1.5 rounded-lg cursor-pointer ${
                        showIntelligence ? 'bg-blue-50 text-blue-600 font-semibold' : 'text-slate-400 hover:bg-slate-100'
                      }`}
                      title="Toggle AI Intelligence Sidecar"
                    >
                      <Sparkles className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Message Header */}
                <div className="p-4 border-b border-slate-100 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <h2 className="text-base font-bold text-slate-900 leading-snug">
                      {selectedEmail.subject || '(No Subject)'}
                    </h2>
                    {selectedEmail.web_link && (
                      <a
                        href={selectedEmail.web_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-slate-400 hover:text-blue-600 shrink-0"
                        title="Open in Outlook Web"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-600">
                    <div>
                      From: <strong className="text-slate-900">{selectedEmail.sender_name}</strong>{' '}
                      <span className="text-slate-400">&lt;{selectedEmail.sender_email}&gt;</span>
                    </div>
                    <div className="text-[11px] text-slate-400">
                      {selectedEmail.received_at ? new Date(selectedEmail.received_at).toLocaleString() : ''}
                    </div>
                  </div>

                  {selectedEmail.recipients && selectedEmail.recipients.length > 0 && (
                    <div className="text-[11px] text-slate-500">
                      To: {selectedEmail.recipients.map((r) => r.name || r.email).join(', ')}
                    </div>
                  )}

                  {selectedEmail.cc_recipients && selectedEmail.cc_recipients.length > 0 && (
                    <div className="text-[11px] text-slate-400">
                      CC: {selectedEmail.cc_recipients.map((r) => r.name || r.email).join(', ')}
                    </div>
                  )}
                </div>

                {/* Message Body */}
                <div className="p-4 flex-1">
                  <div className="text-xs text-slate-800 leading-relaxed bg-white rounded-xl">
                    {selectedEmail.body_content ? (
                      <div
                        dangerouslySetInnerHTML={{ __html: selectedEmail.body_content }}
                        className="prose prose-xs max-w-none break-words"
                      />
                    ) : (
                      <p className="italic text-slate-400">No body content available.</p>
                    )}
                  </div>
                </div>

                {/* Thread History Accordion */}
                {threadMessages.length > 1 && (
                  <div className="p-4 border-t border-slate-200 bg-slate-50/50">
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-xs font-bold text-slate-700 flex items-center space-x-1.5">
                        <MessageSquare className="w-3.5 h-3.5 text-blue-600" />
                        <span>Conversation Thread ({threadMessages.length} messages)</span>
                      </div>
                    </div>
                    <div className="space-y-2">
                      {threadMessages.map((tMsg) => {
                        const isCurrent = tMsg.id === selectedEmail.id;
                        return (
                          <div
                            key={tMsg.id}
                            onClick={() => setSelectedEmail(tMsg)}
                            className={`p-2.5 rounded-xl border text-xs cursor-pointer transition ${
                              isCurrent
                                ? 'bg-white border-blue-500 shadow-xs'
                                : 'bg-white/60 border-slate-200 hover:bg-white'
                            }`}
                          >
                            <div className="flex items-center justify-between text-[11px]">
                              <span className="font-semibold text-slate-800">{tMsg.sender_name || tMsg.sender_email}</span>
                              <span className="text-slate-400">
                                {tMsg.received_at ? new Date(tMsg.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                              </span>
                            </div>
                            <p className="text-slate-600 line-clamp-1 mt-0.5 text-[11px]">{tMsg.body_preview}</p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-slate-400 p-8 text-center">
                <Mail className="w-10 h-10 stroke-[1.2] mb-2 text-slate-300" />
                <p className="text-xs font-medium">Select a conversation from the list to read.</p>
              </div>
            )}
          </div>

          {/* Column 4: Sidecar AI Intelligence Panel (2 Cols) */}
          {showIntelligence && (
            <div className="md:col-span-2 p-3 bg-slate-50/80 overflow-y-auto max-h-[640px] space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <div className="flex items-center space-x-1.5 font-bold text-xs text-slate-900">
                  <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                  <span>Email Intelligence</span>
                </div>
                <button
                  onClick={() => setShowIntelligence(false)}
                  className="p-1 text-slate-400 hover:text-slate-600 rounded cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {selectedEmail ? (
                loadingAnalysis ? (
                  <div className="py-8 text-center text-xs text-slate-400">
                    <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-1 text-blue-500" />
                    <span>Analyzing communication...</span>
                  </div>
                ) : emailAnalysis ? (
                  <div className="space-y-3 text-xs">
                    {/* Department Badges */}
                    <div className="space-y-1">
                      <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Classification</div>
                      <div className="flex flex-wrap gap-1">
                        <span className="px-2 py-0.5 rounded font-bold text-[10px] bg-blue-100 text-blue-800 border border-blue-200">
                          {emailAnalysis.department || 'GENERAL'} [Primary]
                        </span>
                        {emailAnalysis.raw_structured_output?.secondary_departments?.map((sd: string) => (
                          <span
                            key={sd}
                            className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-200 text-slate-700"
                          >
                            {sd}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Intent & Priority */}
                    <div className="p-2 bg-white rounded-xl border border-slate-200 space-y-1">
                      <div className="text-[10px] text-slate-400 uppercase font-bold">Intent & Type</div>
                      <div className="font-semibold text-slate-800 text-[11px]">{emailAnalysis.intent || 'GENERAL_COMMUNICATION'}</div>
                      <div className="flex items-center justify-between text-[11px] pt-1 border-t border-slate-100">
                        <span className="text-slate-500">Priority:</span>
                        <span className="font-bold text-rose-600 uppercase">{emailAnalysis.priority}</span>
                      </div>
                    </div>

                    {/* Identified Entities (Customer PO vs Supplier PO, WO vs Invoice) */}
                    <div className="space-y-1">
                      <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">References & Entities</div>
                      <div className="p-2 bg-white rounded-xl border border-slate-200 space-y-1.5 text-[11px]">
                        {emailAnalysis.raw_structured_output?.references && emailAnalysis.raw_structured_output.references.length > 0 ? (
                          emailAnalysis.raw_structured_output.references.map((r: any, idx: number) => (
                            <div key={idx} className="flex items-center justify-between">
                              <span className="font-semibold text-slate-700">{r.type}:</span>
                              <span className="font-mono text-blue-600 font-bold">{r.value}</span>
                            </div>
                          ))
                        ) : (
                          <div className="text-slate-400 italic text-[10px]">No PO/SO/WO extracted</div>
                        )}

                        {emailAnalysis.raw_structured_output?.materials && emailAnalysis.raw_structured_output.materials.length > 0 && (
                          <div className="pt-1 border-t border-slate-100">
                            <span className="text-slate-500">Materials: </span>
                            <span className="font-medium text-slate-800">{emailAnalysis.raw_structured_output.materials.join(', ')}</span>
                          </div>
                        )}

                        {emailAnalysis.raw_structured_output?.parts && emailAnalysis.raw_structured_output.parts.length > 0 && (
                          <div className="pt-1 border-t border-slate-100">
                            <span className="text-slate-500">Parts: </span>
                            <span className="font-medium text-slate-800">{emailAnalysis.raw_structured_output.parts.join(', ')}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Cross-Department Connections */}
                    {emailAnalysis.raw_structured_output?.cross_department_connections &&
                      emailAnalysis.raw_structured_output.cross_department_connections.length > 0 && (
                        <div className="space-y-1">
                          <div className="text-[10px] font-bold text-amber-600 uppercase tracking-wider flex items-center">
                            <Network className="w-3 h-3 mr-1" /> Cross-Dept Impact
                          </div>
                          {emailAnalysis.raw_structured_output.cross_department_connections.map((conn: any, i: number) => (
                            <div key={i} className="p-2 bg-amber-50/70 border border-amber-200 rounded-xl space-y-1">
                              <div className="font-bold text-amber-900 text-[10px] uppercase">{conn.scenario}</div>
                              <p className="text-[10px] text-amber-800 leading-snug">{conn.explanation}</p>
                              <div className="text-[9px] font-semibold text-rose-700">
                                Commitment Risk: {conn.commitment_at_risk || 'Yes'}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                    {/* Summary */}
                    {emailAnalysis.summary && (
                      <div className="space-y-1">
                        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">AI Summary</div>
                        <p className="text-[11px] text-slate-600 leading-relaxed bg-white p-2 rounded-xl border border-slate-200">
                          {emailAnalysis.summary}
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-4 bg-white rounded-xl border border-slate-200 text-center text-[11px] text-slate-400">
                    No intelligence metadata available for this message.
                  </div>
                )
              ) : (
                <div className="text-slate-400 text-xs italic text-center py-6">Select an email to view analysis.</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Discovered Folders */}
      {status?.is_connected && activeTab === 'folders' && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-400 font-semibold uppercase text-[10px] tracking-wider">
              <tr>
                <th className="px-4 py-3">Folder Name</th>
                <th className="px-4 py-3">Graph ID</th>
                <th className="px-4 py-3">Well Known</th>
                <th className="px-4 py-3">Total Items</th>
                <th className="px-4 py-3">Unread</th>
                <th className="px-4 py-3">Sync Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {folders.map((f) => (
                <tr key={f.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-semibold text-slate-800 flex items-center space-x-2">
                    <Folder className="w-3.5 h-3.5 text-blue-500" />
                    <span>{f.display_name}</span>
                  </td>
                  <td className="px-4 py-3 font-mono text-[11px] text-slate-400">{f.graph_folder_id.slice(0, 16)}...</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-slate-100 font-medium text-slate-600">
                      {f.well_known_name || 'custom'}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-700">{f.total_item_count}</td>
                  <td className="px-4 py-3 text-slate-600">{f.unread_item_count}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                        f.sync_enabled
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-slate-50 text-slate-500 border-slate-200'
                      }`}
                    >
                      {f.sync_enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 3: Sync Run History */}
      {status?.is_connected && activeTab === 'history' && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-400 font-semibold uppercase text-[10px] tracking-wider">
              <tr>
                <th className="px-4 py-3">Sync Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Started At</th>
                <th className="px-4 py-3">Completed At</th>
                <th className="px-4 py-3">Discovered</th>
                <th className="px-4 py-3">Inserted</th>
                <th className="px-4 py-3">Updated</th>
                <th className="px-4 py-3">Deleted</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {syncRuns.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    No synchronization runs recorded yet. Click "Sync Now" to trigger a run.
                  </td>
                </tr>
              ) : (
                syncRuns.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-semibold text-slate-800">{r.sync_type}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                          r.status === 'SUCCESS'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : r.status === 'RUNNING'
                            ? 'bg-blue-50 text-blue-700 border-blue-200 animate-pulse'
                            : r.status === 'PARTIAL'
                            ? 'bg-amber-50 text-amber-700 border-amber-200'
                            : 'bg-rose-50 text-rose-700 border-rose-200'
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">{new Date(r.started_at).toLocaleString()}</td>
                    <td className="px-4 py-3">{r.completed_at ? new Date(r.completed_at).toLocaleString() : 'In progress...'}</td>
                    <td className="px-4 py-3 font-medium text-slate-700">{r.messages_discovered}</td>
                    <td className="px-4 py-3 text-emerald-600 font-semibold">+{r.messages_inserted}</td>
                    <td className="px-4 py-3 text-blue-600">{r.messages_updated}</td>
                    <td className="px-4 py-3 text-rose-600">{r.messages_deleted}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 4: Admin System Overview */}
      {isAdmin && activeTab === 'admin' && adminOverview && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Connected Employees</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">
                {adminOverview.connected_employees_count} / {adminOverview.total_employees}
              </div>
              <div className="text-[11px] text-slate-400 mt-1">Active employee mailboxes</div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Total Mailbox Folders</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">{adminOverview.total_discovered_folders}</div>
              <div className="text-[11px] text-slate-400 mt-1">Monitored across company</div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Synced Messages Ingested</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">{adminOverview.total_synchronized_messages}</div>
              <div className="text-[11px] text-slate-400 mt-1">Bridged to intelligence layer</div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Background Scheduler</div>
              <div className="text-xs font-bold text-emerald-600 mt-1 flex items-center">
                <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Active (Every 5 mins)
              </div>
              <div className="text-[11px] text-slate-400 mt-1">Active Jobs: {adminOverview.active_sync_jobs}</div>
            </div>
          </div>
        </div>
      )}

      {/* Email Composer Modal */}
      {isComposerOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-3xl flex flex-col max-h-[90vh] overflow-hidden">
            {/* Composer Header */}
            <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center space-x-2">
                <Send className="w-4 h-4 text-blue-600" />
                <h3 className="font-bold text-sm text-slate-900">
                  {composerMode === 'new'
                    ? 'New Message'
                    : composerMode === 'reply'
                    ? 'Reply'
                    : composerMode === 'reply_all'
                    ? 'Reply All'
                    : 'Forward'}
                </h3>
                {autoSaveStatus && (
                  <span className="text-[10px] text-slate-400 bg-white px-2 py-0.5 rounded border border-slate-200">
                    {autoSaveStatus}
                  </span>
                )}
              </div>
              <button
                onClick={handleDiscardDraft}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg cursor-pointer"
                title="Discard draft"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Composer Inputs */}
            <div className="p-4 space-y-3 flex-1 overflow-y-auto">
              {/* To */}
              <div className="flex items-center space-x-2 border-b border-slate-100 pb-2">
                <label className="w-12 text-xs font-semibold text-slate-500">To:</label>
                <input
                  type="text"
                  placeholder="recipient@example.com, another@example.com"
                  value={composerTo}
                  onChange={(e) => setComposerTo(e.target.value)}
                  className="flex-1 text-xs focus:outline-none"
                />
                <div className="flex items-center space-x-1 text-[11px] text-blue-600">
                  {!showCc && (
                    <button onClick={() => setShowCc(true)} className="hover:underline cursor-pointer">
                      CC
                    </button>
                  )}
                  {!showBcc && (
                    <button onClick={() => setShowBcc(true)} className="hover:underline cursor-pointer">
                      BCC
                    </button>
                  )}
                </div>
              </div>

              {/* CC */}
              {showCc && (
                <div className="flex items-center space-x-2 border-b border-slate-100 pb-2">
                  <label className="w-12 text-xs font-semibold text-slate-500">CC:</label>
                  <input
                    type="text"
                    placeholder="cc@example.com"
                    value={composerCc}
                    onChange={(e) => setComposerCc(e.target.value)}
                    className="flex-1 text-xs focus:outline-none"
                  />
                  <button onClick={() => setShowCc(false)} className="text-slate-400 hover:text-slate-600 text-xs">
                    ×
                  </button>
                </div>
              )}

              {/* BCC */}
              {showBcc && (
                <div className="flex items-center space-x-2 border-b border-slate-100 pb-2">
                  <label className="w-12 text-xs font-semibold text-slate-500">BCC:</label>
                  <input
                    type="text"
                    placeholder="bcc@example.com"
                    value={composerBcc}
                    onChange={(e) => setComposerBcc(e.target.value)}
                    className="flex-1 text-xs focus:outline-none"
                  />
                  <button onClick={() => setShowBcc(false)} className="text-slate-400 hover:text-slate-600 text-xs">
                    ×
                  </button>
                </div>
              )}

              {/* Subject & Priority */}
              <div className="flex items-center space-x-2 border-b border-slate-100 pb-2">
                <label className="w-12 text-xs font-semibold text-slate-500">Subject:</label>
                <input
                  type="text"
                  placeholder="Enter message subject"
                  value={composerSubject}
                  onChange={(e) => setComposerSubject(e.target.value)}
                  className="flex-1 text-xs font-medium focus:outline-none"
                />
                <select
                  value={composerImportance}
                  onChange={(e: any) => setComposerImportance(e.target.value)}
                  className="text-[11px] border border-slate-200 rounded px-1.5 py-1 text-slate-600 focus:outline-none"
                >
                  <option value="normal">Normal Priority</option>
                  <option value="high">High Priority</option>
                  <option value="low">Low Priority</option>
                </select>
              </div>

              {/* Security Policy Notice regarding attachments */}
              <div className="p-2 bg-amber-50/70 rounded-lg border border-amber-200/80 text-[11px] text-amber-800 flex items-start space-x-1.5">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-600" />
                <span>
                  <strong>Attachment Policy:</strong> Direct binary file attachments are restricted by enterprise zero-trust policy. Formatted tables, data links, and hyperlinks are fully supported.
                </span>
              </div>

              {/* Rich Body Textarea */}
              <div className="border border-slate-200 rounded-xl overflow-hidden focus-within:ring-1 focus-within:ring-blue-500">
                <textarea
                  rows={12}
                  placeholder="Type your email content here (HTML formatting supported)..."
                  value={composerBody}
                  onChange={(e) => setComposerBody(e.target.value)}
                  className="w-full p-3 text-xs focus:outline-none font-sans leading-relaxed resize-none"
                />
              </div>
            </div>

            {/* Composer Footer */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
              <button
                onClick={handleDiscardDraft}
                className="px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-50 rounded-lg font-medium transition cursor-pointer"
              >
                Discard
              </button>

              <div className="flex items-center space-x-2">
                <button
                  onClick={async () => {
                    setAutoSaveStatus('Draft saved manually');
                    alert('Draft saved.');
                  }}
                  className="px-3 py-1.5 text-xs text-slate-700 bg-white border border-slate-200 hover:bg-slate-100 rounded-lg font-medium transition cursor-pointer"
                >
                  Save Draft
                </button>
                <button
                  onClick={handleSendEmail}
                  disabled={isSending}
                  className="px-4 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold shadow-xs transition flex items-center space-x-1.5 disabled:opacity-50 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{isSending ? 'Sending...' : 'Send Message'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Microsoft To Do Modal */}
      {isTodoModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <CheckSquare className="w-5 h-5 text-blue-600" />
                <h3 className="font-bold text-sm text-slate-900">Add to Microsoft To Do</h3>
              </div>
              <button onClick={() => setIsTodoModalOpen(false)} className="text-slate-400 hover:text-slate-600 cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Task Title</label>
                <input
                  type="text"
                  value={todoTitle}
                  onChange={(e) => setTodoTitle(e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">Due Date (Optional)</label>
                <input
                  type="date"
                  value={todoDueDate}
                  onChange={(e) => setTodoDueDate(e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">Importance</label>
                <select
                  value={todoImportance}
                  onChange={(e: any) => setTodoImportance(e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="low">Low</option>
                </select>
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">Notes</label>
                <textarea
                  rows={4}
                  value={todoNotes}
                  onChange={(e) => setTodoNotes(e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setIsTodoModalOpen(false)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg font-medium cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateTodoTask}
                disabled={creatingTodo}
                className="px-4 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold shadow-xs disabled:opacity-50 cursor-pointer"
              >
                {creatingTodo ? 'Creating...' : 'Create Task'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
