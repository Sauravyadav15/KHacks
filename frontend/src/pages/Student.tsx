import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import type { ChatContextType } from '../App';

interface Message {
  role: 'user' | 'bot';
  content: string;
  isWrong?: boolean;
}

interface Lesson {
  id: number;
  name: string;
  category: string;
  uploaded_at: string;
  started: boolean;
  started_at: string | null;
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
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [lessonsLoading, setLessonsLoading] = useState(false);
  const [startingLesson, setStartingLesson] = useState<number | null>(null);

  // Fetch available lessons on mount
  useEffect(() => {
    fetchLessons();
  }, []);

  const fetchLessons = async () => {
    const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
    if (!token) return;

    setLessonsLoading(true);
    try {
      const response = await fetch('http://localhost:8000/student/available-lessons', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setLessons(data.lessons || []);
      }
    } catch (error) {
      console.error('Failed to fetch lessons:', error);
    } finally {
      setLessonsLoading(false);
    }
  };

  const handleStartLesson = async (lessonId: number) => {
    const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
    if (!token) {
      alert('Please log in to start a lesson');
      return;
    }

    setStartingLesson(lessonId);
    try {
      const response = await fetch(`http://localhost:8000/student/start-lesson/${lessonId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const result = await response.json();
        alert(result.message || 'Lesson started! You can now chat about this topic.');
        // Refresh lessons to update UI
        await fetchLessons();
      } else {
        const error = await response.json();
        alert('Failed to start lesson: ' + (error.detail || 'Unknown error'));
      }
    } catch (error) {
      console.error('Failed to start lesson:', error);
      alert('Network error: Failed to start lesson');
    } finally {
      setStartingLesson(null);
    }
  };

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
      let buffer = '';  // FIXED: Buffer for incomplete chunks

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          // FIXED: Accumulate chunks in buffer
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          
          // Keep the last incomplete line in buffer
          buffer = lines.pop() || '';

          for (const line of lines) {
            // FIXED: Add validation and error handling
            if (line.startsWith('data: ') && line.trim().length > 6) {
              try {
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;  // Skip empty data
                
                const data = JSON.parse(jsonStr);

                if (data.type === 'thread_id') {
                  setThreadId(data.thread_id);
                  if (data.conversation_id) {
                    setConversationId(data.conversation_id);
                  }
                } else if (data.type === 'content') {
                  accumulatedContent += data.content || '';
                  // Update the bot message in real-time
                  setChatLog(prevLog => {
                    const updatedLog = [...prevLog];
                    updatedLog[botMessageIndex] = { 
                      role: 'bot', 
                      content: accumulatedContent 
                    };
                    return updatedLog;
                  });
                } else if (data.type === 'done') {
                  if (data.thread_id) {
                    setThreadId(data.thread_id);
                  }
                } else if (data.type === 'error') {
                  console.error('Error from server:', data.error || data.content);
                  setChatLog(prevLog => {
                    const updatedLog = [...prevLog];
                    updatedLog[botMessageIndex] = { 
                      role: 'bot', 
                      content: `Error: ${data.error || data.content}` 
                    };
                    return updatedLog;
                  });
                } else if (data.type === 'status') {
                  // Optional: handle status messages
                  console.log('Status:', data.content);
                }
              } catch (parseError) {
                console.warn('Failed to parse SSE line:', line, parseError);
                // Continue processing other lines instead of breaking
              }
            }
          }
        }
      }
    } catch (err) {
      console.error('Chat failed', err);
      setChatLog(prevLog => {
        const updatedLog = [...prevLog];
        updatedLog[botMessageIndex] = { 
          role: 'bot', 
          content: 'Error: Failed to get response' 
        };
        return updatedLog;
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      {/* Lesson Selection Section */}
      {lessons.length > 0 && (
        <div className="mb-6">
          <h2 className="text-2xl font-bold mb-4">Available Lessons</h2>
          {lessonsLoading ? (
            <div className="text-center py-8">Loading lessons...</div>
          ) : lessons.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No lessons available yet. Your teacher will upload materials soon!
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {lessons.map((lesson) => (
                <div key={lesson.id} className="card bg-base-200 shadow-md">
                  <div className="card-body">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-2xl">{lesson.started ? '✅' : '📚'}</span>
                      <h3 className="card-title text-lg">{lesson.name}</h3>
                    </div>
                    
                    {lesson.category && (
                      <p className="text-sm text-gray-600">
                        Category: {lesson.category}
                      </p>
                    )}
                    
                    {lesson.started && lesson.started_at && (
                      <p className="text-xs text-gray-500">
                        Started: {new Date(lesson.started_at).toLocaleDateString()}
                      </p>
                    )}
                    
                    <div className="card-actions justify-end mt-4">
                      <button
                        onClick={() => {
                          if (lesson.started) {
                            // Just focus on chat input for continue
                            document.querySelector('input[type="text"]')?.focus();
                          } else {
                            handleStartLesson(lesson.id);
                          }
                        }}
                        disabled={startingLesson === lesson.id}
                        className="btn btn-primary btn-sm"
                      >
                        {startingLesson === lesson.id ? (
                          <span className="loading loading-spinner loading-sm"></span>
                        ) : lesson.started ? (
                          'Continue'
                        ) : (
                          'Start Learning'
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Chat Section */}
      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h2 className="card-title text-2xl mb-4">Story Chat</h2>
          
          <div className="h-96 overflow-y-auto mb-4 p-4 bg-base-200 rounded-lg">
            {chatLog.length === 0 && (
              <div className="text-center text-gray-500 py-8">
                Start a new story by saying hello!
              </div>
            )}
            
            {chatLog.map((log, i) => (
              <div
                key={i}
                className={`chat ${log.role === 'user' ? 'chat-end' : 'chat-start'}`}
              >
                <div className="chat-header mb-1">
                  {log.role === 'user' ? 'You' : 'StoryBot'}
                </div>
                <div className={`chat-bubble ${log.role === 'user' ? 'chat-bubble-primary' : ''}`}>
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
              disabled={isLoading || !message}
              className="btn btn-primary"
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
