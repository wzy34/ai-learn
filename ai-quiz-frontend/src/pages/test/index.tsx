import { Component } from 'react'
import { View, Text, Button } from '@tarojs/components'
import { reLaunch } from '@tarojs/taro'
import { getUserProfile } from '../../utils/api'
import { ensureLogin, withSessionRecovery } from '../../utils/auth'
import { getCustomNavigationContentTopOffset } from '../../utils/layout'
import './index.scss'

interface TestState {
  totalXp: number
}

export default class Test extends Component<{}, TestState> {
  private readonly contentTopOffset = getCustomNavigationContentTopOffset()

  constructor(props: {}) {
    super(props)
    this.state = {
      totalXp: 0
    }
  }

  componentDidShow() {
    void this.loadTotalXp()
  }

  loadTotalXp = async () => {
    try {
      await ensureLogin()
      const profile = await withSessionRecovery(() => getUserProfile(), [401, 404])
      this.setState({ totalXp: profile.total_xp })
    } catch (error) {
      console.warn('Failed to load XP for quiz bank:', error)
    }
  }

  handleTabClick = (tabName: string) => {
    // The home page hosts all three tabs; reLaunch avoids stacking pages.
    switch (tabName) {
      case '闯关':
        reLaunch({ url: '/pages/index/index' })
        break
      case '题库':
        // Already on the quiz bank page, do nothing
        break
      case '我的':
        reLaunch({ url: '/pages/index/index?tab=profile' })
        break
    }
  }

  render() {
    const { totalXp } = this.state

    return (
      <View className="page" style={{ paddingTop: `${this.contentTopOffset}px` }}>
        {/* Toolbar */}
        <View className="toolbar">
          <Text className="toolbar-title">题库</Text>
          <View className="coin">
            <Text>{totalXp} XP</Text>
            <View className="coin-icon">🪙</View>
          </View>
        </View>

        {/* Title */}
        <Text className="page-title">所有题库</Text>

        {/* Quiz Bank List */}
        <View className="quiz-bank-list">
          <View className="quiz-bank-item">
            <View className="quiz-bank-icon">📚</View>
            <View className="quiz-bank-info">
              <Text className="quiz-bank-title">RAG 基础概念</Text>
              <Text className="quiz-bank-meta">5 题 · 已完成 80%</Text>
            </View>
            <View className="quiz-bank-progress">
              <View className="progress-ring" style={{ background: 'conic-gradient(#47a4ff 0 80%, #ece7de 80% 100%)' }}>
                <Text>80%</Text>
              </View>
            </View>
          </View>

          <View className="quiz-bank-item">
            <View className="quiz-bank-icon">🔬</View>
            <View className="quiz-bank-info">
              <Text className="quiz-bank-title">提示词工程</Text>
              <Text className="quiz-bank-meta">8 题 · 已完成 60%</Text>
            </View>
            <View className="quiz-bank-progress">
              <View className="progress-ring" style={{ background: 'conic-gradient(#47a4ff 0 60%, #ece7de 60% 100%)' }}>
                <Text>60%</Text>
              </View>
            </View>
          </View>

          <View className="quiz-bank-item">
            <View className="quiz-bank-icon">🧮</View>
            <View className="quiz-bank-info">
              <Text className="quiz-bank-title">数学基础</Text>
              <Text className="quiz-bank-meta">10 题 · 未开始</Text>
            </View>
            <View className="quiz-bank-progress">
              <View className="progress-ring" style={{ background: 'conic-gradient(#47a4ff 0 0%, #ece7de 0% 100%)' }}>
                <Text>0%</Text>
              </View>
            </View>
          </View>

          <View className="quiz-bank-item">
            <View className="quiz-bank-icon">🎨</View>
            <View className="quiz-bank-info">
              <Text className="quiz-bank-title">设计理论</Text>
              <Text className="quiz-bank-meta">6 题 · 已完成 40%</Text>
            </View>
            <View className="quiz-bank-progress">
              <View className="progress-ring" style={{ background: 'conic-gradient(#47a4ff 0 40%, #ece7de 40% 100%)' }}>
                <Text>40%</Text>
              </View>
            </View>
          </View>
        </View>

        {/* Tab Bar */}
        <View className="fixed-tabbar">
          <View className="tab" onClick={() => this.handleTabClick('闯关')}>
            <Text>🏠</Text>
            <Text>闯关</Text>
          </View>
          <View className="tab active" onClick={() => this.handleTabClick('题库')}>
            <Text>📋</Text>
            <Text>题库</Text>
          </View>
          <View className="tab" onClick={() => this.handleTabClick('我的')}>
            <Text>👤</Text>
            <Text>我的</Text>
          </View>
        </View>
      </View>
    )
  }
}
