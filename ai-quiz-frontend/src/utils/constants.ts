// Design System Constants
export const COLORS = {
  // Primary
  orange: '#ff7a2f',
  orangeDeep: '#df5f1f',
  orangeSoft: '#fff1e6',
  orangeCard: '#fff6ef',

  // Secondary
  green: '#2e9e71',
  greenSoft: '#eff9f3',
  blue: '#4b9dff',
  blueSoft: '#ebf4ff',
  coral: '#ff725f',

  // Neutral
  bg: '#f6f4ef',
  panel: 'rgba(255, 255, 255, 0.92)',
  text: '#1f2d37',
  muted: '#6c7b87',
  line: '#ecdccc',

  // Status
  success: '#2e9e71',
  warning: '#ff7a2f',
  error: '#ff725f',
  info: '#4b9dff'
}

export const SPACING = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  '2xl': 26,
  '3xl': 32
}

export const BORDER_RADIUS = {
  sm: 10,
  md: 14,
  lg: 16,
  xl: 18,
  '2xl': 22,
  full: 999
}

export const FONT_SIZES = {
  xs: 11,
  sm: 12,
  base: 13,
  md: 14,
  lg: 16,
  xl: 20,
  '2xl': 24,
  '3xl': 30
}

export const FONT_WEIGHTS = {
  normal: 400,
  medium: 500,
  bold: 700,
  heavy: 800
}

// Quiz Configuration
export const QUIZ_CONFIG = {
  defaultQuestionCount: 5,
  defaultDifficulty: 'mixed' as const,
  questionTypes: {
    single: '单选题',
    multiple: '多选题',
    judge: '判断题'
  },
  difficulties: {
    easy: '简单',
    medium: '中等',
    hard: '困难'
  },
  rewards: {
    correct: 10,
    wrong: 0
  }
}

// Animation Duration
export const ANIMATION_DURATION = {
  fast: 150,
  base: 300,
  slow: 500
}
