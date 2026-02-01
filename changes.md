# X-Assistant Change List

## TODO

## 2026.02.01
- 会话级冷却，关注/点赞/回复按会话设阈值(10–14)，达到后清零并休息 15–20 分钟

## 2026.01.18
- 增加 参数 --only_certified_user ，只回关 蓝V 用户
- 回复，如果是蓝V的帖子，不判断帖子内容，多跟蓝V互动
- 关注，帖子内容里有互关之类的关键词，才去主动关注，否则不乱 Follow ，增大回关几率，如果设置了 --only_certified_user ，则只关注蓝V

## 2025.11.23
- 自动发帖

## 2025.11.22
- 回关时增加用户描述关键词筛选，将广告用户拉黑

## 2025.11.19
- 回复已关注用户的推文时，忽略关键词筛选，既然爱了，就爱他的一切！

## 2025.11.17
- 取关未关注账号
- 回关已关注账号
- 增加账号白名单(ad_user列表自动进白名单)，避免自动取关
- 增加账号黑名单(拉黑广告、低俗账号)，避免自动回关
- 无论互关还是正常回复，都带上自己的广告链接(如果有的话)
- 遇到受限或错误信息，发送告警，Sleep 1-1.2 小时(在此之间随机一个数)

## 2025.05.18
- 钱包加密方式改为 AES 加密

## 2025.04.29
- 支持使用 auth_token 登录 X 账号

## 2025.04.28
- 创建 X 账号时，导出 auth_token

## 2025.04.27
- 增加手动设置 VPN 模式
- 支持自动生成用户名，如果只传域名邮箱后缀，自动补充用户名

## 2025.04.23
- 增加 X 回复功能

## 2025.04.22
- 增加 X 账号注册

## 2025.04.19
- 增加 X Follow 功能
- 通过大模型改写 X 申诉内容
- 增加 okx giveaway 任务辅助完成功能

## 2025.04.17
- 通过 CapMonster 过 Cloudflare 验证

## 2025.04.11
- 通过 Clash Verge API 设置代理
- 通过 Gmail API 获取邮件验证码
- 通过 YesCaptcha Chrome 插件过图形验证码
- 登录后，随机点赞
- 点赞后如果提示账号封禁，跳转到申诉页面，提交申诉

# Twitter
X-Assistant

https://github.com/hunterlarcuad/x-visit.git

# venv
```
# Create venv
python -m venv venv
# Activate venv
source venv/bin/activate
# Exit venv
deactivate
```

# Install
```
pip install --upgrade pip
pip install -r requirements.txt
```

# X 账号文件
```
cd x-visit/
python fun_encode.py --file_in='datas/account/account.csv.sample' --file_ot='datas/account/encrypt.csv.sample' --idx=2 --key='ak6UVCToc32H9#mSAMPLE'
```

# Gmail API
```
创建 Google Cloud 项目并启用 Gmail API

Step 1
在 Google Cloud 控制台中启用 Gmail API
https://console.cloud.google.com/

Step 2
创建一个新项目（或选择已有项目）

Step 3
进入 Gmail API 页面：
https://console.cloud.google.com/apis/library/gmail.googleapis.com
点击“启用”按钮

Step 4
创建 OAuth 2.0 凭证
左侧菜单选择「API 和服务 > 凭据」
或直接访问：https://console.cloud.google.com/apis/credentials
点击「创建凭据」 > 选择「OAuth 客户端 ID」
如果提示你还没有配置“同意屏幕”，请先点击“配置同意屏幕”：
选择“外部”类型
填写应用名称、开发者邮箱等基本信息，然后保存并继续
回到创建凭证界面，创建 OAuth 客户端 ID：
应用类型：选择「桌面应用」
填一个名称（如“Gmail API App”）
点击“创建”
创建后点击“下载”按钮，把 credentials.json 文件保存下来，放在你的 Python 项目文件夹中
并下载的 json 文件重命名为 credentials.json

Step 5
添加测试用户
Google Auth Platform / 受众
左侧选择"目标对象"
受众群体 -> 发布状态，在"测试用户" Add users
```

# 在 Mac 终端运行代码，需要设置代理
## Clash Verge
```
代码 https://github.com/clash-verge-rev/clash-verge-rev
帮助文档 https://www.clashverge.dev/index.html
```

## ClashX (Deprecated)
```
ClashX 复制终端代理命令，会导致无法访问 ClashX API ，无法访问 oapi.dingtalk.com
export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890 all_proxy=socks5://127.0.0.1:7890

增加 NO_PROXY ，改为下面的命令

export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890 all_proxy=socks5://127.0.0.1:7890 NO_PROXY="127.0.0.1,localhost,oapi.dingtalk.com"
```

## 钱包加密
引用 git 项目代码
https://github.com/alondai/private_key_encrypt_toolkit
用法见项目 README.md

# Run
```
cd x-visit/
cp conf.py.sample conf.py
cp datas/account/encrypt.csv.sample datas/account/encrypt.csv
# modify datas/account/encrypt.csv
python xvisit.py
```
