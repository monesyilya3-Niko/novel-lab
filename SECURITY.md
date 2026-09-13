# 安全策略

## 安全模型声明

novel-lab 设计为**单机本application**：

- HTTP 服务硬编码绑定 `127.0.0.1`，不接受外部网络连接
- API 默认无认证（单机信任模型）；设置环境变量 `NOVEL_LAB_TOKEN` 后所有 `/api/*` 请求须携带 `X-Auth-Token` 头（SSE 可用 `?auth=` 查询参数），比较使用常数时间算法
- CORS 仅回显本机 Origin
- 静态文件与 API 路径参数均做路径穿越防护；SQL 全参数化
- API 密钥存储：Windows 下经 **DPAPI 加密**（`config/.secrets.bin`，与当前系统用户绑定，泄漏的密文无法在他人机器解密）；发现旧明文 `.secrets.json` 时自动迁移加密并删除。非 Windows 降级为 0600 权限明文 JSON。两类文件均被 `.gitignore` 排除，永不入库

**请不要把服务改绑到 0.0.0.0 或公网暴露**——这不在设计威胁模型内，等于把本机文件系统和已配置的 API 密钥暴露给局域网。

## 支持的版本

| 版本 | 支持状态 |
|---|---|
| latest release | ✅ 安全修复 |
| 更早版本 | ❌ 请升级 |

## 报告漏洞

**请勿公开 issue 报告安全漏洞。**

使用 GitHub [Security Advisories → Report a vulnerability](https://github.com/monesyilya3-Niko/novel-lab/security/advisories/new) 私密报告（不使用公开 issue、不接受邮件报告）。

包含：影响版本、复现步骤、影响评估。收到后 72 小时内确认，修复协调后公开致谢（除非你希望匿名）。

## 密钥泄露应急

若发现任何密钥进入版本历史：

1. 立即在服务商控制台吊销该密钥（这是唯一可靠的补救）
2. 再按上述渠道报告，协助清理历史
