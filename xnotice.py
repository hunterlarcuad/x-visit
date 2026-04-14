import os  # noqa
import sys  # noqa
import argparse
import random
import time
import copy
import pdb  # noqa
import shutil
import json
import math
import re  # noqa
from datetime import datetime, timedelta, timezone  # noqa
import multiprocessing
from fun_db import DBManager

from DrissionPage._elements.none_element import NoneElement

from fun_utils import format_follow_count_cn
from fun_utils import is_bot_telegram
from fun_utils import is_text_notify_configured
from fun_utils import notify_msg_markdown
from fun_utils import notify_msg_text
from fun_utils import notify_telegram_llm_replies
from fun_utils import format_ts
from fun_utils import time_difference
from fun_utils import get_index_from_header
from fun_utils import load_advertising_urls
from fun_utils import load_ad_user
from fun_utils import load_to_set

from fun_glm import gene_by_llm

from fun_okx import OkxUtils
from fun_x import XUtils
from fun_dp import DpUtils

from conf import DEF_USE_HEADLESS, DEF_LOCAL_PORT
from conf import DEF_DEBUG
from conf import DEF_PATH_USER_DATA
from conf import DEF_DING_TOKEN
from conf import DEF_DING_TOKEN_ALERT
from conf import DEF_DING_TOKEN_SILENT
from conf import DEF_PATH_DATA_STATUS

from conf import EXTENSION_ID_CAPMONSTER
from conf import EXTENSION_ID_YESCAPTCHA

from conf import DEF_HEADER_ACCOUNT

from conf import TZ_OFFSET
from conf import DEL_PROFILE_DIR

from conf import WHITELIST_USER_NEW_POST_HOUR
from conf import WHITELIST_USER_MAX_NUM_POST_PER_ROUND
# from conf import SILENCE_TIME_RANGE

from conf import WHITELIST_USER_MAX_NUM_AD_USER_PER_ROUND

from conf import FILENAME_LOG
from conf import logger

"""
2025.03.18
"""

# Wallet balance
DEF_INSUFFICIENT = -1
DEF_SUCCESS = 0
DEF_FAIL = 1

# Mint would exceed wallet limit
DEF_EXCEED_LIMIT = 10
# Price too high
DEF_PRICE_TOO_HIGH = 11

# output
IDX_STATUS = 1
IDx_wool_DATE = 2
IDX_NUM_VISIT = 3
IDX_UPDATE = 4
FIELD_NUM = IDX_UPDATE + 1

# X STATUS
DEF_STATUS_OK = 'OK'
DEF_STATUS_SUSPEND = 'SUSPEND'
DEF_STATUS_APPEALED = 'APPEALED'

# Interaction Result
DEF_INTERACTION_OK = 'OK'
DEF_INTERACTION_IGNORE = 'IGNORE'

DEF_OKX = False


def parse_follow_count_text(s):
    """
    从 X 关注/粉丝文案中解析整数；无法解析返回 -1。
    例：4,651正在关注 -> 4651；1.1万 -> ×1e4；2.3亿 -> ×1e8。
    """
    if s is None:
        return -1
    s = str(s).strip()
    if not s:
        return -1
    m_yi = re.search(r'([\d,]+\.?\d*)\s*亿', s)
    if m_yi:
        try:
            v = float(m_yi.group(1).replace(',', ''))
            return int(round(v * 100_000_000))
        except ValueError:
            return -1
    m_wan = re.search(r'([\d,]+\.?\d*)\s*万', s)
    if m_wan:
        try:
            v = float(m_wan.group(1).replace(',', ''))
            return int(round(v * 10000))
        except ValueError:
            return -1
    m_num = re.search(r'[\d,]+', s)
    if m_num:
        try:
            return int(m_num.group(0).replace(',', ''))
        except ValueError:
            return -1
    return -1


