"""
utils
"""
import html
import os
import sys
import json
import requests
from datetime import datetime
from dateutil import tz
from datetime import timezone
from datetime import timedelta
import socket
import time
import re
import random
import string

from conf import TZ_OFFSET
from conf import DEF_BOT_TYPE


DEF_URL_DINGTALK = "https://oapi.dingtalk.com/robot/send"
access_token = "0313ed7471f2910596c1d91cef6569c132"  # noqa


def conv_time(ts, style=1):
    """
    ts: second
    style:
        1: 2022-10-20
        2: 2022-10-20T20:51:11+0800
        3: 2022-10-20 00:00:00
        4: 20:51
        5: 2022-10-20 20:51:11
    """
    to_zone = tz.gettz('Asia/Shanghai')
    if style == 1:
        t_format = "%Y-%m-%d"
    elif style == 2:
        t_format = "%Y-%m-%dT%H:%M:%S+0800"
    elif style == 3:
        t_format = "%Y-%m-%d 00:00:00"
    elif style == 4:
        t_format = "%H:%M"
    elif style == 5:
        t_format = "%Y-%m-%d %H:%M:%S"
    else:
        print("conv_time parameter is error.")
        sys.exit(1)
    dt = datetime.utcfromtimestamp(ts)
    # local = dt.astimezone(to_zone)
    local = dt.replace(tzinfo=timezone.utc).astimezone(to_zone)
    s_date = local.strftime(t_format)
    return s_date


def format_ts(ts, style=1, tz_offset=0):
    """
    ts: second
    style:
        1: 2022-10-20
        2: 2022-10-20T20:51:11+0800
        3: 2022-10-20 00:00:00
        4: 20:51
        5: 2022-10-20 20:51:11
    tz_offset:
        timezone offset in hours from UTC
        e.g., 0 for UTC, 8 for Asia/Shanghai
    """
    if style == 1:
        t_format = "%Y-%m-%d"
    elif style == 2:
        t_format = "%Y-%m-%dT%H:%M:%S"
    elif style == 3:
        t_format = "%Y-%m-%d 00:00:00"
    elif style == 4:
        t_format = "%H:%M"
    elif style == 5:
        t_format = "%Y-%m-%d %H:%M:%S"
    else:
        print("conv_time parameter is error.")
        sys.exit(1)
    # Convert timestamp to datetime object in UTC
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)

    # Calculate the target timezone
    to_zone = timezone(timedelta(hours=tz_offset))

    # Convert to target timezone
    local = dt.astimezone(to_zone)

    # Format the datetime object to the specified style
    s_date = local.strftime(t_format)

    # Append the timezone offset to the formatted string if style is 2
    if style == 2:
        s_date += f"{tz_offset:+03d}00"

    return s_date


def get_host_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


def ding_msg(content, access_token, msgtype="markdown"):
    lst_phone = []

    s_ip = get_host_ip()
    if "markdown" == msgtype:
        content["text"] += (
            "\n###### Update:{time}"
            "\n###### From:{ip}".format
            (
                time=conv_time(time.time(), 5),
                ip=s_ip
            )
        )
    else:
        content += (
            "\nUpdate:{time}"
            "\nFrom:{ip}".format
            (
                time=conv_time(time.time(), 5),
                ip=s_ip
            )
        )
        content = {
            "content": content
        }
    data = {
        "msgtype": msgtype,
        msgtype: content,
        "at": {
            "atMobiles": lst_phone,
            "isAtAll": False
        }
    }
    data = json.dumps(data)
    print(data)

    headers = {"Content-Type": "application/json; charset=utf-8"}

    # 增加重试机制和更长的超时时间
    max_retries = 3
    timeout = 10  # 增加超时时间到10秒

    for i in range(max_retries):
        try:
            resp = requests.post(
                url=f"{DEF_URL_DINGTALK}?access_token={access_token}",
                data=data,
                headers=headers,
                timeout=timeout
            )
            print(resp.content)
            return resp
        except requests.exceptions.Timeout:
            if i == max_retries - 1:  # 最后一次重试
                print(f"钉钉消息发送失败: 超时 {max_retries} 次")
                pass
            print(f"钉钉消息发送超时, 正在进行第 {i+1} 次重试...")
            time.sleep(3)  # 重试前等待3秒
        except Exception as e:
            print(f"钉钉消息发送失败: {str(e)}")
            pass


def _bot_type_normalized():
    return (DEF_BOT_TYPE or 'dingding').strip().lower()


