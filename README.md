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

COROS 國際區上傳使用登入後的 `/api/proxy/oss/sts` 取得 AWS 臨時憑證，
依帳號區域選擇國際或歐洲站點及 bucket，並使用憑證回應的 AWS region。
舊的 `faq.coros.com/openapi/oss/sts` 已回傳 404 HTML，會造成 JSON 解析失敗。
上傳憑證取得失敗會立即停止；下載、儲存上傳或活動匯入失敗會以失敗狀態結束，
不會將該活動標記為已同步。這項修復不需要增加 Secrets。

## 致谢
- 本脚本佳明模块代码来自@[yihong0618](https://github.com/yihong0618) 的 [running_page](https://github.com/yihong0618/running_page) 个人跑步主页项目,在此非常感谢@[yihong0618](https://github.com/yihong0618)大佬的无私奉献！！！

## DeepWiki源码解析
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/XiaoSiHwang/garmin-sync-coros)

## 注意
由于高驰平台只允许单设备登录，同步期间如果打开网页会影响到数据同步导致同步失败，同步期间切记不要打开网页。

## Local activity backups

Use Python 3.12 or later. From the repository root, install dependencies in a
local environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The backup script downloads activities from one account without uploading
anything to the other service. Choose the source account explicitly:

```powershell
# Set only the credentials for the selected source.
$env:GARMIN_EMAIL = "you@example.com"
$env:GARMIN_PASSWORD = "your-password"
$env:GARMIN_AUTH_DOMAIN = "COM" # Optional; use CN for China.
.\.venv\Scripts\python.exe scripts/backup_activities.py --source garmin

$env:COROS_EMAIL = "you@example.com"
$env:COROS_PASSWORD = "your-password"
.\.venv\Scripts\python.exe scripts/backup_activities.py --source coros
```

By default, files are stored in `backups\garmin` or `backups\coros` and are
named `YYYYMMDDTHHMMSS_<activity-id>.<extension>` using the activity start
time. Existing activity files are skipped, so rerunning the command downloads
only files not already present. Use `--overwrite` to download every activity again, or
`--output-dir <path>` to use another backup location. The `backups`
directory is ignored by Git; keep it on durable local or cloud storage.

## 参数配置

|       参数名       |                备注                |        案例        |
| :----------------: | :--------------------------------: | :----------------: |
|    GARMIN_EMAIL    |          佳明登录帐号邮箱          |                    |
|  GARMIN_PASSWORD   |            佳明登录密码            |                    |
| GARMIN_AUTH_DOMAIN | 佳明区域（国际区填:COM 国区填:CN） |    (COM or CN)     |
| GARMIN_NEWEST_NUM  | 相容舊設定；目前程式讀取全部活動，未以此值限制筆數 | 可保留原值 |
|    COROS_EMAIL     |           高驰 登录邮箱            |                    |
|   COROS_PASSWORD   |             高驰 密码              |                    |
| GARMIN_SESSION_KEY | Actions session cache 固定加密金鑰，依上方指令產生一次 | 不填 Garmin token |

## Github配置步骤

### 1.参数配置

打开**Setting**
![打开Setting](doc/3451692931372_.pic.jpg)
找到**Secrets and variables**点击**New repository secret**按钮
![Secrets and variables](/doc/3461692931472_.pic.jpg)
打开 **New repository secret**，**Name** 填寫上表參數名，**Secret** 填寫對應的值。
共七個 Secret：原有六個帳號／設定參數，加上 `GARMIN_SESSION_KEY`。
![填入参数](doc/3471692931624_.pic.jpg)

### 2.確認 Actions 已啟用

在儲存庫 **Settings → Actions → General** 確認允許執行 workflow。
新版 workflow 使用 `contents: read`，不需要授予 repository contents 寫入權限，
也不需要設定 `GITHUB_NAME` 或 `GITHUB_EMAIL`。

### 3.選擇同步方向並執行

| Workflow | 同步方向 | 設定檔 |
| --- | --- | --- |
| `garmin-sync-coros` | Garmin → COROS | [.github/workflows/garmin-sync-coros.yml](.github/workflows/garmin-sync-coros.yml) |
| `coros-sync-garmin` | COROS → Garmin | [.github/workflows/coros-sync-garmin.yml](.github/workflows/coros-sync-garmin.yml) |

開啟 GitHub **Actions**，選擇要執行的 workflow，點 **Run workflow**，
分支選擇包含修復的 `master`，再按 **Run workflow**。
更新程式後請建立新執行；舊執行的 **Re-run jobs** 會沿用原提交。
兩個 workflow 也各自有排程；若只需要單向同步，可在 Actions 停用另一個 workflow。

第一次找不到 session cache 是正常情況，程式會使用既有 Garmin 帳密登入。
檢查同步步驟，以及 **Encrypt refreshed Garmin session** 和
**Save encrypted Garmin session** 的結果，確認登入狀態已保存。

若只有 Garmin 登入策略的 429 警告，請繼續確認後續步驟，不能僅據此判定最終登入失敗。
`Garmin activity list loaded` 表示已取得活動列表；若出現
`COROS storage setup failed`，失敗位置是 COROS 上傳憑證或儲存區設定。

## 更新與同步紀錄

更新 fork 前先確認並保留自己的修改；不要用 **Discard commits** 覆蓋需要的修復。
修復登入或上傳問題不需要刪除 `db/`，刪除資料庫會失去本機同步紀錄。
目前 `db/` 被 Git 忽略，Actions 沒有保存該資料庫，session cache 只保存登入狀態，
因此不能用 session cache 是否命中判斷活動是否已同步。
