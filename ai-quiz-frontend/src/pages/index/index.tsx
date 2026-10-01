import { Component } from 'react'
import { View, Text, Textarea, Button, ScrollView, Image, Input } from '@tarojs/components'
import Taro, { getCurrentInstance, navigateTo } from '@tarojs/taro'

import {
  generateDrillQuiz,
  generateQuiz,
  getQuizHistory,
  getUnfinishedQuizzes,
  getUserProfile,
  getWeakPoints,
  QuizHistoryItem,
  UnfinishedQuizItem,
  updateUserProfile,
  uploadUserAvatar,
  UserProfile,
  WeakPointSummary
} from '../../utils/api'
import { ensureLogin, withSessionRecovery } from '../../utils/auth'
import { getCachedUser, updateCachedUser } from '../../utils/auth-storage'
import { getCustomNavigationContentTopOffset } from '../../utils/layout'
import { QUIZ_TOPICS, QuizTopic } from '../../utils/topics'

import './index.scss'
// Profile styles are global in mini programs; the 我的 tab reuses them.
import '../profile/index.scss'

const HISTORY_PAGE_SIZE = 10
const BANK_PAGE_SIZE = 10

type HomeTab = '闯关' | '题库' | '我的'

interface IndexState {
  activeTab: HomeTab
  inputValue: string
  loading: boolean
  totalXp: number
  userName: string
  userAvatar: string
  completedQuizzes: QuizHistoryItem[]
  dashboardError: string
  errorMessage: string
  isInputFocused: boolean
  // 未完成关卡
  unfinishedQuizzes: UnfinishedQuizItem[]
  weakPoints: WeakPointSummary | null
  drillLoading: boolean
  // 题库 tab
  generatingTopicTitle: string
  bankQuizzes: QuizHistoryItem[]
  bankPage: number
  bankTotal: number
  bankLoading: boolean
  loadingMoreBank: boolean
  bankLoaded: boolean
  // 我的 tab
  profile: UserProfile | null
  profileLoading: boolean
  profileLoaded: boolean
  profileError: string
  histories: QuizHistoryItem[]
  historyPage: number
  historyTotal: number
  loadingMoreHistory: boolean
  savingNickname: boolean
  savingAvatar: boolean
  editingNickname: boolean
  nicknameDraft: string
}

export default class Index extends Component<{}, IndexState> {
  private readonly contentTopOffset = getCustomNavigationContentTopOffset()

  constructor(props: {}) {
    super(props)
    this.state = {
      activeTab: '闯关',
      inputValue: '',
      loading: false,
      totalXp: 0,
      userName: '学习者',
      userAvatar: '',
      completedQuizzes: [],
      dashboardError: '',
      errorMessage: '',
      isInputFocused: false,
      unfinishedQuizzes: [],
      weakPoints: null,
      drillLoading: false,
      generatingTopicTitle: '',
      bankQuizzes: [],
      bankPage: 1,
      bankTotal: 0,
      bankLoading: false,
      loadingMoreBank: false,
      bankLoaded: false,
      profile: null,
      profileLoading: false,
      profileLoaded: false,
      profileError: '',
      histories: [],
      historyPage: 1,
      historyTotal: 0,
      loadingMoreHistory: false,
      savingNickname: false,
      savingAvatar: false,
      editingNickname: false,
      nicknameDraft: ''
    }
  }

  componentDidMount() {
    // Deep-link support: other pages' tab bars reLaunch here with ?tab=bank|profile.
    const tab = getCurrentInstance()?.router?.params?.tab
    if (tab === 'bank') {
      this.handleTabClick('题库')
    } else if (tab === 'profile') {
      this.handleTabClick('我的')
    }
  }

  componentDidShow() {
    // Show the latest saved nickname/XP immediately, then refresh from the server.
    const cached = getCachedUser()
    if (cached) {
      this.setState({
        userName: cached.nickname,
        totalXp: cached.total_xp,
        userAvatar: cached.avatar_url || ''
      })
    }
    void this.loadUserDashboard()
    void this.loadLearningModules()
    if (this.state.bankLoaded) {
      void this.loadBankData()
    }
  }

