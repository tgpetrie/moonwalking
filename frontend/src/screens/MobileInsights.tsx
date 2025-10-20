import React from 'react';
import SentimentCard from '../components/cards/SentimentCard';
import { InsightList } from '../components/insights/InsightCard';
import AskHabit from '../components/ask/AskHabit';
import LearningTracker from '../components/learn/LearningTracker';

export default function MobileInsights(): JSX.Element {
  return (
    <div className="p-3 max-w-screen-sm mx-auto grid gap-3">
      <SentimentCard />
      <InsightList />
      <AskHabit />
      <LearningTracker />
    </div>
  );
}
