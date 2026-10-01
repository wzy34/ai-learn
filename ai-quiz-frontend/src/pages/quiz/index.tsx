import { Component } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro, { navigateTo, navigateBack, getCurrentInstance } from '@tarojs/taro'
import { getQuizSession } from '../../utils/api'
import { ensureLogin, withSessionRecovery } from '../../utils/auth'
import { getCustomNavigationContentTopOffset } from '../../utils/layout'
import './quiz.scss'

interface Question {
  id: string
  type: 'single' | 'multiple' | 'judge'
  stem: string
  options: Array<{ key: string; text: string }>
  answer: string[]
  explanation: string
  knowledge_point: string
  difficulty: 'easy' | 'medium' | 'hard'
}

interface QuizData {
  quiz_id: string
  title: string
  summary: string
  questions: Question[]
  /** Generation-time retrieval metadata; absent on history/resumed quizzes. */
  search_used?: boolean
  sources?: Array<{ title: string; url: string }>
}

interface QuizState {
  quizData: QuizData | null
  currentQuestionIndex: number
  selectedAnswers: string[]
  showResult: boolean
  isCorrect: boolean
  coins: number
  answerRecords: Array<{
    question_id: string
    selected_answers: string[]
    is_correct: boolean
    duration_ms: number
  }>
  questionStartTime: number
  loading: boolean
  loadError: boolean
}

export default class Quiz extends Component<{}, QuizState> {
  private readonly contentTopOffset = getCustomNavigationContentTopOffset()

  constructor(props: {}) {
    super(props)
    this.state = {
      quizData: null,
      currentQuestionIndex: 0,
      selectedAnswers: [],
      showResult: false,
      isCorrect: false,
      coins: 602,
      answerRecords: [],
      questionStartTime: 0,
      loading: false,
      loadError: false
    }
  }

  componentDidMount() {
    this.loadQuizData()
  }

  loadQuizData = () => {
    const instance = getCurrentInstance()
    const params = instance?.router?.params || {}

    if (params.quizData) {
      try {
        const quizData: QuizData = JSON.parse(decodeURIComponent(params.quizData))
        this.setState({
          quizData,
          questionStartTime: Date.now()
        })
      } catch (error) {
        console.error('Failed to parse quiz data:', error)
      }
    } else if (params.quizId) {
      // Resuming an unfinished quiz that is already persisted on the server.
      void this.loadQuizById(params.quizId)
    } else if (params.topic) {
      // Fallback for testing without backend
      this.loadMockData(params.topic)
    }
  }

  loadQuizById = async (quizId: string) => {
    try {
      await ensureLogin()
      const quizData = await withSessionRecovery(() => getQuizSession(quizId))
      this.setState({
        quizData,
        questionStartTime: Date.now(),
        loadError: false
      })
    } catch (error) {
      console.error('Failed to load quiz session:', error)
      this.setState({ loadError: true })
    }
  }

  loadMockData = (topic: string) => {
    // Mock data for testing
    const mockQuizData: QuizData = {
      quiz_id: `quiz_${Date.now()}`,
      title: topic,
      summary: `关于 ${topic} 的闯关题库`,
      questions: [
        {
          id: 'q1',
          type: 'single',
          stem: `${topic} 的核心特点是什么？`,
          options: [
            { key: 'A', text: '高效性' },
            { key: 'B', text: '准确性' },
            { key: 'C', text: '灵活性' }
          ],
          answer: ['A'],
          explanation: `${topic} 的核心特点包括高效、准确、灵活等多个方面`,
          knowledge_point: `${topic} 基础`,
          difficulty: 'easy'
        },
        {
          id: 'q2',
          type: 'judge',
          stem: `${topic} 适用于所有场景`,
          options: [
            { key: 'A', text: '正确' },
            { key: 'B', text: '错误' }
          ],
          answer: ['B'],
          explanation: `${topic} 并不适用于所有场景，需要根据具体情况选择`,
          knowledge_point: `${topic} 应用范围`,
          difficulty: 'medium'
        },
        {
          id: 'q3',
          type: 'multiple',
          stem: `${topic} 的主要优势包括？`,
          options: [
            { key: 'A', text: '提高效率' },
            { key: 'B', text: '降低成本' },
            { key: 'C', text: '增强体验' }
          ],
          answer: ['A', 'B', 'C'],
          explanation: `${topic} 的优势是多方面的，包括效率、成本和体验`,
          knowledge_point: `${topic} 优势分析`,
          difficulty: 'hard'
        }
      ]
    }
    this.setState({
      quizData: mockQuizData,
      questionStartTime: Date.now()
    })
  }

