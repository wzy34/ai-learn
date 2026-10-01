export function replaceUnifiedPlatform() {
  return function (
    this: any,
    { sources }: any
  ) {
    if (!Array.isArray(sources)) {
      return
    }
    sources.forEach((source: any) => {
      const { code } = source
      if (typeof code === 'string') {
        source.code = code
          .replace(/\bTaro\./g, 'Taro.')
          .replace(/@tarojs\/taro/g, '@tarojs/taro')
      }
    })
  }
}
