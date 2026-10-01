import { merge } from 'webpack-merge'
import base from './index'

export default merge(base(), {
  env: {
    NODE_ENV: '"production"'
  }
})
