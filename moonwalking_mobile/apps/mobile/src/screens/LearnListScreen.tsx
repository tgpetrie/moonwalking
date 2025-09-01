
import React from 'react';
import { ScrollView, Text, StyleSheet, Pressable } from 'react-native';
import { theme } from '@moonwalking/core/src/index';

const lessons = [
  { id: 'intro-momentum', title: 'Reading Momentum Tables', file: require('../lessons/intro-momentum.md') },
  { id: 'vol-z', title: 'What is Volume Z-Score?', file: require('../lessons/vol-z.md') },
];

export default function LearnListScreen({ navigation }: any){
  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.h1}>Learn</Text>
      {lessons.map(l => (
        <Pressable key={l.id} style={({pressed})=>[styles.card, pressed && styles.cardP]} onPress={()=>navigation.navigate('Lesson', { title: l.title, file: l.file })}>
          <Text style={styles.ttl}>{l.title}</Text>
          <Text style={styles.meta}>~3 min</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { backgroundColor: theme.colors.bg },
  h1: { color: theme.colors.white, fontSize: 24, fontWeight: '700', marginBottom: 8 },
  card: { padding: 14, borderWidth:1, borderColor: theme.colors.line, borderRadius: 12, marginTop: 10 },
  cardP: { backgroundColor: 'rgba(255,255,255,0.03)' },
  ttl: { color: theme.colors.white, fontSize: 16, fontWeight: '700' },
  meta: { color: theme.colors.gray, marginTop: 4 }
});
