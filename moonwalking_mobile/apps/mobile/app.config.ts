
import 'dotenv/config';
export default ({ config }) => ({
  ...config,
  name: 'Moonwalking',
  slug: 'moonwalking',
  ios: { bundleIdentifier: 'com.bhabit.moonwalking' },
  android: { package: 'com.bhabit.moonwalking' },
  extra: {
    API_BASE: process.env.API_BASE || 'http://127.0.0.1:8787',
    RC_IOS: process.env.RC_IOS || '',
    RC_ANDROID: process.env.RC_ANDROID || ''
  },
  updates: { enabled: true }
});
