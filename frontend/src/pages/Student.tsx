import React, { useState } from 'react';
import axios from 'axios';

interface Message {
  role: 'user' | 'bot';
  content: string;
}

const Student: React.FC = () => {
  const [chatLog, setChatLog] = useState<Message[]>([]);
  const [message, setMessage] = useState('');

  const sendMessage = async () => {
    if (!message) return;

    const newLog: Message[] = [...chatLog, { role: 'user', content: message }];
    setChatLog(newLog);
    setMessage('');

    try {
      const res = await axios.post('http://localhost:8000/student/chat', { message: message });
      setChatLog([...newLog, { role: 'bot', content: res.data.reply }]);
    } catch (err) {
      console.error("Chat failed", err);
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
