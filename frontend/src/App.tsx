import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { Sidebar, NavTab } from './components/Sidebar';
import { PendingApprovalBanner } from './components/PendingApprovalBanner';
import { OverviewView } from './views/OverviewView';
import { InboxView } from './views/InboxView';
import { BusinessCasesView } from './views/BusinessCasesView';
import { TasksView } from './views/TasksView';
import { DependenciesView } from './views/DependenciesView';
import { OrdersView } from './views/OrdersView';
import { SmartDraftsView } from './views/SmartDraftsView';
import { DiagnosticsView } from './views/DiagnosticsView';
import { EmployeesView } from './views/EmployeesView';
import { DepartmentsView } from './views/DepartmentsView';
import { LoginView } from './views/LoginView';
import { RegisterView } from './views/RegisterView';
import { UserProfileView } from './views/UserProfileView';
import { AdminUserManagementView } from './views/AdminUserManagementView';
import { AccessDeniedView } from './views/AccessDeniedView';
import { OutlookIntegrationView } from './views/OutlookIntegrationView';
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
  UserAccount,
} from './types';
import { api, authStorage } from './api/client';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<UserAccount | null>(null);
  const [authView, setAuthView] = useState<'login' | 'register'>('login');
  const [authChecking, setAuthChecking] = useState(true);

  const [currentTab, setCurrentTab] = useState<NavTab>('overview');

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [cases, setCases] = useState<BusinessCase[]>([]);
  const [emails, setEmails] = useState<SourceMessage[]>([]);
  const [tasks, setTasks] = useState<LegacyTask[]>([]);
  const [proposals, setProposals] = useState<TaskProposal[]>([]);
  const [dependencies, setDependencies] = useState<TaskDependency[]>([]);
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [alerts, setAlerts] = useState<MonitoringAlert[]>([]);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number>(0);
  const [loading, setLoading] = useState(false);

  // Check existing session on mount
  useEffect(() => {
    const checkSession = async () => {
      const token = authStorage.getToken();
      if (token) {
        try {
          const user = await api.getMe();
          setCurrentUser(user);
          // Set initial default tab based on approved position
          if (user.approved_position === 'EMPLOYEE') {
            setCurrentTab('tasks');
          } else {
            setCurrentTab('overview');
          }
        } catch {
          authStorage.clearToken();
          setCurrentUser(null);
        }
      }
      setAuthChecking(false);
    };
    checkSession();
  }, []);

  const loadData = async () => {
    if (!currentUser) return;
    setLoading(true);

    try {
      const isEmployee = currentUser.approved_position === 'EMPLOYEE';
      const isHOD = currentUser.approved_position === 'DEPT_HEAD';
      const isAdmin = currentUser.approved_position === 'SYSADMIN';

      // Load tasks, dependencies, drafts (accessible to all authenticated positions)
      const tasksPromise = api.listTasks();
      const depsPromise = api.listDependencies();
      const casesPromise = !isEmployee ? api.listCases() : Promise.resolve([]);
      const emailsPromise = !isEmployee ? api.listEmails() : Promise.resolve([]);
      const propsPromise = !isEmployee ? api.listProposals() : Promise.resolve([]);
      const ordersPromise = !isEmployee ? api.listOrders() : Promise.resolve([]);
      const alertsPromise = !isEmployee ? api.listAlerts() : Promise.resolve([]);
      const sumPromise = !isEmployee ? api.getDashboardSummary() : Promise.resolve(null);
      const roleReqsPromise = isAdmin ? api.listRoleRequests('PENDING') : Promise.resolve([]);

      const [sumRes, casesRes, emailsRes, tasksRes, propsRes, depsRes, ordersRes, alertsRes, reqsRes] =
        await Promise.allSettled([
          sumPromise,
          casesPromise,
          emailsPromise,
          tasksPromise,
          propsPromise,
          depsPromise,
          ordersPromise,
          alertsPromise,
          roleReqsPromise,
        ]);

      if (sumRes.status === 'fulfilled' && sumRes.value) setSummary(sumRes.value);
      if (casesRes.status === 'fulfilled') setCases(casesRes.value);
      if (emailsRes.status === 'fulfilled') setEmails(emailsRes.value);
      if (tasksRes.status === 'fulfilled') setTasks(tasksRes.value);
      if (propsRes.status === 'fulfilled') setProposals(propsRes.value);
      if (depsRes.status === 'fulfilled') setDependencies(depsRes.value);
      if (ordersRes.status === 'fulfilled') setOrders(ordersRes.value);
      if (alertsRes.status === 'fulfilled') setAlerts(alertsRes.value);
      if (reqsRes.status === 'fulfilled') setPendingApprovalsCount(reqsRes.value.length);
    } catch (err) {
      console.error('Failed to load application data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentUser) {
      loadData();
    }
  }, [currentUser]);

  const handleLoginSuccess = (user: UserAccount) => {
    setCurrentUser(user);
    if (user.approved_position === 'EMPLOYEE') {
      setCurrentTab('tasks');
    } else {
      setCurrentTab('overview');
    }
  };

  const handleLogout = async () => {
    await api.logout();
    setCurrentUser(null);
    setAuthView('login');
  };

  // If initial auth check is running
  if (authChecking) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-white text-sm">
        <div className="flex items-center space-x-3">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500"></div>
          <span>Validating session credentials...</span>
        </div>
      </div>
    );
  }

  // If not logged in, render Login or Register screen
  if (!currentUser) {
    if (authView === 'register') {
      return (
        <RegisterView
          onRegisterSuccess={() => setAuthView('login')}
          onNavigateToLogin={() => setAuthView('login')}
        />
      );
    }
    return (
      <LoginView
        onLoginSuccess={handleLoginSuccess}
        onNavigateToRegister={() => setAuthView('register')}
      />
    );
  }

  const role = currentUser.approved_position;

  return (
    <div className="min-h-screen bg-slate-100/60 font-sans text-slate-800 antialiased flex flex-col">
      <Header
        currentUser={currentUser}
        onLogout={handleLogout}
        onNavigateToProfile={() => setCurrentTab('profile')}
        openAlertsCount={alerts.filter((a) => a.status === 'OPEN').length}
      />

      <PendingApprovalBanner user={currentUser} />

      <div className="flex flex-1">
        <Sidebar
          currentTab={currentTab}
          onTabChange={setCurrentTab}
          currentRole={role}
          pendingEmailsCount={emails.filter((m) => m.processing_status === 'NEEDS_REVIEW').length}
          pendingProposalsCount={proposals.filter((p) => p.proposal_status === 'PENDING').length}
          pendingApprovalsCount={pendingApprovalsCount}
        />

        <main className="flex-1 p-6 overflow-y-auto max-w-7xl">
          {/* Overview */}
          {currentTab === 'overview' && (
            role === 'EMPLOYEE' ? (
              <AccessDeniedView
                currentRole={role}
                requiredRoles={['HOD', 'Manager', 'Administrator']}
                onNavigateHome={() => setCurrentTab('tasks')}
              />
            ) : (
              <OverviewView summary={summary} onNavigate={setCurrentTab} />
            )
          )}

          {/* Inbox */}
          {currentTab === 'inbox' && (
            role === 'EMPLOYEE' ? (
              <AccessDeniedView
                currentRole={role}
                requiredRoles={['HOD', 'Manager', 'Administrator']}
                onNavigateHome={() => setCurrentTab('tasks')}
              />
            ) : (
              <InboxView emails={emails} onRefresh={loadData} />
            )
          )}

          {/* Business Cases */}
          {currentTab === 'cases' && (
            role === 'EMPLOYEE' ? (
              <AccessDeniedView
                currentRole={role}
                requiredRoles={['HOD', 'Manager', 'Administrator']}
                onNavigateHome={() => setCurrentTab('tasks')}
              />
            ) : (
              <BusinessCasesView cases={cases} />
            )
          )}

          {/* Tasks & Proposals */}
          {currentTab === 'tasks' && (
            <TasksView
              tasks={tasks}
              proposals={proposals}
              onRefresh={loadData}
              currentRole={role}
            />
          )}

          {/* Dependencies / Workflows */}
          {currentTab === 'dependencies' && (
            <DependenciesView dependencies={dependencies} tasks={tasks} onRefresh={loadData} />
          )}

          {/* Departments & HODs */}
          {currentTab === 'departments' && (
            role === 'EMPLOYEE' ? (
              <AccessDeniedView
                currentRole={role}
                requiredRoles={['HOD', 'Manager', 'Administrator']}
                onNavigateHome={() => setCurrentTab('tasks')}
              />
            ) : (
              <DepartmentsView />
            )
          )}

          {/* Employees */}
          {currentTab === 'employees' && (
            role === 'EMPLOYEE' ? (
              <AccessDeniedView
                currentRole={role}
                requiredRoles={['HOD', 'Manager', 'Administrator']}
                onNavigateHome={() => setCurrentTab('tasks')}
              />
            ) : (
              <EmployeesView />
            )
          )}

          {/* Orders & MRP */}
          {currentTab === 'orders' && (
            role === 'EMPLOYEE' ? (
              <AccessDeniedView
                currentRole={role}
                requiredRoles={['HOD', 'Manager', 'Administrator']}
                onNavigateHome={() => setCurrentTab('tasks')}
              />
            ) : (
              <OrdersView orders={orders} />
            )
          )}

          {/* Smart Drafts */}
          {currentTab === 'drafts' && <SmartDraftsView cases={cases} />}

          {/* Microsoft Outlook Integration */}
          {currentTab === 'outlook' && <OutlookIntegrationView currentUser={currentUser} />}

          {/* Diagnostics */}
          {currentTab === 'diagnostics' && (
            role !== 'SYSADMIN' && role !== 'MANAGEMENT' ? (
              <AccessDeniedView
                currentRole={role}
                requiredRoles={['Administrator', 'Manager']}
                onNavigateHome={() => setCurrentTab('profile')}
              />
            ) : (
              <DiagnosticsView />
            )
          )}

          {/* Admin User Management */}
          {currentTab === 'admin-users' && (
            role !== 'SYSADMIN' ? (
              <AccessDeniedView
                currentRole={role}
                requiredRoles={['Administrator']}
                onNavigateHome={() => setCurrentTab('profile')}
              />
            ) : (
              <AdminUserManagementView />
            )
          )}

          {/* Profile */}
          {currentTab === 'profile' && <UserProfileView user={currentUser} />}
        </main>
      </div>
    </div>
  );
};

export default App;
