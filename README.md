# X-Assistant Change List

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

# Run
```
cd x-visit/
cp conf.py.sample conf.py
cp datas/account/encrypt.csv.sample datas/account/encrypt.csv
# modify datas/account/encrypt.csv
python xvisit.py
```
