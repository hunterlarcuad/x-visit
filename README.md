# X互动助手升级版

2025.09.07

## 一、用到两个项目

### 1、X访问及互动

[https://github.com/hunterlarcuad/x-visit](https://github.com/hunterlarcuad/x-visit)

X 自动登录，关注、点赞、回复。可以配置只与包含特点关键词的帖子进行互动。可以配置通过大模型进行智能回复。

本地运行，Web页面控制，傻瓜化操作！

### 2、浏览器

[https://github.com/ungoogled-software/ungoogled-chromium](https://github.com/ungoogled-software/ungoogled-chromium)

ungoogled-chromium 是一个基于 Google Chromium 的浏览器项目，主要目标是去除所有与 Google 服务相关的依赖，增强隐私和用户对浏览器的控制权，同时尽量保持原生 Chromium 的使用体验。

## 二、项目部署

我是在 Mac 上进行部署，如果是 Windows ，操作类似。

### 1、打开终端命令行

点击“启动台”，输入“终端”，打开终端

默认是在当前用户的目录下

在命令行输入下面的命名，显示当前所在目录

```bash
pwd
```

### 2、从 github 代码仓库把代码克隆到本地

```bash
# 如果没有安装 git，先安装一下
git clone https://github.com/hunterlarcuad/x-visit.git
```

### 3、代码部署

```bash
# 进入到代码目录
cd x-visit
# 创建虚拟环境
python -m venv venv
# 激活虚拟环境
source venv/bin/activate
# 在虚拟环境中安装依赖包
pip install -r requirements.txt
# 拷贝默认配置
cp conf.py.sample conf.py
cp datas/account/account.csv.sample datas/account/account.csv
```

### 4、使用记事本编辑 conf.py

设置 ungoogled-chromium 执行文件所在的路径

DEF_PATH_BROWSER = '/Applications/Chromium.app/Contents/MacOS/Chromium’

需要准备几个账号

Yescaptcha 验证码(图形验证码)

# [https://yescaptcha.com/i/Af32Me](https://yescaptcha.com/i/Af32Me)

充 1u 能用好久

Capmonster 验证码(点击进行真人验证)

智普大模型，用来自动回复，新用户注册，白嫖资源包，有3个月的有效期

通过我的邀请链接注册即可获得 2000万Tokens 大礼包，期待和你一起在BigModel上体验最新顶尖模型能力；链接：[https://www.bigmodel.cn/invite?icode=qauKhTeA%2BAzmE%2Ba3pjZTEHHEaazDlIZGj9HxftzTbt4%3D](https://www.bigmodel.cn/invite?icode=qauKhTeA%2BAzmE%2Ba3pjZTEHHEaazDlIZGj9HxftzTbt4%3D)

免费的如果用完，实名认证一下，还能再赠送一个资源包

```bash
# 图形验证码
DEF_CAPTCHA_KEY = 'your_key'

# Cloudflare 人机验证
DEF_CAPMONSTER_KEY = 'your_key'

# GLM API Key
DEF_LLM_ZHIPUAI = 'set_your_secretkey'
# 用哪个模型，如果赠送的资源包指定了模型，在这里设置
DEF_MODEL_ZHIPUAI = 'glm-4-plus'

# 设置浏览器路径
DEF_PATH_BROWSER = '/Applications/Chromium.app/Contents/MacOS/Chromium'
```

如何查看智普赠送的资源包是哪个模型？

打开”资源包管理”

[https://www.bigmodel.cn/finance-center/resource-package/package-mgmt](https://www.bigmodel.cn/finance-center/resource-package/package-mgmt)

在”我的资源包”，适用场景，如果是适用所有按 tokens 计费，就是通用的；如果是指定了适用于 xx 模型，就在配置里设置对应的模型。

例如：我的这个资源包，适用于 glm-4.1v-thinking-flashx 模型的推理

![image.png](https://github.com/hunterlarcuad/x-visit/blob/main/static/img/image1.png?raw=true)

那么配置如下：

```bash
DEF_MODEL_ZHIPUAI = 'glm-4.1v-thinking-flashx'
```

### 5、使用记事本编辑 datas/account/account.csv

account 和 proxy 随便填

x_username 用户名

x_pwd 密码

x_verifycode 一次性密码

proxy 使用的VPN，随便填一个

```bash
account,x_username,x_pwd,x_verifycode,proxy
g01,smithjame0501,nqc6BKXXXXXXXXXXbxc,4SRNGEXXXXXXXXXX,proxy-hk
```

## 三、运行

```bash
cd x-visit/
# 激活虚拟环境
source venv/bin/activate
# 启动服务
python start_web.py
```

在浏览器地址栏输入下面的网址

```bash
http://localhost:5001
```

在 账号状态 页面，可以查看每个 X 账号最后访问时间

![image.png](https://github.com/hunterlarcuad/x-visit/blob/main/static/img/image2.png?raw=true)

在 准备发射 页面，选择账号，配置参数，点击立即发射按钮，就开始执行！

如果是新号，最好循序渐进，逐步增加互动数量。

在当日数量限制，设置当天最大的关注、点赞、回复数量。如果是大 V ，不想随意关注别人，关注数量可以设置为0，这样就不会去自动关注。

![image.png](https://github.com/hunterlarcuad/x-visit/blob/main/static/img/image3.png?raw=true)

开始执行，会自动跳转到 指挥中心 页面，在这里可以停止，看运行日志，看数据统计

![image.png](https://github.com/hunterlarcuad/x-visit/blob/main/static/img/image4.png?raw=true)

[https://x.com/ablenavy/status/1964699986870075476](https://x.com/ablenavy/status/1964699986870075476)
