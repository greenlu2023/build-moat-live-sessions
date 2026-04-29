import { useState, useEffect } from 'react';

interface QRInfo {
  token: string;
  original_url: string;
  short_url?: string;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
  is_deleted: boolean;
}

interface Analytics {
  total_scans: number;
  scans_by_day: { date: string; count: number }[];
}

export default function App() {
  const [urlInput, setUrlInput] = useState('');
  const [qrInfo, setQrInfo] = useState<QRInfo | null>(null);
  
  const [updateUrlInput, setUpdateUrlInput] = useState('');
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [httpStatus, setHttpStatus] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const handleGenerate = async () => {
    if (!urlInput) return;
    try {
      const res = await fetch('/api/qr/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: urlInput }),
      });
      if (res.ok) {
        const data = await res.json();
        const infoRes = await fetch(`/api/qr/${data.token}`);
        if (infoRes.ok) {
          const info = await infoRes.json();
          setQrInfo({ ...info, short_url: data.short_url });
          setAnalytics(null);
          setHttpStatus(null);
          setUpdateUrlInput('');
        }
      } else {
        const err = await res.json();
        alert(`Error: ${err.detail}`);
      }
    } catch (e) {
      console.error(e);
      alert('Failed to generate QR');
    }
  };

  const handleUpdate = async () => {
    if (!qrInfo || !updateUrlInput) return;
    const expiresAt = new Date(Date.now() + 60000).toISOString(); // +1 minute
    try {
      const res = await fetch(`/api/qr/${qrInfo.token}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: updateUrlInput, expires_at: expiresAt }),
      });
      if (res.ok) {
        const updated = await res.json();
        setQrInfo({ ...updated, short_url: qrInfo.short_url });
        setUpdateUrlInput('');
      } else {
        const err = await res.json();
        alert(`Error: ${err.detail}`);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async () => {
    if (!qrInfo) return;
    try {
      const res = await fetch(`/api/qr/${qrInfo.token}`, { method: 'DELETE' });
      if (res.ok) {
        setQrInfo({ ...qrInfo, is_deleted: true });
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleLoadAnalytics = async () => {
    if (!qrInfo) return;
    try {
      const res = await fetch(`/api/qr/${qrInfo.token}/analytics`);
      if (res.ok) {
        const data = await res.json();
        setAnalytics(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleTestRedirect = async () => {
    if (!qrInfo) return;
    try {
      // Use redirect: 'manual' to prevent following the redirect, allowing us to see the 302/410 status
      const res = await fetch(`/r/${qrInfo.token}`, { redirect: 'manual' });
      setHttpStatus(res.status);
    } catch (e) {
      console.error(e);
    }
  };

  const getStatus = () => {
    if (!qrInfo) return null;
    if (qrInfo.is_deleted) return { text: 'Deleted', className: 'status-deleted' };
    if (qrInfo.expires_at && new Date(qrInfo.expires_at).getTime() < now) return { text: 'Expired', className: 'status-expired' };
    return { text: 'Active', className: 'status-active' };
  };

  const status = getStatus();

  const getCountdown = () => {
    if (!qrInfo || !qrInfo.expires_at) return 'Never';
    const diff = Math.max(0, Math.floor((new Date(qrInfo.expires_at).getTime() - now) / 1000));
    const isRed = diff > 0 && diff < 10;
    if (diff === 0) return 'Expired';
    return <span className={isRed ? 'countdown-red' : ''}>{diff}s remaining</span>;
  };

  return (
    <div className="container">
      {/* Row 1 — Header */}
      <div className="row-between panel">
        <h2>QR Code Generator</h2>
        {status && (
          <div className={`status-badge ${status.className}`}>
            {status.text}
          </div>
        )}
      </div>

      {/* Row 2 — Input bar */}
      <div className="row panel">
        <input 
          type="url" 
          placeholder="Enter destination URL (e.g., https://example.com)" 
          value={urlInput}
          onChange={e => setUrlInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleGenerate()}
        />
        <button onClick={handleGenerate}>Generate</button>
      </div>

      {qrInfo && (
        <>
          {/* Row 3 — Main panel */}
          <div className="panel grid-2">
            <div className="qr-island">
              <img src={`/api/qr/${qrInfo.token}/image`} alt="QR Code" />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div>
                <div className="label">Token</div>
                <div className="mono">{qrInfo.token}</div>
              </div>
              <div>
                <div className="label">Short URL</div>
                <div className="mono"><a href={qrInfo.short_url} target="_blank" rel="noreferrer">{qrInfo.short_url}</a></div>
              </div>
              <div>
                <div className="label">Target URL</div>
                <div className="mono">{qrInfo.original_url}</div>
              </div>
              
              <div className="metadata-grid">
                <div className="metadata-item">
                  <span className="label">Created</span>
                  <span className="metadata-val mono">{new Date(qrInfo.created_at).toLocaleTimeString()}</span>
                </div>
                <div className="metadata-item">
                  <span className="label">Updated</span>
                  <span className="metadata-val mono">{new Date(qrInfo.updated_at).toLocaleTimeString()}</span>
                </div>
                <div className="metadata-item">
                  <span className="label">Expires</span>
                  <span className="metadata-val mono">{qrInfo.expires_at ? new Date(qrInfo.expires_at).toLocaleTimeString() : 'N/A'}</span>
                </div>
                <div className="metadata-item">
                  <span className="label">Countdown</span>
                  <span className="metadata-val mono">{getCountdown()}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Row 4 — Update bar */}
          <div className="row panel">
            <input 
              type="url" 
              placeholder="Enter new target URL to update..." 
              value={updateUrlInput}
              onChange={e => setUpdateUrlInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleUpdate()}
            />
            <button onClick={handleUpdate} className="btn-secondary">Update & +1m Expiry</button>
          </div>

          {/* Row 5 — Action bar */}
          <div className="row-between panel">
            <div className="row">
              <button onClick={handleLoadAnalytics} className="btn-secondary">Load Analytics</button>
              <button onClick={handleTestRedirect} className="btn-secondary">Test Redirect</button>
              <button onClick={handleDelete} className="btn-danger" disabled={qrInfo.is_deleted}>Delete</button>
            </div>
            {httpStatus !== null && (
              <div className={`status-badge ${httpStatus === 302 ? 'status-active' : 'status-danger'}`} style={{ color: httpStatus === 302 ? 'var(--accent-primary)' : 'var(--accent-danger)' }}>
                HTTP {httpStatus}
              </div>
            )}
          </div>

          {/* Row 6 — Analytics panel */}
          {analytics && (
            <div className="panel">
              <div className="label">Total Scans</div>
              <div className="mono" style={{ fontSize: '24px', marginBottom: '1rem' }}>{analytics.total_scans}</div>
              
              {analytics.scans_by_day.length > 0 ? (
                <table className="table-container">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Scans</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analytics.scans_by_day.map(row => (
                      <tr key={row.date}>
                        <td className="mono">{row.date}</td>
                        <td className="mono">{row.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="label" style={{ textTransform: 'none' }}>No scan data available yet.</div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
