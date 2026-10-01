import { Component } from 'react'
import { View, Text, Button } from '@tarojs/components'
import { getCurrentInstance, reLaunch } from '@tarojs/taro'

import {
  AnswerRecord,
  generateReport,
  getQuizHistoryDetail,
  LearningReport,
  QuizData
} from '../../utils/api'
import { ensureLogin, withSessionRecovery } from '../../utils/auth'
import { getCustomNavigationContentTopOffset } from '../../utils/layout'

import './report.scss'

interface ReportState {
  quizData: QuizData | null
  answerRecords: AnswerRecord[]
  reportData: LearningReport | null
  loading: boolean
  generating: boolean
  isHistory: boolean
  historyQuizId: string
  errorMessage: string
}

export default class Report extends Component<{}, ReportState> {
  private readonly contentTopOffset = getCustomNavigationContentTopOffset()

  constructor(props: {}) {
    super(props)
    this.state = {
      quizData: null,
      answerRecords: [],
      reportData: null,
      loading: true,
      generating: false,
      isHistory: false,
      historyQuizId: '',
      errorMessage: ''
    }
  }

  componentDidMount() {
    void this.loadReportData()
  }

  loadReportData = async () => {
    const params = getCurrentInstance()?.router?.params || {}

    if (params.quizId) {
      await this.loadHistoryReport(params.quizId)
      return
    }

    if (!params.quizData || !params.answerRecords) {
      this.setState({
        loading: false,
        errorMessage: '缺少本次闯关数据，无法生成报告'
      })
      return
    }

    try {
      const quizData = JSON.parse(decodeURIComponent(params.quizData)) as QuizData
      const answerRecords = JSON.parse(
        decodeURIComponent(params.answerRecords)
      ) as AnswerRecord[]
      this.setState({
        quizData,
        answerRecords,
        loading: false,
        isHistory: false,
        errorMessage: ''
      })
      await this.generateCurrentReport(quizData, answerRecords)
    } catch (error) {
      console.error('Failed to parse report data:', error)
      this.setState({
        loading: false,
        errorMessage: '本次闯关数据无效，无法生成报告'
      })
    }
  }

  loadHistoryReport = async (quizId: string) => {
    this.setState({ loading: true, errorMessage: '' })

    try {
      await ensureLogin()
      const detail = await withSessionRecovery(() => getQuizHistoryDetail(quizId))
      this.setState({
        quizData: {
          quiz_id: detail.quiz_id,
          title: detail.title,
          summary: detail.summary,
          questions: detail.questions
        },
        answerRecords: detail.answer_records,
        reportData: detail.report,
        loading: false,
        isHistory: true,
        historyQuizId: quizId
      })
    } catch (error) {
      console.error('Failed to load history report:', error)
      this.setState({
        loading: false,
        isHistory: true,
        historyQuizId: quizId,
        errorMessage: error instanceof Error ? error.message : '历史报告加载失败'
      })
    }
  }

  generateCurrentReport = async (
    quizData: QuizData,
    answerRecords: AnswerRecord[]
  ) => {
    this.setState({ generating: true, errorMessage: '' })

    try {
      try {
        await ensureLogin()
      } catch (error) {
        console.warn('Report will be generated anonymously because login failed:', error)
      }

      const reportData = await generateReport({
        quiz_id: quizData.quiz_id,
        topic: quizData.title,
        questions: quizData.questions,
        answer_records: answerRecords
      })
      this.setState({ reportData })
    } catch (error) {
      console.error('Report generation failed:', error)
      this.setState({
        errorMessage: error instanceof Error ? error.message : '报告生成失败，请重试'
      })
    } finally {
      this.setState({ generating: false })
    }
  }

  handleRetryReport = () => {
    const { isHistory, historyQuizId, quizData, answerRecords } = this.state
    if (isHistory && historyQuizId) {
      void this.loadHistoryReport(historyQuizId)
      return
    }
    if (quizData) {
      void this.generateCurrentReport(quizData, answerRecords)
    }
  }

  handleRetryQuiz = () => {
    reLaunch({ url: '/pages/index/index' })
  }

  handleGeneratePoster = () => {
    console.log('Generate poster')
  }

  handleTabClick = (tabName: '闯关' | '题库' | '我的') => {
    // The home page hosts all three tabs; reLaunch avoids stacking pages.
    switch (tabName) {
      case '闯关':
        reLaunch({ url: '/pages/index/index' })
        break
      case '题库':
        reLaunch({ url: '/pages/index/index?tab=bank' })
        break
      case '我的':
        reLaunch({ url: '/pages/index/index?tab=profile' })
        break
    }
  }

