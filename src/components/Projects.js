import React from 'react';

const projects = [
  {
    id: 1,
    title: 'E-Commerce Backend API',
    demoUrl: 'https://ecommerce-demo.kevindouglasdelong.net',
    repoUrl: 'https://github.com/yourusername/ecommerce-api', // Private repo
    description: 'A scalable Node.js/Express API with MongoDB for e-commerce platforms, featuring cart and payment integration. [Add details about your project here.]',
    screenshot: '/screenshots/ecommerce.png',
  },
  {
    id: 2,
    title: 'Mobile Fitness Tracker',
    demoUrl: 'https://expo.dev/@yourusername/fitness-app',
    repoUrl: 'https://github.com/yourusername/fitness-app', // Private repo
    description: 'React Native app with real-time fitness tracking and Firebase authentication. [Add details about your project here.]',
    screenshot: '/screenshots/fitness.png',
  },
  {
    id: 3,
    title: 'Desktop Task Manager',
    demoUrl: 'https://taskmanager-demo.kevindouglasdelong.net',
    repoUrl: 'https://github.com/yourusername/task-manager', // Private repo
    description: 'Electron-based desktop app for task management with local storage. [Add details about your project here.]',
    screenshot: '/screenshots/taskmanager.png',
  },
];

const Projects = () => {
  const handleRequestAccess = async (projectId) => {
    try {
      // Replace with your backend URL (e.g., Heroku) or email for manual approval
      const response = await fetch('https://your-backend.herokuapp.com/request-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectId, email: 'client@example.com' }), // Add form for email input later
      });
      const data = await response.json();
      alert(data.message || 'Access request sent! I’ll review and respond soon.');
    } catch (error) {
      alert('Error sending request. Please try again.');
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">Featured Projects</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {projects.map((project) => (
          <div key={project.id} className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
            <img
              src={project.screenshot}
              alt={project.title}
              className="w-full h-48 object-cover rounded mb-4"
            />
            <h2 className="text-xl font-semibold mb-2">{project.title}</h2>
            <p className="text-gray-600 dark:text-gray-400 mb-4 prose dark:prose-invert">{project.description}</p>
            <iframe
              src={project.demoUrl}
              title={project.title}
              className="w-full h-64 border-0 rounded mb-4"
              sandbox="allow-scripts allow-same-origin"
            />
            <button
              onClick={() => handleRequestAccess(project.id)}
              className="bg-primary text-white px-4 py-2 rounded hover:bg-blue-700 transition"
            >
              Request Source Code Access
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Projects;