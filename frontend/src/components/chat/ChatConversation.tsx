import { useEffect, useRef, type KeyboardEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ConversationEntry } from '../../types';

const prompts = [
  { text: 'What are the key principles of the DPDP Act?', label: 'Understand the DPDP Act', tag: 'DATA PROTECTION' },
  { text: 'How quickly should a cyber incident be reported to CERT-In?', label: 'Incident reporting timelines', tag: 'INCIDENT RESPONSE' },
  { text: 'What are the six functions of the NIST Cybersecurity Framework?', label: 'Explore the NIST framework', tag: 'FRAMEWORKS' },
  { text: 'How can I recognize and prevent phishing?', label: 'Recognize phishing attempts', tag: 'SECURITY BASICS' },
];

interface ChatConversationProps {
  messages: ConversationEntry[];
  input: string;
  loading: boolean;
  onInputChange: (value: string) => void;
  onSendQuestion: () => void;
  onPrompt: (text: string) => void;
}

function ChatConversation({
  messages,
  input,
  loading,
  onInputChange,
  onSendQuestion,
  onPrompt,
}: ChatConversationProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onSendQuestion();
    }
  };

  const handlePrompt = (text: string) => {
    onPrompt(text);
    inputRef.current?.focus();
  };

  return (
    <section className="chat-card">
      <div className={`conversation ${messages.length ? 'conversation-active' : ''}`}>
        {messages.length === 0 ? (
          <div className="empty-chat">
            <h3>What would you like to know?</h3>
            <p>Answers use only documents you are authorized to access.</p>
            <div className="prompt-grid">
              {prompts.map((prompt) => (
                <button
                  key={prompt.text}
                  className="prompt-card"
                  onClick={() => handlePrompt(prompt.text)}
                >
                  <span>
                    <small>{prompt.tag}</small>
                    <strong>{prompt.label}</strong>
                  </span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="message-list">
            {messages.map((message, index) => (
              <div key={index} className={`message message-${message.role}`}>
                {message.role === 'assistant' && (
                  <img
                    className="message-avatar"
                    src="/pwa-192x192.png"
                    alt=""
                    aria-hidden="true"
                    width="192"
                    height="192"
                  />
                )}
                <div className="message-body">
                  {message.role === 'assistant' && (
                    <div className="message-meta">
                      <strong>Sentinel</strong>
                    </div>
                  )}
                  <div className="message-content">
                    {message.role === 'assistant'
                      ? <ReactMarkdown>{message.content}</ReactMarkdown>
                      : message.content}
                  </div>
                  {message.role === 'assistant' && message.response && (
                    <details className="message-details">
                      <summary>
                        <span>Sources ({message.response.citations.length})</span>
                        <span className="message-timings">
                          Retrieval {message.response.retrieval_time_ms} ms
                          <span aria-hidden="true"> · </span>
                          Response {message.response.response_time_ms} ms
                        </span>
                      </summary>
                      {message.response.citations.length > 0 ? (
                        <div className="message-sources">
                          {message.response.citations.map((citation, citationIndex) => (
                            <div key={citation.chunk_id} className="source-link">
                              <span className="source-number">
                                {String(citationIndex + 1).padStart(2, '0')}
                              </span>
                              <div className="source-link-text">
                                <strong>{citation.document_title}</strong>
                                <small>{citation.text.substring(0, 120)}...</small>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="message-no-sources">No sources were retrieved for this answer.</p>
                      )}
                    </details>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="message message-assistant">
                <img
                  className="message-avatar"
                  src="/pwa-192x192.png"
                  alt=""
                  aria-hidden="true"
                  width="192"
                  height="192"
                />
                <div className="message-body">
                  <div className="message-meta"><strong>Sentinel</strong></div>
                  <div className="thinking" role="status" aria-label="Sentinel is thinking">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className="composer-wrap">
        <div className="composer">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => onInputChange(event.currentTarget.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter your query here"
            disabled={loading}
            rows={1}
            aria-label="Ask a question"
          />
          <button
            className="send-button"
            onClick={onSendQuestion}
            disabled={loading || !input.trim()}
            aria-label="Send question"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
          </button>
        </div>
        <div className="composer-foot">
          <span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
            Only your authorized documents are searched
          </span>
          <span>Press Enter to send · Shift + Enter for a new line</span>
        </div>
      </div>
    </section>
  );
}

export default ChatConversation;
