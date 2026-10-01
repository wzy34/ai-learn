import Taro from '@tarojs/taro'

// Storage keys
export const STORAGE_KEYS = {
  TOKEN: 'token',
  USER_INFO: 'user_info',
  QUIZ_HISTORY: 'quiz_history',
  REPORT_CACHE: 'report_cache',
  COINS: 'coins'
}

// Generic storage helpers
export const storage = {
  get<T>(key: string): T | null {
    try {
      const value = Taro.getStorageSync(key)
      return value ? JSON.parse(value) : null
    } catch (error) {
      console.error(`Storage get error for key ${key}:`, error)
      return null
    }
  },

  set<T>(key: string, value: T): boolean {
    try {
      Taro.setStorageSync(key, JSON.stringify(value))
      return true
    } catch (error) {
      console.error(`Storage set error for key ${key}:`, error)
      return false
    }
  },

  remove(key: string): void {
    Taro.removeStorageSync(key)
  },

  clear(): void {
    Taro.clearStorageSync()
  }
}

// Quiz history management
export const quizHistory = {
  add(record: QuizRecord): void {
    const history = storage.get<QuizRecord[]>(STORAGE_KEYS.QUIZ_HISTORY) || []
    history.unshift(record)
    // Keep only last 100 records
    if (history.length > 100) {
      history.pop()
    }
    storage.set(STORAGE_KEYS.QUIZ_HISTORY, history)
  },

  getAll(): QuizRecord[] {
    return storage.get<QuizRecord[]>(STORAGE_KEYS.QUIZ_HISTORY) || []
  },

  clear(): void {
    storage.remove(STORAGE_KEYS.QUIZ_HISTORY)
  }
}

// Coins management
export const coins = {
  get(): number {
    return storage.get<number>(STORAGE_KEYS.COINS) || 0
  },

  set(amount: number): void {
    storage.set(STORAGE_KEYS.COINS, amount)
  },

  add(amount: number): void {
    const current = this.get()
    this.set(current + amount)
  }
}

// Types
export interface QuizRecord {
  id: string
  topic: string
  completedAt: string
  accuracy: number
  totalQuestions: number
  correctAnswers: number
  duration: number
}
