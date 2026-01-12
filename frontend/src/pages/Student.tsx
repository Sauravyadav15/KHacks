import React, { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import type { ChatContextType } from '../App';

interface Message {
  role: 'user' | 'bot';
  content: string;
  isWrong?: boolean;
}

const Student: React.FC = () => {
  // === USE PERSISTENT STATE FROM APP ===
  const { 
    chatLog, setChatLog, 
    threadId, setThreadId, 
    conversationId, setConversationId 
  } = useOutletContext<ChatContextType>();

  const [message, setMessage] = useState('');
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

    // Get auth token if available
    const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
    
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch('http://localhost:8000/student/chat', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: userMessage,
          thread_id: threadId,
          conversation_id: conversationId,
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
                if (data.conversation_id) {
                  setConversationId(data.conversation_id);
                }
              } else if (data.type === 'content') {
                accumulatedContent += data.content;
                
                // Update the bot message in real-time
                setChatLog(prevLog => {
                  const updatedLog = [...prevLog];
                  updatedLog[botMessageIndex] = { role: 'bot', content: accumulatedContent };
                  return updatedLog;
                });
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
    <div className="h-full flex flex-col max-w-4xl mx-auto p-4">
      <div className="card bg-base-200 shadow-xl flex-1 mb-4 overflow-hidden flex flex-col">
        <div className="card-body p-4 flex flex-col h-full">
          <h2 className="card-title text-primary mb-2">Story Chat</h2>
          
          <div className="flex-1 overflow-y-auto space-y-4 pr-2">
            {chatLog.length === 0 && (
                <div className="text-center text-gray-500 mt-10">
                    <p>Start a new story by saying hello!</p>
                </div>
            )}
            
            {chatLog.map((log, i) => (
              <div key={i} className={`chat ${log.role === 'user' ? 'chat-end' : 'chat-start'}`}>
                <div className="chat-header opacity-50 text-xs mb-1">
                  {log.role === 'user' ? 'You' : 'StoryBot'}
                </div>
                <div className={`chat-bubble ${
                  log.role === 'user' 
                    ? 'chat-bubble-primary' 
                    : log.isWrong 
                      ? 'chat-bubble-error' 
                      : 'chat-bubble-secondary'
                }`}>
                  {log.content}
                </div>
              </div>
            ))}
          </div>
        </div>
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
          className="btn btn-primary"
          onClick={sendMessage}
          disabled={isLoading}
        >
          {isLoading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
};

export default Student;
