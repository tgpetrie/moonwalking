// TEMP: Log Vite env variables for Supabase at runtime
console.log('[DEBUG] VITE_SUPABASE_URL:', import.meta.env.VITE_SUPABASE_URL);
console.log('[DEBUG] VITE_SUPABASE_ANON_KEY:', import.meta.env.VITE_SUPABASE_ANON_KEY);

// ...existing code...
import { createClient } from '@supabase/supabase-js';

// API configuration for BHABIT CB4
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001';

// ...existing code...