  loadLearningModules = async () => {
    // Auxiliary section: a failed load only means an empty 未完成关卡 list,
    // so it must never break the dashboard above it.
    try {
      await ensureLogin()
      const [unfinished, weakPoints] = await withSessionRecovery(() =>
        Promise.all([getUnfinishedQuizzes(), getWeakPoints()])
      )
      this.setState({
        unfinishedQuizzes: unfinished.items,
        weakPoints
      })
    } catch (error) {
      console.warn('Failed to load unfinished quizzes or weak points:', error)
      this.setState({ unfinishedQuizzes: [], weakPoints: null })
    }
  }

  loadBankData = async () => {
    if (this.state.bankLoading) {
      return
    }

    this.setState({ bankLoading: true })
    try {
      await ensureLogin()
      const history = await withSessionRecovery(() =>
        getQuizHistory(1, BANK_PAGE_SIZE)
      )
      this.setState({
        bankQuizzes: history.items,
        bankPage: history.page,
        bankTotal: history.total,
        bankLoaded: true,
        bankLoading: false
      })
    } catch (error) {
      console.warn('Failed to load quiz bank:', error)
      this.setState({ bankLoading: false })
    }
  }

  handleLoadMoreBank = async () => {
    const { loadingMoreBank, bankPage, bankTotal, bankQuizzes } = this.state
    if (loadingMoreBank || bankQuizzes.length >= bankTotal) {
      return
    }

    this.setState({ loadingMoreBank: true })
    try {
      const nextPage = bankPage + 1
      const history = await withSessionRecovery(() =>
        getQuizHistory(nextPage, BANK_PAGE_SIZE)
      )
      this.setState({
        bankQuizzes: [...bankQuizzes, ...history.items],
        bankPage: history.page,
        bankTotal: history.total,
        loadingMoreBank: false
      })
    } catch (error) {
      console.error('Failed to load more bank quizzes:', error)
      this.setState({ loadingMoreBank: false })
      Taro.showToast({
        title: error instanceof Error ? error.message : '题库加载失败',
        icon: 'none'
      })
    }
  }

  loadUserDashboard = async () => {
    try {
      await ensureLogin()
      const [profile, history] = await withSessionRecovery(() =>
        Promise.all([getUserProfile(), getQuizHistory(1, 4)])
      )
      this.setState({
        userName: profile.nickname,
        totalXp: profile.total_xp,
        userAvatar: profile.avatar_url || '',
        completedQuizzes: history.items,
        dashboardError: ''
      })
    } catch (error) {
      console.warn('Failed to load user dashboard:', error)
      this.setState({
        dashboardError: '用户数据暂不可用，请稍后重试'
      })
    }
  }

  loadProfileData = async () => {
    this.setState({ profileLoading: true, profileError: '' })

    try {
      await ensureLogin()
      const [profile, history] = await withSessionRecovery(
        () =>
          Promise.all([getUserProfile(), getQuizHistory(1, HISTORY_PAGE_SIZE)]),
        // 404 means the token's user row is gone; a fresh login recreates it.
        [401, 404]
      )
      this.setState({
        profile,
        histories: history.items,
        historyPage: history.page,
        historyTotal: history.total,
        nicknameDraft: profile.nickname,
        profileLoading: false,
        profileLoaded: true,
        editingNickname: false,
        userName: profile.nickname,
        totalXp: profile.total_xp,
        userAvatar: profile.avatar_url || ''
      })
    } catch (error) {
      console.error('Failed to load user profile:', error)
      this.setState({
        profileLoading: false,
        profileError: error instanceof Error ? error.message : '用户数据加载失败'
      })
    }
  }

  handleInputChange = (event: { detail: { value: string } }) => {
    this.setState({
      inputValue: event.detail.value,
      errorMessage: ''
    })
  }

  handleInputFocus = () => {
    this.setState({ isInputFocused: true })
  }

  handleInputBlur = () => {
    this.setState({ isInputFocused: false })
  }