class XNotice():
    def __init__(self) -> None:
        self.args = None

        # 是否有更新
        self.is_update = False

        # 账号执行情况
        self.dic_status = {}

        self.dic_account = {}

        # self.account_load()

        if DEF_OKX:
            self.inst_okx = OkxUtils()
        else:
            self.inst_okx = None

        self.inst_dp = DpUtils()
        self.inst_x = XUtils()
        self.db = DBManager()
        self.user_queue = None
        self.tweet_queue = None

        self.inst_dp.plugin_yescapcha = True
        self.inst_dp.plugin_capmonster = True

        self.lst_header_status = [
            'update',
            'op_type',
            'status',
            'url',
            'msg',
        ]
        self.DEF_HEADER_STATUS = ','.join(self.lst_header_status)

        self.set_url_ignored = set([])
        self.set_user_followed = set([])
        self.set_url_liked = set([])
        self.set_url_replied = set([])
        self.set_url_retweeted = set([])

        self.set_user_white = set([])
        self.set_user_black = set([])
        self.set_notice_white = set([])
        self.set_notice_black = set([])

        self.lst_advertise_url = []
        self.lst_attached_url = []

        self.n_follow = 0

        # Notice user list
        self.lst_users_pre = []

        # 处理过的通知 URL
        self.set_url_notice = set([])

        # 候选回复（多风格），由 get_tweet_candidates_reply 填充
        self.lst_candidate_replies = []
        self.tw_url = ''
        self.nickname = ''
        self.tw_text = ''
        self.n_following = -1
        self.n_followers = -1
        self.user_desc = ''

    def reset_vals(self):
        """
        Reset variables
        """
        self.lst_candidate_replies = []
        self.tw_url = ''
        self.nickname = ''
        self.tw_text = ''
        self.n_following = -1
        self.n_followers = -1
        self.user_desc = ''

    def set_args(self, args):
        self.args = args
        self.is_update = False

        # Propagate args to sub-instances
        self.inst_dp.set_args(args)
        self.inst_x.set_args(args)

        # Current X User
        self.i_xuser = None

        self.file_status = (
            f'{DEF_PATH_DATA_STATUS}/xnotice/status_{self.args.s_profile}.csv'
        )
        self.file_advertising = (
            f'{DEF_PATH_DATA_STATUS}/xnotice/advertising.csv'
        )
        self.file_ad_user = f'{DEF_PATH_DATA_STATUS}/xnotice/ad_user.csv'
        self.file_user_white = f'{DEF_PATH_DATA_STATUS}/xnotice/a_user_white.csv'
        self.file_user_black = f'{DEF_PATH_DATA_STATUS}/xnotice/a_user_black.csv'
        self.file_notice_white = (
            f'{DEF_PATH_DATA_STATUS}/xnotice/b_notice_white.csv'
        )
        self.file_notice_black = (
            f'{DEF_PATH_DATA_STATUS}/xnotice/b_notice_black.csv'
        )

        self.load_processed_url()

        self.n_follow = 0

        self.set_user_white = set([])
        self.set_user_black = set([])
        self.set_notice_white = set([])
        self.set_notice_black = set([])

        self.set_user_white = load_to_set(self.file_ad_user, self.set_user_white)  # noqa
        self.set_user_white = load_to_set(self.file_user_white, self.set_user_white)  # noqa
        self.set_user_black = load_to_set(self.file_user_black, self.set_user_black)  # noqa
        self.reload_notice_user_lists()
        self.logit(None, f'set_user_white: {len(self.set_user_white)}')
        self.logit(None, f'set_user_black: {len(self.set_user_black)}')

    def reload_notice_user_lists(self):
        """
        重新加载通知用户黑白名单
        """
        self.set_notice_white = set([])
        self.set_notice_black = set([])
        self.set_notice_white = load_to_set(
            self.file_notice_white, self.set_notice_white
        )
        self.set_notice_black = load_to_set(
            self.file_notice_black, self.set_notice_black
        )
        self.logit(None, f'set_notice_white: {len(self.set_notice_white)}')
        self.logit(None, f'set_notice_black: {len(self.set_notice_black)}')

    def __del__(self):
        pass

    def append2file(self, file_ot, s_content, header=''):
        """
        header: 表头
        s_content: 写入内容
        追加写入文件
        """
        b_ret = True
        s_msg = ''
        mode = 'a'

        dir_file_out = os.path.dirname(file_ot)
        if dir_file_out and (not os.path.exists(dir_file_out)):
            os.makedirs(dir_file_out)

        try:
            # 如果文件不存在，需要写入表头
            if not os.path.exists(file_ot):
                with open(file_ot, 'w') as fp:
                    fp.write(f'{header}\n')

            with open(file_ot, mode) as fp:
                # 写入内容
                fp.write(f'{s_content}\n')
        except Exception as e:
            b_ret = False
            s_msg = f'[save2file] An error occurred: {str(e)}'

        return (b_ret, s_msg)

    def status_append(self, s_op_type, s_url, s_msg, s_status):
        update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)
        s_content = f'{update_time},{s_op_type},{s_status},{s_url},{s_msg}'  # noqa
        self.append2file(
            file_ot=self.file_status,
            s_content=s_content,
            header=self.DEF_HEADER_STATUS
        )
        self.is_update = True

    def load_processed_url(self):
        if os.path.exists(self.file_status):
            with open(self.file_status, 'r') as fp:
                for line in fp:
                    s_line = line.strip()
                    if s_line:
                        fields = s_line.split(',')
                        if len(fields) < 4:
                            continue
                        if fields[2] not in [DEF_INTERACTION_OK, DEF_INTERACTION_IGNORE]:  # noqa
                            continue

        self.logit(None, f'load_ignored_url: {len(self.set_url_ignored)}')  # noqa
        self.logit(None, f'load_followed_user: {len(self.set_user_followed)}')  # noqa
        self.logit(None, f'load_liked_url: {len(self.set_url_liked)}')  # noqa
        self.logit(None, f'load_replied_url: {len(self.set_url_replied)}')  # noqa
        self.logit(None, f'load_retweeted_url: {len(self.set_url_retweeted)}')  # noqa

    def close(self):
        # 在有头浏览器模式 Debug 时，不退出浏览器，用于调试
        if DEF_USE_HEADLESS is False and DEF_DEBUG:
            pass
        else:
            if self.browser:
                try:
                    self.browser.quit()
                except Exception as e:  # noqa
                    # logger.info(f'[Close] Error: {e}')
                    pass

    def logit(self, func_name=None, s_info=None):
        s_text = f'{self.args.s_profile}'
        if func_name:
            s_text += f' [{func_name}]'
        if s_info:
            s_text += f' {s_info}'
        logger.info(s_text)

    def get_error_msg(self):
        """
        Something went wrong, but don’t fret — let’s give it another shot.
        出错了，别担心，让我们再试一次。
        """
        tab = self.browser.latest_tab
        ele_info = tab.ele('@@tag()=span@@class=css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3@@text()=Create your account', timeout=2)  # noqa
        if not isinstance(ele_info, NoneElement):
            s_info = ele_info.text
            self.logit(None, f'{s_info}')
            return s_info
        return None

    def click_back(self):
        tab = self.browser.latest_tab
        ele_btn = tab.ele(
            '@@tag()=button@@data-testid=app-bar-back', timeout=2)
        if not isinstance(ele_btn, NoneElement):
            if ele_btn.wait.clickable(timeout=5) is not False:
                # tab.actions.move_to(ele_btn).click()
                tab.actions.move_to(ele_btn).wait(1).click()
                tab.wait.doc_loaded()
                tab.wait(3)
                return True
        return False

    def click_display_post(self):
        tab = self.browser.latest_tab
        # 显示 xx 帖子
        lst_path = [
            '@@tag()=span@@class:css@@text():显示 ',
        ]
        ele_btn = self.inst_dp.get_ele_btn(tab, lst_path)
        if ele_btn is not NoneElement:
            self.logit(None, f'is_new_post: {ele_btn.text}')
            if ele_btn.wait.clickable(timeout=3):
                ele_btn.click(by_js=True)
                self.logit(None, 'get_new_post [Success]')
            tab.wait(2)

    def get_tweet_blks(self):
        tab = self.browser.latest_tab
        for i in range(1, 5):
            ele_blks_top = tab.eles(
                '@@tag()=div@@class=css-175oi2r@@data-testid=cellInnerDiv',
                timeout=3
            )
            if len(ele_blks_top) > 0:
                return ele_blks_top
            self.inst_x.wrong_retry()
            time.sleep(3)
        return []

    def is_new_post(self, ele_blk):
        """
        检查是否为新帖子，N小时内发的帖子视为新帖子

        参数:
            ele_blk: 帖子元素

            <time datetime="2025-11-12T03:00:02.000Z">2025年11月12日</time>

        返回:
            bool: True 表示为新帖子，False 表示为旧帖子

        # 2 分钟
        # 3 小时
        # 2月26日

        """
        ele_div_time = ele_blk.ele(
            '@@tag()=time@@datetime', timeout=2)
        if isinstance(ele_div_time, NoneElement):
            return False
        val_time = ele_div_time.attr('datetime')
        s_time = ele_div_time.text or ''
        s_time = s_time.strip()
        self.logit(None, f'create-time: {s_time}')

        if not val_time or val_time == '--':
            tab = self.browser.latest_tab
            tab.refresh()
            tab.wait.doc_loaded()
            return False

        # 判断是否是 n 小时内的帖子
        # val_time 格式为 "2025-11-12T03:00:02.000Z" (UTC)
        try:
            s_normalized = val_time.replace('Z', '+00:00')
            dt_post = datetime.fromisoformat(s_normalized)
            if dt_post.tzinfo is None:
                dt_post = dt_post.replace(tzinfo=timezone.utc)
            else:
                dt_post = dt_post.astimezone(timezone.utc)
            now_utc = datetime.now(timezone.utc)
            delta_hours = int((now_utc - dt_post).total_seconds() / 3600)
            return delta_hours <= WHITELIST_USER_NEW_POST_HOUR, val_time
        except (ValueError, AttributeError):
            return False, None

    def click_home(self):
        """
        Click home button
        """
        tab = self.browser.latest_tab
        ele_btn = tab.ele('@@tag()=a@@aria-label=X', timeout=2)
        if not isinstance(ele_btn, NoneElement):
            self.logit(None, 'Click home button')
            if ele_btn.wait.clickable(timeout=5) is not False:
                ele_btn.click()
                tab.wait(3)
                return True
        return False

    def get_notice_num(self):
        """
        Get notice number
        aria-label="提醒（6 条未读 提醒）"
        """
        tab = self.browser.latest_tab
        ele_a = tab.ele('@@tag()=a@@href=/notifications', timeout=2)
        if not isinstance(ele_a, NoneElement):
            s_text = ele_a.attr('aria-label')
            self.logit(None, f'Notice number: {s_text}')
            # 提取数字
            s_num = re.search(r'\d+', s_text)
            if s_num:
                s_num = s_num.group()
                return int(s_num)
        return 0

    def click_notice(self):
        """
        Click notice button
        """
        tab = self.browser.latest_tab
        ele_btn = tab.ele('@@tag()=a@@href=/notifications', timeout=2)
        if not isinstance(ele_btn, NoneElement):
            self.logit(None, 'Click notice button')
            if ele_btn.wait.clickable(timeout=5) is not False:
                ele_btn.click()
                tab.wait(3)
                return True
        return False

    def get_notice_users(self):
        """
        # noqa
        Get notice users

        M11.996 2c-4.062 0-7.49 3.021-7.999 7.051L2.866 18H7.1c.463 2.282 2.481 4 4.9 4s4.437-1.718 4.9-4h4.236l-1.143-8.958C19.48 5.017 16.054 2 11.996 2zM9.171 18h5.658c-.412 1.165-1.523 2-2.829 2s-2.417-.835-2.829-2z
        """
        lst_users = []
        tab = self.browser.latest_tab
        ele_blk_notice = None
        ele_blks = tab.eles('@@tag()=article@@role=article', timeout=2)
        for ele_blk in ele_blks:
            ele_notice = ele_blk.ele('@@tag()=path@@d=M11.996 2c-4.062 0-7.49 3.021-7.999 7.051L2.866 18H7.1c.463 2.282 2.481 4 4.9 4s4.437-1.718 4.9-4h4.236l-1.143-8.958C19.48 5.017 16.054 2 11.996 2zM9.171 18h5.658c-.412 1.165-1.523 2-2.829 2s-2.417-.835-2.829-2z', timeout=2) # noqa
            if not isinstance(ele_notice, NoneElement):
                ele_blk_notice = ele_blk
                break

        if ele_blk_notice:
            ele_ul = ele_blk_notice.ele('@@tag()=ul@@role=list', timeout=2)
            if not isinstance(ele_ul, NoneElement):
                ele_a_lst = ele_ul.eles('@@tag()=a@@href:/', timeout=2)
                for ele_a in ele_a_lst:
                    s_href = ele_a.attr('href')
                    s_user = s_href.split('/')[-1]
                    # self.logit(None, f'Notice user: {s_user}')
                    lst_users.append(s_user)

        return lst_users

    def get_new_notice_users(self, lst_pre, lst_cur):
        """
        Get newly inserted notice users at the head of current list.

        lst_pre: ['a1', 'a2', 'a3', 'a4']
        lst_cur: ['a5', 'a1', 'a2', 'a3']
        return: ['a5']

        lst_pre: ['a1', 'a2', 'a3', 'a4']
        lst_cur: ['a4', 'a1', 'a2', 'a3']
        return: ['a4']
        """
        if not lst_cur:
            return []

        if not lst_pre:
            return lst_cur

        # n_pre_len = len(lst_pre)
        dic_pre_index = {s_user: idx for idx, s_user in enumerate(lst_pre)}

        for cur_offset in range(len(lst_cur)):
            lst_suffix = lst_cur[cur_offset:]
            idx_pre = -1
            is_subsequence = True

            for s_user in lst_suffix:
                if s_user not in dic_pre_index:
                    is_subsequence = False
                    break
                if dic_pre_index[s_user] <= idx_pre:
                    is_subsequence = False
                    break
                idx_pre = dic_pre_index[s_user]

            if is_subsequence:
                return lst_cur[:cur_offset]

        return lst_cur

    def monitor_notice_users(self):
        """
        Ding notice users
        """
        tab = self.browser.latest_tab
        # 如果当前不在通知页面或者 X 域名下，强制跳转一次
        if 'x.com/notifications' not in tab.url:
            logger.info("Navigate to notifications page...")
            tab.get('https://x.com/notifications')
            tab.wait(3)

        if self.args.debug:
            pdb.set_trace()

        # 定期回收超时任务（10分钟未更新的任务）
        self.db.recover_stale_tasks(timeout_seconds=600)
        # 定期清理 3 天之前的已完成/失败任务
        self.db.cleanup_done_tasks(days=3)
        
        self.reload_notice_user_lists()

        n_notice = self.get_notice_num()
        if n_notice <= 0:
            pass
            # return

        self.click_notice()
        tab = self.browser.latest_tab
        tab.wait.doc_loaded()

        lst_users_cur = self.get_notice_users()
        if not lst_users_cur:
            return

        s_pre = ' '.join(self.lst_users_pre)
        s_cur = ' '.join(lst_users_cur)
        self.logit(None, f's_pre: {s_pre}')
        self.logit(None, f's_cur: {s_cur}')

        lst_new_users = self.get_new_notice_users(
            self.lst_users_pre, lst_users_cur)

        s_new = ' '.join(lst_new_users)
        self.logit(None, f's_new: {s_new}')

        self.lst_users_pre = lst_users_cur

        # 黑名单：忽略；白名单/其他均处理，钉钉路由不同
        lst_to_process = []
        for s_user in lst_new_users:
            if s_user in self.set_notice_black:
                self.logit(None, f'notice user in black list, skip: {s_user}')
                continue
            lst_to_process.append(s_user)

        s_todo = ' '.join(lst_to_process)
        self.logit(None, f's_to_process (non-black): {s_todo}')

        if not lst_to_process:
            return

        lst_alert = [u for u in lst_to_process if u in self.set_notice_white]
        lst_silent = [
            u for u in lst_to_process if u not in self.set_notice_white
        ]

        if lst_alert:
            s_info = ''.join(f'{u}\n' for u in lst_alert)
            d_cont = {
                'title': (
                    f'Notice Users [ALERT]: {n_notice} [{lst_alert[0]}]'
                ),
                'text': s_info,
            }
            notify_msg_markdown(d_cont, DEF_DING_TOKEN_ALERT, 'alert')

        if lst_silent:
            s_info = ''.join(f'{u}\n' for u in lst_silent)
            d_cont = {
                'title': (
                    f'Notice Users [SILENT]: {n_notice} [{lst_silent[0]}]'
                ),
                'text': s_info,
            }
            notify_msg_markdown(d_cont, DEF_DING_TOKEN_SILENT, 'silent')

        # 将发现的新通知用户存入数据库，并推送到持久化队列
        for s_user in lst_to_process:
            # notice_time 取当前时间（UTC）作为检测到通知的时间
            notice_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            
            # 这里先不向主表写详细信息（因为主进程没有打开用户主页），
            # 详细信息落库逻辑在 Process B (User Worker) 访问用户主页时完成。
            # 这里仅记录“发现通知”
            
            # 推送到数据库队列，白名单优先
            priority = 10 if s_user in self.set_notice_white else 0
            self.db.push_user_queue(s_user, priority=priority)
            self.logit(None, f'Pushed user to db queue: {s_user} (priority={priority})')

    def proc_all_notice_users(self, lst_users):
        """
        Proc notice user（白名单优先，两组内各自 reversed）。
        白名单：拉取推文并调用大模型生成候选回复，TG/钉钉含 LLM 段落。
        非白名单：同样发 TG/钉钉，但不调用大模型，内容不含 LLM 回复。
        """
        lst_white = [u for u in lst_users if u in self.set_notice_white]
        lst_rest = [u for u in lst_users if u not in self.set_notice_white]
        lst_ordered = list(reversed(lst_white)) + list(reversed(lst_rest))
        for s_user in lst_ordered:
            is_white = s_user in self.set_notice_white
            self.proc_one_notice_user(s_user, skip_llm=not is_white)

            if is_white:
                if not self.lst_candidate_replies:
                    continue
            elif not self.tw_url:
                continue

            s_tg_ch = 'alert' if is_white else 'silent'
            if is_bot_telegram():
                notify_telegram_llm_replies(
                    s_user,
                    self.nickname,
                    self.tw_url,
                    self.tw_text,
                    self.lst_candidate_replies,
                    s_tg_ch,
                    n_following=self.n_following,
                    n_followers=self.n_followers,
                )
                continue

            s_fo = format_follow_count_cn(self.n_following)
            s_fe = format_follow_count_cn(self.n_followers)
            s_md = (
                f"### 👤 用户\n{s_user} ({self.nickname})\n"
                f"### 📊 关注 / 粉丝\n"
                f"{s_fo} / {s_fe}\n\n"
                f"### 🔗 推文链接\n{self.tw_url}\n\n"
                f"### 🧾 原帖内容\n> {self.tw_text[:100]} ...\n"
            )
            if self.lst_candidate_replies:
                s_reply_text = '\n'.join(
                    f'- {item["style"]}: {item["reply"]}'
                    for item in self.lst_candidate_replies
                )
                s_md += f"\n\n### 🤖 LLM 回复\n{s_reply_text}"
            s_title_tail = (
                'LLM Reply' if self.lst_candidate_replies else 'Notice'
            )
            s_token = (
                DEF_DING_TOKEN_ALERT
                if is_white
                else DEF_DING_TOKEN_SILENT
            )
            d_cont = {
                'title': (
                    f'[{s_user} ({self.nickname}) '
                    f'粉{s_fe}] {s_title_tail}'
                ),
                'text': s_md
            }
            notify_msg_markdown(d_cont, s_token, s_tg_ch)

        return True

    def get_follow_num(self):
        """
        Get follow number（千分位逗号、「万」「亿」见 parse_follow_count_text）。
        任一侧为 -1 表示该侧获取失败（DOM 不符、文案无法解析等）。
        """
        n_following = -1
        n_followers = -1

        tab = self.browser.latest_tab
        ele_follow_lst = tab.eles('@@tag()=a@@href:follow', timeout=2)
        if len(ele_follow_lst) >= 2:
            try:
                n_following = parse_follow_count_text(ele_follow_lst[0].text)
                n_followers = parse_follow_count_text(ele_follow_lst[1].text)
            except Exception as e:
                self.logit(None, f'Error getting follow number: {e}')

        return (n_following, n_followers)

    def get_user_desc(self):
        """
        Get user description.
        """
        tab = self.browser.latest_tab
        ele_bio = tab.ele('@@tag()=div@@data-testid=UserDescription', timeout=1)
        if not isinstance(ele_bio, NoneElement):
            return ele_bio.text
        return ''

    def proc_one_notice_user(self, s_user, skip_llm=False):
        """
        Proc notice user。skip_llm=True 时仅抓取推文上下文，不调用大模型。
        """
        self.reset_vals()
        self.logit(None, f'Proc notice user: {s_user}')
        # self.proc_ad_user(s_user, s_user, s_src='notice_user')

        user_url = f'https://x.com/{s_user}'  # noqa
        # tab = self.browser.new_tab(user_url)
        tab = self.browser.latest_tab
        tab.get(user_url)
        tab.wait.doc_loaded()
        tab.wait(5)

        self.user_desc = self.get_user_desc()
        # self.logit(None, f'user_desc: {self.user_desc}')

        ele_blks_top = self.get_tweet_blks()
        n_blks_top = len(ele_blks_top)
        self.logit(None, f'len(ele_blks_top)={n_blks_top}')
        if not ele_blks_top:
            self.inst_x.wrong_retry()
            return False

        self.n_following, self.n_followers = self.get_follow_num()
        self.logit(
            None,
            f'n_following: {self.n_following}, '
            f'n_followers: {self.n_followers}',
        )

        for i in range(n_blks_top):
            if self.args.debug:
                pdb.set_trace()
            ele_blks_top = self.get_tweet_blks()
            if i >= len(ele_blks_top):
                break
            ele_blk = ele_blks_top[i]

            ele_user_nickname = ele_blk.ele(
                '@@tag()=div@@data-testid=User-Name', timeout=3
            )
            if not isinstance(ele_user_nickname, NoneElement):
                # XXXName\n@chairbtc\n·\n8分钟
                self.nickname = ele_user_nickname.text.split('\n')[0]
                self.logit(None, f'user_nickname: {self.nickname}')
            else:
                self.nickname = ''
                self.logit(None, 'user_nickname is not found')

            ele_tweet_url = ele_blk.ele(
                '@@tag()=a@@href:status@@dir=ltr', timeout=3
            )
            if not isinstance(ele_tweet_url, NoneElement):
                tweet_url = ele_tweet_url.attr('href')
                self.logit(None, f'tweet_url: {tweet_url}')
                try:
                    x_user = tweet_url.split('/')[3]
                    if self.i_xuser == x_user:
                        continue
                except:  # noqa
                    continue

                if tweet_url in self.set_url_notice:
                    self.logit(None, 'Already processed before, skip ...')
                    continue

                if tweet_url in self.set_url_ignored:
                    self.logit(None, 'Already ignored before, skip ...')
                    continue

                b_is_new_post, tweet_publish_time = self.is_new_post(ele_blk)
                if (not b_is_new_post):
                    self.logit(None, 'Not a new post, skip')
                    continue
                # tab.actions.move_to(ele_blk).click()
                if ele_tweet_url.wait.clickable(timeout=5) is not False:
                    ele_tweet_url.click()
                    tab.wait.doc_loaded()
                    tab.wait(3)
                if tab.url == 'https://x.com/home':
                    self.logit(
                        None,
                        'tab.url is home, failed to click tweet url ...')
                    continue

                self.tw_url = tweet_url
                # 在抓取阶段只获取文本，不调用 LLM
                self.get_tweet_candidates_reply(skip_llm=True)
                
                # 保存用户信息 (含历史记录自动触发)
                user_data = {
                    'username': s_user,
                    'user_url': user_url,
                    'nickname': self.nickname,
                    'following_count': self.n_following,
                    'follower_count': self.n_followers,
                    'description': self.user_desc,
                    'last_notice_time': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                }
                self.db.add_user(user_data)

                # 保存推文到数据表
                tweet_data_db = {
                    'tweet_url': tweet_url,
                    'content': self.tw_text,
                    'tweet_publish_time': tweet_publish_time.replace('T', ' ').replace('Z', '') if tweet_publish_time else None
                }
                self.db.add_tweet(tweet_data_db)

                # 推送到推文生产队列，如果是白名单则高优先级
                is_white = not skip_llm
                priority = 10 if is_white else 0
                tweet_data_queue = {
                    's_user': s_user,
                    'nickname': self.nickname,
                    'tw_url': self.tw_url,
                    'tw_text': self.tw_text,
                    'n_following': self.n_following,
                    'n_followers': self.n_followers,
                    'is_white': is_white
                }
                self.db.push_tweet_queue(tweet_data_queue, priority=priority)
                self.logit(None, f'Pushed tweet to db queue: {tweet_url} (priority={priority})')

                tab.wait(2)
                self.click_back()
                tab.wait(2)

                self.set_url_notice.add(tweet_url)
                break

        return True

    def get_article_text(self):
        """
        Get article text
        """
        s_title = ''
        s_content = ''

        tab = self.browser.latest_tab
        ele_article_blk = tab.ele(
            '@@tag()=article@@data-testid=tweet', timeout=3
        )
        if isinstance(ele_article_blk, NoneElement):
            # self.logit(None, 'article_text is not found')
            return s_title, s_content

        ele_title = ele_article_blk.ele(
            '@@tag()=div@@data-testid=twitter-article-title', timeout=3
        )
        if not isinstance(ele_title, NoneElement):
            s_title = ele_title.text

        ele_content = ele_article_blk.ele(
            '@@tag()=div@@data-testid=twitterArticleRichTextView', timeout=3
        )
        if not isinstance(ele_content, NoneElement):
            s_content = ele_content.text

        return s_title, s_content

    def get_short_tweet_text(self):
        """
        Get short tweet text
        """
        s_content = ''

        tab = self.browser.latest_tab
        ele_tweet_text = tab.ele(
            '@@tag()=div@@data-testid=tweetText', timeout=3
        )
        if not isinstance(ele_tweet_text, NoneElement):
            s_content = ele_tweet_text.text

        return s_content

    def get_tweet_text(self):
        """
        Get tweet text
        """
        s_title = ''
        s_content = ''

        s_content = self.get_short_tweet_text()
        if not s_content:
            s_title, s_content = self.get_article_text()

        return s_title, s_content

    def get_tweet_candidates_reply(self, skip_llm=False):
        """
        对当前帖子一次 LLM 请求生成 3 种风格候选回复：友好风格、表示赞同、幽默风趣。
        skip_llm=True 时只填充 tw_text，不请求大模型。
        """
        self.tw_text = ''
        self.lst_candidate_replies = []

        s_title, s_tweet_text = self.get_tweet_text()
        if not s_tweet_text:
            self.logit(None, 'tweet_text is not found')
            self.click_back()
            return False

        s_tweet_text = s_tweet_text.replace('\n', ' ')
        self.logit(None, f'tweet_text: {s_tweet_text[:50]} ...')  # noqa

        if s_title:
            s_tweet_text = f'【标题】{s_title}\n【正文】{s_tweet_text}'

        if skip_llm:
            self.tw_text = s_tweet_text.strip()
            self.lst_candidate_replies = []
            self.logit(None, 'skip_llm: 仅通知，不生成候选回复')
            return True

        lst_styles = (
            ("友好风格", "语气友善、亲切自然，积极正面，让对方感到被尊重。"),
            ("表示赞同", "明确表达对推文观点的认同与支持，可简短呼应原文要点。"),
            ("幽默风趣", "轻松俏皮、适度幽默，不失礼貌，避免冒犯或低俗。"),
        )
        s_styles_block = ''.join(
            f"- 「{name}」：{desc}\n" for name, desc in lst_styles
        )

        s_prompt = (
            "# 【功能】\n"
            "阅读给定推文，一次性输出 3 条不同风格的回复候选。\n"
            "\n"
            "# 【重要：语言要求】\n"
            "必须使用与原推文相同的语言撰写每条回复！原推文是英文就用英文，"
            "原推文是中文就用中文。\n"
            "\n"
            "# 【三种风格说明】\n"
            f"{s_styles_block}"
            "\n"
            "# 【通用要求】\n"
            "每条回复要简短；与推文相关；单条字数控制在 70 字以内；"
            "每条回复字符串内不要换行；不要输出与 JSON 无关的说明文字。\n"
            "\n"
            "# 【输出格式】\n"
            "仅输出一个 JSON 对象，三个键名必须为："
            "\"友好风格\"、\"表示赞同\"、\"幽默风趣\"，值为对应回复正文。\n"
            "示例："
            '{"友好风格":"...","表示赞同":"...","幽默风趣":"..."}\n'
            "\n"
            "# 【参考推文内容如下】\n"
            f"{s_tweet_text}"
        )

        self.logit(None, 'generate 3 candidate replies (single request) ...')
        try:
            s_raw = gene_by_llm(s_prompt)
        except Exception as e:
            self.logit(None, f'Error calling gene_by_llm: {e}')
            self.lst_candidate_replies = []
            return False

        if not s_raw:
            self.logit(None, 'gene_by_llm returned empty')
            self.lst_candidate_replies = []
            return False

        s_trim = s_raw.strip()
        m_fence = re.match(
            r'^```(?:json)?\s*\n?(.*?)\n?```\s*$',
            s_trim,
            re.DOTALL | re.IGNORECASE,
        )
        if m_fence:
            s_trim = m_fence.group(1).strip()

        dic = None
        try:
            dic = json.loads(s_trim)
        except json.JSONDecodeError:
            i0, i1 = s_trim.find('{'), s_trim.rfind('}')
            if i0 >= 0 and i1 > i0:
                try:
                    dic = json.loads(s_trim[i0:i1 + 1])
                except json.JSONDecodeError:
                    pass
        if not isinstance(dic, dict):
            self.logit(None, f'failed to parse JSON from LLM: {s_raw[:200]}')
            self.lst_candidate_replies = []
            return False

        self.lst_candidate_replies = []
        for s_name, _ in lst_styles:
            s_reply = dic.get(s_name, '')
            if not isinstance(s_reply, str):
                s_reply = str(s_reply) if s_reply is not None else ''
            s_reply = s_reply.replace('\n', ' ').strip()
            self.lst_candidate_replies.append(
                {'style': s_name, 'reply': s_reply}
            )

        for item in self.lst_candidate_replies:
            preview = (item['reply'] or '')[:100]
            self.logit(
                None,
                f"candidate [{item['style']}]: {preview}"
                + ('...' if len(item['reply'] or '') > 100 else '')
            )
        self.tw_text = s_tweet_text.strip()

        return True

    def xnotice_run(self):
        self.browser = self.inst_dp.get_browser(self.args.s_profile)

        self.inst_x.status_load()
        self.inst_x.set_browser(self.browser)

        idx_xuser = get_index_from_header(DEF_HEADER_ACCOUNT, 'x_username')
        self.i_xuser = self.inst_x.dic_account[self.args.s_profile][idx_xuser]

        if self.args.no_auto_vpn:
            logger.info(f'{self.args.s_profile} Use Current VPN')  # noqa
        elif self.args.vpn_manual:
            pass
        else:
            if self.args.vpn is None:
                idx_vpn = get_index_from_header(DEF_HEADER_ACCOUNT, 'proxy')
                if self.args.s_profile in self.inst_x.dic_account:
                    s_vpn = self.inst_x.dic_account[
                        self.args.s_profile
                    ][idx_vpn]
                else:
                    logger.info(f'{self.args.s_profile} is not in self.inst_x.dic_account [ERROR]')  # noqa
                    sys.exit(0)
            else:
                s_vpn = self.args.vpn

            if self.inst_dp.set_vpn(s_vpn) is False:
                return False

        if self.inst_dp.check_connection() is False:
            self.logit(None, 'Network connection check failed, return ...')
            return False

        if self.args.reset:
            input(
                'Remove the cookie, delete token from status.csv, '
                'Press Enter to continue ...'
            )

        num_visit_pre = self.inst_x.get_pre_num_visit()
        s_status = self.inst_x.get_x_status()
        if num_visit_pre >= 5 and s_status == self.inst_x.DEF_STATUS_EXCEED_ATTEMPT:  # noqa
            self.logit('twitter_run', 'Too many wrong visits, return ...')
            s_msg = f'[{self.args.s_profile}]发生了错误。你已超过允许尝试次数，请稍后再试。' # noqa
            notify_msg_text(s_msg, DEF_DING_TOKEN)
            return True

        # 根据配置决定是否执行扩展检测
        if hasattr(self.args, 'do_extension_check') and self.args.do_extension_check:
            # 使用配置的扩展检测参数
            if hasattr(self.args, 'extension_id') and self.args.extension_id:
                # 使用自定义扩展ID
                lst_extension_id = [
                    (s_id, 'custom') for s_id in self.args.extension_id.split(',')
                ]
            else:
                # 使用默认扩展
                lst_extension_id = [
                    (EXTENSION_ID_YESCAPTCHA, 'yescaptcha'),
                    (EXTENSION_ID_CAPMONSTER, 'capmonster'),
                ]

            # 使用配置的重试次数
            max_try = getattr(self.args, 'extension_check_max_try', 1)
            self.inst_dp.check_extension(
                n_max_try=max_try, lst_extension_id=lst_extension_id
            )
        else:
            logger.info('扩展检测已禁用，跳过扩展检查')

        if self.inst_dp.init_capmonster() is False:
            return False

        if self.inst_dp.init_yescaptcha() is False:
            return False

        if self.args.debug:
            self.logit(None, 'Debug mode, pause ...')
            pdb.set_trace()

        self.inst_x.twitter_run()

        if self.args.debug:
            self.logit(None, 'Debug mode, pause ...')
            pdb.set_trace()

        if self.args.monitor_notice_users:
            while True:
                self.monitor_notice_users()
                time.sleep(60)

        s_x_status = self.inst_x.get_x_status()
        if not s_x_status:
            pass
        elif s_x_status != DEF_STATUS_OK:
            self.logit(None, 'X Account is suspended, return ...')
            return True

        if self.args.manual_exit and self.args.headless is False:
            s_msg = 'Press any key to exit! ⚠️'  # noqa
            self.logit('xnotice_run', f'[manual_exit={self.args.manual_exit}] {s_msg}')  # noqa
            input(s_msg)

        self.logit('xnotice_run', 'Finished!')
        self.close()

        return True