def is_bot_telegram():
    return _bot_type_normalized() == 'telegram'


def _tg_credentials(tg_channel):
    from conf import (
        DEF_TG_TOKEN_ALERT,
        DEF_TG_TOKEN_SILENT,
        DEF_TG_CHAT_ID_ALERT,
        DEF_TG_CHAT_ID_SILENT,
    )
    if tg_channel == 'silent':
        return DEF_TG_TOKEN_SILENT, DEF_TG_CHAT_ID_SILENT
    return DEF_TG_TOKEN_ALERT, DEF_TG_CHAT_ID_ALERT


def _telegram_send_text(bot_token, chat_id, text, parse_mode=None):
    if not bot_token or chat_id is None or str(chat_id).strip() == '':
        return None
    if len(text) > 4096:
        text = text[:4093] + '...'
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    max_retries = 3
    timeout = 10
    for i in range(max_retries):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            print(resp.content)
            if resp.ok:
                return resp
        except requests.exceptions.Timeout:
            if i == max_retries - 1:
                print(f"Telegram 消息发送失败: 超时 {max_retries} 次")
            else:
                print(f"Telegram 消息发送超时, 正在进行第 {i + 1} 次重试...")
                time.sleep(3)
        except Exception as e:
            print(f"Telegram 消息发送失败: {str(e)}")
            break
    return None


def _telegram_send_pre_copyable(bot_token, chat_id, plain_text):
    """
    使用 HTML <pre>，Telegram 客户端可点按整块复制。
    """
    s = (plain_text or '').strip()
    if not s:
        return None
    suffix = ''
    trial = s
    while trial:
        inner = html.escape(trial + suffix)
        full = f"<pre>{inner}</pre>"
        if len(full) <= 4096:
            return _telegram_send_text(
                bot_token, chat_id, full, parse_mode='HTML')
        trial = trial[:-1]
        suffix = '...'
    return _telegram_send_text(
        bot_token, chat_id, '<pre>…</pre>', parse_mode='HTML')


def notify_msg_text(s_msg, ding_token, tg_channel='alert'):
    """
    按 DEF_BOT_TYPE 发送文本：dingding 用钉钉机器人；telegram 用对应频道 Bot。
    tg_channel: 'alert' | 'silent' | 'default'（default 与 alert 同一组 TG 配置）
    """
    bt = _bot_type_normalized()
    if bt == 'telegram':
        ch = 'silent' if tg_channel == 'silent' else 'alert'
        tok, cid = _tg_credentials(ch)
        return _telegram_send_text(tok, cid, s_msg)
    if ding_token:
        return ding_msg(s_msg, ding_token, msgtype='text')
    return None


def notify_msg_markdown(d_cont, ding_token, tg_channel='alert'):
    """
    按 DEF_BOT_TYPE 发送 markdown 结构通知（钉钉 markdown / Telegram 纯文本拼接）。
    tg_channel: 'alert' | 'silent' | 'default'
    """
    bt = _bot_type_normalized()
    if bt == 'telegram':
        ch = 'silent' if tg_channel == 'silent' else 'alert'
        tok, cid = _tg_credentials(ch)
        if not tok or cid is None or str(cid).strip() == '':
            return None
        s_title = d_cont.get('title', '') or ''
        s_body = d_cont.get('text', '') or ''
        text = f"{s_title}\n\n{s_body}" if s_title else s_body
        return _telegram_send_text(tok, cid, text)
    if ding_token:
        d_copy = {
            'title': d_cont.get('title', ''),
            'text': d_cont.get('text', ''),
        }
        return ding_msg(d_copy, ding_token, msgtype="markdown")
    return None


def format_follow_count_cn(n):
    """
    展示关注/粉丝数：未满万用千分位逗号（如 4,651）；万、亿用中文单位。
    """
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    if n < 0:
        return '—'
    if n < 1000:
        return str(n)
    if n < 10000:
        return f'{n:,}'

    def scaled(val, unit):
        ir = int(round(val))
        if abs(val - ir) < 1e-9:
            return f'{ir}{unit}'
        s = f'{round(val, 1):.1f}'.rstrip('0').rstrip('.')
        return f'{s}{unit}'

    if n < 100_000_000:
        return scaled(n / 10000, '万')
    return scaled(n / 100_000_000, '亿')


