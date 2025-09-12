import React, { useState, useEffect } from 'react';
import { fetchData, API_ENDPOINTS } from '../api';
import { FiLock, FiX } from 'react-icons/fi';
import ReactMarkdown from 'react-markdown';

const LearnPanel = ({ onClose, isPremium }) => {
  const [lessons, setLessons] = useState([]);
  const [selectedLesson, setSelectedLesson] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData(API_ENDPOINTS.learnLessons)
      .then(data => {
        setLessons(data.lessons || []);
        // Select the first non-premium lesson by default
        const firstFreeLesson = data.lessons.find(l => !l.premium);
        if (firstFreeLesson) {
          setSelectedLesson(firstFreeLesson);
        } else if (data.lessons.length > 0) {
          setSelectedLesson(data.lessons[0]);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleSelectLesson = (lesson) => {
    if (lesson.premium && !isPremium) {
      alert('Upgrade to Premium to access this lesson!');
      return;
    }
    setSelectedLesson(lesson);
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex justify-center items-center z-50 animate-fade-in-fast">
      <div className="bg-gray-900 border border-purple-800 rounded-2xl shadow-2xl w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden">
        <header className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-bold text-white">Learn Center</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <FiX size={24} />
          </button>
        </header>
        <div className="flex flex-grow overflow-y-auto">
          <aside className="w-1/3 border-r border-gray-700 p-4 overflow-y-auto">
            <nav>
              <ul>
                {loading && <li className="text-gray-400">Loading...</li>}
                {lessons.map(lesson => (
                  <li key={lesson.id}>
                    <button
                      onClick={() => handleSelectLesson(lesson)}
                      disabled={lesson.premium && !isPremium}
                      className={`w-full text-left px-3 py-2 rounded-md flex items-center justify-between ${selectedLesson?.id === lesson.id ? 'bg-purple-700/50' : 'hover:bg-gray-800'} disabled:opacity-60 disabled:cursor-not-allowed`}
                    >
                      <span>{lesson.title}</span>
                      {lesson.premium && <FiLock size={14} title="Premium Lesson" className={isPremium ? 'text-green-400' : 'text-yellow-400'} />}
                    </button>
                  </li>
                ))}
              </ul>
            </nav>
          </aside>
          <main className="w-2/3 p-6 overflow-y-auto prose prose-invert prose-sm max-w-none">
            {selectedLesson ? <ReactMarkdown>{selectedLesson.content}</ReactMarkdown> : <p>Select a lesson to begin.</p>}
          </main>
        </div>
      </div>
    </div>
  );
};

export default LearnPanel;
