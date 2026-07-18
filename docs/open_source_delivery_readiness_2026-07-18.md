# Paneloom 开源交付准备度审计

日期：2026-07-18（Asia/Tokyo）
最新验证源码：`090e7d052de8dd30f291cde0dce822b3fc1b5c8f`

## 1. 执行摘要

本报告只评估当前 Git 源码、Vite production build 和 production-like pywebview/WebView2 运行链，不把“构建成功”写成“安装包已经验证”。本轮没有生成安装包、Release 或正式发行物。

```text
SOURCE_OPEN_SOURCE_PREREQUISITES = PASS
CODE_FUNCTIONAL_REGRESSION = PASS
PRODUCTION_LIKE_DESKTOP_RUNTIME = PASS
TASKBAR_ICON_RUNTIME_CONFIGURATION = PASS
TASKBAR_ICON_USER_VISUAL_CONFIRMATION = PENDING
USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
PUBLIC_OPEN_SOURCE_RELEASE_ALLOWED = NO
PACKAGING_ALLOWED = NO
FINAL_DISTRIBUTION_ARTIFACT_VALIDATED = NO
```

Paneloom 当前已经达到“可继续进行用户人工验收”的开源源码质量线：已知 Python/npm 漏洞清零，最小 Windows CI、lint、仓库卫生检查、版本号、安全政策、社区模板和第三方许可说明均已建立。公开发布仍被用户人工全功能验收和任务栏图标视觉确认阻止；远程 GitHub CI 也尚未实际执行。

当前验证等级为 **State B + production-like runtime evidence**：源码测试和生产构建桌面运行通过，但没有正式 artifact，因此不是 State C 或 State D。

## 2. 唯一源码与运行链

| 项目 | 结果 |
|---|---|
| 仓库根目录 | `C:\Users\esthe\Desktop\StoryboardGenie` |
| 分支 | `main` |
| 当前审计基线 | `090e7d052de8dd30f291cde0dce822b3fc1b5c8f` |
| 生产前端输入 | `frontend/index.html`、`frontend/src/`、`frontend/public/` |
| 生产前端输出 | `frontend/dist/` |
| 桌面入口 | `desktop/launcher.py` |
| 后端入口 | `backend.main:app` |
| 桌面运行 | pywebview 6.1 + WebView2 + 随机 `127.0.0.1` 端口 |
| 当前版本 | `0.1.0-beta.1`（根 `VERSION`、前端 package、`/health` 一致） |
| 正式打包链 | 未建立；当前阶段禁止打包 |

```text
frontend source
  -> npm run build
  -> frontend/dist
  -> desktop/launcher.py
  -> FastAPI on random 127.0.0.1 port
  -> pywebview/WebView2 native window
```

## 3. 图标与桌面身份

用户确认地球图由 AI 生成，并拥有必要使用权。项目内授权说明位于 `desktop/resources/README.md`。

| 文件 | 用途 | SHA-256 |
|---|---|---|
| `desktop/resources/paneloom-icon-source.png` | 用户原图副本 | `0CEAB2281F735DA8864629B3B5FD141CE57AB546AAC4655F40B0C650E1FEC1A1` |
| `desktop/resources/paneloom-icon.png` | 1024x1024 透明标准图标 | `E99F81FAA4CC506312E61267392BD7A7797E10EF70316839049F22283D894E4A` |
| `desktop/resources/paneloom.ico` | Windows 多尺寸图标 | `E91D79C6774E845CC9E0AF299A44A6DDC5F2F38344148A35337C757B4E591985` |
| `frontend/public/paneloom-icon.png` | favicon/侧栏品牌图 | `E99F81FAA4CC506312E61267392BD7A7797E10EF70316839049F22283D894E4A` |

Windows 修复不是只传递 pywebview 的 `icon` 参数。WinForms 窗口在 UI 线程显式设置 `Form.Icon`，进程同时设置 `Paneloom.Desktop` AppUserModelID。最新原生窗口烟测记录 `window_icon_applied=true`、`app_user_model_id_applied=true`。侧栏原 `PL` 文字块已替换为同一透明地球图。

仍需用户观察当前真实测试窗口的任务栏图标。运行标志通过不能替代 Windows 任务栏缓存、分组和用户实际显示结果。

