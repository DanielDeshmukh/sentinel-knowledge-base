import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

const root = fileURLToPath(new URL('..', import.meta.url));

test('renders assistant identity and response details with its answer', async () => {
  const server = await createServer({
    root,
    configFile: false,
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true },
    appType: 'custom',
  });

  try {
    const { default: ChatConversation } = await server.ssrLoadModule(
      '/src/components/chat/ChatConversation.tsx',
    );
    const markup = renderToStaticMarkup(
      React.createElement(ChatConversation, {
        messages: [
          { role: 'user', content: 'What does the first source say?' },
          {
            role: 'assistant',
            content: 'The first source describes the policy.',
            response: {
              answer: 'The first source describes the policy.',
              citations: [{
                chunk_id: 'chunk-1',
                document_id: 'document-1',
                document_title: 'Information Security Policy',
                text: 'A relevant source excerpt.',
                heading_path: 'Access control',
              }],
              retrieval_time_ms: 12.5,
              response_time_ms: 45.7,
            },
          },
          { role: 'user', content: 'What does the second source say?' },
          {
            role: 'assistant',
            content: 'The second source describes the standard.',
            response: {
              answer: 'The second source describes the standard.',
              citations: [{
                chunk_id: 'chunk-2',
                document_id: 'document-2',
                document_title: 'Access Control Standard',
                text: 'A second relevant source excerpt.',
                heading_path: 'Authentication',
              }],
              retrieval_time_ms: 24.3,
              response_time_ms: 81.2,
            },
          },
        ],
        input: '',
        loading: false,
        onInputChange: () => {},
        onSendQuestion: () => {},
        onPrompt: () => {},
      }),
    );

    assert.match(markup, /pwa-192x192\.png/);
    assert.match(markup, /<details[^>]*class="message-details"/);
    assert.match(markup, /Information Security Policy/);
    assert.match(markup, /Access Control Standard/);
    assert.equal((markup.match(/class="message-details"/g) || []).length, 2);
    assert.match(markup, /12\.5 ms/);
    assert.match(markup, /45\.7 ms/);
    assert.match(markup, /24\.3 ms/);
    assert.match(markup, /81\.2 ms/);
    assert.match(markup, /placeholder="Enter your query here"/);
  } finally {
    await server.close();
  }
});