  handleOptionSelect = (optionKey: string) => {
    const { quizData, currentQuestionIndex, selectedAnswers } = this.state
    if (!quizData) return

    const currentQuestion = quizData.questions[currentQuestionIndex]

    if (currentQuestion.type === 'single' || currentQuestion.type === 'judge') {
      // Single select - submit immediately
      const newSelectedAnswers = [optionKey]
      const isCorrect = this.checkAnswer(currentQuestion, newSelectedAnswers)

      // Record answer
      this.recordAnswer(newSelectedAnswers, isCorrect)

      this.setState({
        selectedAnswers: newSelectedAnswers,
        showResult: true,
        isCorrect
      })

      if (isCorrect) {
        this.setState({ coins: this.state.coins + 10 })
      }
    } else {
      // Multiple select - toggle option
      const newSelectedAnswers = selectedAnswers.includes(optionKey)
        ? selectedAnswers.filter(a => a !== optionKey)
        : [...selectedAnswers, optionKey]
      this.setState({ selectedAnswers: newSelectedAnswers })
    }
  }

  handleMultipleSubmit = () => {
    const { quizData, currentQuestionIndex, selectedAnswers } = this.state
    if (!quizData) return

    const currentQuestion = quizData.questions[currentQuestionIndex]
    const isCorrect = this.checkAnswer(currentQuestion, selectedAnswers)

    // Record answer
    this.recordAnswer(selectedAnswers, isCorrect)

    this.setState({
      showResult: true,
      isCorrect
    })

    if (isCorrect) {
      this.setState({ coins: this.state.coins + 10 })
    }
  }

  checkAnswer = (question: Question, answers: string[]): boolean => {
    if (question.type === 'multiple') {
      const correctSet = new Set(question.answer)
      const answerSet = new Set(answers)
      return (
        correctSet.size === answerSet.size &&
        [...correctSet].every(a => answerSet.has(a))
      )
    }
    return answers[0] === question.answer[0]
  }

  recordAnswer = (selectedAnswers: string[], isCorrect: boolean) => {
    const { quizData, currentQuestionIndex, questionStartTime, answerRecords } = this.state
    if (!quizData) return

    const duration_ms = Date.now() - questionStartTime

    const record = {
      question_id: quizData.questions[currentQuestionIndex].id,
      selected_answers: selectedAnswers,
      is_correct: isCorrect,
      duration_ms
    }

    const existingRecordIndex = answerRecords.findIndex(
      (answerRecord) => answerRecord.question_id === record.question_id
    )
    const nextAnswerRecords = existingRecordIndex === -1
      ? [...answerRecords, record]
      : answerRecords.map((answerRecord, index) => (
        index === existingRecordIndex ? record : answerRecord
      ))

    this.setState({
      answerRecords: nextAnswerRecords,
      questionStartTime: Date.now()
    })
  }

  handleNext = () => {
    const { currentQuestionIndex, quizData } = this.state

    if (!quizData) return

    if (currentQuestionIndex < quizData.questions.length - 1) {
      this.setState({
        currentQuestionIndex: currentQuestionIndex + 1,
        selectedAnswers: [],
        showResult: false,
        isCorrect: false
      })
    } else {
      // Quiz completed, navigate to report page
      this.handleQuizComplete()
    }
  }

  handlePrevious = () => {
    const { currentQuestionIndex } = this.state

    if (currentQuestionIndex > 0) {
      this.setState({
        currentQuestionIndex: currentQuestionIndex - 1,
        selectedAnswers: [],
        showResult: false,
        isCorrect: false,
        questionStartTime: Date.now()
      })
    }
  }

  handleExit = () => {
    if (Taro.getCurrentPages().length > 1) {
      navigateBack()
      return
    }

    Taro.reLaunch({ url: '/pages/index/index' })
  }

  handleQuizComplete = () => {
    const { quizData, answerRecords } = this.state

    if (!quizData) return

    // Calculate correct count
    const correctCount = answerRecords.filter(r => r.is_correct).length

    // Navigate to report page with results
    navigateTo({
      url: `/pages/report/index?quizData=${encodeURIComponent(JSON.stringify(quizData))}&answerRecords=${encodeURIComponent(JSON.stringify(answerRecords))}&accuracy=${encodeURIComponent(Math.round((correctCount / answerRecords.length) * 100))}`
    })
  }