def send_msg(x_notice, lst_success):
    if is_text_notify_configured() and len(lst_success) > 0:
        s_info = ''
        for s_profile in lst_success:
            lst_status = None
            if s_profile in x_notice.inst_x.dic_status:
                lst_status = x_notice.inst_x.dic_status[s_profile]

            if lst_status is None:
                lst_status = [s_profile, -1]

            s_info += '- {},{}\n'.format(
                s_profile,
                lst_status[IDx_wool_DATE],
            )
        d_cont = {
            'title': 'Daily Check-In Finished! [xnotice]',
            'text': (
                'Daily Check-In [xnotice]\n'
                '- account,op_date\n'
                '{}\n'
                .format(s_info)
            )
        }
        notify_msg_markdown(d_cont, DEF_DING_TOKEN, 'default')


def user_worker(args):
    """
    子进程 B：消费用户信息，从数据库队列抓取推文。
    """
    logger.info("User Worker (Process B) started.")
    x_notice = XNotice()
    x_notice.set_args(args)
    db = DBManager()

    # 初始化浏览器逻辑
    x_notice.browser = x_notice.inst_dp.get_browser(args.s_profile)
    x_notice.inst_x.status_load()
    x_notice.inst_x.set_browser(x_notice.browser)
    
    while True:
        try:
            # 从数据库队列获取任务
            task = db.pop_user_queue()
            if not task:
                time.sleep(3)
                continue

            username = task['username']
            logger.info(f"User Worker: processing user {username}")
            
            # 抓取推文逻辑
            is_white = username in x_notice.set_notice_white
            x_notice.proc_one_notice_user(username, skip_llm=not is_white)
            
            # 标记任务完成
            db.finish_task('queue_users', task['id'])
            
        except Exception as e:
            logger.error(f"User Worker error: {e}")
            time.sleep(5)
    
    x_notice.close()


