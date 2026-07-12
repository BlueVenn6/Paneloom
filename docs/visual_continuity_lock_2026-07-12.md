# 全剧视觉连续性锁设计与验证（2026-07-12）

## 问题判断

角色、场景和道具参考资产只能约束内容身份，不能单独约束整部剧的曝光、色温、渲染密度、线条粗细、边框颜色和边框厚度。把第一张满意的成片设为全剧视觉基准，是当前供应商能力下最有价值的补充。

## 已实现的三层约束

1. **成片视觉基准**：任意已有本地图片的分镜可以设为全剧视觉基准。系统在项目内保存一份稳定副本，记录来源分镜，不依赖原分镜后续版本变化。
2. **结构化视觉锁**：在线时调用一次文字视觉模型，提取曝光、色温、渲染密度、线条、调色、边框和留白规则；离线或分析失败时使用本地亮度、对比度、饱和度和边缘密度指标兜底。规则写入项目 Bible，并进入后续每一次图片提示词。
3. **本地色调校准**：后续生成图片保存并完成尺寸校验后，本地将亮度、对比度和饱和度向视觉基准做有限校准。校准数据随图片版本保存，不修改此前生成的图片。

有框模式同时使用固定规范：以 1024px 画布为基准，内部格线和外框使用等效 4px 厚度、同一实色、方形连接和统一留白，禁止同图混用不同边框。

## 真实能力边界

当前生产图片接口统一使用 `/images/generations`，不会接收视觉基准的图片像素。因此：

- 亮度、对比度和饱和度有本地确定性校准。
- 色温、线条密度、构图和内部边框依靠结构化强提示约束，能显著降低漂移，但不能伪称像素级绝对一致。
- 若未来要求内部格线粗细达到真正像素级一致，正确方案是分别生成无框单格，再由本地排版器按统一模板合成；不应继续要求图片模型在一张多格图内自行绘制所有边框。

本轮没有实现完整多格排版器，也没有恢复 `/images/edits`。

## 验证

```text
VISUAL_MASTER_OFFLINE_FALLBACK = PASS
VISUAL_MASTER_PROMPT_INJECTION = PASS
LOCAL_TONE_CALIBRATION = PASS
VISUAL_MASTER_DELETE_CLEANUP = PASS
AUTOMATED_TESTS = 48/48 PASS
VITE_PRODUCTION_BUILD = PASS
DESKTOP_PRODUCTION_LIKE_BOOT = PASS
VISUAL_MASTER_ROUTE_LOADED = PASS
PAID_AI_CALL_PERFORMED_BY_AUTOMATION = NO
```

## 人工测试

1. 在分镜制作中找到一张已经满意并已保存的分镜图片。
2. 点击“设为全剧视觉基准”并确认。
3. 左侧应显示“当前视觉基准”和来源镜头编号。
4. 生成下一张分镜，确认生成结果显示已按视觉基准校准。
5. 对比两张图片的整体亮度、对比度、饱和度、线条和边框规则。

```text
FUNCTIONAL_ACCEPTANCE_READY_FOR_USER = YES
USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
PACKAGING_ALLOWED = NO
```
