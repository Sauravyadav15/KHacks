import React, { useState } from 'react';

interface Message {
  role: 'user' | 'bot';
  content: string;
}

const Student: React.FC = () => {
  const [chatLog, setChatLog] = useState<Message[]>([]);
  const [message, setMessage] = useState('');
  const [threadId, setThreadId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = async () => {
    if (!message || isLoading) return;

    const userMessage = message;
    // Optimistic UI update - add user message
    const newLog: Message[] = [...chatLog, { role: 'user', content: userMessage }];
    setChatLog(newLog);
    setMessage('');
    setIsLoading(true);

    // Add placeholder for bot response
    const botMessageIndex = newLog.length;
    setChatLog([...newLog, { role: 'bot', content: '' }]);

    try {
      const response = await fetch('http://localhost:8000/student/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          thread_id: threadId,
        }),
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let accumulatedContent = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'thread_id') {
                setThreadId(data.thread_id);
              } else if (data.type === 'content') {
                accumulatedContent += data.content;
                // Update the bot message in real-time
                setChatLog(prevLog => {
                  const updatedLog = [...prevLog];
                  updatedLog[botMessageIndex] = { role: 'bot', content: accumulatedContent };
                  return updatedLog;
                });
                if (data.thread_id) {
                  setThreadId(data.thread_id);
                }
              } else if (data.type === 'done') {
                if (data.thread_id) {
                  setThreadId(data.thread_id);
                }
              } else if (data.type === 'error') {
                console.error('Error from server:', data.error);
                setChatLog(prevLog => {
                  const updatedLog = [...prevLog];
                  updatedLog[botMessageIndex] = { role: 'bot', content: `Error: ${data.error}` };
                  return updatedLog;
                });
              }
            }
          }
        }
      }
    } catch (err) {
      console.error('Chat failed', err);
      setChatLog(prevLog => {
        const updatedLog = [...prevLog];
        updatedLog[botMessageIndex] = { role: 'bot', content: 'Error: Failed to get response' };
        return updatedLog;
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-6">
      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h2 className="card-title text-2xl mb-4">Story Chat</h2>

          <div className="bg-base-200 rounded-lg p-4 h-96 overflow-y-auto mb-4">
            {chatLog.map((log, i) => (
              <div key={i} className={`chat ${log.role === 'user' ? 'chat-end' : 'chat-start'}`}>
                <div className="chat-header">
                  {log.role === 'user' ? 'You' : 'StoryBot'}
                </div>
                <div className={`chat-bubble ${log.role === 'user' ? 'chat-bubble-primary' : 'chat-bubble-secondary'}`}>
                  {log.content}
                </div>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !isLoading && sendMessage()}
              placeholder="Say something..."
              className="input input-bordered flex-1"
              disabled={isLoading}
            />
            <button
              onClick={sendMessage}
              className="btn btn-primary"
              disabled={isLoading || !message}
            >
              {isLoading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Student;
