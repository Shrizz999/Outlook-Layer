import React from 'react';
import { Building, ShieldCheck, Clock, FileBadge, Lock, ShieldAlert } from 'lucide-react';
import { UserAccount } from '../types';

interface UserProfileViewProps {
  user: UserAccount;
}

export const UserProfileView: React.FC<UserProfileViewProps> = ({ user }) => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">User Profile</h2>
          <p className="text-xs text-slate-500">Your authenticated credentials and authorized operational role</p>
        </div>
        <div className="flex items-center space-x-2">
          <span
            className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${
              user.account_status === 'active'
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : user.account_status === 'pending_approval'
                ? 'bg-amber-50 text-amber-700 border-amber-200'
                : 'bg-rose-50 text-rose-700 border-rose-200'
            }`}
          >
            Status: {user.account_status.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Profile Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
          <div className="flex items-center space-x-3 pb-4 border-b border-slate-100">
            <div className="h-12 w-12 rounded-full bg-blue-100 text-blue-700 font-bold flex items-center justify-center text-lg">
              {user.full_name.charAt(0)}
            </div>
            <div>
              <div className="text-sm font-bold text-slate-900">{user.full_name}</div>
              <div className="text-xs text-slate-500">{user.email}</div>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 flex items-center">
                <Building className="w-3.5 h-3.5 mr-1.5 text-slate-400" />
                Department
              </span>
              <span className="font-semibold text-slate-800">{user.department}</span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-500 flex items-center">
                <ShieldCheck className="w-3.5 h-3.5 mr-1.5 text-slate-400" />
                Approved Role
              </span>
              <span className="font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                {user.approved_position}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-500 flex items-center">
                <FileBadge className="w-3.5 h-3.5 mr-1.5 text-slate-400" />
                Requested Role
              </span>
              <span className="font-medium text-slate-700">{user.requested_position}</span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-500 flex items-center">
                <Clock className="w-3.5 h-3.5 mr-1.5 text-slate-400" />
                Last Login
              </span>
              <span className="text-slate-600">
                {user.last_login_at ? new Date(user.last_login_at).toLocaleString() : 'First Session'}
              </span>
            </div>
          </div>
        </div>

        {/* Access & Linkage Card */}
        <div className="md:col-span-2 bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
          <div className="text-sm font-bold text-slate-900 pb-3 border-b border-slate-100 flex items-center space-x-2">
            <Lock className="w-4 h-4 text-blue-600" />
            <span>Operational Identity & RBAC Enforcement</span>
          </div>

          <div className="space-y-3 text-xs text-slate-600">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div className="font-semibold text-slate-800 mb-1">Linked Employee Record</div>
              <p className="text-slate-500">
                UUID:{' '}
                <code className="bg-slate-200 px-1 py-0.5 rounded text-[11px] text-slate-800">
                  {user.employee_id || 'Not linked'}
                </code>
              </p>
              <p className="mt-1 text-[11px] text-slate-500">
                Your login identity is bound to the company master employees record. All tasks and workflows
                assigned to your name or department are automatically synchronized.
              </p>
            </div>

            <div className="p-3 bg-blue-50/50 rounded-lg border border-blue-200 text-blue-900">
              <div className="font-semibold flex items-center space-x-1.5 mb-1">
                <ShieldAlert className="w-4 h-4 text-blue-600" />
                <span>Security Directive: Self-Escalation Prohibited</span>
              </div>
              <p className="text-[11px] text-blue-800/80 leading-relaxed">
                To prevent privilege escalation attacks, users cannot modify their own approved role or department.
                Any department reassignment or elevated permissions must be authorized by an administrator through the
                administrative approval audit log.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