  handleGenerateQuiz = async () => {
    const { inputValue } = this.state

    if (!inputValue.trim()) {
      this.setState({ errorMessage: '请输入学习内容' })
      return
    }

    this.setState({ loading: true, errorMessage: '' })

    try {
      try {
        await ensureLogin()
      } catch (error) {
        console.warn('Quiz will be generated anonymously because login failed:', error)
      }

      const quizData = await generateQuiz({
        user_input: inputValue,
        question_count: 5,
        difficulty: 'mixed'
      })

      navigateTo({
        url: `/pages/quiz/index?quizData=${encodeURIComponent(JSON.stringify(quizData))}`
      })

      this.setState({ loading: false, inputValue: '' })
    } catch (error) {
      console.error('Generate quiz failed:', error)
      this.setState({
        errorMessage: error instanceof Error ? error.message : '生成失败，请稍后重试',
        loading: false
      })
    }
  }

  handleHistoryClick = (quizId: string) => {
    navigateTo({
      url: `/pages/report/index?quizId=${encodeURIComponent(quizId)}`
    })
  }

  handleResumeQuiz = (quizId: string) => {
    navigateTo({
      url: `/pages/quiz/index?quizId=${encodeURIComponent(quizId)}`
    })
  }

  navigateToQuiz = (quizData: unknown) => {
    navigateTo({
      url: `/pages/quiz/index?quizData=${encodeURIComponent(JSON.stringify(quizData))}`
    })
  }

  handleStartDrill = async () => {
    const { weakPoints, drillLoading } = this.state
    if (drillLoading) {
      return
    }
    const focus = weakPoints?.items[0]?.point
    if (!focus) {
      return
    }

    this.setState({ drillLoading: true })
    try {
      await ensureLogin()
      const quizData = await withSessionRecovery(() => generateDrillQuiz({ focus }))
      this.navigateToQuiz(quizData)
    } catch (error) {
      console.error('Generate drill quiz failed:', error)
      Taro.showToast({
        title: error instanceof Error ? error.message : '专项训练生成失败，请稍后重试',
        icon: 'none'
      })
    } finally {
      this.setState({ drillLoading: false })
    }
  }

  handleTopicClick = async (topic: QuizTopic) => {
    const { generatingTopicTitle, loading } = this.state
    if (generatingTopicTitle || loading) {
      return
    }

    this.setState({ generatingTopicTitle: topic.title })
    try {
      try {
        await ensureLogin()
      } catch (error) {
        console.warn('Quiz will be generated anonymously because login failed:', error)
      }

      const quizData = await generateQuiz({
        user_input: topic.prompt,
        question_count: 5,
        difficulty: 'mixed'
      })
      this.navigateToQuiz(quizData)
    } catch (error) {
      console.error('Generate topic quiz failed:', error)
      Taro.showToast({
        title: error instanceof Error ? error.message : '题目生成失败，请稍后重试',
        icon: 'none'
      })
    } finally {
      this.setState({ generatingTopicTitle: '' })
    }
  }

  handleTabClick = (tabName: HomeTab) => {
    // All three tabs are rendered inside this page, so switching never
    // creates a new page instance.
    this.setState({ activeTab: tabName })
    if (tabName === '题库' && !this.state.bankLoaded && !this.state.bankLoading) {
      void this.loadBankData()
    }
    if (tabName === '我的' && !this.state.profileLoaded && !this.state.profileLoading) {
      void this.loadProfileData()
    }
  }

  handleStartEditNickname = () => {
    const { profile } = this.state
    if (!profile) {
      return
    }

    this.setState({
      editingNickname: true,
      nicknameDraft: profile.nickname,
      profileError: ''
    })
  }

  handleNicknameChange = (event: { detail: { value: string } }) => {
    this.setState({ nicknameDraft: event.detail.value, profileError: '' })
  }

  handleCancelNicknameEdit = () => {
    const { profile } = this.state
    this.setState({
      editingNickname: false,
      nicknameDraft: profile?.nickname || '',
      profileError: ''
    })
  }

