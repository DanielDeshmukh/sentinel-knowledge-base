type SkeletonPage = 'chat' | 'documents' | 'ingestion' | 'access' | 'login' | 'landing';

function Shape({ className = '' }: { className?: string }) {
  return <span className={`skeleton-shape ${className}`} aria-hidden="true" />;
}

function HeadingSkeleton({ wide = false }: { wide?: boolean }) {
  return (
    <header className="inner-page-heading skeleton-heading" aria-hidden="true">
      <div className="skeleton-heading-copy">
        <Shape className="skeleton-kicker" />
        <Shape className={`skeleton-title${wide ? ' skeleton-title-wide' : ''}`} />
        <Shape className="skeleton-description" />
      </div>
      {wide && <Shape className="skeleton-badge" />}
    </header>
  );
}

function ChatSkeleton() {
  return (
    <section className="chat-page">
      <div className="chat-card skeleton-chat-card">
        <div className="skeleton-chat-messages" aria-hidden="true">
          <div className="skeleton-message skeleton-message-user">
            <Shape className="skeleton-message-avatar skeleton-person-avatar" />
            <div className="skeleton-message-copy">
              <Shape className="skeleton-message-meta" />
              <Shape className="skeleton-message-line skeleton-line-medium" />
            </div>
          </div>
          <div className="skeleton-message skeleton-message-assistant">
            <Shape className="skeleton-message-avatar" />
            <div className="skeleton-message-copy">
              <Shape className="skeleton-message-meta" />
              <Shape className="skeleton-message-line skeleton-line-long" />
              <Shape className="skeleton-message-line skeleton-line-medium" />
              <Shape className="skeleton-message-line skeleton-line-short" />
            </div>
          </div>
        </div>
        <div className="composer-wrap skeleton-composer-wrap" aria-hidden="true">
          <div className="composer skeleton-composer">
            <Shape className="skeleton-composer-placeholder" />
            <Shape className="skeleton-send-button" />
          </div>
          <div className="composer-foot">
            <Shape className="skeleton-composer-note" />
            <Shape className="skeleton-composer-note skeleton-note-short" />
          </div>
        </div>
      </div>
    </section>
  );
}

function DocumentsSkeleton() {
  return (
    <section className="documents-page">
      <HeadingSkeleton />
      <div className="documents-toolbar" aria-hidden="true">
        <Shape className="skeleton-document-count" />
        <Shape className="skeleton-search" />
      </div>
      <div className="document-table documents-table skeleton-document-table" aria-hidden="true">
        <div className="document-table-head"><span>DOCUMENT</span><span>CLASSIFICATION</span><span>ADDED</span></div>
        {Array.from({ length: 6 }, (_, index) => (
          <div className="document-row" key={index}>
            <div className="document-name"><Shape className="skeleton-document-title" /></div>
            <Shape className="skeleton-document-badge" />
            <Shape className="skeleton-document-date" />
          </div>
        ))}
      </div>
    </section>
  );
}

