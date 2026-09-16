# 每日微信新闻

纽约时间每天上午 9 点，由当前 Codex 定时任务浏览新闻并生成中文概要；GitHub 收到日报后发布公开网页，再通过用户自己的微信测试号发送一条通知。此方案不调用付费 AI API，不把 ChatGPT 登录凭证放进 GitHub；摘要生成使用当前 Codex 订阅额度。

**配置状态：尚未部署，尚未验证微信发送，定时任务暂停。**

## 内容

世界新闻、中国新闻、深圳新闻、CS2 游戏资讯，每板块最多 3 条，每条为简洁概要和原文链接。只采用生成前 24 小时内的来源；缺少可靠更新时注明，不以旧闻凑数。概要由定时任务核实后写入，不由这个仓库自行生成。

## 配置

1. 创建自己的 GitHub 仓库，把本目录文件上传到 `main`。
2. Settings → Pages → Build and deployment → Source 选择 GitHub Actions。
3. 在微信测试号后台添加模板，标题为“每日新闻简报”，模板内容见下方。
4. Settings → Secrets and variables → Actions 添加以下 Repository secrets：
   - `WECHAT_APP_ID`：测试号 appID。
   - `WECHAT_APP_SECRET`：测试号 appsecret。
   - `WECHAT_OPEN_ID`：关注测试号后，用户列表里你自己的微信号标识。
   - `WECHAT_TEMPLATE_ID`：新增模板的模板 ID。
5. 先上传一份当日日报到 `digests/YYYY-MM-DD.json`，检查 Pages 发布成功。
6. 添加 Repository variable `WECHAT_ENABLED`，值为 `true`。手动运行工作流，勾选 `send_wechat`，验证手机收到通知。
7. 验证成功后，将仓库地址写入当前 Codex 定时任务并启用。保留唯一一个调度，避免重复发送。

模板内容（原样复制）：

```text
日期：{{date.DATA}}
今日简报：{{summary.DATA}}
{{remark.DATA}}
```

## 运行条件与失败处理

- 当前任务是桌面端本地定时任务，运行时需保持电脑开机、联网且 Codex 可运行；这不是仅凭 Plus 在 GitHub 云端独立生成摘要的方案。
- GitHub 发布和微信投递需要时间，9 点是任务启动时间，不保证9点整到账。
- 首次推送以手机实际收到为准。接口成功仅表示微信接受请求。
- 不自动重试微信发送；超时可能意味着已经发送，请先检查手机。工作流重新运行默认不会再次推送；手动勾选发送可以重发。
- 目前测试号接口是否可用、账号权限及网络白名单仍需实际测试。
- 旧日期或超过6小时的日报不会推送。公开网页只包含新闻，四个微信配置值只放 Secrets。

## 日报格式

每日新建一次 `digests/YYYY-MM-DD.json`，不要修改既有日报触发重复推送。JSON 包含 `date`（纽约日期）、`generated_at`（带时区的 ISO 时间）、`sections`（四个固定板块）。每个板块包含 `name`、`items`；条目包含 `summary`、`source`、`url`、`published_at`。空板块需要 `note`。链接必须是可信来源的 HTTPS 原文地址。

## 检查

Python 3.12+，只用标准库：

```text
python -m unittest discover -s tests
python render.py
```
