# Paneloom 交付前干净审计（2026-07-12）

## 执行结论

本轮没有打包、没有创建 Release、没有修改桌面架构，也没有扩展 SaaS、手机端或协作功能。范围仅包括：全剧视觉连续性锁、确认无调用的冗余清理、五种界面语言一致性门禁、完整自动回归、production build 和 pywebview 生产模式复核。

代码与本地桌面架构可以继续进入人工功能验收，但现在仍不能称为正式交付：用户尚未明确完成人工验收；当前 `/images/generations` 不接收视觉基准图片像素，内部多格边框只能通过强提示约束，不能承诺像素级绝对一致。

```text
CODE_DELIVERY_STANDARD = PASS
FUNCTIONAL_ACCEPTANCE_READY_FOR_USER = YES
USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
PIXEL_EXACT_INTERNAL_PANEL_BORDERS = NOT_GUARANTEED
DELIVERY_READY = NO
PACKAGING_ALLOWED = NO
```

## 本轮修改

| 文件 | 原因 | 历史项目影响 | 回退方式 |
| --- | --- | --- | --- |
| `backend/app/models/schemas.py` | 为项目 Bible 增加视觉基准来源、结构化规则和本地图像指标 | 新字段有安全默认值，旧项目可直接读取 | 回退本提交 |
| `backend/app/services/project_service.py` | 新项目默认写入视觉连续性字段；删除未使用导入 | 不迁移、不覆盖旧项目 | 回退本提交 |
| `backend/app/services/shotlist_service.py` | 将视觉连续性规则注入每次后续分镜生成提示词 | 仅视觉基准启用后生效 | 清空视觉基准或回退本提交 |
| `backend/app/services/image_service.py` | 从满意成片建立项目视觉基准；本地校准亮度、对比度、饱和度；保存校准元数据；删除已废弃编辑函数 | 不修改已有图片，视觉基准副本保存在项目目录 | 删除视觉基准参考图或回退本提交 |
| `backend/app/routes/generation.py` | 增加真实视觉基准入口，移除无 UI 调用且已废弃的参考编辑入口 | 不改变现有生成、版本、锁定路径 | 回退本提交 |
| `backend/app/services/project_portability_service.py` | 删除未使用导入 | 无 | 回退本提交 |
| `frontend/src/api.js` | 接通视觉基准入口，删除未使用的组合测试调用器 | 无数据影响 | 回退本提交 |
| `frontend/src/pages/StoryboardPage.jsx` | 提供“设为全剧视觉基准”真实入口及已应用状态 | 不改变已有图片和锁定状态 | 清空视觉基准或回退本提交 |
| `frontend/src/i18n.jsx` | 补齐五种语言同一功能键集合；日/韩不再回退英文；增加完整性守卫 | 仅界面文案 | 回退本提交 |
| `frontend/src/styles/global.css` | 视觉基准状态的紧凑布局 | 无 | 回退本提交 |
| `tests/test_core_workflows.py` | 覆盖离线视觉基准、Prompt 注入、本地色调校准和删除清理 | 测试使用隔离临时目录 | 无生产数据 |

## 关键链路状态

| 链路 | 状态 | 证据 |
| --- | --- | --- |
| 项目创建、保存、移动、备份、恢复 | PASS | 既有 portability/core 回归通过；本轮未改其数据协议 |
| 剧本导入、AI 优化、分镜生成 | PASS（代码回归） | core workflow 回归通过；真实 UI 仍由用户继续验收 |
| Bible/参考资产 -> Prompt | PASS | `apply_bible_to_shot_prompt` 回归与视觉锁测试通过 |
| `/images/generations` -> 原子保存 -> 版本 -> 选择 -> 锁定 | PASS（代码回归） | 生成、重复任务、锁定、版本测试通过 |
| 相邻分镜合并及受保护镜头阻止 | PASS | 上一提交真实 HTTP 4 -> 2 和自动测试通过 |
| 满意成片 -> 视觉基准 -> 后续 Prompt | PASS | 离线视觉基准测试与 production route 检查通过 |
| 视觉基准 -> 本地明暗/对比度/饱和度校准 | PASS | 合成暗图向基准移动的确定性测试通过 |
| 内部边框颜色和粗细像素级一致 | PARTIAL | 已有 4px 等效强规则；供应商在单张多格图内绘制，无法像本地排版器一样保证像素级一致 |
| 导出、排期自动进度、时间记录 | PASS（既有代码回归） | 本轮未改核心逻辑；仍需用户继续逐页人工验收 |
| 文字/图片模型测试 | PASS（代码边界） | 独立接口保留；组合后端兼容契约保留；付费调用不由自动化重复触发 |

