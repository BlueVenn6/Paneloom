# Paneloom Windows Beta 安装器验证

日期：2026-07-20（Asia/Tokyo）

## 1. 源码身份

| 项目 | 值 |
|---|---|
| 仓库 | `C:\Users\esthe\Desktop\StoryboardGenie` |
| 冻结 tag | `v0.1.0-beta.1-functional-baseline` |
| 冻结业务 commit | `09fe927ffde5d1775adc0f7904da021932ecf143` |
| Packaging commit | `cd419eaf4b2507bec1cb849354d81365ca6efc90` |
| 应用版本 | `0.1.0-beta.1` |
| 前端输入 | `frontend/src`、`frontend/public`、`frontend/index.html` |
| 前端输出 | `frontend/dist` |
| 桌面入口 | `packaging/entrypoint.py -> desktop.launcher` |

构建脚本会拒绝打包相对冻结 tag 发生变化的业务文件。冻结后的差异只允许 packaging 配置、构建依赖和构建脚本。

## 2. 构建工具

| 工具 | 版本 |
|---|---|
| Python | 3.12.10 x64 |
| PyInstaller | 6.20.0 |
| NSIS | 3.12 |
| Node.js | 当前开发机锁定环境 |
| Vite | 8.1.3 |

最初验证了 Inno Setup 6.7.3，但编译器明确标记 `Non-commercial use only`。考虑 Paneloom 的商业路线，该临时产物被弃用且不在最终目录。正式安装器改用 zlib/libpng 等开源许可的 NSIS 3.12。

## 3. 构建门禁

| 验证 | 结果 |
|---|---|
| Git worktree clean | PASS |
| Repository hygiene | PASS |
| Ruff | PASS |
| Python unittest | PASS，56/56 |
| pip-audit | PASS，0 known vulnerabilities |
| npm clean install | PASS，135 packages |
| ESLint | PASS |
| Vite production build | PASS，1740 modules |
| npm audit | PASS，0 vulnerabilities |
| PyInstaller one-folder | PASS |
| NSIS UTF-8 中英文安装器 | PASS |
| Microsoft WebView2 bootstrapper 签名 | PASS，Microsoft Corporation |

## 4. 唯一安装器

```text
Absolute path:
C:\Users\esthe\Desktop\StoryboardGenie\artifacts\windows\installer\Paneloom-0.1.0-beta.1-Windows-x64-Setup.exe

Size:
28,193,076 bytes

Modified UTC:
2026-07-20T04:37:09.2377235Z

SHA-256:
F49BB41EB1D650AC2365586ED685A4CF2B133357D80F4EBFBF5ED4E619B980BF
```

构建 manifest：`artifacts/windows/build-manifest.json`。

内嵌应用：

```text
Paneloom.exe size:
12,134,046 bytes

Paneloom.exe SHA-256:
65C968E75546791F3FA9CFBDD42FCD7A390C688C7652146D351CB86D1D5F2091
```

安装目录中的 EXE 与 PyInstaller stage EXE 哈希一致。

## 5. 真实安装与启动验证

使用上述确切安装器静默安装到默认每用户目录：

```text
%LOCALAPPDATA%\Programs\Paneloom
```

结果：

| 验证 | 结果 |
|---|---|
| Installer exit code | 0 |
| 安装注册表版本 | `0.1.0-beta.1` |
| 开始菜单快捷方式 | PASS，指向安装目录 `Paneloom.exe` |
| 真实进程路径 | `%LOCALAPPDATA%\Programs\Paneloom\Paneloom.exe` |
| 原生窗口标题 | `Paneloom` |
| 随机回环地址 | `127.0.0.1:62202` |
| `/health` | PASS，版本 `0.1.0-beta.1` |
| `/projects` | PASS，读取 18 个现有 registry 项目 |
| React production index | PASS，HTTP 200 且包含 root |
| 固定 8000 地址 | NO |
| 正常关闭 | PASS |
| 残留监听端口 | 0 |
| 残留 Paneloom 进程 | 0 |

## 6. 卸载与用户数据保护

真实执行静默卸载后：

| 验证 | 结果 |
|---|---|
| Uninstaller exit code | 0 |
| 程序安装目录删除 | PASS |
| 卸载注册表删除 | PASS |
| 加密 settings 文件保留 | PASS，卸载前后 SHA-256 相同 |
| 项目 registry 保留 | PASS，卸载前后 SHA-256 相同 |
| Documents 项目目录 | 未由卸载器操作 |

随后再次使用同一 SHA-256 安装器安装成功，最终保留安装状态。

## 7. 已知限制

1. 安装器尚未进行 Authenticode 代码签名，Windows SmartScreen 可能显示“未知发布者”。
2. 已在当前 Windows 11 开发机真实安装、启动、关闭、卸载和重装；尚未在独立干净 Windows 10/11 虚拟机验证。
3. 安装后的应用完成了真实运行边界烟测，但本轮没有在安装版中重新执行所有付费 AI 请求和全套人工创作流程。
4. WebView2 缺失路径由安装器内置的微软签名 Evergreen Bootstrapper 处理，但本机已有 WebView2，因此“缺失后在线安装”分支尚未在隔离机器触发。
5. 安装器和应用均为 x64。

## 8. 当前状态

```text
FROZEN_BASELINE = PASS
INSTALLER_BUILD = PASS
EXACT_INSTALLER_INSTALLED = YES
INSTALLED_RUNTIME_SMOKE = PASS
UNINSTALL_USER_DATA_PRESERVATION = PASS
CLEAN_MACHINE_VALIDATION = NOT_RUN
AUTHENTICODE_SIGNED = NO
VALIDATION_STATE = State C
```

该安装器可以作为明确标识的 Windows Beta 提供给受信测试者。它不是代码签名后的正式商业发行版，也不能替代干净机器和收件人实际使用验收。
