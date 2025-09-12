import React from 'react';

const Resume = () => {
  return (
    <div className="min-h-screen bg-gray-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto bg-white shadow-lg rounded-lg p-8">
        {/* Resume Section */}
        <section className="mb-12">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">Kevin Douglas DeLong</h1>
          <p className="text-gray-600">
            Fenton, MI 48430 | (810) 287-7409 | delong.kevin@gmail.com |{' '}
            <a href="#" className="text-blue-600 hover:underline">[LinkedIn/GitHub Portfolio]</a>
          </p>

          <h2 className="text-2xl font-semibold text-gray-800 mt-8 mb-4 border-b-2 border-gray-200 pb-2">
            Professional Summary
          </h2>
          <p className="text-gray-700 leading-relaxed">
            Results-oriented Software Engineer with 10+ years in automotive infotainment systems, specializing in backend automation, frontend UI development, and full-stack integration for web, mobile, and embedded applications. Proven track record in C++, Python, and AutoSAR architecture, collaborating on CI/CD pipelines to deliver high-quality, secure software. Excel at debugging complex SOC/IOC issues, fuzz testing protocols (CAN/Ethernet), and leading cross-functional teams to exceed milestones—reducing defects by 25% through optimized test automation. Eager to drive innovative solutions in scalable software environments.
          </p>

          <h2 className="text-2xl font-semibold text-gray-800 mt-8 mb-4 border-b-2 border-gray-200 pb-2">
            Technical Skills
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h3 className="text-lg font-medium text-gray-700">Languages & Frameworks</h3>
              <ul className="list-disc pl-5 text-gray-600">
                <li>C, C++, Python, Visual Basic, Android (mobile app development)</li>
                <li>AutoSAR RTE architecture for real-time embedded systems</li>
              </ul>
            </div>
            <div>
              <h3 className="text-lg font-medium text-gray-700">Tools & Protocols</h3>
              <ul className="list-disc pl-5 text-gray-600">
                <li>CANoe 9, Vector hardware/tools for simulation and automation</li>
                <li>CAN/CAN-FD/Ethernet bus; TCP/UDP; Wireshark, ZenMap for network analysis</li>
                <li>Fuzz testing (BT, Wi-Fi, Ethernet, CAN-bus)</li>
              </ul>
            </div>
            <div>
              <h3 className="text-lg font-medium text-gray-700">Domains & Methodologies</h3>
              <ul className="list-disc pl-5 text-gray-600">
                <li>ADAS, telematics (OTA updates), camera CVPM systems</li>
                <li>CI/CD, automation scripting, Agile/Scrum; ISTQB-certified QA practices</li>
                <li>Backend: SOC/IOC defect resolution; Frontend: CANoe UI for feature simulation</li>
              </ul>
            </div>
          </div>

          <h2 className="text-2xl font-semibold text-gray-800 mt-8 mb-4 border-b-2 border-gray-200 pb-2">
            Professional Experience
          </h2>
          <div className="mb-6">
            <h3 className="text-xl font-medium text-gray-800">
              Software Testing Lead (Software Engineer Focus)
            </h3>
            <p className="text-gray-600 italic">Harman International Industries Inc., Novi, MI | January 2018 – Present</p>
            <ul className="list-disc pl-5 text-gray-600 mt-2">
              <li>Collaborated with development teams to resolve defects in AutoSAR implementations on SOC/IOC, accelerating deployment cycles by 15% through automated scripting in Python and C++.</li>
              <li>Led test case optimization and configuration management, ensuring 100% milestone compliance and reducing post-release bugs by 25% via CI/CD integration.</li>
              <li>Coordinated multi-team efforts to enhance automation tools, improving testing efficiency for infotainment systems (radio/UI interfaces) across 50+ vehicle ECUs.</li>
              <li>Trained 20+ new hires on hardware/software schematics, Vector tools, and AutoSAR real-time environments, fostering a culture of best-in-class engineering practices.</li>
              <li>Conducted fuzz testing and security audits (DoS, firewall permissions), identifying vulnerabilities in Ethernet/CAN-bus protocols to bolster system security.</li>
            </ul>
          </div>
          <div className="mb-6">
            <h3 className="text-xl font-medium text-gray-800">Software Test Engineer</h3>
            <p className="text-gray-600 italic">Harman International Industries Inc., Novi, MI | January 2013 – January 2018</p>
            <ul className="list-disc pl-5 text-gray-600 mt-2">
              <li>Developed and debugged automation test scripts using Vector tools and CANoe 9, simulating vehicle ECUs and validating customer requirements—cutting manual testing time by 40%.</li>
              <li>Designed user interfaces in CANoe for CAN-bus key feature simulation, supporting frontend-backend integration for mobile-connected infotainment apps.</li>
              <li>Performed on-site customer ride-and-drives, gathering/analyzing data to refine software models and ensure seamless OTA telematics functionality.</li>
              <li>Wrote optimized test cases for manual and automated validation, contributing to zero-defect deliveries in ADAS and camera CVPM systems.</li>
            </ul>
          </div>
          <div className="mb-6">
            <h3 className="text-xl font-medium text-gray-800">Computer Technician</h3>
            <p className="text-gray-600 italic">Barrister Global Services Network Inc., Novi, MI | January 2012 – January 2013</p>
            <ul className="list-disc pl-5 text-gray-600 mt-2">
              <li>Configured hardware, networks, and software for 100+ employee workstations, troubleshooting peripherals (printers/scanners) and integrating backend systems for optimal performance.</li>
              <li>Partnered with vendors to source components and resolve advanced issues, minimizing downtime by 30% through proactive scripting and diagnostics.</li>
            </ul>
          </div>
          <div className="mb-6">
            <h3 className="text-xl font-medium text-gray-800">Maintenance Assistant</h3>
            <p className="text-gray-600 italic">Alexander & Hornung, St. Clair Shores, MI | February 2006 – December 2011</p>
            <ul className="list-disc pl-5 text-gray-600 mt-2">
              <li>Executed preventive maintenance on industrial equipment using tools like MIG/TIG welders, power saws, and soldering irons—applying hands-on problem-solving transferable to hardware-software integration.</li>
              <li>Collaborated on major repair projects with cross-functional teams, ensuring compliance with safety protocols and operational efficiency.</li>
            </ul>
          </div>

          <h2 className="text-2xl font-semibold text-gray-800 mt-8 mb-4 border-b-2 border-gray-200 pb-2">
            Education
          </h2>
          <p className="text-gray-600">
            <span className="font-medium">Master of Science in Computer Engineering</span><br />
            Oakland University, Rochester Hills, MI | May 2018
          </p>
          <p className="text-gray-600 mt-2">
            <span className="font-medium">Bachelor of Science in Computer Engineering</span><br />
            Lawrence Technological University, Southfield, MI | May 2014
          </p>

          <h2 className="text-2xl font-semibold text-gray-800 mt-8 mb-4 border-b-2 border-gray-200 pb-2">
            Certifications
          </h2>
          <ul className="list-disc pl-5 text-gray-600">
            <li>ISTQB Foundation Level (International Software Testing Qualifications Board) | 2020</li>
          </ul>
        </section>

        {/* Cover Letter Section */}
        <section className="mt-12">
          <h2 className="text-2xl font-semibold text-gray-800 mb-4 border-b-2 border-gray-200 pb-2">
            Cover Letter
          </h2>
          <div className="text-gray-600 leading-relaxed">
            <p>Kevin Douglas DeLong<br />Fenton, MI 48430<br />(810) 287-7409 | delong.kevin@gmail.com | [LinkedIn/GitHub]<br />[09/12/2025]</p>
            <p className="mt-4">Dear Hiring Manager,</p>
            <p className="mt-2">
              As a passionate Software Engineer with over a decade of hands-on experience in full-stack development for embedded and automotive systems, I am excited to apply for the Software Engineer position at [Company Name]. My background in building scalable backend automation (Python/C++) and intuitive frontend interfaces (Android/CANoe UIs) aligns seamlessly with your team's focus on innovative web, mobile, and desktop solutions. At Harman International, I led CI/CD optimizations that reduced defects by 25%, and I'm eager to bring that engineering rigor to [Company Name]'s dynamic projects.
            </p>
            <p className="mt-2">
              In my current role as Software Testing Lead, I collaborate closely with development teams to architect and debug AutoSAR-based systems for infotainment platforms, integrating CAN/Ethernet protocols with secure fuzz testing and OTA telematics. Key achievements include developing automation scripts that accelerated milestone deliveries by 15% and training cross-functional teams on Vector tools for real-time embedded environments. Previously, as a Software Test Engineer, I designed simulation UIs and validated ADAS/camera systems, honing my skills in full-lifecycle software engineering—from requirements gathering to on-site data analysis. These experiences, combined with my MS in Computer Engineering from Oakland University, have equipped me to deliver high-impact, quality-driven code that scales across platforms.
            </p>

            <p className="mt-4">Sincerely,<br />Kevin Douglas DeLong</p>
          </div>
        </section>

        {/* Action Buttons */}
        <div className="mt-8 flex space-x-4">
          <a
            href="#"
            className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 transition"
            onClick={() => alert('Download PDF functionality to be implemented')}
          >
            Download Resume PDF
          </a>
          <a
            href="#"
            className="bg-green-600 text-white px-6 py-2 rounded-md hover:bg-green-700 transition"
            onClick={() => alert('Request access to project source code')}
          >
            Request Project Access
          </a>
        </div>
      </div>
    </div>
  );
};

export default Resume;
