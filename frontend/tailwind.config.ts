import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f8fafc',
          100: '#f1f5f9',
          300: '#cbd5e1',
          500: '#64748b',
          700: '#334155',
          900: '#1e293b',
          950: '#091426',
        },
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ba1a1a',
        surface: '#fbf8fa',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 2px 4px rgba(30, 41, 59, 0.05)',
        overlay: '0 10px 15px rgba(30, 41, 59, 0.1)',
      },
      borderRadius: {
        card: '0.75rem',
      },
    },
  },
  plugins: [],
} satisfies Config
