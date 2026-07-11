# Paneloom Windows 桌面版全功能交互验收

日期：2026-07-11

阶段：用户人工全功能验收准备完成，等待用户本人操作

## 1. 执行摘要

真实 production-like pywebview/WebView2 桌面测试窗口已经通过根目录 `start_desktop_test.bat` 拉起，并保持打开供用户操作。当前不是浏览器开发页，没有启动 Vite dev server，不需要手动运行 npm、uvicorn 或输入 localhost。

当前窗口证据：

```text
status                   window_ready
window title             Paneloom
launcher PID             23340
random loopback endpoint 127.0.0.1:49789
health                   OK
offline mode             false
project count            18
manual fixture count     1
listener count           1
production bundle :8000  0
```

本轮只完成“可供用户验收”的准备、确定性缺陷修复和自动回归。用户本人尚未逐项填写人工清单，因此打包仍被硬门禁禁止。

```text
CODE_ARCHITECTURE_PACKAGING_PREREQUISITES = PASS
USER_FUNCTIONAL_ACCEPTANCE = NOT_STARTED
USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
PACKAGING_ALLOWED = NO
```

## 2. Git 验收前基线

```text
FUNCTIONAL_ACCEPTANCE_BASELINE_COMMIT = 883f2155b6e209be552f6886ead79d63ab6de745
FUNCTIONAL_ACCEPTANCE_BASELINE_TAG = functional-acceptance-baseline-2026-07-11
WORKTREE_CLEAN_BEFORE_ACCEPTANCE = YES
branch = main
remote = none
```

基线建立时：

- Git 工作区改动为 0。
- 追踪文件真实密钥模式匹配为 0。
- 用户项目、生成图、私人剧本、日志、缓存、临时文件、环境目录和构建产物追踪数量为 0。
- `.gitignore` 排除完整 `db/`、`assets/`、`exports/`、`logs/`、`uploads/`、所有 `.env*`（保留 `.env.example`）、虚拟环境、node_modules、dist/build、临时/备份/归档/SQLite 文件。
- 没有配置 Git 远程，没有上传代码或资产。

## 3. 桌面测试启动方式

正常模式：双击仓库根目录的：

```text
start_desktop_test.bat
```

离线模式：先关闭正常窗口，再双击：

```text
start_desktop_test_offline.bat
```

测试入口会检查：

- `.desktop-venv` 中的 Python/pythonw；
- FastAPI、Uvicorn 和 pywebview 依赖；
- `desktop/launcher.py`；
- Vite production build 的 `frontend/dist/index.html`；
- 启动进程是否提前退出；
- 120 秒内是否出现 `window_ready`。

启动错误会显示真实失败原因，并指向 `%LOCALAPPDATA%\Paneloom\logs\desktop-startup.log`。这两个入口不是安装包，也不生成发行物。

## 4. 非计费人工验收素材

当前已经创建一个可删除项目：

```text
Paneloom 人工验收素材（可删除）
```

它包含：

- 虚构剧本；
- 角色、场景、道具和视觉风格 Bible；
- 一张角色参考 PNG；
- 一张场景参考 PNG；
- 一个未锁定分镜；
- 两张本地生成的纯色 fixture 图片；
- A/B 两个图片版本；
- 已选择的 A 版本；
- JSON 和带真实项目内图片引用的 HTML 导出。

素材创建过程不调用文本或图片供应商，不读取或修改已有私人项目。若删除后需要重建，请先关闭 Paneloom，再双击 `create_manual_acceptance_fixture.bat`。

## 5. 当前全功能地图

表中状态表示代码连接与自动回归状态，不代表用户已经人工验收。所有页面仍需按人工清单实际点击。

### 总览与全局导航

