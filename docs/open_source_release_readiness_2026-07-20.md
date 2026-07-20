# Paneloom 0.1.0-beta.1 开源发布就绪报告

日期：2026-07-20

## 1. 结论

Paneloom 0.1.0-beta.1 的冻结业务源码已具备公开仓库所需的基础工程与合规材料。本轮只补充发布追溯、锁定依赖、SBOM、传递依赖许可清单和 CI 校验，没有引入后续 WEBTOON/Tapas 投稿包或其他业务功能。

```text
SOURCE_OPEN_SOURCE_READY = YES
PUBLIC_SOURCE_PUBLISHED = YES
REMOTE_CI_EXECUTED = PASS
CLEAN_MACHINE_INSTALLER_VALIDATION = NOT_RUN
AUTHENTICODE_SIGNED = NO
SIGNED_BINARY_RELEASE_READY = NO
```

源码已发布到 `https://github.com/BlueVenn6/Paneloom`。`SOURCE_OPEN_SOURCE_READY = YES` 不表示当前未签名安装器已经满足正式二进制发行标准。

## 2. 源码身份

| 项目 | 值 |
|---|---|
| 隔离发布工作树 | `C:\Users\esthe\Desktop\Paneloom-open-source-v0.1.0-beta.1` |
| 发布分支 | `release/v0.1.0-beta.1-open-source` |
| 冻结业务标签 | `v0.1.0-beta.1-functional-baseline` |
| 冻结业务 commit | `09fe927ffde5d1775adc0f7904da021932ecf143` |
| 原安装器打包源码 commit | `d34d148152f63846bc42fec083b20b3cd29da563` |
| 打包来源标签 | `v0.1.0-beta.1-packaging-source` |
| 开源发布标签 | `v0.1.0-beta.1-open-source` |
| 应用版本 | `0.1.0-beta.1` |

打包来源标签固定指向 `d34d148...`。开源发布标签将在本报告及合规材料提交后创建，业务源码仍与冻结 commit 保持一致。

## 3. 已补充的开源发布材料

- `requirements-lock.txt`：Python 运行和构建环境的精确版本锁定。
- `release-source.json`：冻结业务、原打包源码和发布标签身份。
- `sbom/frontend.cdx.json`：前端 CycloneDX 1.5 SBOM。
- `sbom/python-runtime.cdx.json`：Python 运行依赖 CycloneDX 1.5 SBOM。
- `sbom/python-build.cdx.json`：Python 构建依赖 CycloneDX 1.5 SBOM。
- `THIRD_PARTY_LICENSES.md`：运行及构建传递依赖清单与随附许可文本。
- `THIRD_PARTY_NOTICES.md`：PyInstaller、NSIS、WebView2 等发行组件说明。
- `packaging/licenses/NSIS-COPYING.txt`：构建使用的 NSIS 3.12 许可文本。
- `scripts/generate_release_metadata.py`：可重复生成并校验 Python SBOM 和许可清单。
- CI：使用锁定依赖，校验生成材料无漂移，并继续执行 lint、测试、构建及依赖审计。

MIT `LICENSE`、README、贡献指南、行为准则、安全政策和密钥/用户资产排除规则继续保留。

## 4. 本机验证证据

| 验证 | 结果 |
|---|---|
| 全新 Python 虚拟环境安装锁定依赖 | PASS，安装结果与 `requirements-lock.txt` 一致 |
| `pip check` | PASS |
| `pip-audit` | PASS，0 known vulnerabilities |
| `ruff check backend api desktop scripts tests packaging` | PASS |
| Python unittest | PASS，56/56 |
| `npm ci` | PASS，135 packages |
| `npm audit` | PASS，0 vulnerabilities |
| ESLint | PASS |
| Vite production build | PASS，1740 modules |
| 本地 runtime smoke | PASS |
| 原生 pywebview/WebView2 smoke | PASS |
| Git 仓库密钥与用户资产检查 | PASS |
| SBOM JSON 解析 | PASS |

