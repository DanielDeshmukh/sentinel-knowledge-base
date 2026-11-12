import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDocuments } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type { Document } from '../types';
import ClassificationBadge from '../components/ClassificationBadge';

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

const Documents: React.FC = () => {
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const { data: documents, isLoading, error } = useQuery({
    queryKey: ['documents'],
    queryFn: getDocuments,
  });

  const filteredDocs = documents?.filter((doc: Document) =>
    `${doc.title} ${doc.source} ${doc.classification}`.toLowerCase().includes(search.toLowerCase())
  ) || [];

  if (isLoading) {
    return <div className="loading">LOADING DOCUMENTS</div>;
  }

  if (error) {
    return <div className="loading">ERROR LOADING DOCUMENTS</div>;
  }

  return (
    <>
      <div className="inner-page-heading">
        <div>
          <div className="section-kicker"><span>02</span> / YOUR KNOWLEDGE</div>
          <h1>Knowledge base<span className="heading-period">.</span></h1>
          <p>Every source you can access, in one secure place.</p>
        </div>
      </div>

      <div className="document-summary">
        <div>
          <span style={{ color: '#858585', font: '500 8px IBM Plex Mono, monospace', letterSpacing: '.08em' }}>YOUR KNOWLEDGE COLLECTION</span>
          <strong style={{ display: 'block', fontSize: '30px', letterSpacing: '-.04em', marginTop: '13px', lineHeight: 1 }}>
            {String(documents?.length || 0).padStart(2, '0')} <small style={{ fontSize: '12px', fontWeight: 400, color: '#929292', letterSpacing: 0 }}>documents</small>
          </strong>
          <p style={{ color: '#777', fontSize: '10px', marginTop: '9px' }}>Filtered to your current clearance.</p>
        </div>
        <div className="summary-graphic">
          <div className="summary-stack"><span /><span /><span /></div>
          <span style={{ color: '#666', font: '500 8px IBM Plex Mono, monospace' }}>INDEX / ACTIVE</span>
        </div>
        <div className="summary-detail">
          <span style={{ color: '#858585', font: '500 8px IBM Plex Mono, monospace', letterSpacing: '.08em' }}>ACCESS LEVEL</span>
          <ClassificationBadge value={user?.role || 'public'} />
          <p style={{ marginTop: '10px', color: '#777', fontSize: '10px' }}>Searchable passages</p>
        </div>
      </div>

      <div className="table-heading">
        <div>
          <div className="section-kicker"><span>01</span> / DOCUMENT LIBRARY</div>
          <h2>Your sources <span style={{ font: '500 10px IBM Plex Mono, monospace', color: '#707070', marginLeft: '6px', verticalAlign: '3px' }}>{String(filteredDocs.length).padStart(2, '0')}</span></h2>
        </div>
        <div className="search-box">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search documents..."
            aria-label="Search documents"
          />
          <kbd>⌕</kbd>
        </div>
      </div>

      <div className="document-table">
        <div className="document-table-head">
          <span>DOCUMENT NAME</span>
          <span>CLASSIFICATION</span>
          <span>ADDED</span>
          <span />
        </div>

        {filteredDocs.length === 0 ? (
          <div className="table-empty">
            <svg width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
            <strong>No documents found</strong>
            <span>Try a different search or add a document.</span>
          </div>
        ) : (
          filteredDocs.map((doc: Document) => (
            <div className="document-row" key={doc.id}>
              <div className="document-name">
                <span className="file-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                </span>
                <span>
                  <strong>{doc.title}</strong>
                  <small>{doc.source || ''}</small>
                </span>
              </div>
              <ClassificationBadge value={doc.classification} />
              <span className="table-muted">{formatDate(doc.created_at).toUpperCase()}</span>
              <div className="row-actions">
                <button className="row-icon" aria-label={`Open ${doc.title}`}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="table-foot">
        <span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
          SHOWING ONLY DOCUMENTS AUTHORIZED FOR YOUR ROLE
        </span>
        <span>END OF LIST / {String(filteredDocs.length).padStart(2, '0')}</span>
      </div>
    </>
  );
};

export default Documents;
