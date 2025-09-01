
import React, { useEffect, useState } from 'react';
import { ScrollView, Text, StyleSheet } from 'react-native';
import Markdown from 'react-native-markdown-display';
import { theme } from '@moonwalking/core/src/index';

export default function LearnLessonScreen({ route }: any){
  const { title, file } = route.params || {};
  const [content, setContent] = useState<string>('');

  useEffect(()=>{
    // @ts-ignore — Metro will serve the asset; in dev builds this works out-of-the-box
    fetch(file).then(r=>r.text()).then(setContent).catch(()=>setContent('# Unable to load lesson'));
  }, [file]);

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding:16 }}>
      <Text style={styles.title}>{title || 'Lesson'}</Text>
      <Markdown style={mdStyles}>{content}</Markdown>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { backgroundColor: theme.colors.bg },
  title: { color: theme.colors.white, fontSize:22, fontWeight:'800', marginBottom: 12 }
});

const mdStyles = {
  body: { color: '#E5E7EB', fontSize: 16, lineHeight: 22 },
  heading1: { color: '#FFFFFF' },
  heading2: { color: '#FFFFFF' },
  code_block: { backgroundColor: 'rgba(255,255,255,0.06)', padding: 10, borderRadius: 8 }
} as any;
