---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: quarterly
source_type: security_policy
---

# Private Knowledge Handling

## 固定边界

私有知识提炼是管理员显式运行的离线流程，不属于浏览器扩展、loopback API、
后台清理、定时任务或普通分析 runtime。`backend.private_knowledge` 不枚举邮箱、
不连接 IMAP/SMTP、不读取 raw vault，也不调用 DeepSeek、OpenAI 或本地模型。
Codex、自动化测试和远程模型只可接触人工复核通过的脱敏材料。

唯一 raw-vault 桥接点是 `scripts/manage_mailbox_vault.py stage-knowledge`。它不
要求邮箱密码、不建立 IMAP 会话，只打开既有加密 vault。其 exact-key selection
manifest 必须绑定 `vault_id`、授权 scope fingerprint、固定时间窗、1 至 200 个
随机 record ID、不同 business/privacy reviewer，以及不晚于最后审批后 24 小时的
`expires_at`。manifest 过期、scope/vault/window 不匹配时，在读取记录前失败。

## Staging 与脱敏

桥接器一次只解密一条记录。原文和临时恢复映射在进入下一条记录前释放；Python
无法保证不可变字符串已被物理擦除，因此不得声称 secure erase。脱敏覆盖人员、
组织、域名、邮箱、电话、地址、URL、文件名、路径、Message-ID、交易编号、金额、
日期、来源定位、恢复提示和 prompt injection。残留扫描结果仅包含固定 code 与
count；任一残留会阻止整个 batch 写入。

无法由已验证 header context 明确替换的连续 Title Case 身份样式会被残留门保守
拒绝。这可能产生安全侧误报，需要本地人工复核，但不得以放宽规则换取远程处理。

脱敏候选只写入独立 candidate namespace 的 AES-256-GCM 文件。一个人工复核的
支持集合只生成一个候选；会话/交易对手证据与该候选的 `support_texts` 一起加密，
不得使用 batch-global 证据。staging 输出只含固定 code、count、随机 batch ID 和
随机 candidate ID；这些 ID 在 `repr` 中隐藏。不得输出 raw record ID、文本、映射、
路径、来源定位或身份值。后续导入必须直接使用回执中的 batch/candidate ID，不得
通过枚举文件名发现批次。

## 密钥与存储隔离

candidate、authority、runtime snapshot 使用独立随机密钥、magic、HKDF purpose、
namespace ID 和 AEAD associated data。私有知识 key envelope 使用当前用户范围
Windows DPAPI，默认与当前 Windows 用户和计算机绑定；DPAPI 在实际调用时才加载，
非 Windows 测试不得探测主机。

candidate root、authority root 和 runtime snapshot 必须为项目外绝对路径，不得
位于 OneDrive、系统临时目录、raw vault 内部或彼此嵌套。snapshot 默认路径校验会
独立拒绝系统临时目录、任意 `OneDrive*` 路径组件、raw-vault 标记祖先、reparse
component 及显式 authority/project 根。私有知识首版不声称跨卷原子事务；每个
ciphertext 在同目录通过临时文件、fsync 和 replace 发布。

## 人工审批与生命周期

`scripts/manage_private_knowledge.py` 只提供以下单项命令:

```text
init, import-candidate, create, business-approve, privacy-approve,
owner-approve, reject, expire, approve, deprecate, revoke, publish
```

CLI 不接受 raw 内容、规则文本、证据计数、阈值、bulk、force、密钥、密码、vault
或 record ID 参数。proposal 必须来自本地人工复核文件，并再次通过 exact-key、
schema、残留和 non-verbatim 校验。导入会消费对应 staging candidate，空批次立即
删除；非空批次只重新加密保留其他候选。拒绝立即删除候选，拒绝/到期操作幂等；
加密批次、导入候选和 authority candidate 均继承同一原始到期时间，`create`
不得重置 30 天上限。过期批次在读取时拒绝并删除，后续显式 staging 会执行最多
200 个严格命名、认证批次的有界到期清理；它不扫描或删除 raw vault。这里只保证
逻辑删除，不声称 SSD secure erase。批准知识每 90 天复核。price、payment、
contract、quality、legal 必须增加独立责任人审批。

## 签名快照与回退

publisher 仅投影批准且未过期卡片，先加密再以 Ed25519 对完整 frame 签名，并在
项目外发布 `.pksnap`。runtime loader is read-only: 它只有受限只读文件入口、
验证公钥和 snapshot 解密密钥，不可导入 authority repository、review、candidate、
deidentifier 或写入模块。签名、解密、schema、路径、时间或文件检查失败时返回空
卡片集和固定 code，普通规则分析继续工作。

日志、SQLite、Git diff、测试输出和维护报告不得包含候选文本、真实派生规则、
identity mapping、密钥或来源数据。仓库只保存 schema、加载器、治理文档和重新
创作的合成测试样例。
