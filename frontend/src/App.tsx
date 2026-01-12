import React, { useState, useRef, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';

const API_BASE_URL = 'http://127.0.0.1:8000';

// Define the shape of the context we'll pass down
export interface ChatContextType {
  chatLog: any[];
  setChatLog: React.Dispatch<React.SetStateAction<any[]>>;
  threadId: string | null;
  setThreadId: React.Dispatch<React.SetStateAction<string | null>>;
  conversationId: number | null;
  setConversationId: React.Dispatch<React.SetStateAction<number | null>>;
}

interface DevAccount {
  id: number;
  username: string;
  full_name: string;
  account_type: 'student' | 'teacher';
}

const AuthModal = ({ 
  isOpen, 
  onClose, 
  initialMode = 'login',
  onLogin, 
  onRegister 
}: { 
  isOpen: boolean; 
  onClose: () => void; 
  initialMode?: 'login' | 'register';
  onLogin: (u: string, p: string, r: boolean) => void;
  onRegister: (f: FormData) => void;
}) => {
  const [mode, setMode] = useState<'login' | 'register'>(initialMode);
  const modalRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (isOpen && modalRef.current) {
      modalRef.current.showModal();
      setMode(initialMode);
    } else if (!isOpen && modalRef.current) {
      modalRef.current.close();
    }
  }, [isOpen, initialMode]);

  const toggleMode = () => setMode(mode === 'login' ? 'register' : 'login');

  return (
    <dialog ref={modalRef} className="modal modal-bottom sm:modal-middle backdrop-blur-sm">
      <div className="modal-box p-0 overflow-hidden bg-base-100 shadow-xl border border-base-200 max-w-sm w-full">
        {/* Cleaner Header - Removed heavy background color */}
        <div className="p-8 pb-4 text-center">
          <div className="w-12 h-12 bg-primary/10 text-primary rounded-xl flex items-center justify-center mx-auto mb-4 text-2xl">
             {mode === 'login' ? '🔐' : '🚀'}
          </div>
          <h2 className="text-2xl font-bold mb-1 text-base-content">
            {mode === 'login' ? 'Welcome back' : 'Create an account'}
          </h2>
          <p className="text-base-content/60 text-sm">
            {mode === 'login' ? 'Enter your details to access your account' : 'Start your learning adventure today'}
          </p>
        </div>

        <div className="px-8 pb-8">
          {mode === 'login' ? (
            <form onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const u = (form.elements.namedItem('username') as HTMLInputElement).value;
              const p = (form.elements.namedItem('password') as HTMLInputElement).value;
              const r = (form.elements.namedItem('rememberMe') as HTMLInputElement).checked;
              onLogin(u, p, r);
            }} className="flex flex-col gap-3">
              
              <div className="form-control">
                <input name="username" type="text" className="input input-bordered w-full bg-base-200/50 focus:bg-base-100 transition-all" placeholder="Username" required />
              </div>

              <div className="form-control">
                <input name="password" type="password" className="input input-bordered w-full bg-base-200/50 focus:bg-base-100 transition-all" placeholder="Password" required />
                <label className="label cursor-pointer justify-start gap-2 mt-1">
                  <input name="rememberMe" type="checkbox" className="checkbox checkbox-xs checkbox-primary rounded-md" />
                  <span className="label-text text-xs text-base-content/70">Keep me logged in</span>
                </label>
              </div>

              <button className="btn btn-primary w-full mt-2 no-animation">Sign In</button>
            </form>
          ) : (
            <form onSubmit={(e) => {
              e.preventDefault();
              const formData = new FormData(e.currentTarget);
              onRegister(formData);
            }} className="flex flex-col gap-3">
              
              <div className="form-control">
                <input name="username" type="text" className="input input-bordered input-sm w-full bg-base-200/50 focus:bg-base-100" placeholder="Username" required />
              </div>
              
              <div className="form-control">
                <input name="full_name" type="text" className="input input-bordered input-sm w-full bg-base-200/50 focus:bg-base-100" placeholder="Full Name" required />
              </div>

              <div className="form-control">
                <input name="email" type="email" className="input input-bordered input-sm w-full bg-base-200/50 focus:bg-base-100" placeholder="Email address" required />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="form-control">
                    <input name="password" type="password" className="input input-bordered input-sm w-full bg-base-200/50 focus:bg-base-100" placeholder="Password" required />
                </div>
                <div className="form-control">
                    <select name="account_type" className="select select-bordered select-sm w-full bg-base-200/50 focus:bg-base-100">
                    <option value="student">Student</option>
                    <option value="teacher">Teacher</option>
                    </select>
                </div>
              </div>
              
              <button className="btn btn-primary w-full mt-4 no-animation">Create Account</button>
            </form>
          )}

          {/* Clean Toggle Section */}
          <div className="mt-6 text-center text-sm">
            {mode === 'login' ? (
              <p className="text-base-content/60">
                New here? <button onClick={toggleMode} className="text-primary font-semibold hover:underline">Create an account</button>
              </p>
            ) : (
              <p className="text-base-content/60">
                Already have an account? <button onClick={toggleMode} className="text-primary font-semibold hover:underline">Log in</button>
              </p>
            )}
          </div>
        </div>
      </div>
      <form method="dialog" className="modal-backdrop bg-base-300/50">
        <button onClick={onClose}>close</button>
      </form>
    </dialog>
  );
};

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const currentTab = location.pathname === '/teacher' ? 'teacher' : 'student';

  const [isLoggedIn, setIsLoggedIn] = useState(
    !!localStorage.getItem('access_token') || !!sessionStorage.getItem('access_token')
  );
  
  // Single Modal State
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  
  const [loading, setLoading] = useState(false);
  const [devAccounts, setDevAccounts] = useState<DevAccount[]>([]);

  // Persistent Chat State
  const [chatLog, setChatLog] = useState<any[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);

  useEffect(() => {
    fetchDevAccounts();
  }, []);

  const fetchDevAccounts = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/accounts/dev/all`);
      if (response.ok) {
        const data = await response.json();
        setDevAccounts(data.accounts);
      }
    } catch (error) {
      console.error('Failed to fetch dev accounts:', error);
    }
  };

  const openLogin = () => {
    setAuthMode('login');
    setAuthModalOpen(true);
  };

  const openRegister = () => {
    setAuthMode('register');
    setAuthModalOpen(true);
  };

  const handleDevSwitch = async (username: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/accounts/dev/switch/${username}`, {
        method: 'POST',
      });
      if (response.ok) {
        const token = await response.json();
        localStorage.setItem('access_token', token.access_token);
        sessionStorage.removeItem('access_token');
        setIsLoggedIn(true);
        window.location.reload(); 
      }
    } catch (error) {
      console.error('Failed to switch account:', error);
    }
  };

  const handleLogin = async (username: string, password: string, rememberMe: boolean) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/accounts/signin/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username, password }),
      });

      if (response.ok) {
        const token = await response.json();
        if (rememberMe) {
          localStorage.setItem('access_token', token.access_token);
        } else {
          sessionStorage.setItem('access_token', token.access_token);
        }
        setIsLoggedIn(true);
        setAuthModalOpen(false); // Close modal
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Login failed' }));
        alert('Login failed: ' + (errorData.detail || 'Invalid credentials'));
      }
    } catch (error) {
      alert('Login error: Server unreachable or network issue.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (formData: FormData) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/accounts/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: formData.get('username'),
          full_name: formData.get('full_name'),
          email: formData.get('email'),
          password: formData.get('password'),
          account_type: formData.get('account_type'),
        }),
      });

      if (response.ok) {
        const result = await response.json();
        // Switch to login mode automatically after success
        setAuthMode('login');
        alert(result.message || 'Registration successful! Please login.');
      } else {
        try {
          const error = await response.json();
          alert('Registration failed: ' + (error.detail || 'Unknown error'));
        } catch {
          alert('Registration failed: Server error');
        }
      }
    } catch (error) {
      alert('Registration error: Server unreachable.');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    sessionStorage.removeItem('access_token');
    setIsLoggedIn(false);
    
    // Clear chat state
    setChatLog([]);
    setThreadId(null);
    setConversationId(null);

    navigate('/');
  };

  return (
    <div className="h-screen flex flex-col bg-base-100 text-base-content font-sans">
      {/* Header */}
      <div className="navbar bg-base-100 border-b border-base-200 px-4">
        <div className="flex-1">
          <a className="btn btn-ghost normal-case text-xl text-primary font-bold tracking-tight gap-2">
            <span className="text-2xl">📚</span> StoryTeller AI
          </a>
          
          {/* Custom Toggle Switch */}
          <div className="join bg-base-200 p-1 rounded-full ml-6 hidden sm:flex border border-base-300">
            <button 
              className={`join-item btn btn-sm btn-ghost rounded-full px-6 transition-all duration-200 hover:bg-white/50 ${currentTab === 'teacher' ? 'bg-white shadow-sm text-primary font-bold' : 'text-base-content/70 font-medium'}`}
              onClick={() => navigate('/teacher')}
            >
              Teacher
            </button>
            <button 
              className={`join-item btn btn-sm btn-ghost rounded-full px-6 transition-all duration-200 hover:bg-white/50 ${currentTab === 'student' ? 'bg-white shadow-sm text-primary font-bold' : 'text-base-content/70 font-medium'}`}
              onClick={() => navigate('/student')}
            >
              Student
            </button>
          </div>
        </div>

        <div className="flex-none gap-3">
          {/* Dev Switcher */}
           <div className="dropdown dropdown-end hidden md:block">
            <label tabIndex={0} className="btn btn-ghost btn-xs text-info font-normal">DEV TOOLS</label>
            <ul tabIndex={0} className="dropdown-content z-[20] menu p-2 shadow-lg bg-base-100 rounded-box w-60 border border-base-200">
              <li className="menu-title px-2 py-1 text-xs opacity-50 uppercase font-bold tracking-wider">Quick Switch</li>
              {devAccounts.length === 0 ? (
                <li className="disabled"><a>No accounts found</a></li>
              ) : (
                devAccounts.map((account) => (
                  <li key={account.id}>
                    <a onClick={() => handleDevSwitch(account.username)} className="flex justify-between items-center py-2">
                      <div className="flex flex-col">
                         <span className="font-medium text-xs">{account.full_name}</span>
                         <span className="text-[10px] opacity-50">{account.username}</span>
                      </div>
                      <span className={`badge badge-xs ${account.account_type === 'teacher' ? 'badge-secondary' : 'badge-primary'}`}>
                        {account.account_type === 'teacher' ? 'Teacher' : 'Student'}
                      </span>
                    </a>
                  </li>
                ))
              )}
            </ul>
          </div>

          {isLoggedIn ? (
            <div className="dropdown dropdown-end">
              <label tabIndex={0} className="btn btn-ghost btn-circle avatar placeholder ring ring-primary ring-offset-base-100 ring-offset-2 w-9 h-9">
                <div className="bg-neutral text-neutral-content rounded-full w-full">
                  <span className="text-xs">U</span>
                </div>
              </label>
              <ul tabIndex={0} className="mt-3 z-[20] p-2 shadow-xl menu menu-sm dropdown-content bg-base-100 rounded-box w-52 border border-base-200">
                <li><a>Profile</a></li>
                <li><a>Settings</a></li>
                <div className="divider my-1"></div>
                <li><a onClick={handleLogout} className="text-error">Logout</a></li>
              </ul>
            </div>
          ) : (
            <div className="flex gap-2">
              <button 
                className="btn btn-ghost btn-sm font-normal hover:bg-base-200" 
                onClick={openLogin} 
                disabled={loading}
              >
                Log in
              </button>
              <button 
                className="btn btn-primary btn-sm px-4 shadow-sm font-medium" 
                onClick={openRegister} 
                disabled={loading}
              >
                Sign up
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Unified Auth Modal */}
      <AuthModal 
        isOpen={authModalOpen} 
        onClose={() => setAuthModalOpen(false)}
        initialMode={authMode}
        onLogin={handleLogin}
        onRegister={handleRegister}
      />

      <div className="flex-1 overflow-hidden relative bg-base-50">
        <Outlet context={{ 
          chatLog, setChatLog, 
          threadId, setThreadId, 
          conversationId, setConversationId 
        }} />
      </div>
    </div>
  );
};

export default App;
