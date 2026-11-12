import { Link } from 'react-router-dom';

const querySteps = [
  { number: '01', label: 'Ask', detail: 'Send a question' },
  { number: '02', label: 'Filter', detail: 'Apply your role' },
  { number: '03', label: 'Retrieve', detail: 'Find allowed passages' },
  { number: '04', label: 'Respond', detail: 'Use passages as context' },
  { number: '05', label: 'Cite', detail: 'Show source excerpts' },
];

function ConversationExample() {
  return (
    <section className="landing-chat-card" aria-label="Illustrative Sentinel conversation">
      <header className="landing-chat-header">
        <div className="landing-chat-title">
          <img
            className="landing-assistant-icon"
            src="/pwa-192x192.png"
            alt=""
            aria-hidden="true"
            width="36"
            height="36"
          />
          <div>
            <strong>Ask Sentinel</strong>
            <small>KNOWLEDGE ASSISTANT</small>
          </div>
        </div>
        <span className="landing-example-label">EXAMPLE CONVERSATION</span>
      </header>

      <div className="landing-messages">
        <article className="landing-message">
          <span className="landing-message-avatar" aria-hidden="true">Y</span>
          <div className="landing-message-body">
            <div className="landing-message-meta"><strong>YOU</strong><span>QUESTION</span></div>
            <p className="landing-question">What does the incident response policy say?</p>
          </div>
        </article>

        <article className="landing-message">
          <span className="landing-message-avatar landing-message-avatar-assistant" aria-hidden="true">S</span>
          <div className="landing-message-body">
            <div className="landing-message-meta"><strong>SENTINEL</strong><span>RESPONSE</span></div>
            <p className="landing-answer">
              The response is formed from passages relevant to your question and accessible to your
              account. Review the cited excerpts below for the supporting text.
            </p>
            <div className="landing-sources" aria-label="Illustrative source excerpts">
              <div className="landing-source-heading">SOURCE EXCERPTS <span>ILLUSTRATIVE</span></div>
              <article className="landing-source">
                <span className="landing-source-number">01</span>
                <span className="landing-source-copy">
                  <strong>Example incident response document</strong>
                  <small>Illustrative excerpt from an authorized passage...</small>
                </span>
              </article>
              <article className="landing-source">
                <span className="landing-source-number">02</span>
                <span className="landing-source-copy">
                  <strong>Example security policy</strong>
                  <small>Illustrative excerpt from a matching source...</small>
                </span>
              </article>
            </div>
          </div>
        </article>
      </div>

      <p className="landing-chat-disclaimer">
        Example only. Responses and sources depend on your question, role, and available documents.
      </p>
    </section>
  );
}

function QueryFlow() {
  return (
    <section className="landing-flow" id="query-flow" aria-labelledby="landing-flow-title">
      <div className="landing-flow-heading">
        <h2 id="landing-flow-title">From your question to supporting evidence</h2>
        <span>THE USER QUERY PATH</span>
      </div>
      <ol className="landing-flow-list">
        {querySteps.map((step) => (
          <li className="landing-flow-item" key={step.number}>
            <strong>{step.number} / {step.label.toUpperCase()}</strong>
            <span>{step.detail}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Landing() {
  return (
    <div className="landing-page">
      <header className="landing-header">
        <Link className="landing-brand" to="/" aria-label="Sentinel Knowledge Systems home">
          <img src="/pwa-192x192.png" alt="" aria-hidden="true" width="36" height="36" />
          <span><strong>SENTINEL</strong><small>KNOWLEDGE SYSTEMS</small></span>
        </Link>
        <nav className="landing-nav" aria-label="Main navigation">
          <a className="landing-nav-about" href="#query-flow">How answers work</a>
          <Link to="/login">Sign in</Link>
          <Link className="landing-nav-cta" to="/login?mode=register">Create account</Link>
        </nav>
      </header>

      <main>
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-intro">
            <p className="landing-kicker"><span aria-hidden="true" /> INTELLIGENCE WITH BOUNDARIES</p>
            <h1 id="landing-title">Knowledge you can trust.<br /><span>Sources you can see.</span></h1>
            <p className="landing-copy">
              Ask about the knowledge available to your account. Sentinel retrieves relevant
              passages allowed by your role, uses them to form a response, and shows the supporting
              source excerpts.
            </p>
            <div className="landing-actions">
              <Link className="landing-action landing-action-primary" to="/login?mode=register">
                Create account
              </Link>
              <Link className="landing-action" to="/login">Sign in</Link>
            </div>
            <p className="landing-proof">
              <span aria-hidden="true" /> ROLE-FILTERED SOURCES <span>/</span> ANSWERS WITH EVIDENCE
            </p>
          </div>
          <ConversationExample />
        </section>

        <QueryFlow />

        <section className="landing-notes" aria-label="How answers are handled">
          <p><strong>No relevant authorized passages?</strong> Sentinel returns a no-match response.</p>
          <p><strong>Generation unavailable?</strong> Retrieved passages are returned with a note.</p>
          <p><strong>Conversation context:</strong> Up to six recent messages can be included.</p>
        </section>
      </main>

      <footer className="landing-footer">
        <span>BUILT FOR CLARITY. DESIGNED FOR TRUST.</span>
        <span>SENTINEL KNOWLEDGE SYSTEMS</span>
      </footer>
    </div>
  );
}

export default Landing;