  handleSaveNickname = async () => {
    const nickname = this.state.nicknameDraft.trim()
    if (!nickname) {
      this.setState({ profileError: '昵称不能为空' })
      return
    }

    this.setState({ savingNickname: true, profileError: '' })
    try {
      const profile = await withSessionRecovery(() => updateUserProfile({ nickname }))
      updateCachedUser({
        id: profile.id,
        nickname: profile.nickname,
        avatar_url: profile.avatar_url,
        total_xp: profile.total_xp
      })
      this.setState({
        profile,
        nicknameDraft: profile.nickname,
        editingNickname: false,
        savingNickname: false,
        // Same page instance: the greeting/XP update the moment saving succeeds.
        userName: profile.nickname,
        totalXp: profile.total_xp
      })
    } catch (error) {
      console.error('Failed to update profile:', error)
      this.setState({
        savingNickname: false,
        profileError: error instanceof Error ? error.message : '昵称保存失败'
      })
    }
  }

  /**
   * The WeChat 头像昵称填写能力 hands us a temporary file for the picked
   * image ("用微信头像", album, or camera); upload it so the avatar survives
   * across sessions. The chosen image shows immediately while uploading.
   */
  handleChooseAvatar = async (event: { detail: { avatarUrl?: string } }) => {
    const avatarUrl = event.detail.avatarUrl
    const { profile } = this.state
    if (!avatarUrl || !profile || this.state.savingAvatar) {
      return
    }

    this.setState({
      savingAvatar: true,
      profileError: '',
      profile: { ...profile, avatar_url: avatarUrl }
    })
    try {
      const saved = await withSessionRecovery(() => uploadUserAvatar(avatarUrl))
      updateCachedUser({
        id: saved.id,
        nickname: saved.nickname,
        avatar_url: saved.avatar_url,
        total_xp: saved.total_xp
      })
      this.setState({
        profile: saved,
        savingAvatar: false,
        userAvatar: saved.avatar_url
      })
      Taro.showToast({ title: '头像已更新', icon: 'success' })
    } catch (error) {
      console.error('Failed to upload avatar:', error)
      this.setState({
        profile,
        savingAvatar: false,
        profileError: error instanceof Error ? error.message : '头像上传失败，请稍后重试'
      })
    }
  }

  handleLoadMoreHistory = async () => {
    const { loadingMoreHistory, historyPage, historyTotal, histories } = this.state
    if (loadingMoreHistory || histories.length >= historyTotal) {
      return
    }

    this.setState({ loadingMoreHistory: true })
    try {
      const nextPage = historyPage + 1
      const history = await withSessionRecovery(() =>
        getQuizHistory(nextPage, HISTORY_PAGE_SIZE)
      )
      this.setState({
        histories: [...histories, ...history.items],
        historyPage: history.page,
        historyTotal: history.total,
        loadingMoreHistory: false
      })
    } catch (error) {
      console.error('Failed to load more history:', error)
      this.setState({
        loadingMoreHistory: false,
        profileError: error instanceof Error ? error.message : '历史记录加载失败'
      })
    }
  }

  renderToolbar = () => {
    const { totalXp, userName, userAvatar } = this.state

    return (
      <View className="toolbar">
        <View className="hello-user">
          <View className="hello-avatar">
            {userAvatar ? (
              <Image className="hello-avatar-image" src={userAvatar} mode="aspectFill" />
            ) : (
              <Text>{userName.slice(0, 1)}</Text>
            )}
          </View>
          <Text>你好，{userName}</Text>
        </View>
        <View className="coin">
          <Text>{totalXp} XP</Text>
          <View className="coin-icon">🪙</View>
        </View>
      </View>
    )
  }

