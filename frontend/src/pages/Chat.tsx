import React, { useState } from 'react';
import { chat as apiChat } from '../services/api';
import type { ChatMessage, ChatResponse } from '../types';
import toast from 'react-hot-toast';
import ChatConversation from '../components/chat/ChatConversation';

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);

  const handleSubmit = async () => {
    if (!input.trim() || loading) return;

    const userMessage: ChatMessage = { role: 'user', content: input.trim() };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      const response = await apiChat({
        question: userMessage.content,
        conversation_history: messages,
      });

      setLastResponse(response);
      setMessages([...newMessages, { role: 'assistant', content: response.answer }]);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to get response');
      setMessages(newMessages);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {messages.length === 0 && (
        <section className="hero">
          <div className="hero-art" aria-hidden="true" />
          <div className="hero-grid" aria-hidden="true" />
          <div className="hero-scan" aria-hidden="true" />
          <div className="hero-content">
            <div className="eyebrow hero-eyebrow">
              <span className="eyebrow-square" /> INTELLIGENCE FOR WHAT MATTERS <span className="eyebrow-dash">/</span> 001
            </div>
            <h1>Knowledge,<br /><span>without compromise.</span></h1>
            <p>Answers you can trust, from the knowledge<br />you&apos;re actually allowed to see.</p>
            <div className="hero-foot">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
              <span>PERMISSION-AWARE BY DESIGN</span>
              <span className="hero-foot-line" />
              <span>EST. 2026</span>
            </div>
          </div>
          <div className="hero-coordinate hero-coordinate-top">SYSTEM / 001<br />SECURE KNOWLEDGE</div>
          <div className="hero-coordinate hero-coordinate-bottom">
            <span>●</span> SENTINEL INTELLIGENCE <span className="coord-cross">+</span>
          </div>
        </section>
      )}

      <div className="chat-layout">
        <ChatConversation
          messages={messages}
          input={input}
          loading={loading}
          lastResponse={lastResponse}
          onInputChange={setInput}
          onSendQuestion={handleSubmit}
          onPrompt={setInput}
        />

        <aside className="insight-column">
          <div className="insight-card">
            <div className="insight-head">
              <span>THE SENTINEL DIFFERENCE</span>
              <span>✳</span>
            </div>
            <div className="insight-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>
              <span className="icon-corner icon-corner-one" />
              <span className="icon-corner icon-corner-two" />
            </div>
            <h3>Intelligence with<br /><em>boundaries.</em></h3>
            <p>Good answers start with the right access. Here&apos;s how we keep yours secure.</p>
            <div className="principle-list">
              <div className="principle">
                <span>01</span>
                <div>
                  <strong>Access verified</strong>
                  <small>Your role is checked on every request.</small>
                </div>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
              </div>
              <div className="principle">
                <span>02</span>
                <div>
                  <strong>Sources filtered</strong>
                  <small>Permissions are applied before retrieval.</small>
                </div>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
              </div>
              <div className="principle">
                <span>03</span>
                <div>
                  <strong>Answers grounded</strong>
                  <small>Trace every answer back to its source.</small>
                </div>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
              </div>
            </div>
          </div>
          <div className="mini-status">
            <div>
              <span className="status-ring"><span /></span>
              <div>
                <strong>All systems in check</strong>
                <small>YOUR WORKSPACE IS READY</small>
              </div>
            </div>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
          </div>
        </aside>
      </div>

      <div className="page-footer">
        <span>BUILT FOR CLARITY. DESIGNED FOR TRUST.</span>
        <span>SENTINEL KNOWLEDGE BASE <span className="footer-cross">✳</span> 2026</span>
      </div>
    </>
  );
};

export default Chat;
