# 动态语言与参考资产权限修复（2026-07-13）

## 人工验收问题

1. 简体中文界面点击“提取风格”后，用户可读的风格规则仍显示英文。
2. 角色/场景/道具设定图常包含九宫格、设定表边框和不同曝光，可能与成片视觉基准的边框规则发生概念冲突。

## 根因

- 静态翻译键虽然完整，但风格分析后端明确要求所有内容使用英文，并把机器 Prompt 直接作为用户说明显示。
- `/images/generations` 不接收参考图像素。此前 UI 仍容易让用户理解为所选图片本身会发给图片模型。
- 普通风格参考与成片视觉基准共用 `style_reference_filename`，导致两种不同权限的数据源互相覆盖。
- 剧本拆分、Bible 分析和参考资产计划主要依赖“跟随源语言”，没有显式携带当前界面语言，供应商可以返回其他语言而仍被判成功。

## 修复

### 动态语言

- 简体中文、繁体中文、英文、日文、韩文的当前界面语言会传入：
  - AI 剧本拆分；
  - AI 分镜重写；
  - Bible 分析；
  - 参考资产规划；
  - 普通画风提取；
  - 全剧视觉基准提取；
  - 故事优化（原有链路继续保留）。
- 风格提取返回双通道结果：
  - `style_prompt`：内部机器生成规则，可保持英文以兼容图片供应商；
  - `style_analysis_localized`：只用于当前界面展示，按语言分别保存。
- 旧项目仅保存英文 `style_analysis` 时，中文界面不会继续直接显示该英文；用户在当前语言重新提取一次即可建立对应语言版本。
- 增加动态语言校验。供应商忽略指定语言时：
  - 风格分析回退为当前语言的本地测量摘要；
  - 剧本拆分、Bible、参考资产计划、故事优化明确失败并允许重试，不把混语结果伪装成成功。

### 参考资产权限

| 数据源 | 允许控制 | 明确禁止控制 |
| --- | --- | --- |
| 角色资产 | 人物身份、脸型、发型、服装、体型、动作特征 | 九宫格、设定表边框、留白、曝光、成片构图 |
| 场景资产 | 地点身份、标志物、空间元素 | 资产图边框、背景版式、成片分格 |
| 道具资产 | 物件形状、颜色、材质、归属 | 设定表布局和成片边框 |
| 普通画法参考 | 笔触、调色规律、纹理、线条质量 | 设定表格子、边框、留白、曝光和构图 |
| 全剧视觉基准 | 曝光、色温、渲染密度、线条、成片边框、留白和版式 | 人物身份替换 |

生成 Prompt 现在明确写入：内容资产无权控制版式；不得复制参考设定表的 grid、collage、turnaround layout、border、gutter、margin、background、exposure、lighting 或 framing。

普通画法参考和视觉基准来源已经拆为：

```text
style_reference_filename
visual_anchor_reference_filename
```

删除普通画法参考不会再清空视觉基准；删除视觉基准才会清除视觉连续性规则和本地校准指标。

## 能力边界

当前图片供应商只提供 `/images/generations`。因此所选角色、场景和道具图片像素不会发送给图片模型，系统实际使用项目 Bible、资产名称、用途和缓存设计描述形成文字连续性约束。界面现已明确展示这一事实。

这意味着：

- 资产设定图自身的边框像素不会直接污染生成，因为图片模型没有看到这些像素。
- 如果用户曾把角色设定图当作“风格参考”提取，旧规则可能包含设定表版式；需要用当前版本重新点击“提取画风（忽略版式）”。
- 严格人物像素一致性需要供应商支持真实参考图输入，或使用专门的一致性模型；不能把纯文本 `/images/generations` 伪称为像素参考生成。
- 多格内部边框的像素级绝对一致仍需要未来的本地确定性合成器；当前是强 Prompt 约束，不伪称像素级保证。

## 验证

```text
DYNAMIC_UI_LANGUAGE_PROPAGATION = PASS
WRONG_LANGUAGE_PROVIDER_RESULT_REJECTED = PASS
LOCALIZED_STYLE_DISPLAY = PASS
MACHINE_PROMPT_AND_DISPLAY_TEXT_SEPARATED = PASS
CONTENT_ASSET_LAYOUT_AUTHORITY = BLOCKED
STYLE_REFERENCE_AND_VISUAL_ANCHOR_SEPARATED = PASS
VISUAL_ANCHOR_DELETE_DEPENDENCY = PASS
AUTOMATED_TESTS = 52/52 PASS
PYTHON_COMPILE = PASS
PYFLAKES = PASS
VITE_PRODUCTION_BUILD = PASS
```

## 人工复测

1. 在简体中文界面选择一张角色或场景资产。
2. 点击“提取画风（忽略版式）”。
3. “已提取风格规则”应显示中文，不应显示英文 Brushwork、Linework 等段落。
4. 确认页面说明明确指出 `/images/generations` 不接收参考图像素。
5. 从一张满意的已生成分镜设置“全剧视觉基准”。
6. 再生成一张分镜，确认角色资产只约束身份，视觉基准负责明暗和边框规则。
7. 切换到繁中、英文、日文、韩文分别重新提取，确认返回对应语言；供应商返回错误语言时应失败或显示本地对应语言摘要。

```text
FUNCTIONAL_ACCEPTANCE_READY_FOR_USER = YES
USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
DELIVERY_READY = NO
PACKAGING_ALLOWED = NO
```
