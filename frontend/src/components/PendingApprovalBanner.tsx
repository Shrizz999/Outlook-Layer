import React from 'react';
import { Clock, ShieldAlert } from 'lucide-react';
import { UserAccount } from '../types';

interface PendingApprovalBannerProps {
  user: UserAccount;
}

export const PendingApprovalBanner: React.FC<PendingApprovalBannerProps> = ({ user }) => {
  if (user.account_status !== 'pending_approval') {
    return null;
  }

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-6 py-2.5 flex items-center justify-between text-amber-900 text-xs">
      <div className="flex items-center space-x-2.5">
        <Clock className="w-4 h-4 text-amber-600 flex-shrink-0" />
        <div>
          <span className="font-semibold">Role Approval Pending:</span> You requested the{' '}
          <span className="font-semibold px-1.5 py-0.5 rounded bg-amber-200 text-amber-950">
            {user.requested_position}
          </span>{' '}
          position in <span className="font-semibold">{user.department}</span>. An administrator must review and approve this
          request. You currently have standard <span className="font-semibold">Employee</span> permissions.
        </div>
      </div>
      <div className="hidden sm:flex items-center space-x-1 text-[11px] text-amber-700 font-medium bg-amber-100 px-2 py-0.5 rounded-full border border-amber-300">
        <ShieldAlert className="w-3.5 h-3.5 mr-1 text-amber-600" />
        <span>Restricted Active State</span>
      </div>
    </div>
  );
};