| 功能 ID | 页面 | 入口 | 预期行为 | 当前真实行为 | 状态 | 问题/严重度 |
| --- | --- | --- | --- | --- | --- | --- |
| DASH-01 | 全局 | 左侧五个导航按钮 | 切换对应页面 | React hash 页面切换；原生 smoke 已点击项目页 | PASS | 人工观感待确认 |
| DASH-02 | 总览 | 本地服务状态 | 显示连接/错误 | 真实调用 `/health` | PASS | 无 |
| DASH-03 | 总览 | 当前项目卡片 | 显示当前项目或首次引导 | 来自真实项目列表 | PASS | 无 |
| DASH-04 | 总览 | 打开项目资产 | 进入分镜资产区 | 调用页面导航和滚动 | PASS | 人工滚动位置待确认 |
| DASH-05 | 顶部 | 当前项目下拉框 | 切换项目 | 保存项目 ID 到 localStorage，后端数据按项目加载 | PASS | 无 |
| DASH-06 | 顶部 | 语言下拉框 | 切换系统/五种语言 | 真实 i18n 字典和持久化 | PARTIAL | 五语言逐页人工检查未完成，P2 |
| DASH-07 | 总览 | 后端技术地址 | 桌面用户不显示 localhost | 本轮已移除 URL，只保留本地服务状态 | PASS | 已修复 P2 |

### 项目

| 功能 ID | 页面 | 入口 | 预期行为 | 当前真实行为 | 状态 | 问题/严重度 |
| --- | --- | --- | --- | --- | --- | --- |
| PROJ-01 | 项目 | 项目名称/描述/位置 + 创建 | 创建自包含项目 | 调用真实创建 API | PASS | 人工点击待确认 |
| PROJ-02 | 项目 | 选择文件夹图标 | 打开原生文件夹选择 | pywebview 原生对话框 | PASS | 人工对话框待确认 |
| PROJ-03 | 项目 | 项目列表卡片 | 选择当前项目 | 真实项目 ID 切换 | PASS | 无 |
| PROJ-04 | 项目 | 已有项目文件夹 + 打开 | 重新注册移动项目 | 调用 `/projects/open` | PASS | 人工移动待确认 |
| PROJ-05 | 项目 | 名称/描述 + 保存 | 更新项目 | 原子更新项目配置 | PASS | 无 |
| PROJ-06 | 项目 | 复制项目 | 复制完整自包含目录 | 后端复制并改写项目 ID | PASS | 人工资产核对待确认 |
| PROJ-07 | 项目 | 归档/取消归档 | 保存归档状态 | 真实更新项目配置 | PASS | 无 |
| PROJ-08 | 项目 | 删除项目 | 二次确认，可恢复删除 | 有 `window.confirm`；目录移入回收目录 | PASS | 人工文案待确认 |
| PROJ-09 | 项目 | 备份项目 | 生成完整校验 ZIP | 后端 manifest/size/SHA-256 已验证 | PASS | UI 人工待确认 |
| PROJ-10 | 项目 | 选择备份 | 打开原生 ZIP 选择 | pywebview 原生对话框 | PASS | 人工待确认 |
| PROJ-11 | 项目 | 恢复为新项目 | 不覆盖原项目 | 后端创建新 ID | PASS | UI 人工待确认 |
| PROJ-12 | 项目 | 迁移自包含项目 | 迁移旧项目 | 只对 legacy 项目显示/启用 | PASS | 17 项已迁移 |

### 剧本与故事优化

| 功能 ID | 页面 | 入口 | 预期行为 | 当前真实行为 | 状态 | 问题/严重度 |
| --- | --- | --- | --- | --- | --- | --- |
| SCR-01 | 分镜制作 | 剧本/旁白文本框 | 输入并自动保存 | 700ms 延迟保存 workspace | PASS | 人工输入待确认 |
| SCR-02 | 分镜制作 | 文件上传 | 解析文档 | 真实 multipart 解析 | PASS | 无 |
| SCR-03 | 分镜制作 | TXT/MD/SRT/CSV | 提取文本 | 自动测试通过 | PASS | 人工文件待确认 |
| SCR-04 | 分镜制作 | 文本 PDF | 提取可选择文字 | pypdf 真实解析 | PASS | 人工文件待确认 |
| SCR-05 | 分镜制作 | DOCX/EPUB/RTF/HTML/XLSX | 提取正文/单元格 | 自动测试通过 | PASS | 人工文件待确认 |
| SCR-06 | 分镜制作 | 扫描 PDF | 不能假装 OCR | 明确提示先 OCR | NOT_APPLICABLE | OCR 引擎未实现，诚实拒绝 |
| STORY-01 | 分镜制作 | AI 优化故事 | 真实文本调用、loading、结果 | 当前文本供应商已真实验证，UI 调用真实 API | PASS | 用户 UI 调用待确认 |
| STORY-02 | 分镜制作 | 应用优化 | 替换剧本并保存旧版 | 保存 script_versions | PASS | 无 |
| STORY-03 | 分镜制作 | 放弃优化 | 不覆盖原剧本 | 清除建议快照 | PASS | 无 |
| STORY-04 | 分镜制作 | 撤销修改 | 回到上一剧本 | 栈式撤销 | PASS | 无 |
| STORY-05 | 分镜制作 | 历史/差异/部分接受 | 完整版本管理 | 无可浏览历史、diff 或逐段接受 | PARTIAL | P1 产品限制 |

