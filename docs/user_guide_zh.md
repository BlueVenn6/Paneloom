# Paneloom / 格织 新用户使用指南

这份指南给第一次拿到工具的用户使用。Paneloom / 格织目前是一个桌面优先、local-first 的开源漫画分镜与视觉连续性工作台：它用本机后端和本机前端运行，打开方式像网页，但数据、项目文件、导出文件都在你的电脑本地目录里。后续确认流程稳定后，再打包成 Windows `.exe`。

## 1. 它适合做什么

Paneloom / 格织的核心用途是：把剧本、旁白稿、故事梗概拆成稳定漫画分镜，管理角色资产、风格锁、参考图、导出和创作复盘，方便后续继续做成解说漫画、图文内容或旁白视频素材。

当前它不做视频剪辑，也不负责发布到社媒平台。它负责的是视频之前的资产生产和进度管理。

## 2. 第一次启动

在 Windows 上打开 PowerShell，进入项目目录：

```powershell
cd C:\Users\esthe\Desktop\StoryboardGenie
```

如果是第一次运行，需要先准备依赖：

```powershell
python -m pip install -r backend\requirements.txt
cd frontend
npm install
cd ..
```

启动工具：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_desktop_dev.ps1
```

启动后会打开本地前端：

```text
http://127.0.0.1:5173
```

后端服务地址是：

```text
http://127.0.0.1:8000
```

停止工具：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop_desktop_dev.ps1
```

如果页面打不开，先执行停止脚本，再重新启动。

## 3. 配置模型

进入左侧 `Settings`。

文本模型用于剧本拆分、分镜规划等文字任务。当前支持三类：

- GPT / OpenAI
- GLM / 智谱
- Google Gemini

每类都可以走两种模式：

- `native`：使用官方原生接口。
- `relay`：使用兼容 OpenAI 风格的中转接口。

图片生成目前使用 OpenAI-compatible 图片接口设置。你需要填写图片模型、Base URL、API Key、图片尺寸和质量。

配置完成后，点击测试按钮确认接口可用。API Key 会保存在本地配置文件中，所以这台电脑应当视为你的工作电脑，不要把 `db/settings.json` 发给别人。

## 4. 创建项目

进入 `Projects` 或首页项目区域。

1. 新建一个项目。
2. 项目名建议用漫画系列名或单集名，例如 `EP01-雨夜便利店`。
3. 描述里写清楚用途，例如 `竖屏解说漫画，发布到 Reels/Shorts/Pinterest`。
4. 选中项目后，再进入 `Storyboard`。

一个项目对应本地一个项目文件夹，里面会保存分镜、图片、日程、反馈和导出结果。

## 5. 建立 Project Bible

进入 `Storyboard` 页面后，先填写 `Project Bible`。

建议填写：

- `Visual Style`：整体画风，例如黑白漫画、彩色条漫、电影感分镜。
- `Characters`：主要角色外貌、服装、年龄、气质、固定道具。
- `Locations`：主要场景，例如卧室、便利店、学校走廊。
- `World Notes`：世界观、时代、光线、禁忌元素。
- `Prompt Prefix`：希望每张图都继承的提示词。
- `Negative Prompt`：不希望出现的内容，例如水印、乱码文字、畸形手。

先写 Project Bible 的好处是后面每张分镜更容易保持角色和风格一致。

## 6. 从剧本生成分镜

在 `Script Breakdown` 区域：

1. 粘贴剧本、旁白稿、故事梗概或故事节拍。
2. 也可以导入 `.txt`、`.md`、`.srt` 文件。
3. 设置 `Panels`，例如 6、8、12。
4. 勾选是否保留对白信息。
5. 勾选 `Use AI` 使用大模型拆分；如果关闭，会走本地简易拆分逻辑。
6. 点击 `Create Panels From Script`。

生成后，下方表格会出现每个分镜。你可以逐条检查：

- 场景编号是否合理。
- 画面描述是否能直接画出来。
- Prompt 是否清楚。
- 是否需要删减、增加或重排。

## 7. 手动补充分镜

如果某些镜头需要手动添加，可以在 `Add Panel` 区域创建单条分镜。

建议每条分镜至少写清楚：

- 画面主体。
- 人物动作。
- 镜头距离或角度。
- 场景和情绪。
- 是否有关键道具。

生成图片前，最好先把分镜表调整到满意状态。分镜越清楚，后面图片越容易可用。

## 8. 选择图片比例

在 `Production` 区域先选择输出比例。这个选择会影响生成图片的尺寸和未来发布平台。

常用选择：

- `9:16`：竖屏视频、Reels、Shorts、TikTok 风格内容。
- `16:9`：横屏视频、YouTube 横版或横屏封面。
- `1:1`：Instagram 方图、通用社媒图片。
- `4:5`：Instagram Feed 竖图。
- `2:3`：Pinterest 常见竖图。

可以一次选择多个比例。这样同一条分镜会为不同平台生成不同版本。

## 9. 生成图片

你有两种生成方式：

- 单条生成：在分镜表格里点击某条分镜的 `Generate`。
- 批量生成：在 `Production` 区域点击 `Generate Pending`。

建议第一次调试时先单条生成，确认模型、比例和提示词都正确，再批量生成。

