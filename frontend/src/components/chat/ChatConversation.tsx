import { useEffect, useRef, type KeyboardEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ChatMessage, ChatResponse } from '../../types';

const prompts = [
  { text: 'What are the key principles of the DPDP Act?', label: 'Understand the DPDP Act', tag: 'DATA PROTECTION' },
  { text: 'How quickly should a cyber incident be reported to CERT-In?', label: 'Incident reporting timelines', tag: 'INCIDENT RESPONSE' },
  { text: 'What are the six functions of the NIST Cybersecurity Framework?', label: 'Explore the NIST framework', tag: 'FRAMEWORKS' },
  { text: 'How can I recognize and prevent phishing?', label: 'Recognize phishing attempts', tag: 'SECURITY BASICS' },
];

interface ChatConversationProps {
  messages: ChatMessage[];
  input: string;
  loading: boolean;
  lastResponse: ChatResponse | null;
  onInputChange: (value: string) => void;
  onSendQuestion: () => void;
  onPrompt: (text: string) => void;
}

function ChatConversation({
  messages,
  input,
  loading,
  lastResponse,
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
      {messages.length === 0 && (
        <div className="chat-card-header">
          <div className="chat-title">
            <div>
              <strong>New conversation</strong>
              <span>ASK A QUESTION OR CHOOSE A STARTER</span>
            </div>
          </div>
        </div>
      )}

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
                <div className="message-avatar">
                  {message.role === 'user' ? 'U' : (
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                  )}
                </div>
                <div className="message-body">
                  <div className="message-meta">
                    <strong>{message.role === 'user' ? 'You' : 'Sentinel'}</strong>
                    <span>{message.role}</span>
                  </div>
                  <div className="message-content">
                    {message.role === 'assistant' ? (
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    ) : (
                      message.content
                    )}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="message message-assistant">
                <div className="message-avatar">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                </div>
                <div className="message-body">
                  <div className="thinking">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {lastResponse && (
        <div style={{ padding: '12px 20px', borderTop: '1px solid #292929' }}>
          <div className="timings">
            <span>RETRIEVAL <strong>{lastResponse.retrieval_time_ms} ms</strong></span>
            <span>RESPONSE <strong>{lastResponse.response_time_ms} ms</strong></span>
            {lastResponse.citations.length > 0 && (
              <span>SOURCES <strong>{lastResponse.citations.length}</strong></span>
            )}
          </div>
          {lastResponse.citations.length > 0 && (
            <div className="message-sources">
              <div className="source-heading">
                SOURCES <span>{lastResponse.citations.length} FOUND</span>
              </div>
              {lastResponse.citations.map((citation, index) => (
                <div key={index} className="source-link">
                  <span className="source-number">{String(index + 1).padStart(2, '0')}</span>
                  <div className="source-link-text">
                    <strong>{citation.document_title}</strong>
                    <small>{citation.text.substring(0, 120)}...</small>
                  </div>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="composer-wrap">
        <div className="composer">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => onInputChange(event.currentTarget.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your knowledge base..."
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
            <span>ASK SENTINEL</span>
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
          </button>
        </div>
        <div className="composer-foot">
          <span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
            Only your authorized documents are searched
          </span>
          <span>ENTER TO SEND <kbd>↵</kbd></span>
        </div>
      </div>
    </section>
  );
}

export default ChatConversation;