def reply_worker():
    """
    子进程 C：消费推文信息，调用 LLM 并分发通知。
    """
    logger.info("Reply Worker (Process C) started.")
    db = DBManager()
    while True:
        try:
            # 从数据库队列获取任务
            tweet_data = db.pop_tweet_queue()
            if not tweet_data:
                time.sleep(3)
                continue
            
            logger.info(f"Reply Worker: processing tweet {tweet_data['tweet_url']}")
            
            candidate_replies = []
            if tweet_data['is_white']:
                from xnotice import XNotice
                xn = XNotice() 
                xn.tw_text = tweet_data['content']
                if xn.get_tweet_candidates_reply(skip_llm=False):
                    candidate_replies = xn.lst_candidate_replies
            
            # 发送通知
            s_tg_ch = 'alert' if tweet_data['is_white'] else 'silent'
            if is_bot_telegram():
                notify_telegram_llm_replies(
                    tweet_data['username'],
                    tweet_data['nickname'],
                    tweet_data['tweet_url'],
                    tweet_data['content'],
                    candidate_replies,
                    s_tg_ch,
                    n_following=tweet_data['following_count'],
                    n_followers=tweet_data['followers_count'],
                )
            else:
                s_fo = format_follow_count_cn(tweet_data['following_count'])
                s_fe = format_follow_count_cn(tweet_data['followers_count'])
                s_md = (
                    f"### 👤 用户\n{tweet_data['username']} ({tweet_data['nickname']})\n"
                    f"### 📊 关注 / 粉丝\n"
                    f"{s_fo} / {s_fe}\n\n"
                    f"### 🔗 推文链接\n{tweet_data['tweet_url']}\n\n"
                    f"### 🧾 原帖内容\n> {tweet_data['content'][:100]} ...\n"
                )
                if candidate_replies:
                    s_reply_text = '\n'.join(
                        f'- {item["style"]}: {item["reply"]}'
                        for item in candidate_replies
                    )
                    s_md += f"\n\n### 🤖 LLM 回复\n{s_reply_text}"
                
                s_title_tail = 'LLM Reply' if candidate_replies else 'Notice'
                s_token = DEF_DING_TOKEN_ALERT if tweet_data['is_white'] else DEF_DING_TOKEN_SILENT
                d_cont = {
                    'title': f"[{tweet_data['username']} ({tweet_data['nickname']}) 粉{s_fe}] {s_title_tail}",
                    'text': s_md
                }
                notify_msg_markdown(d_cont, s_token, s_tg_ch)
            
            # 记录回复归档并更新对列状态
            reply_record = {
                'tweet_url': tweet_data['tweet_url'],
                'reply_username': tweet_data['username'],
                'reply_content': 'Bot Notification Sent', # 目前仅为通知摘要
                'reply_time': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                'llm_replies_json': json.dumps(candidate_replies),
                'llm_generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            }
            db.add_reply(reply_record)
            db.finish_task('queue_tweets', tweet_data['id'])
            
        except Exception as e:
            logger.error(f"Reply Worker error: {e}")
            time.sleep(5)


def show_msg(args):
    current_directory = os.getcwd()
    FILE_LOG = f'{current_directory}/{FILENAME_LOG}'
    FILE_STATUS = f'{current_directory}/{DEF_PATH_DATA_STATUS}/status.csv'

    print('########################################')
    print('The program is running')
    print(f'headless={args.headless}')
    print('Location of the running result file:')
    print(f'{FILE_STATUS}')
    print('The running process is in the log file:')
    print(f'{FILE_LOG}')
    print('########################################')


def main(args):
    if args.sleep_sec_at_start > 0:
        logger.info(f'Sleep {args.sleep_sec_at_start} seconds at start !!!')  # noqa
        time.sleep(args.sleep_sec_at_start)

    if DEL_PROFILE_DIR and os.path.exists(DEF_PATH_USER_DATA):
        logger.info(f'Delete {DEF_PATH_USER_DATA} ...')
        shutil.rmtree(DEF_PATH_USER_DATA)
        logger.info(f'Directory {DEF_PATH_USER_DATA} is deleted')  # noqa

    x_notice = XNotice()

    if args.debug:
        pdb.set_trace()

    # 如果指定了 --init_db，则初始化并退出
    if getattr(args, 'init_db', False):
        logger.info("Initializing database...")
        x_notice.db.init_db()
        return True

    # 如果是独立 Worker 模式，则不启动主循环
    if getattr(args, 'run_user_worker', False):
        # 确定 profiles 以获取默认 s_profile
        if len(args.profile) > 0:
            profiles = args.profile.split(',')
        else:
            profiles = list(x_notice.inst_x.dic_account.keys())
        if profiles:
            args.s_profile = profiles[0]

        logger.info(f"Starting as standalone User Worker (Process B) with profile: {args.s_profile}")
        user_worker(args)
        return True
    
    if getattr(args, 'run_reply_worker', False):
        logger.info("Starting as standalone Reply Worker (Process C)...")
        reply_worker()
        return True

    # 确定 profiles 列表
    if len(args.profile) > 0:
        items = args.profile.split(',')
    else:
        # 从配置文件里获取钱包名称列表
        items = list(x_notice.inst_x.dic_account.keys())

    profiles = copy.deepcopy(items)
    if not profiles:
        logger.error("No profiles found. Exiting.")
        return False
        
    # 为子进程/主采集进程设置默认的 s_profile
    if not hasattr(args, 's_profile') or not args.s_profile:
        args.s_profile = profiles[0]

    # 如果指定了 monitor 模式，则仅运行采集器循环
    if args.monitor_notice_users:
        logger.info(f"Starting as standalone Collector (Process A) with profile: {args.s_profile}")
        # 首先设置参数，确保 inst_dp 等组件被正确初始化
        x_notice.set_args(args)
        # 在进入循环前初始化浏览器
        x_notice.browser = x_notice.inst_dp.get_browser(args.s_profile)
        while True:
            # 循环中保持参数同步
            x_notice.set_args(args)
            x_notice.monitor_notice_users()
            time.sleep(60)
        return True

    # 如果没有指定任何独立模式，启动原有的所有并发逻辑（保持向后兼容）
    # 启动工作进程（Process B & Process C）
    p_user = multiprocessing.Process(
        target=user_worker, args=(args,), name="Process-B"
    )
    p_reply = multiprocessing.Process(
        target=reply_worker, name="Process-C"
    )
    p_user.daemon = True
    p_reply.daemon = True
    p_user.start()
    p_reply.start()
    logger.info(f"Database-backed Multiprocessing workers started with default profile: {args.s_profile}")

    # 每次随机取一个出来，并从原列表中删除，直到原列表为空
    total = len(profiles)
    n = 0

    lst_success = []

    def get_sec_wait(lst_status):
        n_sec_wait = 0
        if lst_status:
            avail_time = lst_status[IDX_UPDATE]
            if avail_time:
                n_sec_wait = time_difference(avail_time) + 1

        return n_sec_wait

    # 将已完成的剔除掉
    x_notice.inst_x.status_load()
    # 从后向前遍历列表的索引
    for i in range(len(profiles) - 1, -1, -1):
        s_profile = profiles[i]
        if s_profile in x_notice.inst_x.dic_status:
            lst_status = x_notice.inst_x.dic_status[s_profile]
        else:
            continue
    logger.info('#'*40)

    percent = math.floor((n / total) * 100)
    logger.info(f'Progress: {percent}% [{n}/{total}]')  # noqa

    while profiles:
        n += 1
        logger.info('#'*40)
        s_profile = random.choice(profiles)
        percent = math.floor((n / total) * 100)
        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile}]')  # noqa
        profiles.remove(s_profile)

        args.s_profile = s_profile

        if s_profile not in x_notice.inst_x.dic_account:
            logger.info(f'{s_profile} is not in account conf [ERROR]')
            sys.exit(0)

        # 如果出现异常(与页面的连接已断开)，增加重试
        max_try_except = 3
        for j in range(1, max_try_except+1):
            try:
                if j > 1:
                    logger.info(f'⚠️ 正在重试，当前是第{j}次执行，最多尝试{max_try_except}次 [{s_profile}]')  # noqa

                x_notice.set_args(args)

                x_notice.inst_dp.set_args(args)
                x_notice.inst_x.set_args(args)

                x_notice.inst_x.set_vpn_manual(s_profile, DEF_DING_TOKEN)

                if s_profile in x_notice.inst_x.dic_status:
                    lst_status = x_notice.inst_x.dic_status[s_profile]
                else:
                    lst_status = None

                if x_notice.xnotice_run():
                    lst_success.append(s_profile)
                    break

            except Exception as e:
                logger.info(f'[{s_profile}] An error occurred: {str(e)}')
                # x_notice.close()
                if j < max_try_except:
                    time.sleep(5)

        if x_notice.inst_x.is_update is False:
            continue

        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile} Finish]')

        if len(profiles) > 0:
            sleep_time = random.randint(args.sleep_sec_min, args.sleep_sec_max)
            if sleep_time > 60:
                logger.info('sleep {} minutes ...'.format(int(sleep_time/60)))
            else:
                logger.info('sleep {} seconds ...'.format(int(sleep_time)))
            time.sleep(sleep_time)

    send_msg(x_notice, lst_success)


