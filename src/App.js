import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import About from './components/About';
import Projects from './components/Projects';
import Contact from './components/Contact';
import Resume from './components/Resume';

function App() {
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    const isDark = localStorage.getItem('darkMode') === 'true';
    setDarkMode(isDark);
    document.documentElement.classList.toggle('dark', isDark);
  }, []);

  const toggleDarkMode = () => {
    const newDarkMode = !darkMode;
    setDarkMode(newDarkMode);
    localStorage.setItem('darkMode', newDarkMode);
    document.documentElement.classList.toggle('dark', newDarkMode);
  };

  return (
    <Router>
      <div className="min-h-screen">
        <nav className="bg-white dark:bg-gray-800 shadow-lg fixed w-full top-0 z-10">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex justify-between items-center py-4">
          <div className="text-xl font-bold text-gray-900 dark:text-white">Kevin D. Delong | Software Engineer</div>
            <ul className="flex space-x-4 sm:space-x-8">
              <li>
                <NavLink
                  to="/"
                  className={({ isActive }) =>
                    isActive
                      ? "text-primary font-semibold"
                      : "text-gray-700 dark:text-gray-300 hover:text-primary"
                  }
                >
                  About Me
                </NavLink>
              </li>
              <li>
                <NavLink
                  to="/projects"
                  className={({ isActive }) =>
                    isActive
                      ? "text-primary font-semibold"
                      : "text-gray-700 dark:text-gray-300 hover:text-primary"
                  }
                >
                  Projects
                </NavLink>
              </li>
              <li>
                <NavLink
                  to="/contact"
                  className={({ isActive }) =>
                    isActive
                      ? "text-primary font-semibold"
                      : "text-gray-700 dark:text-gray-300 hover:text-primary"
                  }
                >
                  Contact Me
                </NavLink>
              </li>
              <li>
                <NavLink
                  to="/resume"
                  className={({ isActive }) =>
                    isActive
                      ? "text-primary font-semibold"
                      : "text-gray-700 dark:text-gray-300 hover:text-primary"
                  }
                >
                  Resume
                </NavLink>
              </li>
            </ul>
            <button
              onClick={toggleDarkMode}
              className="p-2 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200"
              aria-label="Toggle dark mode"
            >
              {darkMode ? '☀️' : '🌙'}
            </button>
          </div>
        </nav>
        <div className="pt-20">
          <Routes>
            <Route path="/" element={<About />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/contact" element={<Contact />} />
            <Route path="/resume" element={<Resume />} />
          </Routes>
        </div>
        <div className="fixed bottom-4 right-4">
          <a
            href="https://www.paypal.com/donate?hosted_button_id=YOUR_PAYPAL_BUTTON_ID"
            target="_blank"
            rel="noopener noreferrer"
            className="bg-primary text-white px-4 py-2 rounded-lg shadow hover:bg-blue-700 transition"
          >
            Support My Projects
          </a>
        </div>
      </div>
    </Router>
  );
}

export default App;
