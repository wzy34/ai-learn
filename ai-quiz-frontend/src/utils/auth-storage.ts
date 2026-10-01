import Taro from '@tarojs/taro'

import { STORAGE_KEYS } from './storage'

export interface CachedUser {
  id: number
  nickname: string
  avatar_url: string
  total_xp: number
}

export function getStoredToken(): string {
  const token = Taro.getStorageSync(STORAGE_KEYS.TOKEN)
  return typeof token === 'string' ? token : ''
}

export function setSession(token: string, user: CachedUser): void {
  Taro.setStorageSync(STORAGE_KEYS.TOKEN, token)
  Taro.setStorageSync(STORAGE_KEYS.USER_INFO, user)
}

export function getCachedUser(): CachedUser | null {
  const user = Taro.getStorageSync(STORAGE_KEYS.USER_INFO)

  if (typeof user === 'object' && user !== null) {
    return user as CachedUser
  }

  if (typeof user !== 'string' || !user) {
    return null
  }

  try {
    return JSON.parse(user) as CachedUser
  } catch (error) {
    console.warn('Cached user data is invalid:', error)
    return null
  }
}

export function updateCachedUser(user: CachedUser): void {
  Taro.setStorageSync(STORAGE_KEYS.USER_INFO, user)
}

export function clearSession(): void {
  Taro.removeStorageSync(STORAGE_KEYS.TOKEN)
  Taro.removeStorageSync(STORAGE_KEYS.USER_INFO)
}
