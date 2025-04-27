import os
import pickle
import base64
import re

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# OAuth 2.0 权限范围
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# 获取当前脚本所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 构建凭证路径
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(BASE_DIR, 'token.pickle')


def extract_verify_code(text):
    # 使用正则表达式匹配6位数字
    match = re.search(r'\b\d{6}\b', text)
    if match:
        return match.group()
    else:
        return None


def get_gmail_service():
    """获取 Gmail API 服务"""
    creds = None
    # token.pickle 文件保存用户的访问和刷新令牌。第一次运行时，它会创建该文件。
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    # 如果没有有效的凭证，提示用户登录。
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        # 保存凭证供下次使用
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    try:
        # 返回 Gmail 服务
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as error:
        print(f'An error occurred: {error}')
        return None


def get_email_body(message):
    """递归解析邮件内容，处理多部分邮件，提取正文"""
    parts = message['payload'].get('parts', [])

    if not parts:  # 如果邮件没有 parts，直接查看 body
        body = message['payload'].get('body', {}).get('data', '')
        if body:
            return base64.urlsafe_b64decode(body).decode('utf-8')
        return "邮件正文内容为空"

    # 如果邮件有多个部分，则递归查找正文
    for part in parts:
        mime_type = part.get('mimeType')
        if mime_type == 'text/plain':  # 如果是纯文本邮件
            body = part['body'].get('data', '')
            return base64.urlsafe_b64decode(body).decode('utf-8')
        elif mime_type == 'text/html':  # 如果是 HTML 格式邮件
            body = part['body'].get('data', '')
            return base64.urlsafe_b64decode(body).decode('utf-8')

    return "邮件正文内容为空"


def get_emails_by_subject():
    """获取邮件标题包含特定关键词的邮件列表"""
    service = get_gmail_service()
    if not service:
        print("无法连接到 Gmail 服务")
        return

    try:
        # 获取所有邮件（不区分已读和未读），过滤条件为主题包含特定文字
        # query = 'subject:"confirm your email address to access all of X"'
        query = 'is:unread subject:"confirm your email address to access all of X"' # noqa
        query = 'is:unread subject:"confirm your email address to access all of X"' # noqa

        s_in_title = 'is your X verification code'
        query = f'is:unread subject:"{s_in_title}"' # noqa

        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute() # noqa
        # results = service.users().messages().list(userId='me', q=query).execute() # noqa
        messages = results.get('messages', [])

        if not messages:
            print('没有找到符合条件的邮件.')
        else:
            print(f'找到 {len(messages)} 封符合条件的邮件：')
            for message in messages:
                msg = service.users().messages().get(userId='me', id=message['id']).execute() # noqa

                # 获取邮件的主题和发件人
                payload = msg['payload']
                headers = payload['headers']
                from_name = subject = None
                for header in headers:
                    if header['name'] == 'From':
                        from_name = header['value']
                    elif header['name'] == 'Subject':
                        subject = header['value']

                # 获取邮件正文
                body = get_email_body(msg)

                print(f'发件人: {from_name}')
                print(f'主题: {subject}')
                print(f'邮件正文: {body[:100]}...')  # 打印前 100 个字符
                s_code = extract_verify_code(body)
                print(f'验证码: {s_code}')
                print('-' * 50)

    except HttpError as error:
        print(f'发生错误: {error}')


def get_verify_code_from_gmail(s_in_title):
    """
    获取邮件标题包含特定关键词的邮件列表

    Return:
        None: 未获取到验证码
        string: 验证码
    """
    service = get_gmail_service()
    if not service:
        print("无法连接到 Gmail 服务")
        return None

    try:
        # 获取所有邮件（不区分已读和未读），过滤条件为主题包含特定文字
        # query = 'subject:"confirm your email address to access all of X"'
        # query = 'is:unread subject:"confirm your email address to access all of X"' # noqa
        query = f'is:unread subject:"{s_in_title}"' # noqa
        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute() # noqa
        messages = results.get('messages', [])

        if not messages:
            # print('没有找到符合条件的邮件.')
            pass
        else:
            # print(f'找到 {len(messages)} 封符合条件的邮件')
            for message in messages:
                msg = service.users().messages().get(userId='me', id=message['id']).execute() # noqa

                # 获取邮件正文
                body = get_email_body(msg)
                s_code = extract_verify_code(body)
                return s_code

    except HttpError as error:
        print(f'发生错误: {error}')

    return None


if __name__ == '__main__':
    get_emails_by_subject()
