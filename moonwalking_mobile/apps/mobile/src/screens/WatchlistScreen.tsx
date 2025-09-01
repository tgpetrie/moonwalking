
import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet } from 'react-native';
import { addWatch, removeWatch, getWatch } from '../api/queries';

export default function WatchlistScreen(){
  const [symbol, setSymbol] = useState('');
  const [list, setList] = useState<string[]>([]);

  const refresh = async ()=> {
    const data = await getWatch();
    setList(data.watchlist || []);
  };

  useEffect(()=>{ refresh(); }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.h1}>Watchlist</Text>
      <View style={{ flexDirection:'row', gap:8 }}>
        <TextInput style={styles.input} placeholder="SOL-USD" placeholderTextColor="#666" value={symbol} onChangeText={setSymbol} />
        <Button title="Add" onPress={async ()=>{ await addWatch(symbol.trim()); setSymbol(''); refresh(); }} />
      </View>
      <View style={{ marginTop: 16 }}>
        {list.map(s => (
          <View key={s} style={styles.row}>
            <Text style={styles.sym}>{s}</Text>
            <Button title="Remove" onPress={async ()=>{ await removeWatch(s); refresh(); }} />
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex:1, backgroundColor: '#0A0A0D', padding: 16 },
  h1: { color: '#FFF', fontSize: 24, fontWeight: '700', marginBottom: 12 },
  input: { flex:1, borderWidth: 1, borderColor:'#333', color:'#fff', padding:10, borderRadius:8 },
  row: { flexDirection:'row', alignItems:'center', justifyContent:'space-between', paddingVertical:10, borderBottomWidth:1, borderBottomColor:'#222' },
  sym: { color:'#FFF', fontWeight:'600' }
});
