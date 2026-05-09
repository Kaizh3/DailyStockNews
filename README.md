# 📊 Stock Monitor — Setup Guide

自动抓取美股+马股新闻与股价，每天4次推送到 Telegram。

---

## 文件结构

```
stock-monitor/
├── scripts/
│   └── monitor.py          ← 主脚本
├── .github/
│   └── workflows/
│       └── stock-monitor.yml  ← GitHub Actions 定时任务
├── requirements.txt
└── README.md
```

---

## Step 1：创建 GitHub 仓库

1. 去 https://github.com/new 创建新仓库（Private）
2. 名字：`stock-monitor`
3. 把以下文件上传到对应路径：
   - `scripts/monitor.py`
   - `.github/workflows/stock-monitor.yml`
   - `requirements.txt`

---

## Step 2：设置 Secrets

进入仓库 → **Settings → Secrets and variables → Actions → New repository secret**

添加以下3个：

| Secret 名称 | 值 |
|------------|---|
| `TELEGRAM_BOT_TOKEN` | 你的 Bot Token（从 @BotFather 获取新的） |
| `TELEGRAM_CHAT_ID` | 你的 Chat ID（从 @userinfobot 获取） |
| `ANTHROPIC_API_KEY` | 你的 Claude API Key |

---

## Step 3：启用 GitHub Actions

1. 进入仓库 → **Actions** 标签
2. 点击 **"I understand my workflows, go ahead and enable them"**
3. 左侧找到 **"Stock Monitor — 4x Daily"**
4. 点击 **"Run workflow"** 手动测试一次

---

## Step 4：测试

手动触发时，在 `test_hour` 输入框填入 `7` / `12` / `17` / `22`
来模拟对应时段的推送格式。

---

## 触发时间表（JST）

| JST 时间 | UTC cron | 内容 |
|---------|---------|------|
| 07:00 周一至周五 | `0 22 * * 1-5` | 🌅 早安快訊（盤前） |
| 12:00 周二至周六 | `0 3 * * 2-6`  | ☀️ 午間快訊（盤中） |
| 17:00 周二至周六 | `0 8 * * 2-6`  | 🌆 收盤快訊 |
| 22:00 周一至周五 | `0 13 * * 1-5` | 🌙 美股盤中 |

---

## Telegram 消息样本

```
🌅 早安快訊 07:00 JST

━━━ 🇺🇸 美股 ━━━
🟢 MSFT $415.12 ▲1.23%
   └ 微軟 Azure 季度營收超預期，雲端業務加速成長
⚪ VOO $678.04 ▲0.82%
⚪ QQQ $711.23 ▲2.34%
🔴 TSLA $428.35 ▼0.50%
   └ 特斯拉歐洲銷量下滑，競爭壓力加劇

━━━ 🇲🇾 馬股 ━━━
🟢 MAYBANK RM11.18 ▲0.40%
   └ 馬銀行公佈季度股息，股息率維持6%水平
⚪ PAVREIT RM1.89 —0.00%
⚪ SUNREIT RM2.54 ▲0.40%

━━━ 🌐 宏觀 ━━━
⚪ USD/MYR: 匯率維持4.42，林吉特走勢平穩
🟢 Fed: 聯準會官員暗示暫停加息，市場情緒回暖

🔎 下次更新 盤中
```

---

## 费用估算（每月）

| 项目 | 费用 |
|------|------|
| GitHub Actions | 免费（2000分钟/月，实际用约30分钟） |
| Anthropic API (Haiku) | ~$0.50-1.00/月（约120次调用） |
| yfinance 股价 | 免费 |
| Telegram Bot | 免费 |
| **合计** | **< $1/月** |

---

## 常见问题

**Q: 消息没发送怎么办？**
- 检查 Actions 日志（仓库 → Actions → 点击对应 run）
- 确认3个 Secrets 都已正确填写
- 确认 Bot Token 是最新的（旧 token 已 revoke 的需重新生成）

**Q: 股价显示"暫無"怎么办？**
- yfinance 偶尔有延迟，属正常现象
- 马股（.KL 后缀）在非交易时段价格不更新

**Q: 如何修改监控股票？**
- 编辑 `scripts/monitor.py` 顶部的 `US_HOLDINGS` / `MY_HOLDINGS` 字典
- 提交到 GitHub 即自动生效