  getCurrentQuestion = (): Question | null => {
    const { currentQuestionIndex, quizData } = this.state
    if (!quizData) return null
    return quizData.questions[currentQuestionIndex] || null
  }

  render() {
    const { currentQuestionIndex, quizData, selectedAnswers, showResult, isCorrect, coins, loadError } = this.state
    const currentQuestion = this.getCurrentQuestion()
    const progress = quizData ? ((currentQuestionIndex + 1) / quizData.questions.length) * 100 : 0

    if (!quizData) {
      if (loadError) {
        return (
          <View className="loading error-state">
            <Text>题目加载失败，请稍后重试</Text>
            <Button className="retry-button" onClick={this.handleExit}>返回</Button>
          </View>
        )
      }
      return <View className="loading">加载中...</View>
    }

    if (!currentQuestion) {
      return <View className="loading">题目加载失败</View>
    }

    const isMultipleChoice = currentQuestion.type === 'multiple'
    const correctCount = this.state.answerRecords.filter(r => r.is_correct).length

    return (
      <View className="quiz-page" style={{ paddingTop: `${this.contentTopOffset}px` }}>
        {/* Status Bar */}
        <View className="statusbar">
          <View className="exit-button" onClick={this.handleExit}>
            <Text>×</Text>
          </View>
          <Text className="question-count">第 {currentQuestionIndex + 1} / {quizData.questions.length} 题</Text>
          <View className="coin">
            <Text>{coins}</Text>
            <Text>🪙</Text>
          </View>
        </View>

        {/* Progress Bar */}
        <View className="quiz-progress">
          <View className="progress-track">
            <View className="progress-fill" style={{ width: `${progress}%` }}></View>
          </View>
          <View className="progress-meta">
            <Text>{quizData.title}</Text>
            <Text>答对 {correctCount} 题</Text>
          </View>
        </View>

        {/* Retrieval verification badge — only on fresh generations */}
        {quizData.search_used === true && (
          <View className="retrieval-badge verified">
            <Text>🌐 已联网核实 · {quizData.sources?.length ?? 0} 条资料</Text>
          </View>
        )}
        {quizData.search_used === false && (
          <View className="retrieval-badge unverified">
            <Text>⚠️ 未经联网核实，请谨慎参考</Text>
          </View>
        )}

        {/* Question */}
        <Text className="quiz-title">{currentQuestion.stem}</Text>

        {/* Options */}
        <View className="options-container">
          {currentQuestion.options.map((option) => {
            const isSelected = selectedAnswers.includes(option.key)
            const isCorrectOption = currentQuestion.answer.includes(option.key)
            const showCorrect = showResult && isCorrectOption
            const showSelected = isMultipleChoice && isSelected && !showResult

            return (
              <Button
                key={option.key}
                className={`option ${showSelected ? 'selected' : ''} ${showCorrect ? 'correct' : ''} ${showResult && isSelected && !isCorrectOption ? 'wrong' : ''}`}
                onClick={() => !showResult && this.handleOptionSelect(option.key)}
                disabled={showResult}
              >
                {(showCorrect || showSelected) && <Text className="check-icon">✓</Text>}
                <Text>{option.key}. {option.text}</Text>
              </Button>
            )
          })}
        </View>

        {/* Multiple Choice Submit Button */}
        {isMultipleChoice && !showResult && selectedAnswers.length > 0 && (
          <Button
            className="submit-btn"
            onClick={this.handleMultipleSubmit}
          >
            提交答案
          </Button>
        )}

        {/* Result */}
        {showResult && (
          <View className="result-section">
            <View className={`result-tip ${isCorrect ? 'correct' : 'wrong'}`}>
              <View className="tip-content">
                <Text>{isCorrect ? '✓ 答对啦' : '✗ 答错了'}</Text>
                <Text>{isCorrect ? '+10 金币' : '继续加油'}</Text>
              </View>
            </View>

            <View className="explain-box">
              <Text className="explain-label">解析：</Text>
              <Text>{currentQuestion.explanation}</Text>
            </View>

            <View className="answer-note">
              <Text>知识点：{currentQuestion.knowledge_point}</Text>
            </View>

            <View className="navigation-buttons">
              <Button
                className="nav-btn prev-btn"
                onClick={this.handlePrevious}
                disabled={currentQuestionIndex === 0}
              >
                上一题
              </Button>
              <Button
                className="nav-btn next-btn"
                onClick={this.handleNext}
              >
                {currentQuestionIndex < quizData.questions.length - 1 ? '继续 →' : '查看报告'}
              </Button>
            </View>
          </View>
        )}
      </View>
    )
  }
}
