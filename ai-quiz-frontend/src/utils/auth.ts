import Taro from '@tarojs/taro'

import { ApiError, loginWithWechatCode } from './api'
import {
  CachedUser,
  getCachedUser,
  getStoredToken,
  setSession
} from './auth-storage'

let loginInFlight: Promise<CachedUser> | null = null

export async function ensureLogin(force = false): Promise<CachedUser> {
  const token = getStoredToken()
  const cachedUser = getCachedUser()
  if (!force && token && cachedUser) {
    return cachedUser
  }

  if (loginInFlight === null) {
    loginInFlight = loginWithWechat().finally(() => {
      loginInFlight = null
    })
  }

  return loginInFlight
}

/**
 * Run an authenticated request and recover from a session the backend no
 * longer accepts (rotated signing secret, expired token, or a token whose
 * user row is gone). The session is re-established with a fresh login and
 * the request is retried once instead of surfacing a load failure.
 */
export async function withSessionRecovery<T>(
  action: () => Promise<T>,
  retryOnStatusCodes: number[] = [401]
): Promise<T> {
  try {
    return await action()
  } catch (error) {
    const recoverable =
      error instanceof ApiError && retryOnStatusCodes.includes(error.statusCode)
    if (!recoverable) {
      throw error
    }

    await ensureLogin(true)
    return await action()
  }
}

export async function initializeSession(): Promise<void> {
  try {
    await ensureLogin()
  } catch (error) {
    console.warn('Automatic WeChat login failed:', error)
    Taro.showToast({
      title: '登录未完成，当前为匿名体验',
      icon: 'none'
    })
  }
}

async function loginWithWechat(): Promise<CachedUser> {
  const loginResult = await Taro.login()
  if (!loginResult.code) {
    throw new Error('微信未返回登录凭证')
  }

  const session = await loginWithWechatCode(loginResult.code)
  setSession(session.token, session.user)
  return session.user
}