  render闯关Content = () => {
    const {
      inputValue,
      loading,
      completedQuizzes,
      unfinishedQuizzes,
      weakPoints,
      drillLoading,
      dashboardError,
      errorMessage,
      isInputFocused
    } = this.state
    const topWeakPoint = weakPoints?.items[0]

    return (
      <>
        {this.renderToolbar()}

        <Text className="page-title">今天想闯哪一关？</Text>

        <View className="quick-input">
          <View className="quick-input-head">
            <Text className="input-label">输入你想学的内容</Text>
            <View className="mini-mascot">🐟</View>
          </View>
          <View className={`input-surface ${isInputFocused ? 'focused' : ''}`}>
            <Textarea
              className="input-textarea"
              value={inputValue}
              onInput={this.handleInputChange}
              onFocus={this.handleInputFocus}
              onBlur={this.handleInputBlur}
              placeholder={'例如：RAG 和传统搜索有什么区别？\n我想顺便搞懂向量数据库是怎么配合工作的。\n最好通过闯关题帮我记住重点。'}
              placeholderStyle="color: #9a8f84;"
              disableDefaultPadding
              maxlength={5000}
            />
          </View>
          {errorMessage && <Text className="error-text">{errorMessage}</Text>}
          <View className="home-actions">
            <Button
              className="home-btn primary"
              onClick={this.handleGenerateQuiz}
              disabled={loading}
            >
              {loading ? '检索资料并生成中...' : '开始生成题目 →'}
            </Button>
          </View>
        </View>

        <Text className="list-title">已完成关卡</Text>
        {dashboardError ? (
          <Text className="dashboard-error">{dashboardError}</Text>
        ) : completedQuizzes.length > 0 ? (
          <View className="cards">
            {completedQuizzes.map((quiz) => (
              <View
                key={quiz.quiz_id}
                className="quiz-card"
                onClick={() => this.handleHistoryClick(quiz.quiz_id)}
              >
                <View className="quiz-dot">✓</View>
                <View className="quiz-body">
                  <Text className="quiz-name">{quiz.title}</Text>
                  <Text className="quiz-meta">
                    {quiz.question_count} 题 · 正确率 {Math.round(quiz.accuracy)}%
                  </Text>
                </View>
              </View>
            ))}
          </View>
        ) : (
          <View className="empty-history">
            <Text>完成一次闯关后，记录会出现在这里</Text>
          </View>
        )}

        <Text className="list-title">未完成关卡</Text>

        {topWeakPoint && (
          <View className="item" onClick={this.handleStartDrill}>
            <View className="avatar">🎯</View>
            <View className="item-content">
              <Text className="item-title">专项训练 · {topWeakPoint.point}</Text>
              <Text className="item-subtitle">
                AI 基于你近 {weakPoints!.total_reports} 次报告的薄弱点生成
              </Text>
            </View>
            <View className="item-action">{drillLoading ? '生成中' : '开始'}</View>
          </View>
        )}

        {unfinishedQuizzes.map((quiz) => (
          <View
            key={quiz.quiz_id}
            className="item"
            onClick={() => this.handleResumeQuiz(quiz.quiz_id)}
          >
            <View className="avatar">📖</View>
            <View className="item-content">
              <Text className="item-title">{quiz.title}</Text>
              <Text className="item-subtitle">
                {quiz.question_count} 题 · {quiz.created_at.slice(0, 10)}
              </Text>
            </View>
            <View className="item-action">继续</View>
          </View>
        ))}

        {!topWeakPoint && unfinishedQuizzes.length === 0 && (
          <View className="empty-history">
            <Text>暂无待完成的关卡，先生成一局题库吧</Text>
          </View>
        )}
      </>
    )
  }