## 语言一致性

简体中文、繁体中文、英文、日文、韩文现在使用同一组 563 个功能键。繁体中文由完整简中基准转换并叠加人工修订；日文和韩文已补齐此前会回退为英文的 80 个键，覆盖项目迁移、错误恢复、生成队列、参考资产计划、分镜合并、导出网格及视觉基准。

`assertCompleteTranslation` 会在 production build 时比较所有语言与英文基准的键集合。缺失或多余键会中断构建，不再静默显示英文或裸键名。

```text
ZH_CN_TRANSLATION_KEYS = 563/563
ZH_TW_TRANSLATION_KEYS = 563/563
EN_TRANSLATION_KEYS = 563/563
JA_TRANSLATION_KEYS = 563/563
KO_TRANSLATION_KEYS = 563/563
LANGUAGE_KEY_PARITY = PASS
ENGLISH_FALLBACK_IN_JA_KO = NO
```

## 冗余与安全审计

- 生产代码未发现 `TODO`、`FIXME`、`HACK`、mock、fake 或模拟成功逻辑。
- `setTimeout` 仅用于连接超时、轮询等待、保存防抖和桌面诊断，不用于假进度或假成功。
- 删除了已废弃的参考图片编辑路由/函数、未使用前端 API 方法及 Python 未使用导入。
- 后端组合模型测试接口虽然当前 UI 不调用，但仍由安全回归覆盖，作为兼容契约保留。
- Git 未跟踪用户项目、生成图、日志、缓存、LocalAppData、数据库、压缩备份或构建产物。
- 密钥扫描仅命中测试中的假密钥脱敏断言；未发现真实明文 API key。
- `npm audit --omit=dev`：0 个已知生产依赖漏洞。

## 测试证据

```text
PYTHON_COMPILE = PASS
PYFLAKES = PASS
AUTOMATED_TESTS = 48/48 PASS
GIT_DIFF_CHECK = PASS
VITE_PRODUCTION_BUILD = PASS
NPM_PRODUCTION_VULNERABILITIES = 0
DESKTOP_BACKEND_HEALTH = PASS
DESKTOP_RUNTIME_HOST = 127.0.0.1
DESKTOP_RUNTIME_PORT = RANDOM
VISUAL_MASTER_ROUTE = PASS
DEPRECATED_REFERENCE_EDIT_ROUTE = ABSENT
TEXT_AND_IMAGE_TEST_ROUTES = SEPARATE
PAID_IMAGE_CALL_TRIGGERED_BY_AUDIT = NO
```

## 未解决风险

1. 用户尚未明确完成本轮全功能人工验收，因此不能进入安装包阶段。
2. 单张多格图的内部格线由图片模型生成，当前只能强约束，无法保证每一像素完全相同。若这是交付硬标准，应在后续独立任务中改为生成无框单格并由本地确定性合成；这不是本轮应悄悄加入的小改动。
3. 图片供应商响应时间和生成画面细节仍受外部服务影响；本地可以控制超时、失败、重试、队列和持久化，不能伪称能缩短供应商推理时间。

## 最终判断

本轮代码结果足够干净，可以提交为新的本地测试基线，并让用户继续真实桌面验收。它还不是可正式交付或可打包的最终版本。

```text
FUNCTIONAL_ACCEPTANCE_READY_FOR_USER = YES
USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
DESKTOP_LOCAL_BETA_READY = YES
DELIVERY_READY = NO
PACKAGING_ALLOWED = NO
```