### Bible 与资产连续性

| 功能 ID | 页面 | 入口 | 预期行为 | 当前真实行为 | 状态 | 问题/严重度 |
| --- | --- | --- | --- | --- | --- | --- |
| BIBLE-01 | 分镜制作 | 风格/角色/场景/道具/世界说明 | 保存并重启恢复 | 项目 JSON 原子保存 | PASS | 人工待确认 |
| BIBLE-02 | 分镜制作 | Prompt 前缀/Negative Prompt | 参与生成 | 自动测试确认进入最终 Prompt | PASS | 无 |
| BIBLE-03 | 分镜制作 | AI 分析设置 | 文本模型提取建议 | 真实文本客户端 + 离线 fallback | PASS | UI 人工待确认 |
| ASSET-01 | 分镜制作 | 参考图上传 | 校验并保存 PNG/JPEG/WEBP | 真实文件校验和项目内保存 | PASS | 无 |
| ASSET-02 | 分镜制作 | 选择参考图 | 后续生成使用 | workspace 保存所选文件名 | PASS | 无 |
| ASSET-03 | 分镜制作 | 预览/下载/复制链接 | 对真实资产操作 | 真实项目文件 URL | PASS | 人工待确认 |
| ASSET-04 | 分镜制作 | 删除参考图 | 确认后删除 | 后端真实删除 | PASS | 人工确认待测 |
| ASSET-05 | 分镜制作 | 风格分析 | 视觉模型/本地分析并写 Bible | 请求路径已接通；供应商调用可能计费 | EXTERNAL_BLOCKED | 未授权视觉费用 |
| ASSET-06 | 分镜制作 | 生成角色/世界资产 | 真实图片生成 | 请求构造存在 | EXTERNAL_BLOCKED | 未授权图片费用 |
| CONT-01 | 生成链路 | 角色到 Prompt | 角色文字参与请求 | 非计费测试断言通过 | PASS | 无 |
| CONT-02 | 生成链路 | 场景到 Prompt | 场景文字参与请求 | 非计费测试断言通过 | PASS | 无 |
| CONT-03 | 生成链路 | 参考图到生成 | 走图片编辑请求 | 非计费测试确认 `edit_image` 收到真实本地文件 | PASS | 无 |

### 分镜、图片与版本

