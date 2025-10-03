import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import Constants from 'expo-constants'
import { useSession } from '../state/useSession'
import { theme } from '@moonwalking/core/src/index'

export default function SettingsScreen() {
  const { pro } = useSession()
  return (
    <View style={styles.container}>
      <Text style={styles.h1}>Settings</Text>
      <Text style={styles.label}>API: {Constants.expoConfig?.extra?.API_BASE}</Text>
      <Text style={styles.label}>Pro: {pro ? 'Yes' : 'No'}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.bg, padding: 16 },
  h1: { color: theme.colors.white, fontSize: 24, fontWeight: '700', marginBottom: 12 },
  label: { color: theme.colors.gray, marginTop: 6 },
})
