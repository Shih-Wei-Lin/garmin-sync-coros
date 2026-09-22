# Garmin / COROS 自动同步

登入 429 请先按下面的 token 设置处理；不要删除同步数据库，否则可能重复上传已有活动。

## GitHub Actions 登入 429 修正

此版本保留 `garth==0.4.38`，使用已有的 OAuth token 登录，不依赖每次执行时重新输入帐号密码。
已确认的失败记录发生在 `connectapi.garmin.com/oauth-service/oauth/preauthorized`，
也就是帐号密码验证之后的 token 获取步骤。单改登录页面 User-Agent 不能确认修复这个端点。

### 一次性设置 GARMIN_TOKEN

在自己的电脑、项目根目录执行（Python 3.9+）：

```powershell
# uv 使用临时环境，不修改系统 Python；也可在已安装项目依赖的环境执行 python scripts/garmin_token.py。
uv run --no-project --with "garth==0.4.38" python scripts/garmin_token.py
```

按提示输入 Garmin 邮箱、密码及 MFA 验证码。中国区先设置 `$env:GARMIN_AUTH_DOMAIN = "CN"`；
国际区默认 COM。脚本也支持已有的 `GARMIN_EMAIL` / `GARMIN_PASSWORD` 环境变量。

如果已有正常使用的 Garth session（目录包含 `oauth1_token.json` 和 `oauth2_token.json`），
可以直接转换，不重新输入帐号密码：

```powershell
uv run --no-project --with "garth==0.4.38" python scripts/garmin_token.py --session-dir "$HOME/.garth"
```

成功后会生成 `.garmin-token`，此文件已被 Git 忽略。用下面命令复制完整内容：

```powershell
Get-Content -Raw .garmin-token | Set-Clipboard
```

到 GitHub 仓库 **Settings → Secrets and variables → Actions → New repository secret**，
新增名为 **`GARMIN_TOKEN`** 的 secret 并贴上内容。它是登录凭证，不要贴到 issue、日志或聊天。
token 包含原本的 Garmin 区域，载入后以 token 区域为准。保留 COROS 相关 secrets。

将本次代码更新到 GitHub 默认分支后，在 **Actions → garmin-sync-coros → Run workflow** 测试一次。
此 workflow 是 Garmin → COROS；反向同步使用 `coros-sync-garmin`，通常只需启用想要的方向。
两个 workflow 都要求 `GARMIN_TOKEN`，缺少时会立即显示设置提示，不自动反复尝试帐号密码登录。

Garth 会使用 OAuth1 token 更新过期的 OAuth2 token，所以无需每次修改 secret。
若长期 token 被撤销或失效，须重新生成并更新 secret。若本机第一次取得 token 也遇到 429，
此方案尚未完成初始化；停止连续重试，优先使用已有有效 session。更换版本或 User-Agent
并不能保证解除 Garmin 端封锁。

### 排程与同步进度

- Garmin → COROS：UTC 01:00、08:00、21:00（台湾 09:00、16:00、次日 05:00）。
- COROS → Garmin：UTC 00:00、07:00、20:00（台湾 08:00、15:00、次日 04:00）。
- workflow 使用同一个 concurrency group，避免两边同时登入 COROS。
- 只有 `db/` 同步进度存入 Actions cache；token 不写入 cache、artifact 或 Git。
- 每次执行保存新的进度 cache，部分失败时也保存已完成的记录。cache 会被 GitHub 淘汰，
  不是永久备份；如果 cache 丢失，会重新扫描活动并可能重复上传。不要主动清除进度 cache。
- 不再需要 workflow 对仓库的写入权限，也不再自动 `git add .` / `git push`。

离线验证：`uv run --no-project --with "garth==0.4.38" python -m unittest scripts.tests.test_garmin_auth`。

## 致谢
- 本脚本佳明模块代码来自@[yihong0618](https://github.com/yihong0618) 的 [running_page](https://github.com/yihong0618/running_page) 个人跑步主页项目,在此非常感谢@[yihong0618](https://github.com/yihong0618)大佬的无私奉献！！！

## DeepWiki源码解析
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/XiaoSiHwang/garmin-sync-coros)

## 注意
由于高驰平台只允许单设备登录，同步期间如果打开网页会影响到数据同步导致同步失败，同步期间切记不要打开网页。

## Local activity backups

`sync-coros-garmin.ps1` can download activities from one account without
uploading anything to the other service. Choose the source account explicitly:

```powershell
# Set only the credentials for the selected source.
$env:GARMIN_EMAIL = "you@example.com"
$env:GARMIN_PASSWORD = "your-password"
$env:GARMIN_AUTH_DOMAIN = "COM" # Optional; use CN for China.
.\sync-coros-garmin.ps1 -Mode backup -Source garmin

$env:COROS_EMAIL = "you@example.com"
$env:COROS_PASSWORD = "your-password"
.\sync-coros-garmin.ps1 -Mode backup -Source coros
```

By default, files are stored in `backups\garmin` or `backups\coros` and are
named `YYYYMMDDTHHMMSS_<activity-id>.<extension>` using the activity start
time. Existing activity files are skipped, so rerunning the command downloads
only files not already present. Use `-Overwrite` to download every activity again, or
`-OutputDirectory <path>` to use another backup location. The `backups`
directory is ignored by Git; keep it on durable local or cloud storage.

Running `.\sync-coros-garmin.ps1` with no arguments preserves its original
COROS to Garmin sync behavior.

## 参数配置
|       参数名       |                备注                |        案例        |
| :----------------: | :--------------------------------: | :----------------: |
|    GARMIN_EMAIL    |          佳明登录帐号邮箱          |                    |
|  GARMIN_PASSWORD   |            佳明登录密码            |                    |
| GARMIN_AUTH_DOMAIN | 佳明区域（国际区填:COM 国区填:CN） |    (COM or CN)     |
| GARMIN_TOKEN | Actions 必填；由本机一次性登录产生 | 不要公开内容 |
| GARMIN_NEWEST_NUM  |            最新记录条数            | (默认0，可写大于0) |
|    COROS_EMAIL     |           高驰 登录邮箱            |                    |
|   COROS_PASSWORD   |             高驰 密码              |                    |

## Github配置步骤
### 1.参数配置
打开**Setting**
![打开Setting](doc/3451692931372_.pic.jpg)
找到**Secrets and variables**点击**New repository secret**按钮
![Secrets and variables](/doc/3461692931472_.pic.jpg)
打开**New repository secret**后将上述的参数填入，下图以佳明帐号为例,**Name**填写参数名,**Secret**填写你的信息，重复以上步骤填入五个参数即可
![填入参数](doc/3471692931624_.pic.jpg)

### 2.配置WorkFlow权限
当前 workflow 只需 `contents: read`，同步进度使用 Actions cache，不需要开启仓库写入权限。

### 3. wrokflow配置
完成上方 `GARMIN_TOKEN` 设置后，启用所需方向的 workflow 并手动执行一次；不需修改 Git 用户名或邮箱。

## 重新fork项目步骤
点击页面上**Sync Frok**然后点击**Dicard commit**即可
![fork sync](doc/image.png)
## 历史删除db步骤（仅供手动重置，不适用于登入 429）
按照图片顺序执行即可
![alt text](doc/image5.png)
![alt text](doc/image-1.png)
![alt text](doc/image-2.png)
![alt text](doc/image-3.png)
![alt text](doc/image-4.png)
删除完后等脚本自己执行即可
