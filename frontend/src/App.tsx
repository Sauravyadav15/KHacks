import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// Define the shape of a chat message
interface Message {
  role: 'user' | 'bot';
  content: string;
}

const App: React.FC = () => {
  const [chatLog, setChatLog] = useState<Message[]>([]);
  const [message, setMessage] = useState('');
  const [file, setFile] = useState<File | null>(null);

  // FETCH HISTORY ON LOAD
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await axios.get('http://localhost:8000/chat');
        // Assuming backend returns an array of objects like { role: 'user', content: '...' }
        setChatLog(res.data); 
      } catch (err) {
        console.error("Failed to load history", err);
      }
    };
    fetchHistory();
  }, []); // Empty dependency array ensures this runs only once on mount

  // 1. Teacher Upload Logic
  const handleFileUpload = async () => {
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      await axios.post('http://localhost:8000/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      alert('File uploaded successfully!');
    } catch (err) {
      console.error("Upload failed", err);
      alert('Upload failed');
    }
  };

  // 2. Story Chat Logic
  const sendMessage = async () => {
    if (!message) return;

    // Optimistically update UI
    const newLog: Message[] = [...chatLog, { role: 'user', content: message }];
    setChatLog(newLog);
    setMessage('');

    try {
      const res = await axios.post('http://localhost:8000/student/chat', { message: message });
      // Update with actual bot response from backend
      setChatLog([...newLog, { role: 'bot', content: res.data.reply }]);
    } catch (err) {
      console.error("Chat failed", err);
      // Optional: Revert optimistic update on error if needed
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
        <div style={{ height: '200px', overflowY: 'scroll', background: '#f9f9f9', marginBottom: '10px', padding: '10px' }}>
          {chatLog.map((log, i) => (
            <p key={i} style={{ color: log.role === 'bot' ? 'blue' : 'black', margin: '5px 0' }}>
              <strong>{log.role === 'user' ? 'You' : 'StoryBot'}:</strong> {log.content}
            </p>
          ))}
        </div>
        <input 
          value={message} 
          onChange={(e) => setMessage(e.target.value)} 
          placeholder="Say something..." 
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          style={{ width: '70%', marginRight: '10px' }}
        />
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
};

export default App;
