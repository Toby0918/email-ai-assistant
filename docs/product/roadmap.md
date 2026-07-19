---
last_update: 2026-07-18
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: product_spec
---

# 路线图

## 阶段 1：本地原型

- 完成 Python 后端分析 API。
- 完成当前邮件输入格式和分析结果 JSON schema。
- 完成邮件正文清洗、AI 调用、风险识别和回复草稿生成。
- 使用本地调试页面或模拟前端验证“点击分析当前邮件”。
- 不接入真实邮箱账号。

## 阶段 2：辅助窗口路线选择

- 评估 Outlook Add-in、浏览器扩展和 Google Workspace Add-on。
- 明确目标企业邮箱环境。
- 已选择第二阶段原型路线：Chrome / Edge browser extension for Tencent Exmail Web (`https://exmail.qq.com/*`)。
- Tencent Exmail Web 原型仍只允许用户点击后分析当前打开邮件。
- 确定前端框架和构建工具。
- 继续禁止前端保存 API key。

## 阶段 2.1：辅助窗口体验修复

- 修复真实长邮件分析结果的弹窗排版问题。
- 将风险、建议动作和附件元数据按条目展示，避免长 RFQ 编号、URL 和中英文混排挤在一行。
- 明确本地服务不可用、当前邮件无法识别、无草稿可复制等状态。
- 保持“用户点击后分析当前邮件”的边界，不新增任何自动邮箱动作。

## 阶段 2.2：已实现的分析质量增强

- 扩充 RFQ、新品开发、质量投诉、物流交付、付款、合同类脱敏样例。
- 优化本地 Qwen 和规则兜底的分类、摘要、风险证据和建议动作。
- 已实现 Decision Brief：用行动结论、邮件目的、当前动作、关键事实、必须核查项、缺失信息和回复建议，让用户无需回看整封邮件也能判断下一步。
- 已为 Decision Brief 实现 schema 校验、模型输出修复、规则兜底和浏览器扩展展示。
- 继续保持中文分析反馈、英文回复草稿。
- 回复草稿必须基于分析结果，不自动承诺价格、交期、付款、合同或质量结论。

## 阶段 2.3：附件辅助分析

- 自动化和合成样例范围已实现；Task 9 synthetic provider and current-clicked Tencent smokes are complete。Task 5 real current-message attachment smoke remains pending，且必须在离线 Tasks 1-4 评审通过后取得 fresh explicit authorization。
- 在用户明确点击后，支持当前打开邮件中可见的图片、PDF、XLSX 和 DOCX 资源的受限传输和后端解析。
- 附件内容提取、OCR 和临时文件清理必须在后端完成，前端不调用 AI 或本地模型。
- 请求临时文件在每次请求的 `finally` 中删除；SQLite 只保存最终结构化分析结果，不保存附件二进制或私有下载信息。
- 24 小时 mtime 清理只用于 crash recovery，不是正常保留期且不由 scheduler 运行；没有后台邮箱轮询器或常驻调度器。
- 不声称已读取未下载、未打开、未解析或不受支持的附件内容。
- 无文字业务照片可在显式点击后进入受限视觉分析；签名头像、logo、tracker、隐藏/外部/归属歧义资源必须拒绝。视觉只提供与匹配附件有关的定性观察，不支撑身份、精确值或业务承诺。

## 阶段 2.4：可安装原型

- Chrome / Edge unpacked extension `0.2.3` 已完成仓库内自动化和合成稳定验证；此前 Task 9 current-click smoke 已完成，新的 Task 5 attachment smoke 仍待 fresh explicit authorization。
- 已增加扩展版本号、安装/reload 说明、本地服务健康检查、生命周期安全诊断和排障路径。
- 已形成可重复执行的 release checklist、rollback 步骤和 staged-snapshot 检查。
- 继续禁止自动发送、删除、归档、移动、转发或回复邮件。

## 阶段 3：单独授权的私有分析离线就绪

- 当前状态标识为 `authorized_private_analysis_offline_ready`；offline completion does not equal live authorization。管理员 mailbox、private dataset、人工 judge 和 DeepSeek 仍需分别批准并由本地操作者启动。
- 仅允许管理员手动运行 `scripts/manage_mailbox_vault.py`，处理一个授权账号、固定 `imap.exmail.qq.com:993` 和滚动 24 个日历月。
- inventory 先输出 content-free fingerprint；scan 必须显式确认同一 fingerprint。
- 原始分析快照使用项目外的 NTFS BitLocker vault、逐记录 AES-256-GCM、当前用户 DPAPI envelope 和分离的 offline recovery envelope。
- 建立私有知识候选、业务/隐私/额外 accountable-owner 审核、30 天候选过期和季度复核。
- 建立本地去标识门和 aggregate-only DeepSeek 评估；任何 20-case gate 失败都停止后续调用，不重试。
- 加入 `revoke` 和 crash-recoverable `rewrap-recovery`，但不声称跨卷原子性或 SSD 物理安全擦除。
- 全部自动化只使用 synthetic fakes；live mailbox、vault material 和 DeepSeek 调用仍需管理员再次单独确认。
- 浏览器扩展继续只允许用户点击后分析当前打开邮件，不获得全邮箱扫描或管理员导入能力。

## 阶段 3.1：多模态 current-email 离线就绪

- 当前状态标识为 `multimodal_current_email_offline_ready_live_pending`。
- Tasks 1-7 已在合成 fixture、fake provider 和静态/机械测试下 implemented and review-clean；Task 8 对齐活动文档与状态生成器。
- Option C 路由为显式启用的 OpenAI `gpt-5.6-sol` 多模态主调用，eligible failure 后最多一次 DeepSeek text-only fallback，最后才是确定性规则；all providers disabled by default。
- Task 9 synthetic provider and current-clicked Tencent smokes are complete；新的 Task 5 real current-message attachment smoke remains pending、not live-tested，并需要 fresh explicit authorization。此前 smoke 不构成新附件获取路径的真实邮件验收。
- 真实邮箱管理员扫描、用户点击的当前邮件分析和最多两段 provider 路由继续使用独立授权门；离线完成不授权任何真实调用。

## 阶段 4：团队协作能力

- 可配置分类和优先级规则。
- 可配置回复风格。
- 人工审核后的草稿插入。
- 管理员可见的安全策略。


