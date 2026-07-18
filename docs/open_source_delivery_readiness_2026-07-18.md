# Paneloom 开源交付准备度审计

日期：2026-07-18（Asia/Tokyo）

## 1. 执行摘要

本轮完成了用户提供图标的项目内接入，并基于当前真实 Git 源码、生产构建、production-like WebView2 运行结果、完整自动测试、依赖审计和仓库卫生检查，评估 Paneloom 是否已经达到公开开源交付标准。

结论：

```text
ICON_INTEGRATION = PASS
CODE_FUNCTIONAL_REGRESSION = PASS
PRODUCTION_LIKE_DESKTOP_RUNTIME = PASS
OPEN_SOURCE_DELIVERY_READY = NO
USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
PACKAGING_ALLOWED = NO
FINAL_DISTRIBUTION_ARTIFACT_VALIDATED = NO
```

Paneloom 已经具备较好的本地桌面 Beta 源码基础，核心项目、生成、版本、锁定、导出、迁移、备份和离线流程都有自动化证据。但是当前锁定的 Python 依赖存在已知安全漏洞，仓库也没有 CI、稳定的静态检查命令和安全报告入口。因此不应现在公开宣称“已达到开源交付标准”。

本轮没有制作安装包、Release 或正式发行物。

## 2. 源码状态与可追溯性

| 项目 | 结果 |
|---|---|
| 仓库根目录 | `C:\Users\esthe\Desktop\StoryboardGenie` |
| 分支 | `main` |
| 本轮开始 HEAD | `fd13633f5f5e0717b974018c6645a913cab62423` |
| 本轮开始工作区 | 干净 |
| 图标接入 commit | `afdd6d20c96837fd92dafadae62e3065f998006a` |
| Windows 原生图标显示修复 commit | `e9f29cb71783d881708f360108cd2de8a61402d5` |
| 生产前端输入 | `frontend/index.html`、`frontend/src/`、`frontend/public/` |
| 生产前端输出 | `frontend/dist/` |
| 桌面运行入口 | `desktop/launcher.py` |
| 本地后端入口 | `backend.main:app` |
| 桌面运行方式 | pywebview 6.1 + WebView2 + 随机 `127.0.0.1` 端口 |
| 正式打包输入/输出 | 未建立；本阶段禁止打包 |

真实生产式链路：

```text
frontend/index.html + frontend/src + frontend/public
  -> Vite production build
  -> frontend/dist
  -> desktop/launcher.py 挂载同一 FastAPI 应用
  -> 随机 127.0.0.1 端口
  -> pywebview/WebView2 原生窗口
```

不存在本轮最终安装包，因此不能达到最终交付物验证 State D。本轮达到的是 State C：production build 已生成并由 production-like 原生窗口实际加载，但没有正式发行 artifact。

## 3. 图标接入

用户提供的原图角色：唯一图标源，不进行重新绘制。

处理方式：使用本地 Pillow 做确定性裁切、居中、透明画布标准化和 ICO 多尺寸编码；没有调用生成式图片模型，没有生成 prompt，也没有改变地球主体。

输出：

| 文件 | 用途 | SHA-256 |
|---|---|---|
| `desktop/resources/paneloom-icon-source.png` | 用户原始源图副本 | `0CEAB2281F735DA8864629B3B5FD141CE57AB546AAC4655F40B0C650E1FEC1A1` |
| `desktop/resources/paneloom-icon.png` | 1024x1024 标准透明图标 | `E99F81FAA4CC506312E61267392BD7A7797E10EF70316839049F22283D894E4A` |
| `desktop/resources/paneloom.ico` | Windows 多尺寸图标 | `E91D79C6774E845CC9E0AF299A44A6DDC5F2F38344148A35337C757B4E591985` |
| `frontend/public/paneloom-icon.png` | Vite/favicon 输入 | `E99F81FAA4CC506312E61267392BD7A7797E10EF70316839049F22283D894E4A` |

图标规格：

- PNG 为 RGBA 透明背景，角点 alpha 为 0。
- 地球主体 alpha 边界为 `(86, 84, 938, 939)`，约占 1024 画布的 84%。
- 没有外加方形底板、描边、圆角容器或阴影。
- ICO 包含 16、24、32、48、64、128、256 像素尺寸。
- pywebview 的 Windows WinForms 原生窗口和窗口烟测都将同一 `paneloom.ico` 设置为 `Form.Icon`。
- Vite production build 中的 `paneloom-icon.png` 与项目标准 PNG 哈希一致。

项目所有者已于 2026-07-18 确认：该图标由 AI 生成，项目所有者拥有必要使用权并授权其随 Paneloom 按项目 MIT License 再分发。授权说明记录在 `desktop/resources/README.md`。

## 4. 本轮修改

