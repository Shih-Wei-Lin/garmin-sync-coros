# Garmin / COROS 活動同步

## Garmin 登入 429 與 Actions session

使用 Python 3.12 以上及 `garminconnect==0.3.18`，取代舊的 Garth OAuth1
登入流程。登入狀態會自動重用及刷新。429 仍可能是 Garmin 的限制；請勿連續重跑，
也不要為了修復登入而刪除 `db/garmin.db`（那是活動同步紀錄）。

原有六個 Actions Secrets 繼續使用，不需把值提供給他人。
另新增一個固定的 `GARMIN_SESSION_KEY` Secret，用來加密 session cache，
它不是 Garmin token。安裝依賴後，在自己的電腦產生一次：

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

將輸出存入 GitHub → Settings → Secrets and variables → Actions →
New repository secret，名稱為 `GARMIN_SESSION_KEY`。不要貼到聊天或提交到 Git。
兩個工作流程共用這把金鑰，以每次執行獨立的 cache key 保存加密後的 session，
並互斥執行，避免同時刷新；金鑰變更時會建立新的 cache。
即使同步失敗，成功登入後的 session 仍會嘗試保存。
cache 不含密碼或明文 token，且不再使用 `git add .` / commit / push 保存 cookie。

本機 session 預設在 `.garmin-session/`，可用 `GARMINTOKENS` 指定其他目錄；
本機 session、`.env`、加密 cache 均已加入 Git 忽略清單。
Actions 的明文 session 只放在 runner 暫存目錄。
GitHub cache 有保留期限且可能被清除，並非永久儲存；cache 不存在或 session
失效時會重新登入。若 Garmin 要求 MFA，Actions 無法互動輸入，需另外處理登入，
本修復不保證繞過 Garmin 端的限流或 MFA。
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
打开**Setting**找到**Actions**点击**General**按钮,按照下图勾选并save
![配置WorkFlow权限](doc/3481692931856_.pic.jpg)

### 3. wrokflow配置
打开**github/workflows/garmin-sync-coros.yml**文件,将**GITHUB_NAME**更改为你的Github用户名、**GITHUB_EMAIL**更改为你的Github登录邮箱，更改步骤如下:
![更改步骤](doc/3491692932110_.pic.jpg)
更改完成后点击右上角**Commit changes...**提交即可
![Commit](doc/3501692932345_.pic.jpg)

## 重新fork项目步骤
点击页面上**Sync Frok**然后点击**Dicard commit**即可
![fork sync](doc/image.png)
## 删除db步骤
按照图片顺序执行即可
![alt text](doc/image5.png)
![alt text](doc/image-1.png)
![alt text](doc/image-2.png)
![alt text](doc/image-3.png)
![alt text](doc/image-4.png)
删除完后等脚本自己执行即可
