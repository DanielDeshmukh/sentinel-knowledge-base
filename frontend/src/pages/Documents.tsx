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
    `${doc.title} ${doc.source ?? ''} ${doc.classification}`.toLowerCase().includes(search.toLowerCase())
  ) || [];

  const pageHeading = (
    <header className="inner-page-heading">
      <div>
        <div className="section-kicker">YOUR KNOWLEDGE</div>
        <h1>Knowledge base<span className="heading-period">.</span></h1>
        <p>Sources available to your {user?.role ?? 'public'} role.</p>
      </div>
    </header>
  );

  if (isLoading) return <section className="documents-page">{pageHeading}<div className="loading">LOADING DOCUMENTS</div></section>;
  if (error) return <section className="documents-page">{pageHeading}<div className="loading" role="alert">ERROR LOADING DOCUMENTS</div></section>;

  return (
    <section className="documents-page">
      {pageHeading}

      <div className="documents-toolbar">
        <div className="documents-count" aria-live="polite">
          <strong>{filteredDocs.length}</strong>
          <span>{filteredDocs.length === 1 ? 'document' : 'documents'}</span>
        </div>
        <label className="search-box documents-search">
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            value={search}
            onChange={(event) => setSearch(event.currentTarget.value)}
            placeholder="Search documents"
            aria-label="Search documents"
          />
        </label>
      </div>

      <div className="document-table documents-table">
        <div className="document-table-head">
          <span>DOCUMENT</span>
          <span>CLASSIFICATION</span>
          <span>ADDED</span>
        </div>
        {filteredDocs.length === 0 ? (
          <div className="table-empty">
            <strong>{search ? 'No matching documents' : 'No documents available'}</strong>
            <span>{search ? 'Try a different search term.' : 'Documents available to your role will appear here.'}</span>
          </div>
        ) : filteredDocs.map((doc) => (
          <div className="document-row" key={doc.id}>
            <div className="document-name">
              <span>
                <strong>{doc.title}</strong>
                {doc.source && <small>{doc.source}</small>}
              </span>
            </div>
            <ClassificationBadge value={doc.classification} />
            <span className="table-muted">{formatDate(doc.created_at)}</span>
          </div>
        ))}
      </div>
    </section>
  );
};

export default Documents;