| 文件 | 原因 |
|---|---|
| `desktop/launcher.py` | 将项目 ICO 设置到 pywebview 的 Windows WinForms 原生窗口；修正已经过时的动态端口烟测断言 |
| `frontend/index.html` | 引用项目 favicon |
| `frontend/public/paneloom-icon.png` | 让 Vite 生产构建包含同一图标 |
| `desktop/resources/*` | 保存原图、标准 PNG 和 Windows ICO |
| `tests/test_desktop_runtime.py` | 验证 PNG 透明度、ICO 尺寸、favicon 引用和动态运行端口请求 |

烟测修正的根因：总览页面在 `fff96ac` 中按桌面产品要求隐藏了 localhost/API 地址，但 `7453581` 中的旧烟测仍要求页面必须显示该地址。实际网络请求已经全部使用随机运行端口。修复后，烟测验证真实 `/health`、`/projects` 请求和 `window.location.origin`，不会重新向普通用户暴露技术地址。

## 5. 测试证据

| 验证 | 结果 | 证据 |
|---|---|---|
| Python compileall | PASS | `backend`、`api`、`desktop`、`scripts` 编译通过 |
| 完整 unittest | PASS | 54/54，59.127 秒 |
| 图标专项 unittest | PASS | 6/6 |
| Vite production build | PASS | Vite 8.1.3，1740 modules，1.70 秒 |
| production-like WebView2 smoke | PASS | production build 真实加载并可导航 |
| Windows 原生窗口图标 | PASS | `window_icon_applied=true`，WinForms `Form.Icon` 已设置 |
| 动态 API 端点 | PASS | `/health`、`/projects` 全部使用 `http://127.0.0.1:54900` |
| WebView2 首次交互 | PASS | 6.625 秒（原生图标修复后的最新 smoke） |
| 完整烟测退出 | PASS | 7.016 秒（原生图标修复后的最新 smoke） |
| 后端停止 | PASS | `server_stopped=true` |
| 监听端口残留 | PASS | 0 |
| `git diff --check` | PASS | 无空白错误 |
| npm dependency tree | PASS | 顶层依赖完整 |
| npm audit | PASS | 0 vulnerabilities，52 dependencies |
| pip check | PASS | No broken requirements found |
| Python vulnerability audit | FAIL | 3 个包共 22 条记录（包含重复的传递依赖记录） |
| Python pyflakes | NOT RUN | 两个现有 venv 都没有安装 pyflakes |
| Frontend lint/typecheck | NOT IMPLEMENTED | package scripts 只有 dev/build/preview |

production build 关键输出：

| 文件 | SHA-256 |
|---|---|
| `frontend/dist/index.html` | `1466DB46D2FF3036D7D800773794A3763693ED153FBD6D2F77AA56C9B6EBAE03` |
| `frontend/dist/assets/index-D9xeFu3Z.js` | `2BEFEB6C58DCB573F49C3B36CAF9149086EA3D6B1216E5339B1EA92A80580E1B` |
| `frontend/dist/assets/index-CTRwcZOS.css` | `BB7910EAE3BB1E5F1E634643E908ED366AB997D9956975B9488438DBDC140954` |
| `frontend/dist/paneloom-icon.png` | `E99F81FAA4CC506312E61267392BD7A7797E10EF70316839049F22283D894E4A` |

## 6. 安全与隐私

通过项：

- 当前 Git 跟踪文件未发现真实 API key、私钥、用户 settings 或凭据文件。
- 全 Git 历史（排除明确的测试 fixture）未命中检查的密钥模式、用户 relay 地址或已截图的密钥尾号。
- 没有受 Git 跟踪的用户项目、generated、exports、logs、cache、db 或 LocalAppData 数据。
- `.env.example` 只有空占位值。
- API key 仍通过 Windows DPAPI 保存；自动测试覆盖密钥遮蔽、清除和日志脱敏。
- npm audit 当前为 0。

阻塞项：

1. `python-multipart==0.0.20` 命中 6 条审计记录，最高修复目标要求升级到至少 `0.0.31`。
2. `pillow==12.2.0` 命中 8 条审计记录，修复版本为 `12.3.0`。
3. `starlette==0.47.3` 是 FastAPI 的传递依赖，命中多条审计记录。不能单独强行升级到 1.x；应选择兼容的新 FastAPI/Starlette 组合，重新执行完整 API、文件上传、离线、备份和桌面烟测。
4. 仓库没有 `SECURITY.md`，外部用户没有私密报告漏洞的明确渠道。
5. 没有自动依赖漏洞扫描、secret scanning 或更新机器人配置。

## 7. 开源仓库完整性

已有：

- MIT `LICENSE`。
- `README.md`、`CONTRIBUTING.md`、`.env.example`。
- Python requirements 使用精确版本。
- npm 使用 `package-lock.json`。
- demo 为虚构文本和 JSON，不包含真实用户项目或版权图片。
- README 已明确当前是 local desktop beta architecture，没有安装器或免费模型额度。

