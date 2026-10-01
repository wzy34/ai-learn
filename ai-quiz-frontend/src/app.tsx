import './app.scss'

import { useLaunch } from '@tarojs/taro'

import { initializeSession } from './utils/auth'

interface AppProps {
  children: React.ReactNode
}

export default function App(props: AppProps) {
  useLaunch(() => {
    void initializeSession()
  })

  return props.children
}
