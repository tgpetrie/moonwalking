
import * as Notifications from 'expo-notifications';
import client from '../api/client';

export async function registerPush(){
  const perms = await Notifications.getPermissionsAsync();
  if (!perms.granted){
    const { status } = await Notifications.requestPermissionsAsync();
    if (status !== 'granted') return null;
  }
  const tok = await Notifications.getExpoPushTokenAsync();
  const token = tok.data;
  try { await client.post('/devices/register', { token }); } catch {}
  return token;
}