如果失败，先检查：

- Settings 里的 API Key 和 Base URL。
- 图片模型名称是否真实可用。
- 图片接口是否支持当前尺寸。
- Prompt 是否过长或包含接口不接受的内容。

## 10. 使用参考图

在 `References` 区域上传参考图。

适合上传：

- 角色设定图。
- 场景参考图。
- 已经满意的一张分镜图。

选择参考图后，可以对某条分镜点击 `Ref Edit`。这适合在已有图基础上修改风格、角色、构图或一致性。

## 11. 预览漫画网格

生成图片后，`Comic Preview` 会显示已生成的分镜图。

在 `Grid Canvas` 里选择网格输出比例，再设置列数，例如：

- 1 列：适合条漫或竖屏滚动。
- 2 列：适合 6 格、8 格漫画预览。
- 3 列：适合横版展示或密集分镜草稿。

点击 `Export Grid PNG` 可以导出一张拼好的漫画网格图。这个功能适合快速做社媒图、预览图或后续视频素材。

## 12. 导出项目

在 `Production` 区域可以导出：

- `JSON`：保留结构化数据，适合备份和二次处理。
- `CSV`：适合表格检查。
- `Excel`：适合人工编辑、给协作者看。
- `SRT`：适合旁白时间轴或字幕草稿。
- `Comic HTML`：适合浏览器查看漫画分镜。

导出文件会放在本地 `exports` 目录下。

## 13. 使用日程管理

进入 `Schedule` 页面。

### 13.1 生成计划

在 `Generate production schedule` 中填写：

- `Start Date`：开始制作日期。
- `Target Publish Date`：目标发布日期。
- `Updates / Week`：每周更新频率。
- `Hours / Day`：每天可投入时间。
- `Content Items`：这段周期内要做几条内容。
- `Panels / Item`：每条内容平均多少分镜。
- `Platforms`：目标平台，例如 Reels、Shorts、Pinterest。
- `Workflow Steps`：制作步骤，例如 script、storyboard、image、edit、copy、publish。

点击 `Generate Schedule` 后，会生成任务列表。注意：重新生成计划会替换当前项目的任务列表。

### 13.2 处理到期任务

`Due` 区域会显示今天及以前还没完成的任务，也就是你当前最应该处理的事情。

每个任务可以改状态：

- `todo`：未开始。
- `doing`：正在做。
- `done`：完成。
- `blocked`：卡住。
- `skipped`：跳过。

### 13.3 记录工作时间

在 `Log work session` 中记录一次工作：

1. 选择关联任务。
2. 填写日期和分钟数。
3. 填写阶段，例如 script、storyboard、image、edit。
4. 选择工作状态：smooth、normal、blocked、rework。
5. 如果卡住，填写 Blocker。
6. 在 Notes 写下原因、收获或下次要注意的事。

这些记录会用于周复盘和月复盘。

### 13.4 记录社媒反馈

在 `Log social metrics` 中记录发布后的反馈：

- 内容编号。
- 平台。
- 发布日期。
- 标题。
- 图片比例。
- 内容形式，例如 single image、comic grid。
- 播放量、点赞、评论、收藏、分享。
- 完播率或完成率。
- 主观判断：great、good、average、poor。
- 备注：钩子、标题、发布时间、评论区反馈、下一次实验方向。

建议每条发布内容至少在发布后 24 小时和 72 小时各记录一次。

### 13.5 周复盘和月复盘

点击 `Weekly Review` 或 `Monthly Review`。

系统会汇总：

- 任务完成数量。
- 已记录工作时长。
- 发布内容数量。
- 总浏览量。
- 表现较好的平台和比例。
- 简单建议。

目前复盘是规则型总结，适合做 MVP 阶段的基础判断。未来可以升级为 AI 复盘和自动重排期。

## 14. 推荐工作流

建议每个漫画内容按这个顺序走：

1. 新建项目。
2. 填 Project Bible。
3. 在 Schedule 里设定发布日期和制作节奏。
4. 粘贴剧本并拆分分镜。
5. 人工检查并修改分镜。
6. 选择目标平台比例。
7. 先生成 1 到 2 张测试图。
8. 调整提示词和风格。
9. 批量生成。
10. 导出单图或漫画网格图。
11. 发布到平台。
12. 回到 Schedule 记录反馈。
13. 每周复盘并调整下一轮内容策略。

## 15. 常见问题

页面打不开：先运行停止脚本，再运行启动脚本。

模型测试失败：检查 API Key、Base URL、模型名称、网络和中转服务状态。

能拆分剧本但不能生成图：通常是图片接口配置问题，不是文本模型问题。

生成图比例不对：先检查 `Production` 区域选择的比例，再检查图片模型是否支持该尺寸。

日程没有任务：需要先在 Schedule 页面生成计划。

复盘结果太简单：当前是基础复盘，建议你先持续记录时间和反馈，后续再加 AI 分析与自动重排期。

## 16. 当前阶段建议

现在最适合做的是：用 1 个真实短篇项目跑完整流程。不要急着打包 `.exe`，先确认剧本拆分、图片生成、网格导出、日程记录、复盘这条链路能稳定产出。等这条链路跑顺，再进入 Windows 桌面封装阶段。
