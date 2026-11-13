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
    <section className="chat-page">
      <header className="inner-page-heading">
        <div>
          <div className="section-kicker">ASK YOUR KNOWLEDGE BASE</div>
          <h1>Ask Sentinel<span className="heading-period">.</span></h1>
          <p>Get answers grounded in documents available to your role.</p>
        </div>
      </header>
      <ChatConversation
        messages={messages}
        input={input}
        loading={loading}
        lastResponse={lastResponse}
        onInputChange={setInput}
        onSendQuestion={handleSubmit}
        onPrompt={setInput}
      />
      <aside className="chat-access-summary" aria-label="How access is applied">
        <h2>How access is applied</h2>
        <div>
          <p><strong>Role checked.</strong> Your role is verified for each question.</p>
          <p><strong>Sources filtered.</strong> Retrieval only includes documents your role can access.</p>
          <p><strong>Answers grounded.</strong> Citations show which sources support the answer.</p>
        </div>
      </aside>
    </section>
  );
};

export default Chat;
