import React, { useState } from 'react';
import axios from 'axios';

interface Message {
  role: 'user' | 'bot';
  content: string;
}

const Student: React.FC = () => {
  const [chatLog, setChatLog] = useState<Message[]>([]);
  const [message, setMessage] = useState('');
  // Add state to store the current thread ID
  const [threadId, setThreadId] = useState<string | null>(null);

  const sendMessage = async () => {
    if (!message) return;

    // Optimistic UI update
    const newLog: Message[] = [...chatLog, { role: 'user', content: message }];
    setChatLog(newLog);
    setMessage('');

    try {
      // Send message AND current thread_id to backend
      const res = await axios.post('http://localhost:8000/student/chat', { 
        message: message,
        thread_id: threadId // Send null for first message, actual ID for others
      });
      
      // Update with bot response
      setChatLog([...newLog, { role: 'bot', content: res.data.reply }]);
      
      // Save the thread ID for next time
      if (res.data.thread_id) {
        setThreadId(res.data.thread_id);
      }
      
    } catch (err) {
      console.error("Chat failed", err);
      // Optional: Add error message to chat log
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
              onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Say something..."
              className="input input-bordered flex-1"
            />
            <button onClick={sendMessage} className="btn btn-primary">
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Student;
