import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { Sidebar, NavTab } from './components/Sidebar';
import { OverviewView } from './views/OverviewView';
import { InboxView } from './views/InboxView';
import { BusinessCasesView } from './views/BusinessCasesView';
import { TasksView } from './views/TasksView';
import { DependenciesView } from './views/DependenciesView';
import { OrdersView } from './views/OrdersView';
import { SmartDraftsView } from './views/SmartDraftsView';
import { DiagnosticsView } from './views/DiagnosticsView';
import {
  BIRole,
  BusinessCase,
  DashboardSummary,
  LegacyTask,
  MonitoringAlert,
  SalesOrder,
  SourceMessage,
  TaskDependency,
  TaskProposal,
} from './types';
import { api } from './api/client';

export const App: React.FC = () => {
  const [currentRole, setCurrentRole] = useState<BIRole>('MANAGEMENT');
  const [currentTab, setCurrentTab] = useState<NavTab>('overview');

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [cases, setCases] = useState<BusinessCase[]>([]);
  const [emails, setEmails] = useState<SourceMessage[]>([]);
  const [tasks, setTasks] = useState<LegacyTask[]>([]);
  const [proposals, setProposals] = useState<TaskProposal[]>([]);
  const [dependencies, setDependencies] = useState<TaskDependency[]>([]);
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [alerts, setAlerts] = useState<MonitoringAlert[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [sumRes, casesRes, emailsRes, tasksRes, propsRes, depsRes, ordersRes, alertsRes] =
        await Promise.allSettled([
          api.getDashboardSummary(),
          api.listCases(),
          api.listEmails(),
          api.listTasks(),
          api.listProposals(),
          api.listDependencies(),
          api.listOrders(),
          api.listAlerts(),
        ]);

      if (sumRes.status === 'fulfilled') setSummary(sumRes.value);
      if (casesRes.status === 'fulfilled') setCases(casesRes.value);
      if (emailsRes.status === 'fulfilled') setEmails(emailsRes.value);
      if (tasksRes.status === 'fulfilled') setTasks(tasksRes.value);
      if (propsRes.status === 'fulfilled') setProposals(propsRes.value);
      if (depsRes.status === 'fulfilled') setDependencies(depsRes.value);
      if (ordersRes.status === 'fulfilled') setOrders(ordersRes.value);
      if (alertsRes.status === 'fulfilled') setAlerts(alertsRes.value);
    } catch (err) {
      console.error('Failed to load application data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="min-h-screen bg-slate-100/60 font-sans text-slate-800 antialiased flex flex-col">
      <Header
        currentRole={currentRole}
        onRoleChange={setCurrentRole}
        openAlertsCount={alerts.filter((a) => a.status === 'OPEN').length}
      />

      <div className="flex flex-1">
        <Sidebar
          currentTab={currentTab}
          onTabChange={setCurrentTab}
          pendingEmailsCount={emails.filter((m) => m.processing_status === 'NEEDS_REVIEW').length}
          pendingProposalsCount={proposals.filter((p) => p.proposal_status === 'PENDING').length}
        />

        <main className="flex-1 p-6 overflow-y-auto max-w-7xl">
          {currentTab === 'overview' && <OverviewView summary={summary} onNavigate={setCurrentTab} />}
          {currentTab === 'inbox' && <InboxView emails={emails} onRefresh={loadData} />}
          {currentTab === 'cases' && <BusinessCasesView cases={cases} />}
          {currentTab === 'tasks' && (
            <TasksView tasks={tasks} proposals={proposals} onRefresh={loadData} />
          )}
          {currentTab === 'dependencies' && (
            <DependenciesView dependencies={dependencies} tasks={tasks} onRefresh={loadData} />
          )}
          {currentTab === 'orders' && <OrdersView orders={orders} />}
          {currentTab === 'drafts' && <SmartDraftsView cases={cases} />}
          {currentTab === 'diagnostics' && <DiagnosticsView />}
        </main>
      </div>
    </div>
  );
};

export default App;