保留原生 Windows 标题栏。移除原生框会引入拖动、缩放、Snap、系统菜单、DPI 和无障碍回归；当前没有足够产品收益支持该风险。

## 4. 字体与许可边界

- 仓库没有分发 `.ttf`、`.otf` 或 `.woff` 字体文件。
- `PL` 不是字体资产，只是旧的普通文字品牌标记，现已被地球图替换。
- 前端已移除未捆绑的 `Inter` 声明，使用 `ui-sans-serif`、`system-ui`、`Segoe UI` 等系统 UI 字体回退。
- 应用只调用用户 Windows 已安装字体，不复制或随项目重新分发 Segoe UI 字体文件。
- 本结论是代码与分发边界审计，不替代法律意见。

## 5. 已完成的开源基线修复

| 范围 | 当前结果 |
|---|---|
| Python 依赖 | FastAPI 0.139.2、Starlette 1.3.1、python-multipart 0.0.32、Pillow 12.3.0 |
| Python 漏洞扫描 | `pip-audit`：0 个已知漏洞 |
| npm 漏洞扫描 | `npm audit`：0 个漏洞 |
| 静态检查 | Ruff、ESLint、Vite build 已固定为可重复命令 |
| 仓库卫生 | `scripts/check_repository_hygiene.py` 检查受跟踪密钥和用户运行数据 |
| CI | `.github/workflows/ci.yml` 提供 Windows Python/Node 全链检查 |
| 版本 | `VERSION=0.1.0-beta.1`，`/health` 与前端一致 |
| 文档 | README、CONTRIBUTING、CHANGELOG、SECURITY、CODE_OF_CONDUCT |
| 社区入口 | Issue 模板、PR 模板、私密漏洞报告说明 |
| 许可 | MIT + `THIRD_PARTY_NOTICES.md` + 图标授权说明 |
| 忽略规则 | 用户项目、日志、缓存、临时文件、虚拟环境、coverage、build artifacts 均不入库 |
| 错误修复 | 修复参考图“复制图片链接”的未定义函数；删除重复翻译键；校正 Hook 生命周期 |

最小 CI 文件已经通过本地 YAML 解析，但尚未配置远程仓库，也没有真实 GitHub Actions 运行记录，不能标成远程 CI PASS。

## 6. 最新验证证据

| 验证 | 结果 | 证据 |
|---|---|---|
| Repository hygiene | PASS | 无受跟踪真实密钥或用户运行数据 |
| Ruff | PASS | All checks passed |
| Python compileall | PASS | `backend`、`api`、`desktop`、`scripts` |
| 完整 unittest | PASS | 56/56 |
| Frontend check | PASS | ESLint 0 error；Vite 8.1.3 production build，1740 modules |
| npm audit | PASS | 0 vulnerabilities |
| pip check | PASS | No broken requirements found |
| pip-audit | PASS | No known vulnerabilities found |
| Runtime smoke | PASS | `127.0.0.1:49274`，production frontend served |
| WebView2 window smoke | PASS | `127.0.0.1:53421`，React root 和 UI 交互通过 |
| 动态 API 地址 | PASS | `/health`、`/projects` 全部使用当前运行 origin |
| Time to interactive | PASS | 9.203 秒 |
| Clean shutdown | PASS | WebView 关闭后约 0.406 秒后端停止；端口释放 |
| 黑屏回归 | PASS | 10 轮、5 页面、50 次路由切换；根节点和导航始终存在 |
| 页面异常恢复 | PASS | 页面级和全局受控异常均显示 fallback，可返回总览 |
| 项目切换/离线 | PASS | 切换项目后根节点存在；离线提示可见 |

production build 身份：

| 文件 | SHA-256 |
|---|---|
| `frontend/dist/index.html` | `92D5B25F84E13935529460D6ECF67C9C87E037808F9D6CF64B4471F360E1340B` |
| `frontend/dist/assets/index-i6LLi7zh.js` | `6D7BD1838BE23686820176D6A6F1CC804C49F8E9D13ADCE6710B4F086BA45B2A` |
| `frontend/dist/assets/index-BJWTXF3T.css` | `EAA027CA5D79FA15630D9226FFFF8F84AB4178FD482D06477B2A585384EE6DE8` |
| `frontend/dist/paneloom-icon.png` | `E99F81FAA4CC506312E61267392BD7A7797E10EF70316839049F22283D894E4A` |

