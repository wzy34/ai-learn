# AI 闯关学习小程序

基于 Taro 4.x + React + TypeScript 开发的微信小程序。

## 技术栈

- **框架**: Taro 4.2.1
- **视图**: React 18
- **语言**: TypeScript
- **样式**: SCSS
- **构建工具**: Webpack 5

## 项目结构

```
ai-quiz-frontend/
├── config/           # Taro 配置文件
├── src/
│   ├── pages/        # 页面组件
│   │   ├── index/    # 首页（输入 + 关卡列表）
│   │   ├── quiz/     # 闯关答题页
│   │   └── report/   # 报告页
│   │   └── profile/  # 我的（档案 + 历史记录）
│   ├── components/   # 公共组件
│   ├── utils/        # 工具函数
│   ├── app.tsx       # 应用入口
│   ├── app.scss      # 全局样式
│   └── app.config.ts # 应用配置
├── package.json
└── tsconfig.json
```

## 开发

### 安装依赖

```bash
npm install
```

### 开发模式

```bash
npm run dev:weapp
```

首次使用时，将 `project.config.example.json` 复制为 `project.config.json`，
并将其中的 `appid` 替换为自己的微信小程序 AppID。`project.config.json`
是本地文件，已加入 Git 忽略规则；不要提交真实 AppID 或密钥。

然后在微信开发者工具中打开 `dist` 目录。

### 生产构建

```bash
npm run build:weapp:prod
```

## 页面说明

### 首页 (pages/index)
- 用户输入学习主题
- 快速生成题库
- 展示当前用户昵称、XP 和已完成关卡
- 未完成关卡：AI 薄弱点专项训练（基于历史报告自动定向出题）+ 未完成闯关续答
- 题库 tab：主题精选（预置主题一键生成）+ 我的题库（生成过的题库与正确率）

### 闯关页 (pages/quiz)
- 题目展示（单选/多选/判断）
- 即时反馈和讲解
- 进度跟踪
- 答题奖励
- 联网核实标识：新生成的题库按后端返回的 `search_used` 显示「🌐 已联网核实 · N 条资料」
  或「⚠️ 未经联网核实，请谨慎参考」；历史/续答题库不含该字段，不展示标识

### 报告页 (pages/report)
- 正确率分析
- 掌握点/薄弱点
- 知识总结
- 分享海报
- 支持从历史记录读取已保存报告

### 我的 (pages/profile)
- 启动时微信静默登录并读取用户档案
- 点击头像即可通过微信「头像昵称填写能力」更换头像（可选微信头像/相册/拍照），图片上传后端持久化
- 修改昵称（输入法键盘支持「使用微信昵称」一键填入）
- 展示累计闯关次数、答对题数、平均正确率和 XP
- 分页加载历史闯关记录并跳转回看报告

## 设计系统

项目使用统一的设计系统，详见 `src/utils/constants.ts`。

## API 接口

- `POST /api/v1/quiz/generate` - 生成题库；响应含 `search_used`（是否经联网核实）
  与 `sources`（资料来源列表）；检索成功但无可读资料时返回 422 与中文提示
- `POST /api/v1/quiz/drill` - 薄弱点专项训练（需登录）；元数据语义同上
- `POST /api/v1/report/generate` - 生成报告
- `GET /api/v1/health` - 健康检查
- `POST /api/v1/user/login` - 微信登录
- `GET|PUT /api/v1/user/profile` - 用户档案
- `POST /api/v1/user/avatar` - 上传头像图片（multipart，字段名 `file`）
- `GET /api/v1/user/quizzes` - 历史列表
- `GET /api/v1/user/quizzes/unfinished` - 未完成闯关列表
- `GET /api/v1/user/quizzes/{quiz_id}` - 历史详情
- `GET /api/v1/user/quizzes/{quiz_id}/resume` - 读取题库用于续答
- `GET /api/v1/user/weak-points` - 薄弱点聚合

## 开发注意事项

1. 所有样式需精确还原 UI 原型
2. 使用 SCSS 变量进行样式统一管理
3. TypeScript 严格模式开启
4. 组件采用 Class Components（Taro 4.x 兼容性）
5. App 启动时调用 `Taro.login()`；请在微信开发者工具中配置与后端 `.env` 相同的小程序 AppID
6. 头像/昵称使用微信「头像昵称填写能力」（`open-type="chooseAvatar"` + `type="nickname"`，基础库 ≥ 2.21.2）。`wx.getUserProfile` 已被微信废弃，只会返回匿名数据，请勿再使用
7. 头像上传与图片加载都走 `src/utils/api.ts` 里的 `API_BASE_URL`；真机预览时需在开发者工具勾选「不校验合法域名」，正式发布需配置合法的 HTTPS 上传/下载域名
