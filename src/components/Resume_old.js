import React, { useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.js`;

const Resume = () => {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);

  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages);
  };

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">Resume & Cover Letters</h1>
      <div className="space-y-4 mb-8">
        <a
          href="/resume/KevinDouglasDelong_Resume.pdf"
          download
          className="bg-primary text-white px-4 py-2 rounded hover:bg-blue-700 transition inline-block"
        >
          Download Resume
        </a>
        <a
          href="/resume/KevinDouglasDelong_CoverLetter.pdf"
          download
          className="bg-primary text-white px-4 py-2 rounded hover:bg-blue-700 transition inline-block ml-4"
        >
          Download Cover Letter
        </a>
      </div>
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md">
        <Document
          file="/resume/KevinDouglasDelong_Resume.pdf"
          onLoadSuccess={onDocumentLoadSuccess}
        >
          <Page pageNumber={pageNumber} />
        </Document>
        <p className="text-center mt-4">
          Page {pageNumber} of {numPages}
          <button
            onClick={() => setPageNumber((prev) => Math.max(prev - 1, 1))}
            className="ml-4 px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
            disabled={pageNumber <= 1}
          >
            Previous
          </button>
          <button
            onClick={() => setPageNumber((prev) => Math.min(prev + 1, numPages))}
            className="ml-2 px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
            disabled={pageNumber >= numPages}
          >
            Next
          </button>
        </p>
      </div>
    </div>
  );
};

export default Resume;