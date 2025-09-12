import React from 'react';

const About = () => (
  <div className="max-w-4xl mx-auto p-8 text-center">
    <img
      src="/headshot.jpg"
      alt="Kevin Delong"
      className="w-40 h-40 rounded-full mx-auto mb-6 border-4 border-primary"
    />
    <h1 className="text-4xl font-bold mb-4">Kevin Douglas Delong</h1>
    <p className="text-lg prose dark:prose-invert mx-auto">
      I'm a Software Engineer with expertise in backend and frontend development for web, mobile, and desktop applications. 
      Explore my projects or contact me to discuss your next idea!
    </p>
  </div>
);

export default About;
