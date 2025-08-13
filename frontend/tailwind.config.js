export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Saira', 'sans-serif'], // Use Saira as the default sans-serif font
        mono: ['Saira', 'monospace'], // Use Saira for mono as well, or keep a monospace if needed
      },
      colors: {
        orange: '#FF6B00',
        blue: '#00BFFF',
        pink: '#FF69B4',
        purple: '#810996',
        teal: '#00C0A5',
        light: '#cccccc',
        dark: '#000000',
        'mid-dark': '#111111',
        'light-dark': '#1a1a1a',
        muted: '#888888',
      },
      keyframes: {
        marquee: {
          '0%': { transform: 'translateX(0%)' },
          '100%': { transform: 'translateX(-100%)' }
        },
        scroll: {
          '0%': { transform: 'translateX(0%)' },
          '100%': { transform: 'translateX(-100%)' }
        },
        'fade-in-up': {
          '0%': { 
            opacity: '0', 
            transform: 'translateY(20px)' 
          },
          '100%': { 
            opacity: '1', 
            transform: 'translateY(0)' 
          }
        },
        breathing: {
          '0%, 100%': { 
            transform: 'scale(1)', 
            opacity: '1' 
          },
          '50%': { 
            transform: 'scale(1.05)', 
            opacity: '0.9' 
          }
        },
        gradient: {
          '0%': { 'background-position': '0% 50%' },
          '50%': { 'background-position': '100% 50%' },
          '100%': { 'background-position': '0% 50%' }
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' }
        },
        'pulse-glow': {
          '0%, 100%': { 'box-shadow': '0 0 5px rgba(168, 85, 247, 0.3)' },
          '50%': { 'box-shadow': '0 0 20px rgba(168, 85, 247, 0.6), 0 0 30px rgba(168, 85, 247, 0.4)' }
        },
        'shimmer': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' }
        },
        'bounce-subtle': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-4px)' }
        },
        'gradient-shift': {
          '0%': { 'background-position': '0% 50%' },
          '50%': { 'background-position': '100% 50%' },
          '100%': { 'background-position': '0% 50%' }
        }
      },
      animation: {
        marquee: 'marquee 7200s linear infinite',
        scroll: 'scroll 115200s linear infinite',
        'fade-in': 'fade-in 0.6s ease-out',
        'fade-in-up': 'fade-in-up 0.6s ease-out',
        breathing: 'breathing 3s ease-in-out infinite',
        gradient: 'gradient 3s ease infinite',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'shimmer': 'shimmer 1.5s ease-in-out infinite',
        'bounce-subtle': 'bounce-subtle 2s ease-in-out infinite',
        'gradient-shift': 'gradient-shift 3s ease infinite'
      }
    }
  },
  plugins: [
    function ({ addUtilities, theme }) {
      const newUtilities = {
        '.text-shadow-purple': {
          textShadow: `0 0 5px ${theme('colors.purple')}, 0 0 10px ${theme('colors.purple')}`,
        },
        '.text-shadow-light-purple': {
          textShadow: `0 0 2px ${theme('colors.purple')}, 0 0 5px ${theme('colors.purple')}`,
        },
        '.text-shadow-blue': {
          textShadow: `0 0 5px ${theme('colors.blue')}, 0 0 10px ${theme('colors.blue')}`,
        },
        '.text-shadow-orange': {
          textShadow: `0 0 5px ${theme('colors.orange')}, 0 0 10px ${theme('colors.orange')}`,
        },
        '.text-shadow-pink': {
          textShadow: `0 0 5px ${theme('colors.pink')}, 0 0 10px ${theme('colors.pink')}`,
        },
      };
      addUtilities(newUtilities, ['responsive', 'hover']);
    },
    function ({ addUtilities, theme }) {
      const colors = theme('colors');
      const newUtilities = {
        '.group-hover\\:radial-gradient-pink': {
          '--tw-gradient-from': `${colors.pink}10 var(--tw-gradient-from-position)`,
          '--tw-gradient-to': 'transparent var(--tw-gradient-to-position)',
          '--tw-gradient-stops': 'var(--tw-gradient-from), var(--tw-gradient-to)',
          backgroundImage: 'radial-gradient(circle at center, var(--tw-gradient-stops))',
        },
      };
      addUtilities(newUtilities, ['responsive', 'group-hover']);
    },
  ]
}