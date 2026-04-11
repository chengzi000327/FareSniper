import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#1B2B5E',
          light: '#2D3F7A',
          muted: '#4A5F9E',
          50: '#EEF1F9',
        },
        signal: {
          DEFAULT: '#22C55E',
          muted: '#DCFCE7',
          text: '#166534',
        },
        bg: {
          gray: '#F5F6F8',
        },
      },
      fontFamily: {
        heading: ['var(--font-heading)', 'Georgia', 'serif'],
        sans: ['var(--font-sans)', '"PingFang SC"', '"Hiragino Sans GB"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'monospace'],
      },
      boxShadow: {
        card: '0 4px 24px -4px rgba(27,43,94,0.10)',
        'card-hover': '0 12px 40px -8px rgba(27,43,94,0.18)',
        'card-float': '0 24px 64px -12px rgba(27,43,94,0.24)',
      },
      keyframes: {
        floatUp: {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGlow: {
          '0%,100%': { boxShadow: '0 0 0 0 rgba(34,197,94,0.3)' },
          '50%': { boxShadow: '0 0 0 6px rgba(34,197,94,0)' },
        },
        driftA: {
          '0%,100%': { transform: 'translateY(0px) rotate(-6deg)' },
          '50%': { transform: 'translateY(-10px) rotate(-6deg)' },
        },
        driftB: {
          '0%,100%': { transform: 'translateY(0px) rotate(4deg)' },
          '50%': { transform: 'translateY(-8px) rotate(4deg)' },
        },
        driftC: {
          '0%,100%': { transform: 'translateY(0px) rotate(3deg)' },
          '50%': { transform: 'translateY(-12px) rotate(3deg)' },
        },
        driftD: {
          '0%,100%': { transform: 'translateY(0px) rotate(-4deg)' },
          '50%': { transform: 'translateY(-6px) rotate(-4deg)' },
        },
      },
      animation: {
        'float-up': 'floatUp 0.5s ease-out forwards',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'drift-a': 'driftA 7s ease-in-out infinite',
        'drift-b': 'driftB 8s ease-in-out infinite 1s',
        'drift-c': 'driftC 6s ease-in-out infinite 0.5s',
        'drift-d': 'driftD 9s ease-in-out infinite 2s',
      },
    },
  },
  plugins: [],
}

export default config
