
import React from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { theme, fmtPct } from '@moonwalking/core/src/index';

export default function TableList({ title, items }:{ title:string, items?: any[] }){
  return (
    <View style={{ marginTop: 16 }}>
      <Text style={styles.title}>{title}</Text>
      <View style={styles.table}>
        {items?.length ? items.map((r, idx)=> (
          <Pressable key={r.symbol + idx} style={({pressed})=>[styles.row, pressed && styles.rowPressed]}>
            <Text style={styles.sym}>{r.symbol}</Text>
            <Text style={(r.changePct1m ?? r.changePct3m) >= 0 ? styles.pctUp : styles.pctDown}>
              {fmtPct(r.changePct1m ?? r.changePct3m)}
            </Text>
          </Pressable>
        )) : <Text style={styles.muted}>No data</Text>}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  title: { color: theme.colors.gray, fontSize: 14, marginBottom: 6 },
  table: { borderTopWidth:1, borderTopColor: theme.colors.line },
  row: { flexDirection:'row', justifyContent:'space-between', paddingVertical:10, borderBottomWidth:1, borderBottomColor: theme.colors.line },
  rowPressed: { backgroundColor: 'rgba(255,255,255,0.03)' },
  sym: { color: theme.colors.white, fontWeight:'600' },
  pctUp: { color: theme.colors.orange, fontWeight:'700' },
  pctDown: { color: theme.colors.pink, fontWeight:'700' },
  muted: { color: theme.colors.gray, paddingVertical:10 }
});