| 功能 ID | 页面 | 入口 | 预期行为 | 当前真实行为 | 状态 | 问题/严重度 |
| --- | --- | --- | --- | --- | --- | --- |
| SHOT-01 | 分镜制作 | 从剧本生成 | 本地/文本 AI 拆分并保存 | 两条真实路径 | PASS | 用户 UI 待确认 |
| SHOT-02 | 分镜制作 | 重写连续分镜 | 重写现有镜头 | 后端真实重写 | PASS | 文本调用可能计费 |
| SHOT-03 | 分镜制作 | 手动添加 | 新建镜头 | 后端 CRUD | PASS | 无 |
| SHOT-04 | 分镜制作 | 编辑/保存/取消 | 更新真实镜头 | 后端原子保存 | PASS | 无 |
| SHOT-05 | 分镜制作 | 上移/下移 | 保存顺序 | 后端 reorder | PASS | 无 |
| SHOT-06 | 分镜制作 | 删除 | 确认并删除未锁定镜头 | 后端约束 | PASS | 无 |
| SHOT-07 | 分镜制作 | 锁定/解锁 | 保存批准状态 | 后端强制锁定 | PASS | 无 |
| SHOT-08 | 分镜制作 | 编辑/删除/换版/生成锁定镜头 | 后端拒绝 | 自动测试通过 | PASS | 无 |
| SHOT-09 | 分镜字段 | 场景 ID、时长、说明、Prompt、Negative、修订 | 保存现有结构 | 真实字段存在 | PASS | 无独立机位/景别/对白/旁白字段，产品限制 |
| IMG-01 | 分镜制作 | 单镜头生成 | 发起真实图片任务 | UI/API 已连接 | EXTERNAL_BLOCKED | 未授权真实供应商费用 |
| IMG-02 | 分镜制作 | 待生成批量队列 | 串行队列、停止、错误 | 实际队列并发 1 | EXTERNAL_BLOCKED | 真实供应商未验收 |
| IMG-03 | 分镜制作 | loading/轮询/失败 | 状态明确、可重试 | job API、超时/失败测试通过 | PASS | UI 人工待确认 |
| IMG-04 | 分镜制作 | 历史版本按钮 | 切换版本 | 后端真实选版 | PASS | 非计费 fixture 已准备 |
| IMG-05 | 分镜制作 | 图片预览弹窗 | 关闭/下载/打开/复制 | 真实图片 URL | PASS | 人工待确认 |

### 导出

| 功能 ID | 页面 | 入口 | 预期行为 | 当前真实行为 | 状态 | 问题/严重度 |
| --- | --- | --- | --- | --- | --- | --- |
| EXP-01 | 分镜制作 | JSON | 非空可解析 | 自动测试通过 | PASS | 无 |
| EXP-02 | 分镜制作 | CSV | 非空、表格安全 | 自动测试通过 | PASS | 无 |
| EXP-03 | 分镜制作 | XLSX | 可打开 | openpyxl 验证通过 | PASS | 无 |
| EXP-04 | 分镜制作 | SRT | 时间格式正确 | 自动测试通过 | PASS | 无 |
| EXP-05 | 分镜制作 | HTML | 文字和项目图片可显示 | 本轮修复为 `../generated/...` 项目内引用并测试 | PASS | 已修复 P1 |
| EXP-06 | 图片预览 | 下载单图 | 下载真实文件 | 真实项目 URL | PASS | 人工待确认 |
| EXP-07 | 漫画网格 | 比例/列数/导出 PNG | Canvas 生成非空 PNG | 真实 Canvas 实现 | PARTIAL | 需要用户视觉检查，P2 |
| EXP-08 | HTML 缺图 | 确认弹窗 | 用户决定占位符导出 | 有确认逻辑 | PASS | 人工文案待确认 |

### 排期复盘

| 功能 ID | 页面 | 入口 | 预期行为 | 当前真实行为 | 状态 | 问题/严重度 |
| --- | --- | --- | --- | --- | --- | --- |
| SCHED-01 | 排期复盘 | 计划表单 + 生成 | 创建任务计划 | 真实项目 JSON/CSV 数据 | PASS | 人工待确认 |
| SCHED-02 | 排期复盘 | 任务状态下拉 | 编辑状态 | 后端更新 task | PASS | 无 |
| SCHED-03 | 排期复盘 | 工时表单 | 添加工时 | 真实 CSV | PASS | 无 |
| SCHED-04 | 排期复盘 | 发布反馈表单 | 添加平台指标 | 真实 CSV | PASS | 无 |
| SCHED-05 | 排期复盘 | 截图识别 | 视觉模型提取指标 | 真实请求路径 | EXTERNAL_BLOCKED | 视觉供应商未授权 |
| SCHED-06 | 排期复盘 | 周/月复盘 | 统计和保存复盘 | 自动统计测试通过 | PASS | 人工待确认 |
| SCHED-07 | 排期复盘 | 完成率/工时/反馈统计 | 根据记录计算 | useMemo 真实计算 | PASS | 无 |
| SCHED-08 | 排期复盘 | 删除计划/工时/反馈 | 可撤销清理错误记录 | 当前无删除入口 | PARTIAL | P1 功能限制 |
| SCHED-09 | 排期与分镜 | 自动同步镜头状态 | 任务随镜头变化 | 当前仅项目关联和手动状态 | PARTIAL | P1 功能限制 |

