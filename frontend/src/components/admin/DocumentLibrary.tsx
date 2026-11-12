import type { Document } from '../../types';
import ClassificationBadge from '../ClassificationBadge';

interface DocumentLibraryProps {
  documents: Document[] | undefined;
  isLoading: boolean;
  onDelete: (document: Document) => void;
}

function DocumentLibrary({ documents, isLoading, onDelete }: DocumentLibraryProps) {
  return (
    <>
      <div className="table-heading">
        <div>
          <div className="section-kicker"><span>01</span> / INGESTED DOCUMENTS</div>
          <h2>Document library <span style={{ font: '500 10px IBM Plex Mono, monospace', color: '#707070', marginLeft: '6px', verticalAlign: '3px' }}>{String(documents?.length || 0).padStart(2, '0')}</span></h2>
        </div>
      </div>

      {isLoading ? (
        <div className="loading">LOADING DOCUMENTS</div>
      ) : (
        <div className="document-table">
          <div className="document-table-head">
            <span>DOCUMENT NAME</span>
            <span>CLASSIFICATION</span>
            <span>ADDED</span>
            <span />
          </div>
          {documents?.length === 0 ? (
            <div className="table-empty">
              <svg width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              <strong>No documents ingested yet</strong>
              <span>Upload a document to get started.</span>
            </div>
          ) : (
            documents?.map((doc) => (
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
                <span className="table-muted">{new Date(doc.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase()}</span>
                <div className="row-actions">
                  <button
                    className="row-icon delete-icon"
                    onClick={() => onDelete(doc)}
                    aria-label={`Delete ${doc.title}`}
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </>
  );
}

export default DocumentLibrary;