缺口：

- `CONTRIBUTING.md` 仍写着“如果以后增加测试再运行”，但当前已有 54 个测试；贡献者验证命令不完整。
- README 和 `.env.example` 仍列出 `IMAGE_SIZE`，实际工作台比例会覆盖旧的设置尺寸，公开文档会误导用户。
- `.gitignore` 没有忽略 README 指导创建的 `.venv/`，也没有覆盖常见的 `coverage/`、`.coverage`。
- 没有 CI workflow，外部 pull request 无法自动验证 Python 测试、Vite build、npm audit 和文档命令。
- 没有稳定的 Python lint 命令，也没有 frontend lint/typecheck script。
- 没有 `CHANGELOG.md`、公开版本策略或运行时可见的源码 commit/build 标识。
- 没有 `CODE_OF_CONDUCT.md`、Issue 模板、PR 模板；这些不是核心代码阻塞，但会影响公开社区维护。
- README 明确还缺公开截图。
- 没有自动生成的第三方许可证清单；直接依赖抽查为 MIT/BSD/Apache/ISC 等宽松许可证，但应在公开发行前固化扫描结果。

## 8. 评分

| 维度 | 分数 | 说明 |
|---|---:|---|
| 核心行为与回归保护 | 90/100 | 54 个测试和 production-like 桌面烟测较完整，用户最终人工验收仍未明确 PASS |
| 源码与构建可追溯性 | 84/100 | Git 基线清晰，production build 哈希可记录；尚无正式打包链和运行版本标识 |
| 安全与隐私 | 55/100 | 密钥与用户数据隔离良好，但 Python 依赖存在已知漏洞且无 SECURITY/自动扫描 |
| 文档与可复现性 | 68/100 | 基础文档完整，但存在失真配置和过时贡献命令，没有 CI |
| 开源法律与资产 | 85/100 | MIT 清晰，直接依赖许可证宽松，图标来源与再分发授权已记录 |
| 社区与维护治理 | 52/100 | 缺少安全渠道、CI、模板、变更日志和版本策略 |

```text
OPEN_SOURCE_DELIVERY_READINESS_SCORE = 71 / 100
```

## 9. 优先级与优化方向

### P0：公开开源前必须完成

1. 建立独立依赖升级分支，升级 `python-multipart`、Pillow，并选择兼容的新 FastAPI/Starlette 组合。
2. 升级后重新运行 54 个测试、Vite production build、production-like WebView2 smoke、离线和文件上传回归。
3. 重新运行 `pip-audit`，结果必须为 0 个未接受的已知漏洞；如果某项无法升级，必须有明确风险接受和影响说明。
4. 用户本人继续完成功能验收；在明确批准前保持 `PACKAGING_ALLOWED=NO`。

### P1：首个公开源码版本前应完成

1. 修正 README、`.env.example` 和 `CONTRIBUTING.md` 的失真说明。
2. 在 `.gitignore` 中加入 `.venv/`、`coverage/`、`.coverage`。
3. 添加 `SECURITY.md`，提供私密漏洞报告方式和支持版本范围。
4. 添加最小 CI：Python compile/test、Vite production build、npm audit、pip-audit、secret scan。
5. 增加稳定的 Python lint 和 frontend lint/typecheck 命令，并在贡献指南中固定。
6. 建立版本号、CHANGELOG 和 build/commit 可识别机制，避免用户运行旧版本却无法判断。

### P2：公开维护质量提升

1. 添加真实 production-like 截图和最短桌面测试视频。
2. 添加 Issue/PR 模板和 Code of Conduct。
3. 生成第三方许可证清单。
4. 为图标标准化过程增加可重复脚本，防止未来手工替换后 desktop/frontend 资源漂移。

## 10. 最终门禁

```text
MIT_LICENSE_PRESENT = YES
TRACKED_PLAINTEXT_SECRET = NO
USER_PROJECT_ASSETS_TRACKED = NO
NPM_AUDIT = PASS
PYTHON_DEPENDENCY_AUDIT = FAIL
FULL_AUTOMATED_REGRESSION = PASS
PRODUCTION_BUILD = PASS
PRODUCTION_LIKE_DESKTOP_SMOKE = PASS
ICON_RUNTIME_INTEGRATION = PASS
ICON_PUBLIC_LICENSE_PROVENANCE = PASS
CI_AVAILABLE = NO
USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
OPEN_SOURCE_DELIVERY_READY = NO
PACKAGING_ALLOWED = NO
```

明确结论：当前代码可以继续作为 Windows 本地桌面开源项目的基础，但还不能按“已达到开源交付标准”公开交付。先清零 Python 依赖漏洞、补齐图标许可来源和最小开源维护链，再进行一次同源码状态的全量回归；正式安装包仍必须等待用户人工验收明确批准后的独立阶段。
