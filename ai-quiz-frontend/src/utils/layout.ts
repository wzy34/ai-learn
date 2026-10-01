import Taro from '@tarojs/taro'

const CUSTOM_NAVIGATION_GAP = 12

export const getCustomNavigationContentTopOffset = (): number =>
  Taro.getMenuButtonBoundingClientRect().bottom + CUSTOM_NAVIGATION_GAP
