import React, { useState, useRef, useEffect } from 'react';
import { Send, FileText, Brain, Loader2, MessageSquare, Network } from 'lucide-react';
import { api } from './api';
import GraphWidget from './GraphWidget';

const QAInterface = () => {
  const [messages, setMessages] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showGraph, setShowGraph] = useState(true);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!currentQuestion.trim() || isLoading) return;

    const question = currentQuestion.trim();
    setCurrentQuestion('');
    setIsLoading(true);

    // Add user message
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: question,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      // Call the API
      const response = await api.post('/ask', { question });
      
      // Add AI response
      const aiMessage = {
        id: Date.now() + 1,
        type: 'assistant',
        content: response.answer,
        sources: response.sources,
        entities: response.sources?.top_chunks || [],
        timestamp: new Date()
      };
      setMessages(prev => [...prev, aiMessage]);

    } catch (error) {
      console.error('Error asking question:', error);
      const errorMessage = {
        id: Date.now() + 1,
        type: 'error',
        content: `Sorry, I encountered an error: ${error.message}`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExampleQuestion = (question) => {
    setCurrentQuestion(question);
  };

  const exampleQuestions = [
    "What is Acme Corporation?",
    "Who founded the company?",
    "What partnerships does the company have?",
    "What is the company's revenue?",
    "Who leads the AI research team?"
  ];

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Main Q&A Interface */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white shadow-sm border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Knowledge Assistant</h1>
              <p className="text-gray-600">Ask questions about your documents</p>
            </div>
            <button
              onClick={() => setShowGraph(!showGraph)}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 ${
                showGraph 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              <Network size={16} />
              Graph View
            </button>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <MessageSquare size={48} className="mx-auto text-gray-400 mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Welcome to your Knowledge Assistant
              </h3>
              <p className="text-gray-600 mb-6">
                Ask questions about your uploaded documents and I'll provide answers with sources.
              </p>
              
              {/* Example Questions */}
              <div className="max-w-2xl mx-auto">
                <p className="text-sm font-medium text-gray-700 mb-3">Try these example questions:</p>
                <div className="grid gap-2">
                  {exampleQuestions.map((question, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleExampleQuestion(question)}
                      className="p-3 text-left bg-white rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-6 max-w-4xl mx-auto">
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {isLoading && (
                <div className="flex items-center gap-3 text-gray-600">
                  <Loader2 size={20} className="animate-spin" />
                  <span>Thinking...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="bg-white border-t p-6">
          <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
            <div className="flex gap-4">
              <input
                type="text"
                value={currentQuestion}
                onChange={(e) => setCurrentQuestion(e.target.value)}
                placeholder="Ask a question about your documents..."
                disabled={isLoading}
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!currentQuestion.trim() || isLoading}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isLoading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Send size={16} />
                )}
                Ask
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Graph Widget Sidebar */}
      {showGraph && (
        <div className="w-96 bg-white shadow-lg border-l">
          <GraphWidget />
        </div>
      )}
    </div>
  );
};

// Message Bubble Component
const MessageBubble = ({ message }) => {
  if (message.type === 'user') {
    return (
      <div className="flex justify-end">
        <div className="bg-blue-600 text-white rounded-lg px-4 py-3 max-w-xs lg:max-w-md">
          <p>{message.content}</p>
          <p className="text-xs text-blue-100 mt-1">
            {message.timestamp.toLocaleTimeString()}
          </p>
        </div>
      </div>
    );
  }

  if (message.type === 'error') {
    return (
      <div className="flex justify-start">
        <div className="bg-red-100 text-red-800 rounded-lg px-4 py-3 max-w-xs lg:max-w-2xl">
          <p>{message.content}</p>
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div className="flex justify-start">
      <div className="bg-white rounded-lg shadow-sm border px-4 py-3 max-w-xs lg:max-w-2xl">
        <div className="flex items-center gap-2 mb-2">
          <Brain size={16} className="text-blue-600" />
          <span className="font-medium text-gray-900">Assistant</span>
        </div>
        
        <div className="prose prose-sm">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Sources */}
        {message.sources && (
          <div className="mt-4 pt-3 border-t border-gray-100">
            <h4 className="text-xs font-medium text-gray-700 mb-2">Sources</h4>
            <div className="space-y-1">
              {message.sources.top_chunks?.map((chunk, idx) => (
                <div key={idx} className="text-xs bg-gray-50 rounded p-2">
                  <div className="font-medium text-gray-800">{chunk.source}</div>
                  <div className="text-gray-600 truncate">{chunk.content}</div>
                </div>
              )) || (
                <div className="text-xs text-gray-600">
                  Found {message.sources.vector_matches || 0} relevant passages
                </div>
              )}
            </div>
          </div>
        )}

        <p className="text-xs text-gray-500 mt-2">
          {message.timestamp.toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
};

export default QAInterface;