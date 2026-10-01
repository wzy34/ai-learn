import path from 'path'

const isDev = process.env.NODE_ENV !== 'production'

const config = {
  projectName: 'ai-quiz-frontend',
  date: '2025-8-17',
  designWidth: 390,
  deviceRatio: {
    390: 2 / 1,
    750: 2 / 1,
    828: 1.81 / 1,
    375: 2 / 1
  },
  sourceRoot: 'src',
  outputRoot: 'dist',
  plugins: [
    '@tarojs/plugin-framework-react'
  ],
  defineConstants: {},
  copy: {
    patterns: [
      {
        from: 'src/sitemap.json',
        to: 'dist/sitemap.json'
      }
    ],
    options: {}
  },
  framework: 'react' as const,
  compiler: {
    type: 'webpack5',
    prebundle: {
      enable: false
    }
  },
  cache: {
    enable: false
  },
  mini: {
    postcss: {
      pxtransform: {
        enable: true,
        config: {
          selectorBlackList: [/^taro-/, /^weapp-/]
        }
      },
      url: {
        enable: true,
        config: {
          limit: 1024
        }
      },
      cssModules: {
        enable: false
      }
    },
    addChunkPages(pages: any, pagesNames: any) {},
    singleThread: false,
    // 增加调试选项
    debugReact: true,
    lazyCodeLoading: false
  },
  h5: {
    publicPath: '/',
    staticDirectory: 'static',
    postcss: {
      pxtransform: {
        enable: true,
        config: {}
      },
      autoprefixer: {
        enable: true,
        config: {}
      },
      cssModules: {
        enable: false
      }
    }
  },
  alias: {
    '@': path.resolve(process.cwd(), 'src'),
    '@/components': path.resolve(process.cwd(), 'src/components'),
    '@/utils': path.resolve(process.cwd(), 'src/utils')
  },
  tsconfigPath: 'tsconfig.json'
}

export default function (merge: any) {
  if (isDev) {
    return merge({}, config, {
      env: {
        NODE_ENV: '"development"'
      }
    })
  }
  return merge({}, config, {
    env: {
      NODE_ENV: '"production"'
    }
  })
}