黑屏测试中的静态资源失败条目是受控失败注入目标；测试结论同时确认 `main_bundle_loaded=true`、`css_loaded=true`，不是生产资源加载失败。

## 7. 历史功能链保护

本轮没有重构项目数据、AI 请求、图片版本、锁定、导出、备份或迁移协议。56 个测试继续覆盖：

- 项目自包含、迁移、备份恢复和 schema 兼容；
- 文档导入、文本 AI 请求、图片生成请求和供应商错误；
- 图片原子落盘、版本选择、镜头锁定和覆盖保护；
- 活动任务关闭、陈旧 running 恢复、离线编辑和导出；
- 动态桌面端口、错误边界、运行日志脱敏和 DPAPI 密钥边界。

用户的真实项目和 17 个历史项目未在本轮修改或迁移。

## 8. 评分

| 维度 | 分数 | 说明 |
|---|---:|---|
| 核心行为与回归保护 | 93/100 | 自动回归和 production-like 运行完整；仍待用户全流程复验 |
| 源码与构建可追溯性 | 93/100 | Git、版本、构建输入输出、哈希明确；尚无正式打包链 |
| 安全与隐私 | 94/100 | npm/pip 漏洞为 0，密钥和用户数据边界通过 |
| 文档与可复现性 | 91/100 | 本地命令和 CI 已固化；远程 CI 尚未实际运行 |
| 开源法律与资产 | 91/100 | MIT、直接依赖说明和图标授权存在；二进制发布前仍需固化完整传递依赖清单 |
| 社区与维护治理 | 87/100 | 模板、安全政策和 CI 已建立；缺少公开仓库真实运行记录和验收后截图 |

```text
OPEN_SOURCE_SOURCE_READINESS_SCORE = 92 / 100
```

该分数表示源码准备度，不代表用户人工验收、安装包或公开发布已经通过。

## 9. 未完成与下一步

### 发布前硬门禁

1. 用户在当前 production-like 桌面测试窗口确认任务栏和侧栏均显示地球图标。
2. 用户完成一轮真实全功能测试，并明确允许进入下一阶段。
3. 对人工测试中新发现的 P0/P1 使用同一复现路径修复和回归。

### 首次公开源码仓库建立后

1. 首次远程 push 前再次运行 secret scan，并确认没有私人项目资产进入提交。
2. 观察 GitHub Actions 的首个真实运行；失败时按真实日志修复，不能把本地 YAML 存在当作 CI 成功。
3. 人工验收完成后再添加真实截图；当前不以旧 UI 截图误导用户。

### 未来二进制发布前

1. 生成完整传递依赖许可证清单和 SBOM。
2. 单独设计、构建和验证安装包链；记录唯一 artifact 的路径、大小、时间和 SHA-256。
3. 在干净 Windows 环境实际安装该确切 artifact，并重新执行用户核心流程。

## 10. 最终门禁

```text
MIT_LICENSE_PRESENT = YES
TRACKED_PLAINTEXT_SECRET = NO
USER_PROJECT_ASSETS_TRACKED = NO
NPM_AUDIT = PASS
PYTHON_DEPENDENCY_AUDIT = PASS
FULL_AUTOMATED_REGRESSION = PASS
PRODUCTION_BUILD = PASS
PRODUCTION_LIKE_DESKTOP_SMOKE = PASS
BLACK_SCREEN_REGRESSION_10_RUNS = PASS
ICON_RUNTIME_INTEGRATION = PASS
ICON_PUBLIC_LICENSE_PROVENANCE = PASS
CI_DEFINITION_AVAILABLE = YES
REMOTE_CI_EXECUTED = NO
SOURCE_OPEN_SOURCE_PREREQUISITES = PASS
TASKBAR_ICON_USER_VISUAL_CONFIRMATION = PENDING
USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
PUBLIC_OPEN_SOURCE_RELEASE_ALLOWED = NO
PACKAGING_ALLOWED = NO
```

明确结论：当前源码可以交给用户继续进行 Windows 桌面全功能人工验收；当前不能公开发布，不能打包，也不能声称最终交付物已验证。只有用户明确验收通过后，才进入独立的打包链设计和干净机器验证阶段。
