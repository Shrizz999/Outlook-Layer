import React from 'react';
import { ShieldX, ArrowLeft } from 'lucide-react';
import { BIRole } from '../types';

interface AccessDeniedViewProps {
  currentRole: BIRole;
  requiredRoles: string[];
  onNavigateHome: () => void;
}

export const AccessDeniedView: React.FC<AccessDeniedViewProps> = ({ currentRole, requiredRoles, onNavigateHome }) => {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center p-6">
      <div className="h-16 w-16 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mb-4 shadow-xs">
        <ShieldX className="w-8 h-8" />
      </div>
      <h2 className="text-xl font-bold text-slate-900 mb-2">Access Restricted</h2>
      <p className="text-sm text-slate-500 max-w-md mb-6 leading-relaxed">
        Your current approved role is <strong className="text-slate-800">{currentRole}</strong>. This operational section requires{' '}
        <strong className="text-slate-800">{requiredRoles.join(' or ')}</strong> authorization.
      </p>
      <button
        onClick={onNavigateHome}
        className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg shadow-sm transition space-x-2"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Return to Authorized Dashboard</span>
      </button>
    </div>
  );
};