  render题库Content = () => {
    const {
      unfinishedQuizzes,
      bankQuizzes,
      bankTotal,
      bankLoading,
      loadingMoreBank,
      generatingTopicTitle
    } = this.state

    return (
      <>
        {this.renderToolbar()}

        <Text className="page-title">所有题库</Text>

        <Text className="list-title">主题精选</Text>
        <View className="quiz-bank-list">
          {QUIZ_TOPICS.map((topic) => (
            <View
              key={topic.title}
              className="quiz-bank-item"
              onClick={() => this.handleTopicClick(topic)}
            >
              <View className="quiz-bank-icon">{topic.icon}</View>
              <View className="quiz-bank-info">
                <Text className="quiz-bank-title">{topic.title}</Text>
                <Text className="quiz-bank-meta">{topic.description}</Text>
              </View>
              <View className="quiz-bank-action">
                {generatingTopicTitle === topic.title ? '生成中' : '开始'}
              </View>
            </View>
          ))}
        </View>

        <Text className="list-title">我的题库</Text>
        {bankLoading && bankQuizzes.length === 0 ? (
          <View className="empty-history">
            <Text>正在加载题库...</Text>
          </View>
        ) : unfinishedQuizzes.length > 0 || bankQuizzes.length > 0 ? (
          <View className="quiz-bank-list">
            {unfinishedQuizzes.map((quiz) => (
              <View
                key={quiz.quiz_id}
                className="quiz-bank-item"
                onClick={() => this.handleResumeQuiz(quiz.quiz_id)}
              >
                <View className="quiz-bank-icon">📖</View>
                <View className="quiz-bank-info">
                  <Text className="quiz-bank-title">{quiz.title}</Text>
                  <Text className="quiz-bank-meta">
                    {quiz.question_count} 题 · 未完成
                  </Text>
                </View>
                <View className="quiz-bank-action">继续</View>
              </View>
            ))}
            {bankQuizzes.map((quiz) => {
              const accuracy = Math.round(quiz.accuracy)
              return (
                <View
                  key={quiz.quiz_id}
                  className="quiz-bank-item"
                  onClick={() => this.handleHistoryClick(quiz.quiz_id)}
                >
                  <View className="quiz-bank-icon">📚</View>
                  <View className="quiz-bank-info">
                    <Text className="quiz-bank-title">{quiz.title}</Text>
                    <Text className="quiz-bank-meta">
                      {quiz.question_count} 题 · 正确率 {accuracy}%
                    </Text>
                  </View>
                  <View className="quiz-bank-progress">
                    <View
                      className="progress-ring"
                      style={{
                        background: `conic-gradient(#47a4ff 0 ${accuracy}%, #ece7de ${accuracy}% 100%)`
                      }}
                    >
                      <Text>{accuracy}%</Text>
                    </View>
                  </View>
                </View>
              )
            })}
          </View>
        ) : (
          <View className="empty-history">
            <Text>生成过的题库会自动收进这里</Text>
          </View>
        )}

        {bankQuizzes.length < bankTotal && (
          <Button
            className="load-more-button"
            onClick={this.handleLoadMoreBank}
            disabled={loadingMoreBank}
          >
            {loadingMoreBank ? '加载中...' : '加载更多'}
          </Button>
        )}
      </>
    )
  }

  renderProfileAvatar = (profile: UserProfile) => {
    if (profile.avatar_url) {
      return (
        <Image
          className="profile-avatar-image"
          src={profile.avatar_url}
          mode="aspectFill"
        />
      )
    }

    return <Text>{profile.nickname.slice(0, 1)}</Text>
  }

