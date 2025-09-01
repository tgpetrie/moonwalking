
import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { theme, fmtPct, fmtPrice } from '@moonwalking/core/src/index';

export default function TopBanner({ items }:{ items?: any[] }){
  if (!items?.length) return null;
  return (
    <View style={styles.wrap}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 8 }}>
        {items.map((r)=> (
          <View key={r.symbol} style={styles.pill}>
            <Text style={styles.sym}>{r.symbol}</Text>
            <Text style={styles.meta}>{fmtPrice(r.price)} • {fmtPct(r.changePct1h)}</Text>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingVertical: 8, borderBottomWidth:1, borderBottomColor: theme.colors.line },
  pill: { paddingHorizontal:12, paddingVertical:8, backgroundColor: theme.colors.surface, borderRadius: 999, marginRight:8 },
  sym: { color: theme.colors.white, fontWeight:'700' },
  meta: { color: theme.colors.gray, marginTop:2, fontSize:12 }
});
