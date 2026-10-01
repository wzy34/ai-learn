import Taro from '@tarojs/taro'

import {
  CachedUser,
  clearSession,
  getStoredToken
} from './auth-storage'

const API_BASE_URL = 'http://localhost:8000'

type RequestMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

interface ApiEnvelope<T> {
  code: number
  message: string
  data: T | null
}

interface RequestOptions {
  method?: RequestMethod
  data?: unknown
  headers?: Record<string, string>
  skipAuthentication?: boolean
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly statusCode: number
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function isApiEnvelope<T>(value: unknown): value is ApiEnvelope<T> {
  return (
    typeof value === 'object' &&
    value !== null &&
    'code' in value &&
    'message' in value &&
    'data' in value
  )
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = payload.detail
    if (typeof detail === 'string') {
      return detail
    }
    if (
      typeof detail === 'object' &&
      detail !== null &&
      'message' in detail &&
      typeof detail.message === 'string'
    ) {
      return detail.message
    }
  }

  if (
    typeof payload === 'object' &&
    payload !== null &&
    'message' in payload &&
    typeof payload.message === 'string'
  ) {
    return payload.message
  }

  return fallback
}

export async function request<T>(
  url: string,
  options: RequestOptions = {}
): Promise<T> {
  const token = options.skipAuthentication ? '' : getStoredToken()
  const response = await Taro.request<unknown>({
    url: `${API_BASE_URL}${url}`,
    method: options.method || 'GET',
    data: options.data,
    header: {
      'content-type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  })

  if (response.statusCode < 200 || response.statusCode >= 300) {
    if (response.statusCode === 401 && !options.skipAuthentication) {
      // The token is no longer trusted; drop it so the next login is fresh.
      // Callers wrapped in withSessionRecovery re-login and retry transparently.
      clearSession()
    }

    throw new ApiError(
      extractErrorMessage(response.data, '请求失败，请稍后重试'),
      response.statusCode
    )
  }

  if (isApiEnvelope<T>(response.data)) {
    if (response.data.code !== 0 || response.data.data === null) {
      throw new ApiError(response.data.message || '请求失败，请稍后重试', response.statusCode)
    }
    return response.data.data
  }

  return response.data as T
}

export interface QuizQuestion {
  id: string
  type: 'single' | 'multiple' | 'judge'
  stem: string
  options: Array<{ key: string; text: string }>
  answer: string[]
  explanation: string
  knowledge_point: string
  difficulty: 'easy' | 'medium' | 'hard'
}

export interface GenerateQuizRequest {
  user_input: string
  question_count?: number
  difficulty?: 'easy' | 'medium' | 'hard' | 'mixed'
}

export interface QuizSource {
  title: string
  url: string
}

export interface QuizData {
  quiz_id: string
  title: string
  summary: string
  questions: QuizQuestion[]
  /** Generation-time retrieval metadata; absent on history/resumed quizzes. */
  search_used?: boolean
  sources?: QuizSource[]
}

export async function generateQuiz(params: GenerateQuizRequest): Promise<QuizData> {
  return request<QuizData>('/api/v1/quiz/generate', {
    method: 'POST',
    data: params
  })
}

export interface DrillQuizRequest {
  focus?: string
  question_count?: number
}

export async function generateDrillQuiz(params: DrillQuizRequest = {}): Promise<QuizData> {
  return request<QuizData>('/api/v1/quiz/drill', {
    method: 'POST',
    data: params
  })
}

export interface AnswerRecord {
  question_id: string
  selected_answers: string[]
  is_correct: boolean
  duration_ms: number
}

export interface LearningReport {
  accuracy: number
  mastered_points: string[]
  weak_points: string[]
  three_line_summary: string[]
  advice: string[]
  share_quote: string
}

export interface GenerateReportRequest {
  quiz_id: string
  topic: string
  questions: QuizQuestion[]
  answer_records: AnswerRecord[]
}

export async function generateReport(
  params: GenerateReportRequest
): Promise<LearningReport> {
  return request<LearningReport>('/api/v1/report/generate', {
    method: 'POST',
    data: params
  })
}

export interface LoginResponse {
  token: string
  user: CachedUser
}

export async function loginWithWechatCode(code: string): Promise<LoginResponse> {
  return request<LoginResponse>('/api/v1/user/login', {
    method: 'POST',
    data: { code },
    skipAuthentication: true
  })
}

export interface UserProfile extends CachedUser {
  quiz_count: number
  correct_count: number
  average_accuracy: number
}

export interface UpdateProfileRequest {
  nickname?: string
  avatar_url?: string
}

export interface QuizHistoryItem {
  quiz_id: string
  title: string
  accuracy: number
  question_count: number
  created_at: string
}

export interface QuizHistoryPage {
  items: QuizHistoryItem[]
  total: number
  page: number
  page_size: number
}

export interface QuizHistoryDetail extends QuizData {
  answer_records: AnswerRecord[]
  report: LearningReport
  created_at: string
}

export async function getUserProfile(): Promise<UserProfile> {
  return request<UserProfile>('/api/v1/user/profile')
}

export async function updateUserProfile(
  params: UpdateProfileRequest
): Promise<UserProfile> {
  return request<UserProfile>('/api/v1/user/profile', {
    method: 'PUT',
    data: params
  })
}

/**
 * Upload a locally chosen avatar image (e.g. the temporary path returned by
 * the chooseAvatar capability) and persist it as the caller's avatar.
 */
export async function uploadUserAvatar(filePath: string): Promise<UserProfile> {
  const token = getStoredToken()
  const response = await Taro.uploadFile({
    url: `${API_BASE_URL}/api/v1/user/avatar`,
    filePath,
    name: 'file',
    header: token ? { Authorization: `Bearer ${token}` } : {}
  })

  if (response.statusCode === 401) {
    // Same contract as request(): drop the rejected token so
    // withSessionRecovery can re-login and retry transparently.
    clearSession()
  }

  if (response.statusCode < 200 || response.statusCode >= 300) {
    throw new ApiError(
      extractErrorMessage(parseUploadPayload(response.data), '头像上传失败，请稍后重试'),
      response.statusCode
    )
  }

  const payload = parseUploadPayload(response.data)
  if (isApiEnvelope<UserProfile>(payload)) {
    if (payload.code !== 0 || payload.data === null) {
      throw new ApiError(
        payload.message || '头像上传失败，请稍后重试',
        response.statusCode
      )
    }
    return payload.data
  }

  throw new ApiError('头像上传失败，请稍后重试', response.statusCode)
}

function parseUploadPayload(data: string): unknown {
  try {
    return JSON.parse(data)
  } catch (error) {
    return null
  }
}

export async function getQuizHistory(
  page = 1,
  pageSize = 10
): Promise<QuizHistoryPage> {
  return request<QuizHistoryPage>(
    `/api/v1/user/quizzes?page=${page}&page_size=${pageSize}`
  )
}

export async function getQuizHistoryDetail(
  quizId: string
): Promise<QuizHistoryDetail> {
  return request<QuizHistoryDetail>(`/api/v1/user/quizzes/${encodeURIComponent(quizId)}`)
}

export interface UnfinishedQuizItem {
  quiz_id: string
  title: string
  question_count: number
  created_at: string
}

export interface UnfinishedQuizList {
  items: UnfinishedQuizItem[]
}

export interface WeakPointStat {
  point: string
  count: number
  last_seen_at: string
}

export interface WeakPointSummary {
  items: WeakPointStat[]
  total_reports: number
}

export async function getUnfinishedQuizzes(limit = 20): Promise<UnfinishedQuizList> {
  return request<UnfinishedQuizList>(`/api/v1/user/quizzes/unfinished?limit=${limit}`)
}

export async function getWeakPoints(): Promise<WeakPointSummary> {
  return request<WeakPointSummary>('/api/v1/user/weak-points')
}

export async function getQuizSession(quizId: string): Promise<QuizData> {
  return request<QuizData>(`/api/v1/user/quizzes/${encodeURIComponent(quizId)}/resume`)
}

export async function healthCheck(): Promise<{ status: string }> {
  return request('/api/v1/health', { skipAuthentication: true })
}
