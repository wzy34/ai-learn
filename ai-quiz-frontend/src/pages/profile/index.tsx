import { Component } from 'react'
import { Button, Image, Input, ScrollView, Text, View } from '@tarojs/components'
import { navigateTo, reLaunch, showToast } from '@tarojs/taro'

import {
  getQuizHistory,
  getUserProfile,
  QuizHistoryItem,
  updateUserProfile,
  uploadUserAvatar,
  UserProfile
} from '../../utils/api'
import { ensureLogin, withSessionRecovery } from '../../utils/auth'
import { updateCachedUser } from '../../utils/auth-storage'
import { getCustomNavigationContentTopOffset } from '../../utils/layout'

import './index.scss'

const HISTORY_PAGE_SIZE = 10

interface ProfileState {
  profile: UserProfile | null
  histories: QuizHistoryItem[]
  page: number
  total: number
  loading: boolean
  loadingMore: boolean
  saving: boolean
  savingAvatar: boolean
  editingNickname: boolean
  nicknameDraft: string
  errorMessage: string
}

export default class Profile extends Component<{}, ProfileState> {
  private readonly contentTopOffset = getCustomNavigationContentTopOffset()

  constructor(props: {}) {
    super(props)
    this.state = {
      profile: null,
      histories: [],
      page: 1,
      total: 0,
      loading: true,
      loadingMore: false,
      saving: false,
      savingAvatar: false,
      editingNickname: false,
      nicknameDraft: '',
      errorMessage: ''
    }
  }

  componentDidShow() {
    void this.loadProfile()
  }

  loadProfile = async () => {
    this.setState({ loading: true, errorMessage: '' })

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
        page: history.page,
        total: history.total,
        nicknameDraft: profile.nickname,
        loading: false,
        editingNickname: false
      })
    } catch (error) {
      console.error('Failed to load user profile:', error)
      this.setState({
        loading: false,
        errorMessage: error instanceof Error ? error.message : '用户数据加载失败'
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
      errorMessage: '',
      profile: { ...profile, avatar_url: avatarUrl }
    })
    try {
      const saved = await withSessionRecovery(() => uploadUserAvatar(avatarUrl))
      this.setState({ profile: saved, savingAvatar: false })
      updateCachedUser({
        id: saved.id,
        nickname: saved.nickname,
        avatar_url: saved.avatar_url,
        total_xp: saved.total_xp
      })
      showToast({ title: '头像已更新', icon: 'success' })
    } catch (error) {
      console.error('Failed to upload avatar:', error)
      this.setState({
        profile,
        savingAvatar: false,
        errorMessage: error instanceof Error ? error.message : '头像上传失败，请稍后重试'
      })
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
      errorMessage: ''
    })
  }

  handleNicknameChange = (event: { detail: { value: string } }) => {
    this.setState({ nicknameDraft: event.detail.value, errorMessage: '' })
  }

  handleCancelNicknameEdit = () => {
    const { profile } = this.state
    this.setState({
      editingNickname: false,
      nicknameDraft: profile?.nickname || '',
      errorMessage: ''
    })
  }

  handleSaveNickname = async () => {
    const nickname = this.state.nicknameDraft.trim()
    if (!nickname) {
      this.setState({ errorMessage: '昵称不能为空' })
      return
    }

    this.setState({ saving: true, errorMessage: '' })
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
        saving: false
      })
    } catch (error) {
      console.error('Failed to update profile:', error)
      this.setState({
        saving: false,
        errorMessage: error instanceof Error ? error.message : '昵称保存失败'
      })
    }
  }

  handleLoadMore = async () => {
    const { loadingMore, page, total, histories } = this.state
    if (loadingMore || histories.length >= total) {
      return
    }

    this.setState({ loadingMore: true })
    try {
      const nextPage = page + 1
      const history = await withSessionRecovery(() =>
        getQuizHistory(nextPage, HISTORY_PAGE_SIZE)
      )
      this.setState({
        histories: [...histories, ...history.items],
        page: history.page,
        total: history.total,
        loadingMore: false
      })
    } catch (error) {
      console.error('Failed to load more history:', error)
      this.setState({
        loadingMore: false,
        errorMessage: error instanceof Error ? error.message : '历史记录加载失败'
      })
    }
  }

  handleHistoryClick = (quizId: string) => {
    navigateTo({
      url: `/pages/report/index?quizId=${encodeURIComponent(quizId)}`
    })
  }

  handleTabClick = (tabName: '闯关' | '题库' | '我的') => {
    // The home page hosts all three tabs; reLaunch avoids stacking pages.
    if (tabName === '闯关') {
      reLaunch({ url: '/pages/index/index' })
      return
    }
    if (tabName === '题库') {
      reLaunch({ url: '/pages/index/index?tab=bank' })
    }
  }

  renderAvatar = (profile: UserProfile) => {
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

  renderProfileContent = () => {
    const {
      profile,
      histories,
      total,
      loadingMore,
      saving,
      savingAvatar,
      editingNickname,
      nicknameDraft,
      errorMessage
    } = this.state

    if (!profile) {
      return null
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
              {this.renderAvatar(profile)}
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
                disabled={saving}
              >
                {saving ? '保存中' : '保存'}
              </Button>
              <Button
                className="profile-cancel-button"
                onClick={this.handleCancelNicknameEdit}
                disabled={saving}
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

        {errorMessage && <Text className="profile-error">{errorMessage}</Text>}

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
            {histories.length < total && (
              <Button
                className="load-more-button"
                onClick={this.handleLoadMore}
                disabled={loadingMore}
              >
                {loadingMore ? '加载中...' : '加载更多'}
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
    const { loading, errorMessage } = this.state

    return (
      <View className="profile-page">
        <ScrollView
          className="profile-scroll"
          scrollY
          style={{ paddingTop: `${this.contentTopOffset}px` }}
        >
          {loading ? (
            <View className="loading">正在加载学习档案...</View>
          ) : this.state.profile ? (
            this.renderProfileContent()
          ) : (
            <View className="loading error-state">
              <Text>{errorMessage || '学习档案加载失败'}</Text>
              <Button className="retry-button" onClick={this.loadProfile}>重新加载</Button>
            </View>
          )}
        </ScrollView>

        <View className="fixed-tabbar">
          <View className="tab" onClick={() => this.handleTabClick('闯关')}>
            <Text>🏠</Text>
            <Text>闯关</Text>
          </View>
          <View className="tab" onClick={() => this.handleTabClick('题库')}>
            <Text>📋</Text>
            <Text>题库</Text>
          </View>
          <View className="tab active">
            <Text>👤</Text>
            <Text>我的</Text>
          </View>
        </View>
      </View>
    )
  }
}
