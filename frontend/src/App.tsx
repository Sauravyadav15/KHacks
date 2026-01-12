import React, { useState, useRef, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';

const API_BASE_URL = 'http://127.0.0.1:8000';

const LoginForm = ({ onClose, onSubmit }: { onClose: () => void; onSubmit: (username: string, password: string, rememberMe: boolean) => void }) => {
  const modalRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (modalRef.current) {
      modalRef.current.showModal();
    }
  }, []);

  return (
    <dialog ref={modalRef} className="modal" onClose={onClose}>
      <div className="modal-box">
        <button type="button" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={onClose}>✕</button>
        <h3 className="font-bold text-lg mb-6 text-center">Login</h3>
        <form onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const username = (form.elements.namedItem('username') as HTMLInputElement).value;
          const password = (form.elements.namedItem('password') as HTMLInputElement).value;
          const rememberMe = (form.elements.namedItem('rememberMe') as HTMLInputElement).checked;
          onSubmit(username, password, rememberMe);
        }}>
          <div className="space-y-4">
            <input name="username" type="text" placeholder="Username" className="input input-bordered w-full" required />
            <input name="password" type="password" placeholder="Password" className="input input-bordered w-full" required />
            
            <div className="form-control">
              <label className="label cursor-pointer justify-start gap-4">
                {/* 
                   Fix: Added 'border-opacity-100' and 'border-gray-400' to ensure visibility 
                   even if DaisyUI defaults are overridden. 
                */}
                <input 
                  type="checkbox" 
                  name="rememberMe" 
                  className="checkbox checkbox-primary border-2 border-base-content/20" 
                />
                <span className="label-text">Remember me</span>
              </label>
            </div>

            <button type="submit" className="btn btn-primary w-full">Sign In</button>
          </div>
        </form>
      </div>
    </dialog>
  );
};

const RegisterForm = ({ onClose, onSubmit }: { onClose: () => void; onSubmit: (formData: FormData) => void }) => {
  const modalRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (modalRef.current) {
      modalRef.current.showModal();
    }
  }, []);

  return (
    <dialog ref={modalRef} className="modal" onClose={onClose}>
      <div className="modal-box">
        <button type="button" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={onClose}>✕</button>
        <h3 className="font-bold text-lg mb-6 text-center">Register</h3>
        <form onSubmit={(e) => {
          e.preventDefault();
          const formData = new FormData(e.currentTarget);
          onSubmit(formData);
        }}>
          <div className="space-y-4">
            <input name="username" type="text" placeholder="Username" className="input input-bordered w-full" required />
            <input name="full_name" type="text" placeholder="Full Name" className="input input-bordered w-full" required />
            <input name="email" type="email" placeholder="Email" className="input input-bordered w-full" required />
            <input name="password" type="password" placeholder="Password" className="input input-bordered w-full" required />
            <select name="account_type" className="select select-bordered w-full" required>
              <option value="student">Student</option>
              <option value="teacher">Teacher</option>
            </select>
            <button type="submit" className="btn btn-success w-full">Create Account</button>
          </div>
        </form>
      </div>
    </dialog>
  );
};

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const currentTab = location.pathname === '/teacher' ? 'teacher' : 'student';
  
  // Check both localStorage (persistent) and sessionStorage (temporary)
  const [isLoggedIn, setIsLoggedIn] = useState(
    !!localStorage.getItem('access_token') || !!sessionStorage.getItem('access_token')
  );
  const [showLogin, setShowLogin] = useState(false);
  const [showRegister, setShowRegister] = useState(false);
  const [loading, setLoading] = useState(false);

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
        
        // Store based on "Remember Me" preference
        if (rememberMe) {
          localStorage.setItem('access_token', token.access_token);
        } else {
          sessionStorage.setItem('access_token', token.access_token);
        }

        setIsLoggedIn(true);
        setShowLogin(false);
        alert('Login successful!');
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Login failed' }));
        alert('Login failed: ' + (errorData.detail || 'Invalid credentials'));
      }
    } catch (error) {
      alert('Login error: Server unreachable or network issue.');
    }
    setLoading(false);
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
        setShowRegister(false);
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
    }
    setLoading(false);
  };

  const handleLogout = () => {
    // Clear both storages to ensure complete logout
    localStorage.removeItem('access_token');
    sessionStorage.removeItem('access_token');
    setIsLoggedIn(false);
    navigate('/');
    
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  };

  return (
    <div className="min-h-screen bg-base-200">
      <div className="navbar bg-base-100 shadow-lg">
        <div className="navbar-start">
          <div className="tabs tabs-boxed mx-4">
            <a className={`tab ${currentTab === 'teacher' ? 'tab-active' : ''}`} onClick={() => navigate('/teacher')}>
              Teacher
            </a>
            <a className={`tab ${currentTab === 'student' ? 'tab-active' : ''}`} onClick={() => navigate('/student')}>
              Student
            </a>
          </div>
        </div>
        
        <div className="navbar-end mr-4 space-x-2">
          {isLoggedIn ? (
            <div className="dropdown dropdown-end">
              <div tabIndex={0} role="button" className="btn btn-ghost btn-circle avatar placeholder">
                <div className="bg-neutral text-neutral-content rounded-full w-10">
                  <span className="text-xl">U</span>
                </div>
              </div>
              <ul tabIndex={0} className="mt-3 z-[1] p-2 shadow menu menu-sm dropdown-content bg-base-100 rounded-box w-52">
                <li><a>Profile</a></li>
                <li><a>Settings</a></li>
                <li><a onClick={handleLogout} className="text-error">Logout</a></li>
              </ul>
            </div>
          ) : (
            <>
              <button className="btn btn-primary btn-sm" onClick={() => setShowLogin(true)} disabled={loading}>
                Login
              </button>
              <button className="btn btn-success btn-sm" onClick={() => setShowRegister(true)} disabled={loading}>
                Register
              </button>
            </>
          )}
        </div>
      </div>

      <main className="p-6">
        <Outlet />
      </main>

      {showLogin && <LoginForm onClose={() => setShowLogin(false)} onSubmit={handleLogin} />}
      {showRegister && <RegisterForm onClose={() => setShowRegister(false)} onSubmit={handleRegister} />}
    </div>
  );
};

export default App;
