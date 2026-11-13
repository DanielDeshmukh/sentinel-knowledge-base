import React, { useState } from 'react';
import { chat as apiChat } from '../services/api';
import type { ConversationEntry } from '../types';
import toast from 'react-hot-toast';
import ChatConversation from '../components/chat/ChatConversation';

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<ConversationEntry[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!input.trim() || loading) return;

    const userMessage: ConversationEntry = { role: 'user', content: input.trim() };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      const response = await apiChat({
        question: userMessage.content,
        conversation_history: messages.map(({ role, content }) => ({ role, content })),
      });

      setMessages([
        ...newMessages,
        { role: 'assistant', content: response.answer, response },
      ]);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to get response');
      setMessages(newMessages);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="chat-page">
      <ChatConversation
        messages={messages}
        input={input}
        loading={loading}
        onInputChange={setInput}
        onSendQuestion={handleSubmit}
        onPrompt={setInput}
      />
    </section>
  );
};

export default Chat;
