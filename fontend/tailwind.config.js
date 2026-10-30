/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Design system màu cho AI Gia Sư Toán
        bg: {
          primary:   '#0d0f14',
          secondary: '#13161e',
          tertiary:  '#1a1e2a',
          panel:     '#151820',
        },
        accent: {
          DEFAULT: '#6C63FF',
          soft:    '#8b85ff',
          muted:   '#6C63FF22',
        },
        math: {
          green:  '#4ade80',
          blue:   '#60a5fa',
          yellow: '#fbbf24',
          red:    '#f87171',
          purple: '#c084fc',
        },
        border: {
          subtle: '#ffffff0f',
          dim:    '#ffffff1a',
          glow:   '#6C63FF33',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'fade-in':    'fadeIn 0.2s ease-out',
        'slide-up':   'slideUp 0.25s ease-out',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'typing':     'typing 1.2s steps(3) infinite',
      },
      keyframes: {
        fadeIn:    { from: { opacity: '0' },              to: { opacity: '1' } },
        slideUp:   { from: { transform: 'translateY(8px)', opacity: '0' }, to: { transform: 'translateY(0)', opacity: '1' } },
        pulseGlow: { '0%,100%': { boxShadow: '0 0 0 0 #6C63FF44' }, '50%': { boxShadow: '0 0 16px 4px #6C63FF44' } },
        typing:    { '0%': { content: '""' }, '33%': { content: '"."' }, '66%': { content: '".."' }, '100%': { content: '"..."' } },
      },
    },
  },
  plugins: [],
}