原生窗口烟测使用随机 `127.0.0.1:52178`：

| 时间点 | 秒 |
|---|---:|
| FastAPI ready | 1.719 |
| Windows 原生窗口出现 | 6.172 |
| React 首屏渲染 | 8.250 |
| UI 可交互 | 8.282 |
| WebView 关闭 | 8.297 |
| FastAPI 停止 | 8.594 |

烟测确认图标加载、React root 渲染、项目导航交互和全部 API 请求使用同一个随机运行时端点。测试使用独立临时目录，结束后临时目录已清理。

## 5. 供应链文件摘要

| 文件 | SHA-256 |
|---|---|
| `requirements-lock.txt` | `2280F9686AA5F526CF1D96753D9DDAC75EC71EDFBB6FFE091F0F6F219869F7EA` |
| `sbom/frontend.cdx.json` | `A4CC49BBACB4C235D9125D2613223A252FDC6D2C1A0B01D27A777C43FBA6F735` |
| `sbom/python-runtime.cdx.json` | `16F9F1EC7A433D96128695120DD6A20F5235702AAF3BBAA16A8B36C94F8437B5` |
| `sbom/python-build.cdx.json` | `991C773C2E0D45CC92E5C68457CE3E1CED165F4295C55EC49363EAA32EABC220` |
| `THIRD_PARTY_LICENSES.md` | `DB92B96C53543D593394CC117F068C566C639FB1F4FDA579197A382460C78FD0` |
| `packaging/licenses/NSIS-COPYING.txt` | `4B7AFCAFF275686C674620360908E5A3907C23433FDEED985AE6A078B9FB8B20` |

公开仓库 `main` 已通过 GitHub Windows CI。安装器对应的开源标签仍固定在 `7f0a6abc21bbb02f9fb68d8e45b2416143f76316`；四语 README、真实截图和 CI 修复位于后续纯仓库材料提交中，不改变冻结业务源码或既有安装器。

## 6. 公开仓库与远程 CI

- 公开仓库：`https://github.com/BlueVenn6/Paneloom`
- 远程验证 commit：`bc2fd4141ed1f0c3430697dcb1c694383687e547`
- 成功 workflow：`https://github.com/BlueVenn6/Paneloom/actions/runs/29731123755`
- Windows job：所有安装、SBOM、仓库安全、lint、编译、Vite build、56 项测试、依赖审计和 production runtime smoke 步骤均为 `success`。

首次 CI 暴露并修复了两个只在干净 runner 出现的问题：job 级别错误使用 `runner.temp`，以及桌面测试早于 Vite production build。修复后使用新 commit 完整重跑通过，没有删除或弱化测试。

## 7. 尚需外部完成的事项

1. 使用独立、干净的 Windows 10/11 机器安装并运行本轮确切安装器。
2. 正式二进制发行前取得 Authenticode 代码签名证书，对应用和安装器签名并验证签名链。
3. 对最终公开说明、品牌素材及第三方许可清单进行一次发布者复核；必要时进行法律审阅。

这些事项无法由当前无代码签名证书、无独立干净机的本地环境替代完成。

## 8. 发布边界

- 公开源码、不可移动标签和可追溯源码归档已经建立。
- 尚未创建 GitHub Release，也没有把未签名安装器描述为正式发行物。
- 当前未签名安装器只能作为明确标识的 Beta 测试包；不作为签名后的正式公开二进制发行物。
- 后续 WEBTOON/Tapas 投稿包属于冻结基线之后的功能，不进入 `0.1.0-beta.1` 开源冻结版本。

## 9. 验证等级

公开源码及远程 CI 已验证。与 `v0.1.0-beta.1-open-source` 对应的本地安装器产物处于 **State C**：唯一产物、哈希、构建来源和打包后应用运行已经确认。

只有独立环境安装该确切安装器并按目标场景完成最终交付物验收后，才可称为 State D。