  render我的Content = () => {
    const {
      profile,
      profileLoading,
      profileError,
      histories,
      historyTotal,
      loadingMoreHistory,
      savingNickname,
      savingAvatar,
      editingNickname,
      nicknameDraft
    } = this.state

    if (profileLoading && !profile) {
      return <View className="loading">正在加载学习档案...</View>
    }

    if (!profile) {
      return (
        <View className="loading error-state">
          <Text>{profileError || '学习档案加载失败'}</Text>
          <Button className="retry-button" onClick={this.loadProfileData}>重新加载</Button>
        </View>
      )
    }

    return (
      <>
        <View className="toolbar">
          <Text className="toolbar-title">学习档案</Text>
          <View className="coin">
            <Text>{profile.total_xp} XP</Text>
            <Text>🪙</Text>
          </View>
        </View>

        <Text className="page-title">我的学习记录</Text>
        <Text className="page-subtitle">每一次闯关，都会留下可回看的成长。</Text>

        <View className="profile-card">
          <Button
            className="profile-avatar-button"
            openType="chooseAvatar"
            onChooseAvatar={this.handleChooseAvatar}
            disabled={savingAvatar}
          >
            <View className="profile-avatar">
              {this.renderProfileAvatar(profile)}
            </View>
            <View className="profile-avatar-badge">📷</View>
          </Button>
          <View className="profile-info">
            {editingNickname ? (
              <Input
                className="nickname-input"
                type="nickname"
                value={nicknameDraft}
                maxlength={100}
                onInput={this.handleNicknameChange}
                focus
              />
            ) : (
              <Text className="profile-name">{profile.nickname}</Text>
            )}
            <Text className="profile-caption">持续闯关，积累属于你的知识 XP</Text>
          </View>
          {editingNickname ? (
            <View className="profile-edit-actions">
              <Button
                className="profile-save-button"
                onClick={this.handleSaveNickname}
                disabled={savingNickname}
              >
                {savingNickname ? '保存中' : '保存'}
              </Button>
              <Button
                className="profile-cancel-button"
                onClick={this.handleCancelNicknameEdit}
                disabled={savingNickname}
              >
                取消
              </Button>
            </View>
          ) : (
            <Button className="profile-edit-button" onClick={this.handleStartEditNickname}>
              修改昵称
            </Button>
          )}
        </View>

        {profileError && <Text className="profile-error">{profileError}</Text>}

        <View className="stats-grid">
          <View className="stat-card">
            <Text className="stat-value">{profile.quiz_count}</Text>
            <Text className="stat-label">闯关次数</Text>
          </View>
          <View className="stat-card">
            <Text className="stat-value">{profile.correct_count}</Text>
            <Text className="stat-label">答对题数</Text>
          </View>
          <View className="stat-card">
            <Text className="stat-value">{Math.round(profile.average_accuracy)}%</Text>
            <Text className="stat-label">平均正确率</Text>
          </View>
        </View>

        <Text className="list-title">闯关历史</Text>
        {histories.length > 0 ? (
          <>
            <View className="history-list">
              {histories.map((history) => (
                <View
                  key={history.quiz_id}
                  className="history-item"
                  onClick={() => this.handleHistoryClick(history.quiz_id)}
                >
                  <View className="history-icon">✓</View>
                  <View className="history-content">
                    <Text className="history-title">{history.title}</Text>
                    <Text className="history-meta">
                      {history.question_count} 题 · {history.created_at.slice(0, 10)}
                    </Text>
                  </View>
                  <View className="history-accuracy">
                    <Text>{Math.round(history.accuracy)}%</Text>
                  </View>
                </View>
              ))}
            </View>
            {histories.length < historyTotal && (
              <Button
                className="load-more-button"
                onClick={this.handleLoadMoreHistory}
                disabled={loadingMoreHistory}
              >
                {loadingMoreHistory ? '加载中...' : '加载更多'}
              </Button>
            )}
          </>
        ) : (
          <View className="empty-history">
            <Text>完成第一次闯关后，就能在这里回看报告。</Text>
          </View>
        )}
      </>
    )
  }

  render() {
    const { activeTab } = this.state

    return (
      <View className="page">
        <ScrollView
          scrollY
          className="content-scroll"
          style={{ paddingTop: `${this.contentTopOffset}px` }}
        >
          {activeTab === '闯关' && this.render闯关Content()}
          {activeTab === '题库' && this.render题库Content()}
          {activeTab === '我的' && this.render我的Content()}
        </ScrollView>

        <View className="fixed-tabbar">
          <View
            className={`tab ${activeTab === '闯关' ? 'active' : ''}`}
            onClick={() => this.handleTabClick('闯关')}
          >
            <Text>🏠</Text>
            <Text>闯关</Text>
          </View>
          <View
            className={`tab ${activeTab === '题库' ? 'active' : ''}`}
            onClick={() => this.handleTabClick('题库')}
          >
            <Text>📋</Text>
            <Text>题库</Text>
          </View>
          <View
            className={`tab ${activeTab === '我的' ? 'active' : ''}`}
            onClick={() => this.handleTabClick('我的')}
          >
            <Text>👤</Text>
            <Text>我的</Text>
          </View>
        </View>
      </View>
    )
  }
}
