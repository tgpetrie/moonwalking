
import React, { useEffect } from 'react';
import { ScrollView, Text, StyleSheet } from 'react-native';
import { useBundle } from '../api/queries';
import TopBanner from '../components/TopBanner';
import TableList from '../components/TableList';
import { registerPush } from '../notify/register';
import { theme } from '@moonwalking/core/src/index';

export default function HomeScreen(){
  const { data } = useBundle();
  useEffect(()=>{ registerPush(); }, []);
  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.h1}>Moonwalking</Text>
      <TopBanner items={data?.banner1h} />
      <TableList title="1m Gainers" items={data?.gainers1m} />
      <TableList title="3m Gainers" items={data?.gainers3m} />
      <TableList title="3m Losers" items={data?.losers3m} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { backgroundColor: theme.colors.bg },
  h1: { color: theme.colors.white, fontSize: 24, fontWeight: '700', marginBottom: 8 }
});
