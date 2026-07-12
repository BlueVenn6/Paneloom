# 分镜相邻合并与交付检查（2026-07-12）

## 产品判断

增加“合并相邻分镜”有明确价值，但它是可选的叙事压缩工具，不替代细分镜：

- 漫画创作保留细分镜，以维持动作、对白和阅读节奏。
- 视频创作可将相邻两个叙事节拍合并为一个关键帧，减少关键帧数量。
- 支持单镜“与下一镜合并”和整表“相邻合并为关键帧”；例如 42 镜可在安全条件满足时变为 21 镜。

## 数据保护规则

- 只允许合并当前确实相邻的分镜。
- 已锁定、已批准、正在生成、已有图片、已有图片版本或已选择最终版本的分镜禁止合并。
- 批量合并先校验全部配对；任一配对不安全时整批不写入。
- 合并保留画面描述、提示词、负面提示词、备注、起止时间和累计时长。
- 合并结果记录 `merged_from_shot_ids` 和 `merged_at`，便于追踪来源。
- `shots.json` 继续使用原子替换和 `.bak` 备份；历史项目无需迁移。

## 验证证据

- Python 编译：PASS
- Vite production build：PASS
- 自动测试：46/46 PASS
- 新增单次相邻合并测试：PASS
- 新增批量 6→3 合并测试：PASS
- 生成图片/版本保护和整批原子失败测试：PASS
- 真实 production-like 桌面窗口：PASS
- 随机 127.0.0.1 回环端口：PASS
- 真实 HTTP 临时项目 4→2 合并：PASS
- 合并后两个原始提示词保留：PASS
- 合并来源 ID 保留：PASS
- 临时项目清理：PASS

自动测试已隔离 `SETTINGS_PATH`，不会读取、修改或尝试解密用户真实 DPAPI 密钥。

## 交付结论

```text
STORYBOARD_ADJACENT_MERGE_CODE_READY = YES
AUTOMATED_FUNCTIONAL_REGRESSION = PASS
DESKTOP_TEST_MODE_AVAILABLE = YES
FUNCTIONAL_ACCEPTANCE_READY_FOR_USER = YES
USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
PACKAGING_ALLOWED = NO
```

代码级和自动回归没有发现新的桌面 Beta P0。新增合并功能仍需用户本人在当前桌面测试窗口中完成一次单次合并和一次批量合并确认。用户明确批准整轮人工验收前，不允许进入安装包、Release 或正式发布阶段。
