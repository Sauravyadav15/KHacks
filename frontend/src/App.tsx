import React, { useState } from 'react';
import axios from 'axios';

const App: React.FC = () => {
  const [message, setMessage] = useState('');
  const [chatLog, setChatLog] = useState<{ role: string; content: string }[]>([]);
  const [file, setFile] = useState<File | null>(null);

  // 1. Test File Upload (Teacher Role)
  const handleFileUpload = async () => {
    if (!file) return alert("Select a file first!");
    const formData = new FormData();
    formData.append('file', file);

    try {
      await axios.post('http://localhost:8000/upload-lesson', formData);
      alert("Lesson uploaded to Backboard!");
    } catch (err) {
      console.error("Upload failed", err);
    }
  };

  // 2. Test Story Chat (Kid Role)
  const sendMessage = async () => {
    if (!message) return;
    const newLog = [...chatLog, { role: 'user', content: message }];
    setChatLog(newLog);
    setMessage('');

    try {
      const res = await axios.post('http://localhost:8000/chat', { text: message });
      setChatLog([...newLog, { role: 'bot', content: res.data.reply }]);
    } catch (err) {
      console.error("Chat failed", err);
    }
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h2>KingHacks: Storyteller Test Bench</h2>
      
      {/* Teacher Section */}
      <div style={{ border: '1px solid #ccc', padding: '10px', marginBottom: '20px' }}>
        <h3>Teacher: Upload Lesson</h3>
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <button onClick={handleFileUpload}>Upload to Backboard</button>
      </div>

      {/* Chat Section */}
      <div style={{ border: '1px solid #ccc', padding: '10px' }}>
        <h3>Kid: Story Chat</h3>
        <div style={{ height: '200px', overflowY: 'scroll', background: '#f9f9f9', marginBottom: '10px' }}>
          {chatLog.map((log, i) => (
            <p key={i}><strong>{log.role}:</strong> {log.content}</p>
          ))}
        </div>
        <input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Say something..." />
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
};

export default App;