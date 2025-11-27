import React, { useEffect, useState } from 'react';
import { authFetch } from '@/utils/authFetch';


interface Report {
  filename: string;
  size: number;
  created: string;
  url: string;
}

export const Downloads: React.FC = () => {
  const [caseId, setCaseId] = useState<number>(1);
  const [reports, setReports] = useState<Report[]>([]);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadReports();
  }, [caseId]);

  const loadReports = async () => {
    const response = await authFetch(`/reports/list/${caseId}`);
    const data = await response.json();
    setReports(data);
  };

  const generateReport = async (period: string) => {
    setGenerating(true);
    try {
      await authFetch(`/reports/generate/${caseId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ period })
      });
      await loadReports();
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="downloads-page">
      <h1>Reports</h1>
      
      <div className="generate-buttons">
        <button onClick={() => generateReport('daily')} disabled={generating}>
          Generate Daily Report
        </button>
        <button onClick={() => generateReport('weekly')} disabled={generating}>
          Generate Weekly Report
        </button>
        <button onClick={() => generateReport('monthly')} disabled={generating}>
          Generate Monthly Report
        </button>
      </div>

      <table>
        <thead>
          <tr>
            <th>Filename</th>
            <th>Created</th>
            <th>Size</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {reports.map(report => (
            <tr key={report.filename}>
              <td>{report.filename}</td>
              <td>{new Date(report.created).toLocaleString()}</td>
              <td>{(report.size / 1024).toFixed(2)} KB</td>
              <td>
                <a href={report.url} download>Download</a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};