### 模型设置、语言和离线

| 功能 ID | 页面 | 入口 | 预期行为 | 当前真实行为 | 状态 | 问题/严重度 |
| --- | --- | --- | --- | --- | --- | --- |
| SET-01 | 模型设置 | 文本供应商/模式/地址/模型 | 改变真实请求配置 | 后端读取保存值 | PASS | 人工切换待确认 |
| SET-02 | 模型设置 | 图片供应商/模型/尺寸/质量 | 改变真实图片配置 | 后端读取保存值 | PASS | 真实图片调用外部阻塞 |
| SET-03 | 模型设置 | 密钥输入/保存 | DPAPI 加密 | 自动安全测试通过 | PASS | 无 |
| SET-04 | 模型设置 | 测试连接 | 真实供应商/models 检查 | 错误不会假成功 | PASS | 人工错误 key 待测 |
| SET-05 | 模型设置 | 清除已保存密钥 | 删除两类本地密钥 | 本轮新增明确按钮和后端标志；密文移除测试通过 | PASS | 已修复 P1 |
| LANG-01 | 全局 | 系统/简中/繁中/英/日/韩 | 全页面一致 | 字典存在且选择持久化 | PARTIAL | 人工逐页检查未完成，P2 |
| OFF-01 | 离线入口 | `start_desktop_test_offline.bat` | 原生窗口离线启动 | 环境强制离线，launcher/production build 相同 | PASS | 用户 UI 待确认 |
| OFF-02 | 全局离线 | 本地项目/编辑/资产/导出/备份 | 不依赖网络 | 自动 E2E 通过 | PASS | 用户 UI 待确认 |
| OFF-03 | 云 AI 离线 | 禁用或明确失败 | 不无限加载/假成功 | UI cloud flag + 后端 offline guard | PASS | 用户 UI 待确认 |

## 6. 自动测试结果

```text
Python compileall                         PASS
Python unittest                           27 / 27 PASS
Vite production build                     PASS (1,738 modules)
npm audit                                 0 vulnerabilities
production bundle fixed :8000 matches     0
desktop test launcher                     PASS
current native window                     window_ready
current project list                      18
```

新增自动覆盖：

- Bible 角色、场景、道具、风格进入最终 Prompt；
- 已选参考图进入图片编辑请求；
- HTML 导出引用自包含项目生成图；
- 用户明确清除 DPAPI 保存密钥；
- 既有 25 项项目、备份、离线、锁定、图片失败/超时和桌面生命周期测试。

## 7. 真实 UI 流程状态

已自动确认：

- 原生 Paneloom 窗口真实出现；
- React production build 真实加载；
- FastAPI 动态端口连接成功；
- 项目列表真实读取；
- production bundle 不含固定 8000；
- 先前 smoke 已实际点击“项目”导航并成功切换。

未由模型代替用户确认：

- 每个按钮的视觉反馈与可理解性；
- 原生文件/文件夹对话框的人工体验；
- 所有文件格式通过 UI 选择后的体验；
- 语言逐页一致性；
- PNG 网格视觉质量；
- 备份恢复文案是否足够清楚；
- 全流程是否符合用户本人工作习惯。

这些项目必须由用户按 [manual_full_functional_acceptance_checklist_2026-07-11.md](manual_full_functional_acceptance_checklist_2026-07-11.md) 填写。

## 8. 问题分级

### P0

当前自动回归未发现新的 P0。用户人工测试仍可能发现 P0，发现后必须先停止其他工作并修复。

### P1

1. 故事优化只有应用、放弃和栈式撤销，没有完整 diff、逐段接受和可浏览历史。
2. 排期、工时、反馈记录没有删除入口。
3. 排期任务与分镜状态没有自动双向同步。

