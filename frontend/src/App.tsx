import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const currentTab = location.pathname === '/teacher' ? 'teacher' : 'student';

  return (
    <div className="min-h-screen bg-base-200">
      <div className="navbar bg-base-100 shadow-lg">
        <div className="flex-1">
          <a className="btn btn-ghost text-xl">KingHacks: Storyteller Test Bench</a>
        </div>
      </div>

      <div className="container mx-auto p-6">
        <div role="tablist" className="tabs tabs-boxed mb-6 max-w-md mx-auto">
          <a
            role="tab"
            className={`tab ${currentTab === 'student' ? 'tab-active' : ''}`}
            onClick={() => navigate('/student')}
          >
            Student
          </a>
          <a
            role="tab"
            className={`tab ${currentTab === 'teacher' ? 'tab-active' : ''}`}
            onClick={() => navigate('/teacher')}
          >
            Teacher
          </a>
        </div>

        <Outlet />
      </div>
    </div>
  );
};

export default App;