def notify_telegram_llm_replies(
    s_user,
    nickname,
    tw_url,
    tw_text,
    lst_candidate_replies,
    tg_channel,
    n_following=-1,
    n_followers=-1,
):
    """
    Telegram：上下文一条，每条候选回复单独一条（<pre> 可点按复制），仅 reply 正文。
    """
    ch = 'silent' if tg_channel == 'silent' else 'alert'
    tok, cid = _tg_credentials(ch)
    if not tok or cid is None or str(cid).strip() == '':
        return None
    s_preview = (tw_text or '')[:100]
    header_lines = [
        f"👤 {s_user} ({nickname})",
    ]
    if n_following >= 0 or n_followers >= 0:
        header_lines.append(
            "📊 关注 "
            f"{format_follow_count_cn(n_following)} · "
            f"粉丝 {format_follow_count_cn(n_followers)}"
        )
    header_lines.extend(
        [
            f"🔗 {tw_url}",
            "",
            f"🧾 {s_preview} ...",
        ]
    )
    header = "\n".join(header_lines)
    _telegram_send_text(tok, cid, header)
    last = None
    for item in lst_candidate_replies:
        body = (item.get('reply') or '').strip()
        if not body:
            continue
        last = _telegram_send_pre_copyable(tok, cid, body)
    return last


def is_text_notify_configured():
    """普通文本通知（如日报、异常）是否已配置对应渠道。"""
    if _bot_type_normalized() == 'telegram':
        tok, cid = _tg_credentials('alert')
        return bool(tok and str(cid).strip())
    from conf import DEF_DING_TOKEN
    return len(DEF_DING_TOKEN) > 0


def ts_human(n_sec):
    s_ret = ""
    n_hour = 0
    n_min = 0
    n_sec = int(n_sec)
    if n_sec >= 3600:
        n_hour = int(n_sec / 3600)
        n_sec = n_sec % 3600
    if n_sec >= 60:
        n_min = int(n_sec / 60)
        n_sec = int(n_sec % 60)

    if n_hour:
        s_ret += "{}h".format(n_hour)
    if n_min:
        s_ret += "{}m".format(n_min)
    if n_sec:
        s_ret += "{}s".format(n_sec)

    return s_ret


def get_date(is_utc=True):
    # 获取当前 UTC 时间的日期
    now = datetime.utcnow()

    # 格式化为 yyyymmdd
    s_date = now.strftime('%Y%m%d')

    return s_date


def get_index_from_header(header, field):
    """
    根据给定的字段获取其在header中的下标。

    参数:
        header (str): 以逗号分隔的字段字符串，例如 "account,purse,evm_address,vpn"
        field (str): 需要查找的字段名称，例如 "vpn"

    返回:
        int: 字段在header中的下标，如果字段不存在则返回 -1
    """
    # 将header字符串分割为列表
    fields = header.split(',')
    # 获取字段的下标
    try:
        index = fields.index(field)
    except ValueError:
        # 如果字段不存在，返回 -1
        index = -1
    return index


def load_file(file_in, idx_key=0, header=''):
    """
    Return:
        dict(key, list)
    跳过以 # 开头的行
    """
    d_ret = {}
    try:
        with open(file_in, 'r') as fp:
            # Skip the header line
            next(fp)
            for line in fp:
                if len(line.strip()) == 0:
                    continue
                if line.startswith('#'):
                    continue
                # 逗号分隔，字段中不能包含逗号
                fields = line.strip().split(',')
                s_key = fields[idx_key]
                d_ret[s_key] = fields
    except StopIteration:
        # print("File is empty.")
        pass
    except FileNotFoundError:
        print(f'[load_file] file is not found! [{file_in}] [ERROR]')
    except Exception as e:
        print(f'[load_file] An error occurred: {str(e)}')

    return d_ret


def save2file(file_ot, dic_status, idx_key=0, header=''):
    """
    header: 表头
    dic_status: 输出的字段列表
    idx_key: dic_status value 的主键下标
    """
    b_ret = True
    s_msg = ''

    dir_file_out = os.path.dirname(file_ot)
    if dir_file_out and (not os.path.exists(dir_file_out)):
        os.makedirs(dir_file_out)

    if not os.path.exists(file_ot):
        with open(file_ot, 'w') as fp:
            fp.write(f'{header}\n')

    try:
        # 先读取原有内容，合并至 dic_status
        if os.path.exists(file_ot):
            with open(file_ot, 'r') as fp:
                lines = fp.readlines()
                for line in lines[1:]:  # 跳过表头
                    fields = line.strip().split(',')
                    if len(fields) == 0:
                        continue
                    s_key = fields[idx_key]
                    if s_key in dic_status:
                        continue
                    dic_status[s_key] = fields

        lst_sorted = sorted(dic_status.keys())
        with open(file_ot, 'w') as fp:
            fp.write(f'{header}\n')
            for s_key in lst_sorted:
                s_out = ','.join(str(item) for item in dic_status[s_key])
                fp.write(f'{s_out}\n')
    except Exception as e:
        b_ret = False
        s_msg = f'[save2file] An error occurred: {str(e)}'

    return (b_ret, s_msg)


