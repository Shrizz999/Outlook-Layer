import React from 'react';
import { ShieldCheck, Bell, LogOut, Building2 } from 'lucide-react';
import { UserAccount } from '../types';

interface HeaderProps {
  currentUser: UserAccount | null;
  onLogout: () => void;
  onNavigateToProfile: () => void;
  openAlertsCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  currentUser,
  onLogout,
  onNavigateToProfile,
  openAlertsCount,
}) => {
  return (
    <header className="h-16 border-b border-slate-200 bg-white px-6 flex items-center justify-between sticky top-0 z-20 shadow-xs">
      <div className="flex items-center space-x-3">
        <div className="h-9 w-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold tracking-wider shadow-sm">
          BI
        </div>
        <div>
          <h1 className="text-base font-semibold text-slate-900 leading-tight">Balbird Intelligence</h1>
          <p className="text-xs text-slate-500">Business Coordination & Task Monitoring Layer</p>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {/* Safe Mode Badge */}
        <div className="hidden lg:flex items-center text-xs font-medium text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
          <ShieldCheck className="w-3.5 h-3.5 mr-1" />
          <span>RBAC Protected</span>
        </div>

        {/* Alerts Pill */}
        <div className="relative">
          <button className="flex items-center text-xs text-slate-600 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200 transition">
            <Bell className="w-4 h-4 mr-1.5 text-slate-500" />
            <span>Alerts</span>
            {openAlertsCount > 0 && (
              <span className="ml-1.5 bg-rose-600 text-white font-semibold text-[10px] px-1.5 py-0.2 rounded-full">
                {openAlertsCount}
              </span>
            )}
          </button>
        </div>

        {/* Authenticated User Profile Pill */}
        {currentUser && (
          <div className="flex items-center space-x-3 pl-3 border-l border-slate-200">
            <button
              onClick={onNavigateToProfile}
              className="flex items-center space-x-2 p-1.5 rounded-lg hover:bg-slate-100 transition text-left group"
              title="View your profile"
            >
              <div className="h-8 w-8 rounded-full bg-blue-600 text-white font-bold flex items-center justify-center text-xs shadow-xs group-hover:bg-blue-500">
                {currentUser.full_name.charAt(0)}
              </div>
              <div className="hidden sm:block">
                <div className="text-xs font-bold text-slate-800 leading-tight flex items-center space-x-1">
                  <span>{currentUser.full_name}</span>
                  <span
                    className={`text-[10px] font-semibold px-1.5 py-0.2 rounded ${
                      currentUser.approved_position === 'SYSADMIN'
                        ? 'bg-purple-100 text-purple-800'
                        : currentUser.approved_position === 'MANAGEMENT'
                        ? 'bg-amber-100 text-amber-800'
                        : currentUser.approved_position === 'DEPT_HEAD'
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-blue-100 text-blue-800'
                    }`}
                  >
                    {currentUser.approved_position}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 flex items-center space-x-1">
                  <Building2 className="w-3 h-3 text-slate-400" />
                  <span>{currentUser.department}</span>
                </div>
              </div>
            </button>

            {/* Logout Button */}
            <button
              onClick={onLogout}
              className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 border border-transparent hover:border-rose-200 transition"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
