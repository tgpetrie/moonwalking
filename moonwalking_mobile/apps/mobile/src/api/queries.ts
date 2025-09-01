
import { useQuery } from '@tanstack/react-query';
import client from './client';

export function useBundle(){
  return useQuery({
    queryKey: ['bundle'],
    queryFn: async ()=> (await client.get('/data')).data,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });
}

export function useSignals(enabled:boolean){
  return useQuery({
    enabled,
    queryKey: ['signals'],
    queryFn: async ()=> (await client.get('/signals/pumpdump')).data,
    refetchInterval: 10_000,
    staleTime: 8_000,
  });
}

export function useSentiment(symbols: string[], enabled:boolean){
  return useQuery({
    enabled,
    queryKey: ['sentiment', symbols.sort().join(',')],
    queryFn: async ()=> (await client.get('/sentiment', { params: { symbols: symbols.join(',') } })).data,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export async function addWatch(symbol: string){
  return (await client.post('/watchlist/add', { symbol })).data;
}
export async function removeWatch(symbol: string){
  return (await client.post('/watchlist/remove', { symbol })).data;
}
export async function getWatch(){
  return (await client.get('/watchlist')).data;
}