def time_difference(input_time_str):
    # 将传入的时间字符串转换为datetime对象
    input_time = datetime.strptime(input_time_str, "%Y-%m-%dT%H:%M:%S%z")

    # 获取当前时间，并设置为UTC时区
    current_time_utc = datetime.now(timezone.utc)

    # 将当前时间转换为传入时间的时区
    current_time = current_time_utc.astimezone(input_time.tzinfo)

    # 计算时间差并转换为秒
    time_diff_seconds = (input_time - current_time).total_seconds()

    time_diff_seconds = int(time_diff_seconds)

    return time_diff_seconds


def extract_numbers(s):
    # 使用正则表达式找到所有的数字
    numbers = re.findall(r'\d+', s)
    # 将找到的数字字符串转换为整数
    return [int(num) for num in numbers]


def seconds_to_hms(seconds):
    """
    Convert seconds to hours, minutes, and seconds.
    Args:
    - seconds (int): The number of seconds to convert.
    Returns:
    - str: A string representing the time in the format "xx小时xx分钟xx秒".
      Hours and minutes are omitted if they are zero.
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0 or (hours > 0 and seconds > 0):
        parts.append(f"{minutes}分钟")
    parts.append(f"{seconds}秒")

    return ''.join(parts)


def generate_password(length):
    """
    生成指定长度的密码
    :param length: 密码长度
    :return: 生成的密码

    至少包含2个下划线。
    不能出现连续2个相同的字符。
    首尾不能是下划线。
    """
    if length < 6:
        raise ValueError("密码长度至少为6，以满足至少2个下划线和首尾非下划线的要求")

    # 包含大小写字母和数字的字符集
    non_underscore_characters = string.ascii_letters + string.digits

    # 初始化密码，先放3个下划线
    password = ['_'] * 3

    # 填充剩余的字符，直到密码长度达到要求
    while len(password) < length:
        next_char = random.choice(non_underscore_characters)
        # 确保不出现连续相同的字符
        if len(password) > 0 and password[-1] == next_char:
            continue
        password.append(next_char)

    # 打乱密码字符顺序
    random.shuffle(password)

    # 确保首尾不是下划线
    if password[0] == '_':
        password[0] = random.choice(non_underscore_characters)
    if password[-1] == '_':
        password[-1] = random.choice(non_underscore_characters)

    # 确保至少2个下划线
    if password.count('_') < 2:
        # 找到一个不是首尾的位置，插入一个下划线
        insert_pos = random.randint(1, len(password) - 2)  # 不插入到首尾
        password.insert(insert_pos, '_')

    # 再次检查并调整，确保不出现连续相同的字符
    for i in range(len(password) - 1):
        if password[i] == password[i + 1]:
            password[i + 1] = random.choice(non_underscore_characters)

    return ''.join(password)


def load_advertising_urls(csv_file):
    """
    加载广告 URL

    过滤当天的 url 列表
    如果当天结果为空，取前一天的列表
    如果前一天的列表也为空，则加载所有 url
    如果所有列表都为空，则返回空列表

    date,project,url
    2025-06-21,Spark,https://x.com/ablenavy/status/1936212691250823202
    """
    # csv_file = 'datas/status/xwool/advertising.csv'
    lst_urls_today = []
    lst_urls_yesterday = []
    lst_urls_all = []
    lst_ret = []

    if not os.path.exists(csv_file):
        print(f'CSV file not found: {csv_file}')
        return []

    # 获取今天的日期
    today = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)
    yesterday = format_ts(
        time.time() - 24 * 60 * 60, style=1, tz_offset=TZ_OFFSET)

    try:
        # 使用 load_file 函数加载 CSV 数据
        dic_data = load_file(csv_file, idx_key=2)

        # 提取 URL（CSV 格式：date,project,url）
        for key, fields in dic_data.items():
            if len(fields) >= 3:
                date_str = fields[0].strip()
                url = fields[2].strip()

                if url and url.startswith('https://'):
                    lst_urls_all.append(url)
                    # 如果是今天的日期，添加到今天的列表
                    if date_str == today:
                        lst_urls_today.append(url)
                    elif date_str == yesterday:
                        lst_urls_yesterday.append(url)
                    else:
                        lst_urls_all.append(url)

        # 优先使用今天的 URL，如果今天没有则使用所有 URL
        if lst_urls_today:
            print(f'Loaded {len(lst_urls_today)} URLs for today')
            lst_ret = lst_urls_today
        elif lst_urls_yesterday:
            print(
                f'No URLs for today, loaded {len(lst_urls_yesterday)} '
                'URLs for yesterday')
            lst_ret = lst_urls_yesterday
        elif lst_urls_all:
            print(
                f'No URLs for today and yesterday, loaded '
                f'{len(lst_urls_all)} total URLs from CSV')
            lst_ret = lst_urls_yesterday
        else:
            print(
                f'No URLs for today and yesterday, loaded '
                f'{len(lst_urls_all)} total URLs from CSV')
            lst_ret = lst_urls_all

    except Exception as e:
        print(f'Error loading advertising URLs: {str(e)}')
        # 加载失败，使用空列表

    return lst_ret


def load_ad_user(csv_file):
    """
    加载 X 账号列表

    文件格式：
    x_user,x_nickname
    ablenavy,iGarlic
    hunterlarcuad

    如果只有一个字段，x_nickname 赋值为 x_user

    """
    # csv_file = 'datas/status/xwool/advertising.csv'
    lst_ad_user = []

    if not os.path.exists(csv_file):
        print(f'CSV file not found: {csv_file}')
        return lst_ad_user

    try:
        # 使用 load_file 函数加载 CSV 数据
        dic_data = load_file(csv_file, idx_key=0)

        # 提取 URL（CSV 格式：date,project,url）
        for key, fields in dic_data.items():
            if len(fields) >= 2:
                x_user = fields[0].strip()
                x_nickname = fields[1].strip()
            else:
                x_user = fields[0].strip()
                x_nickname = fields[0].strip()
            lst_ad_user.append((x_user, x_nickname))

    except Exception as e:
        print(f'Failed to load ad_user: {str(e)}')
        # 加载失败，使用空列表

    return lst_ad_user


def load_to_set(csv_file, set_user):
    """
    加载 X 账号列表

    文件格式：
    x_user,x_nickname
    ablenavy,iGarlic
    hunterlarcuad

    只有一个字段，则赋值为 x_user

    return set_user
    set_user = set([])

    """
    # csv_file = 'datas/status/xwool/advertising.csv'
    # set_user = set([])

    if not os.path.exists(csv_file):
        print(f'CSV file not found: {csv_file}')
        return set_user

    try:
        # 使用 load_file 函数加载 CSV 数据
        dic_data = load_file(csv_file, idx_key=0)

        # 提取 URL（CSV 格式：date,project,url）
        for key, fields in dic_data.items():
            if len(fields) >= 1:
                x_user = fields[0].strip()
            else:
                continue
            set_user.add(x_user)

    except Exception as e:
        print(f'Failed to load x_user: {str(e)}')
        # 加载失败，使用空列表

    return set_user


def rm_url(s_cont):
    """
    去掉 URL
    """
    if not s_cont:
        return s_cont

    # 匹配 http:// 或 https:// 开头的 URL
    url_pattern = r'https?://[^\s]+'
    s_ret = re.sub(url_pattern, '', s_cont)

    # 清理多余的空格
    s_ret = re.sub(r'\s+', ' ', s_ret).strip()

    return s_ret


if __name__ == "__main__":
    """
    """

    # 示例用法
    password_length = 20  # 指定密码长度
    password = generate_password(password_length)
    print(f"生成的密码为: {password}")
    sys.exit(-1)

    input_time_str = "2024-09-09T18:21:22+0800"
    n_sec = time_difference(input_time_str)
    print(n_sec)
    sys.exit(-1)

    file_test = 'ttt.csv'
    dic_status = load_file(file_test, idx_key=0, header='')
    dic_status['p005'] = ['p005', 'DONE', 10, 5, -1]
    save2file(file_test, dic_status, idx_key=0, header='header')
    sys.exit(-1)

    s_token = 'ff930a850a7feebb7db0ea1f0e5b3032f175dab'  # noqa
    d_cont = {
        'title': 'my title',
        'text': (
            '- first line\n'
            '- second line\n'
        )
    }
    ding_msg(d_cont, s_token, msgtype="markdown")
