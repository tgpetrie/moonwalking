import React, { useEffect } from 'react'
import { ScrollView, View, Text, StyleSheet, Button } from 'react-native'
import { useSignals } from '../api/queries'
import { useSession } from '../state/useSession'
import { theme } from '@moonwalking/core/src/index'

export default function ProSignalsScreen() {
  const { init, pro, purchasePro, initialized } = useSession()
  useEffect(() => {
    init()
  }, [])
  const { data } = useSignals(!!pro)

  if (!initialized) {
    return (
      <View style={styles.container}>
        <Text style={styles.muted}>Loading…</Text>
      </View>
    )
  }
  if (!pro) {
    return (
      <View style={styles.container}>
        <Text style={styles.h1}>Moonwalking Pro</Text>
        <Text style={styles.muted}>Unlock pump/dump indicators and notifications.</Text>
        <Button title="Upgrade" onPress={() => purchasePro()} />
      </View>
    )
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.h1}>Signals (Pro)</Text>
      {data?.length ? (
        data.map((s) => (
          <View key={s.symbol + s.ts} style={styles.card}>
            <Text style={styles.sym}>{s.symbol}</Text>
            <Text style={s.direction === 'PUMP' ? styles.pump : styles.dump}>
              {s.direction} — score {s.score.toFixed(2)}
            </Text>
            <Text style={styles.meta}>
              1m {s.pct_1m}% • 3m {s.pct_3m}% • vz {s.vol_z} • px {s.streak}
            </Text>
            {s.tags?.length ? <Text style={styles.tags}>{s.tags.join(' · ')}</Text> : null}
          </View>
        ))
      ) : (
        <Text style={styles.muted}>No signals</Text>
      )}
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.bg, padding: 16 },
  h1: { color: theme.colors.white, fontSize: 24, fontWeight: '700', marginBottom: 12 },
  card: { padding: 12, borderWidth: 1, borderColor: '#222', borderRadius: 12, marginTop: 12 },
  sym: { color: theme.colors.white, fontWeight: '700', fontSize: 16 },
  pump: { color: theme.colors.orange, fontWeight: '700' },
  dump: { color: theme.colors.pink, fontWeight: '700' },
  meta: { color: theme.colors.gray, marginTop: 4 },
  tags: { color: theme.colors.gray, marginTop: 4, fontStyle: 'italic' },
  muted: { color: theme.colors.gray },
})