function IngestionSkeleton() {
  return (
    <section className="admin-page">
      <HeadingSkeleton wide />
      <div className="admin-tabs skeleton-tabs" aria-hidden="true"><Shape /><Shape /></div>
      <div className="admin-section-heading skeleton-admin-section-heading" aria-hidden="true"><Shape className="skeleton-section-title" /><Shape className="skeleton-description" /></div>
      <div className="ingestion-layout skeleton-ingestion-layout" aria-hidden="true">
        <div className="ingestion-form panel skeleton-form-panel">
          <div className="ingestion-panel-heading"><Shape className="skeleton-section-title" /><Shape className="skeleton-description" /></div>
          <div className="ingestion-form-body">
            <div className="skeleton-field-grid">
              <div><Shape className="skeleton-field-label" /><Shape className="skeleton-field-input" /></div>
              <div><Shape className="skeleton-field-label" /><Shape className="skeleton-field-input" /></div>
              <div className="skeleton-field-wide"><Shape className="skeleton-field-label" /><Shape className="skeleton-field-area" /></div>
              <div className="skeleton-field-wide"><Shape className="skeleton-field-label" /><Shape className="skeleton-field-area" /></div>
            </div>
            <Shape className="skeleton-dropzone" />
            <Shape className="skeleton-submit" />
          </div>
        </div>
        <div className="pipeline-panel panel skeleton-pipeline-panel">
          <div className="ingestion-panel-heading"><Shape className="skeleton-section-title" /><Shape className="skeleton-description" /></div>
          <div className="pipeline-panel-body skeleton-pipeline-body">
            {Array.from({ length: 10 }, (_, index) => (
              <div className="skeleton-pipeline-step" key={index}>
                <Shape className="skeleton-step-index" />
                <Shape className="skeleton-step-label" />
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="skeleton-library" aria-hidden="true"><Shape className="skeleton-section-title" />{Array.from({ length: 3 }, (_, index) => <Shape className="skeleton-library-row" key={index} />)}</div>
    </section>
  );
}

function AccessSkeleton() {
  return (
    <section className="access-page-skeleton">
      <HeadingSkeleton wide />
      <div className="access-directory-heading skeleton-access-heading" aria-hidden="true">
        <div><Shape className="skeleton-section-title" /><Shape className="skeleton-description" /></div>
        <div className="skeleton-access-counts"><Shape /><Shape /></div>
      </div>
      <div className="access-user-list skeleton-access-list" aria-hidden="true">
        {Array.from({ length: 5 }, (_, index) => (
          <div className="access-user-row skeleton-access-row" key={index}>
            <div className="access-user-identity"><Shape className="skeleton-user-avatar" /><div><Shape className="skeleton-user-name" /><Shape className="skeleton-user-email" /></div></div>
            <div><Shape className="skeleton-field-label" /><Shape className="skeleton-role" /></div>
            <div><Shape className="skeleton-field-label" /><Shape className="skeleton-role-request" /></div>
            <div className="skeleton-access-action"><Shape className="skeleton-field-input" /><Shape className="skeleton-save-role" /></div>
          </div>
        ))}
      </div>
    </section>
  );
}

function AuthSkeleton({ landing = false }: { landing?: boolean }) {
  return (
    <section className={landing ? 'auth-shell skeleton-auth-shell' : 'auth-shell'} role="status" aria-label={landing ? 'Loading workspace' : 'Loading sign in'} aria-busy="true">
      <div className={landing ? 'auth-panel skeleton-auth-panel skeleton-landing-panel' : 'auth-panel skeleton-auth-panel'} aria-hidden="true">
        <Shape className="skeleton-auth-brand" />
        <Shape className="skeleton-auth-title" />
        <Shape className="skeleton-auth-description" />
        {landing ? <Shape className="skeleton-auth-submit" /> : <>
          <Shape className="skeleton-field-label" /><Shape className="skeleton-auth-input" />
          <Shape className="skeleton-field-label" /><Shape className="skeleton-auth-input" />
          <Shape className="skeleton-auth-submit" />
        </>}
      </div>
    </section>
  );
}

export default function PageSkeleton({ page }: { page: SkeletonPage }) {
  const labels: Record<SkeletonPage, string> = {
    chat: 'Loading chat',
    documents: 'Loading knowledge base',
    ingestion: 'Loading ingestion workspace',
    access: 'Loading access control',
    login: 'Loading sign in',
    landing: 'Loading workspace',
  };

  if (page === 'login' || page === 'landing') return <AuthSkeleton landing={page === 'landing'} />;

  const content = page === 'chat'
    ? <ChatSkeleton />
    : page === 'documents'
      ? <DocumentsSkeleton />
      : page === 'ingestion'
        ? <IngestionSkeleton />
        : <AccessSkeleton />;

  return <div className={`page-skeleton page-skeleton-${page}`} role="status" aria-label={labels[page]} aria-busy="true">{content}</div>;
}

export type { SkeletonPage };
