import React from 'react';
import { ShieldCheck, UserCheck, Bell, Activity } from 'lucide-react';
import { BIRole } from '../types';

interface HeaderProps {
  currentRole: BIRole;
  onRoleChange: (role: BIRole) => void;
  openAlertsCount: number;
}

export const Header: React.FC<HeaderProps> = ({ currentRole, onRoleChange, openAlertsCount }) => {
  return (
    <header className="h-16 border-b border-slate-200 bg-white px-6 flex items-center justify-between sticky top-0 z-20 shadow-sm">
      <div className="flex items-center space-x-3">
        <div className="h-9 w-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold tracking-wider shadow-sm">
          BI
        </div>
        <div>
          <h1 className="text-base font-semibold text-slate-900 leading-tight">Balbird Intelligence</h1>
          <p className="text-xs text-slate-500">Business Coordination & Task Monitoring Layer</p>
        </div>
      </div>

      <div className="flex items-center space-x-5">
        {/* Safe Mode Badge */}
        <div className="flex items-center text-xs font-medium text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
          <ShieldCheck className="w-3.5 h-3.5 mr-1" />
          <span>Additive Mode Active (Schema Protected)</span>
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

        {/* Role Selector */}
        <div className="flex items-center space-x-2 pl-2 border-l border-slate-200">
          <UserCheck className="w-4 h-4 text-slate-400" />
          <span className="text-xs text-slate-500 font-medium">Role:</span>
          <select
            value={currentRole}
            onChange={(e) => onRoleChange(e.target.value as BIRole)}
            className="text-xs font-semibold bg-slate-50 border border-slate-300 rounded-md px-2.5 py-1.5 text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="MANAGEMENT">Management (Cross-Dept)</option>
            <option value="DEPT_HEAD">Department Head</option>
            <option value="TEAM_LEADER">Team Leader</option>
            <option value="EMPLOYEE">Employee</option>
            <option value="SYSADMIN">System Admin</option>
          </select>
        </div>
      </div>
    </header>
  );
};