这些是已明确标记的产品限制，不伪装为完整功能。本轮不扩展为大型版本系统或项目管理系统。

### P2

1. 五种语言仍需用户逐页检查混合语言和长文本布局。
2. PNG 网格需要用户检查实际构图、裁切与视觉质量。
3. 设置页保留供应商协议值 `auto/prefer_b64_json/url_only` 等技术选项；属于专业设置，但文案可在人工反馈后调整。

## 9. 本轮已修复

| 文件 | 修复 |
| --- | --- |
| `frontend/src/pages/Dashboard.jsx` | 桌面总览隐藏随机 localhost 技术地址，只显示可理解的服务状态。 |
| `backend/app/services/export_service.py` | HTML 导出从自包含项目的 `generated/` 引用真实图片。 |
| `backend/app/models/schemas.py`、`backend/app/routes/settings.py` | 增加明确清除已保存密钥的后端语义。 |
| `frontend/src/pages/SettingsPage.jsx`、`frontend/src/i18n.jsx` | 增加带确认的“清除已保存密钥”入口和多语言文案。 |
| `scripts/start_desktop_test.ps1`、`start_desktop_test.bat` | 简单 production-like 用户测试入口。 |
| `start_desktop_test_offline.bat` | 简单离线桌面测试入口。 |
| `scripts/create_manual_acceptance_fixture.py`、`create_manual_acceptance_fixture.bat` | 非计费版本/锁定/资产测试素材。 |
| `tests/test_core_workflows.py` | 增加连续性、参考图、HTML 图片导出和清除密钥测试。 |

## 10. 图片 AI 外部阻塞

```text
TEXT_AI_REAL_PROVIDER_VALIDATED = YES
IMAGE_AI_REAL_PROVIDER_VALIDATED = EXTERNAL_BLOCKED
```

本轮没有调用付费图片 API。图片请求构造、输入校验、状态、失败、超时、保存、版本、选定、锁定、防覆盖和恢复由自动测试及非计费 fixture 覆盖。真实供应商图片生成只能在用户明确授权费用后进行。

## 11. 当前阶段门禁

```text
DESKTOP_TEST_WINDOW_LAUNCHED = YES
DESKTOP_TEST_MODE_AVAILABLE = YES
FULL_FUNCTION_MAP_CREATED = YES

AUTOMATED_FUNCTIONAL_REGRESSION = PASS
CORE_PROJECT_WORKFLOW = PASS
SCRIPT_IMPORT_WORKFLOW = PASS
STORY_AI_WORKFLOW = PASS
BIBLE_CONTINUITY_WORKFLOW = PASS
CHARACTER_TO_PROMPT = PASS
SCENE_TO_PROMPT = PASS
REFERENCE_ASSET_TO_GENERATION = PASS
STORYBOARD_WORKFLOW = PASS
IMAGE_GENERATION_UI_FLOW = EXTERNAL_BLOCKED
IMAGE_VERSION_WORKFLOW = PASS
IMAGE_SELECTION = PASS
SHOT_LOCKING_WORKFLOW = PASS
LOCKED_SHOT_OVERWRITE_PROTECTION = PASS
EXPORT_WORKFLOW = PASS
BACKUP_RESTORE_UI_WORKFLOW = PASS
SCHEDULE_REVIEW_WORKFLOW = PARTIAL
MODEL_SETTINGS_WORKFLOW = PASS
OFFLINE_UI_WORKFLOW = PASS

USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
FUNCTIONAL_ACCEPTANCE_READY_FOR_USER = YES
PACKAGING_ALLOWED = NO
```

上述 PASS 是自动回归与代码连接结论，不替代人工清单。用户人工验收仍为 PENDING。

## 12. 是否允许打包

不允许。

即使架构和自动功能回归通过，只有用户本人完整测试后明确回复“这一轮功能测试完成，可以进入打包阶段”或同等明确批准，后续阶段才可以讨论将 `PACKAGING_ALLOWED` 改为 YES。

本轮未执行 PyInstaller、Nuitka、cx_Freeze、MSI、NSIS、Inno Setup、安装器、RC、Release 或公开发布。