  getEarnedXp = () => {
    const { answerRecords } = this.state
    if (answerRecords.length === 0) {
      return 0
    }
    const correctCount = answerRecords.filter((record) => record.is_correct).length
    return 10 + correctCount * 2
  }

  render() {
    const { reportData, generating, loading, errorMessage, answerRecords } = this.state

    if (loading || generating) {
      return (
        <View className="loading">
          {loading ? '加载报告中...' : 'AI 生成报告中...'}
        </View>
      )
    }

    if (!reportData) {
      return (
        <View className="loading error-state">
          <Text>{errorMessage || '报告加载失败'}</Text>
          <Button className="retry-button" onClick={this.handleRetryReport}>
            重新尝试
          </Button>
        </View>
      )
    }

    const wrongCount = answerRecords.filter((record) => !record.is_correct).length
    const earnedXp = this.getEarnedXp()

    return (
      <View className="report-page" style={{ paddingTop: `${this.contentTopOffset}px` }}>
        <View className="toolbar">
          <Text className="toolbar-title">{this.state.quizData?.title || '学习报告'}</Text>
          <View className="xp-badge">+{earnedXp} XP</View>
        </View>

        <Text className="page-title">你这局学得很稳</Text>
        <Text className="page-subtitle">先看结果，再看错因，最后给你下一步建议。</Text>

        <View className="tags-row">
          <View className="tag achievement">
            <Text>⭐</Text>
            <Text>掌握度 +1</Text>
          </View>
          <View className="tag improvement">
            <Text>📈</Text>
            <Text>错题 {wrongCount} 题</Text>
          </View>
        </View>

        <View className="card">
          <View className="card-header">
            <Text className="card-title">⏱ 掌握度</Text>
          </View>
          <View className="mastery-content">
            <View
              className="mastery-ring"
              style={{
                background: `conic-gradient(#ff7a2f 0 ${reportData.accuracy}%, #ece7de ${reportData.accuracy}% 100%)`
              }}
            >
              <Text className="mastery-percent">{reportData.accuracy}%</Text>
            </View>
            <View className="mastery-text">
              <Text>本次学习表现不错，继续保持学习热情。</Text>
              <View className="mastery-bar">
                <View className="mastery-bar-fill" style={{ width: `${reportData.accuracy}%` }} />
              </View>
            </View>
          </View>
        </View>

        <View className="card">
          <View className="card-header">
            <Text className="card-title">⚠ 最该补的 {reportData.weak_points.length} 点</Text>
          </View>
          <View className="weak-points">
            {reportData.weak_points.map((point, index) => (
              <Text key={index} className="weak-point-item">
                {index + 1}. {point}
              </Text>
            ))}
          </View>
        </View>

        <View className="card">
          <View className="card-header">
            <Text className="card-title">📝 知识总结</Text>
          </View>
          <View className="summary-list">
            {reportData.three_line_summary.map((line, index) => (
              <View key={index} className="summary-item">
                <Text className="summary-bullet">{index + 1}</Text>
                <Text className="summary-text">{line}</Text>
              </View>
            ))}
          </View>
        </View>

        <View className="card">
          <View className="card-header">
            <Text className="card-title">💡 学习建议</Text>
          </View>
          <View className="advice-list">
            {reportData.advice.map((advice, index) => (
              <Text key={index} className="advice-item">
                {index + 1}. {advice}
              </Text>
            ))}
          </View>
        </View>

        <View className="card poster-card">
          <View className="card-header">
            <Text className="card-title">🖼 分享海报</Text>
          </View>
          <View className="poster-preview">
            <Text className="poster-quote">{reportData.share_quote}</Text>
            <View className="poster-qrcode">
              <Text>小程序码</Text>
            </View>
          </View>
        </View>

        <View className="action-buttons">
          <Button className="action-btn primary" onClick={this.handleRetryQuiz}>
            再来一组
          </Button>
          <Button className="action-btn secondary" onClick={this.handleGeneratePoster}>
            生成海报
          </Button>
        </View>

        <View className="fixed-tabbar">
          <View className="tab" onClick={() => this.handleTabClick('闯关')}>
            <Text>🏠</Text>
            <Text>闯关</Text>
          </View>
          <View className="tab" onClick={() => this.handleTabClick('题库')}>
            <Text>📋</Text>
            <Text>题库</Text>
          </View>
          <View className="tab active" onClick={() => this.handleTabClick('我的')}>
            <Text>👤</Text>
            <Text>我的</Text>
          </View>
        </View>
      </View>
    )
  }
}