if __name__ == '__main__':
    """
    每次随机取一个出来，并从原列表中删除，直到原列表为空
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--loop_interval', required=False, default=60, type=int,
        help='[默认为 60] 执行完一轮 sleep 的时长(单位是秒)，如果是0，则不循环，只执行一次'
    )
    parser.add_argument(
        '--sleep_sec_min', required=False, default=3, type=int,
        help='[默认为 3] 每个账号执行完 sleep 的最小时长(单位是秒)'
    )
    parser.add_argument(
        '--sleep_sec_max', required=False, default=10, type=int,
        help='[默认为 10] 每个账号执行完 sleep 的最大时长(单位是秒)'
    )
    parser.add_argument(
        '--sleep_sec_at_start', required=False, default=0, type=int,
        help='[默认为 0] 在启动后先 sleep 的时长(单位是秒)'
    )
    parser.add_argument(
        '--profile', required=False, default='',
        help='按指定的 profile 执行，多个用英文逗号分隔'
    )
    parser.add_argument(
        '--auto_like', required=False, action='store_true',
        help='Like a post after login automatically'
    )
    parser.add_argument(
        '--force', required=False, action='store_true',
        help='Run ignore status'
    )
    parser.add_argument(
        '--manual_exit', required=False, action='store_true',
        help='Close chrome manual'
    )
    parser.add_argument(
        '--vpn', required=False, default=None,
        help='Set vpn, default is None'
    )
    parser.add_argument(
        '--no_auto_vpn', required=False, action='store_true',
        default=True,
        help='Ignore Clash Verge API'
    )
    # 手动设置 VPN，默认为 False
    parser.add_argument(
        '--vpn_manual', required=False, action='store_true',
        help='Set vpn manually, default is False'
    )
    # 添加 --headless 参数
    parser.add_argument(
        '--headless',
        action='store_true',   # 默认为 False，传入时为 True
        default=False,         # 设置默认值
        help='Enable headless mode'
    )
    # 添加 --no-headless 参数
    parser.add_argument(
        '--no-headless',
        action='store_false',
        dest='headless',  # 指定与 --headless 参数共享同一个变量
        help='Disable headless mode'
    )

    parser.add_argument(
        '--water', required=False, action='store_true',
        help='Water by url, like '
             'https://x.com/xuser/status/1896000000000000000'
    )

    parser.add_argument(
        '--ad_user', required=False, action='store_true',
        help='Water by ad_user file'
    )

    # 增加 --reset 参数，用于重置账号
    parser.add_argument(
        '--reset', required=False, action='store_true',
        help='Reset account status'
    )

    parser.add_argument(
        '--max_interactions', required=False, default=10, type=int,
        help='[默认为 10] 最大互动次数，控制每个账号的互动轮数'
    )

    parser.add_argument(
        '--init_db', required=False, action='store_true',
        help='Initialize database tables'
    )

    # 扩展检测相关参数
    parser.add_argument(
        '--do_extension_check', required=False, action='store_true',
        help='Do extension check'
    )
    parser.add_argument(
        '--extension_check_max_try', required=False, default=3, type=int,
        help='[默认为 3] 扩展检测最大重试次数'
    )
    parser.add_argument(
        '--extension_id', required=False, default='',
        help='自定义扩展ID，多个用逗号分隔，留空则使用默认扩展'
    )

    parser.add_argument(
        '--monitor_notice_users', required=False, action='store_true',
        help='Run as Collector: Monitor notice users and push to queue'
    )

    parser.add_argument(
        '--run_user_worker', required=False, action='store_true',
        help='Run as User Worker: Fetch tweets from user queue'
    )

    parser.add_argument(
        '--run_reply_worker', required=False, action='store_true',
        help='Run as Reply Worker: Process replies from tweet queue'
    )

    parser.add_argument(
        '--port', required=False, default=None, type=int,
        help=f'[默认为 {DEF_LOCAL_PORT}] 浏览器启动端口'
    )

    # 添加 --debug 参数，用于调试
    parser.add_argument(
        '--debug', required=False, action='store_true',
        help='Debug'
    )

    args = parser.parse_args()
    show_msg(args)
    if args.loop_interval <= 0:
        main(args)
    else:
        while True:
            should_exit = main(args)
            if should_exit:
                break
            logger.info('#####***** Loop sleep {} seconds ...'.format(args.loop_interval))  # noqa
            time.sleep(args.loop_interval)

"""
# noqa
python xnotice.py --auto_like --manual_exit --monitor_notice_users --profile=g01

在新环境中初始化数据库，您可以使用以下两种方式之一（请确保 conf.py 中的数据库配置正确）：
python3 xnotice.py --init_db
python3 fun_db.py


推荐运行方式：
您可以开启三个终端标签页分别运行：

终端 1:
python3 xnotice.py --monitor_notice_users --profile=g01
# 使用自定义端口 启动浏览器
python3 xnotice.py --monitor_notice_users --profile=g01 --port=9400

终端 2:
python3 xnotice.py --run_user_worker --profile=g01
终端 3:
python3 xnotice.py --run_reply_worker
"""
