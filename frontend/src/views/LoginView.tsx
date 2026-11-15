import React, { useState } from 'react';
import { LogIn, Lock, Mail, AlertCircle, Shield, CheckCircle2, UserCheck } from 'lucide-react';
import { api } from '../api/client';
import { UserAccount } from '../types';

interface LoginViewProps {
  onLoginSuccess: (user: UserAccount) => void;
  onNavigateToRegister: () => void;
}

export const LoginView: React.FC<LoginViewProps> = ({ onLoginSuccess, onNavigateToRegister }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email || !password) {
      setError('Please provide both email address and password');
      return;
    }

    setLoading(true);
    try {
      const res = await api.login({ email, password });
      onLoginSuccess(res.user);
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const fillDemoAccount = (demoEmail: string, demoRole: string) => {
    setEmail(demoEmail);
    setPassword(demoEmail === 'admin@balbird.com' ? 'AdminSecure2026!' : 'Password123!');
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center py-12 sm:px-6 lg:px-8 font-sans">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex h-12 w-12 rounded-xl bg-blue-600 items-center justify-center text-white font-bold text-xl shadow-lg shadow-blue-500/30 mb-4">
          BI
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Balbird Intelligence</h2>
        <p className="mt-1 text-sm text-slate-400">Sign in to your authorized operational account</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-slate-800/90 border border-slate-700/80 py-8 px-6 shadow-2xl rounded-2xl sm:px-10 backdrop-blur-xl">
          {error && (
            <div className="mb-5 rounded-lg bg-rose-950/50 border border-rose-800/80 p-3.5 flex items-start space-x-2.5 text-rose-300 text-xs">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Email Address</label>
              <div className="relative rounded-lg shadow-xs">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@balbird.invalid"
                  className="block w-full pl-9 pr-3 py-2 bg-slate-900/80 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Password</label>
              <div className="relative rounded-lg shadow-xs">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="block w-full pl-9 pr-3 py-2 bg-slate-900/80 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center items-center py-2.5 px-4 border border-transparent rounded-lg text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 transition shadow-md"
            >
              {loading ? (
                <span className="flex items-center space-x-2">
                  <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                  <span>Signing in...</span>
                </span>
              ) : (
                <span className="flex items-center space-x-2">
                  <LogIn className="w-4 h-4" />
                  <span>Sign In</span>
                </span>
              )}
            </button>
          </form>

          <div className="mt-6 border-t border-slate-700/80 pt-4 text-center">
            <p className="text-xs text-slate-400">
              Don't have an account?{' '}
              <button
                type="button"
                onClick={onNavigateToRegister}
                className="font-medium text-blue-400 hover:text-blue-300 underline underline-offset-2 transition"
              >
                Register an account
              </button>
            </p>
          </div>

          {/* Quick Demo Credentials Bar */}
          <div className="mt-6 border-t border-slate-700/80 pt-4">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center">
              <UserCheck className="w-3.5 h-3.5 mr-1 text-slate-500" />
              <span>Quick Login Demo Accounts</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => fillDemoAccount('admin@balbird.com', 'Admin')}
                className="text-left px-2.5 py-1.5 rounded bg-slate-900/60 hover:bg-slate-700/60 border border-slate-700 text-slate-300 transition"
              >
                <div className="font-semibold text-blue-400">Administrator</div>
                <div className="text-[10px] text-slate-500 truncate">admin@balbird.com</div>
              </button>
              <button
                type="button"
                onClick={() => fillDemoAccount('alice.purchase@balbird.invalid', 'HOD')}
                className="text-left px-2.5 py-1.5 rounded bg-slate-900/60 hover:bg-slate-700/60 border border-slate-700 text-slate-300 transition"
              >
                <div className="font-semibold text-emerald-400">HOD (Purchase)</div>
                <div className="text-[10px] text-slate-500 truncate">alice.purchase@...</div>
              </button>
              <button
                type="button"
                onClick={() => fillDemoAccount('john.sales@balbird.invalid', 'Employee')}
                className="text-left px-2.5 py-1.5 rounded bg-slate-900/60 hover:bg-slate-700/60 border border-slate-700 text-slate-300 transition"
              >
                <div className="font-semibold text-indigo-400">Employee (Sales)</div>
                <div className="text-[10px] text-slate-500 truncate">john.sales@...</div>
              </button>
              <button
                type="button"
                onClick={() => fillDemoAccount('grace.mgmt@balbird.invalid', 'Manager')}
                className="text-left px-2.5 py-1.5 rounded bg-slate-900/60 hover:bg-slate-700/60 border border-slate-700 text-slate-300 transition"
              >
                <div className="font-semibold text-amber-400">Manager</div>
                <div className="text-[10px] text-slate-500 truncate">grace.mgmt@...</div>
              </button>
            </div>
          </div>
        </div>

        <div className="mt-4 text-center text-xs text-slate-500 flex items-center justify-center space-x-1.5">
          <Shield className="w-3.5 h-3.5 text-slate-600" />
          <span>Internal system. Passwords hashed with bcrypt. Secure sessions enforced.</span>
        </div>
      </div>
    </div>
  );
};
