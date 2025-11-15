import os  # noqa
import sys  # noqa
import argparse
import random
import time
import copy
import pdb  # noqa
import shutil
import math
import re  # noqa
from datetime import datetime  # noqa

from DrissionPage._elements.none_element import NoneElement

from fun_utils import ding_msg
from fun_utils import format_ts
from fun_utils import time_difference
from fun_utils import get_index_from_header
from fun_utils import load_advertising_urls
from fun_utils import load_ad_user

from fun_glm import gene_by_llm

from fun_okx import OkxUtils
from fun_x import XUtils
from fun_dp import DpUtils

from conf import DEF_USE_HEADLESS
from conf import DEF_DEBUG
from conf import DEF_PATH_USER_DATA
from conf import DEF_DING_TOKEN
from conf import DEF_PATH_DATA_STATUS

from conf import EXTENSION_ID_CAPMONSTER
from conf import EXTENSION_ID_YESCAPTCHA

from conf import DEF_HEADER_ACCOUNT

from conf import TZ_OFFSET
from conf import DEL_PROFILE_DIR

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


class XWool():
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

        self.lst_advertise_url = []

        # 按日期统计 关注、点赞、回复、转发 数量
        self.dic_date_count = {}

    def update_daily_stats(self, date, op_type, count=1):
        """
        更新每日操作统计

        Args:
            date (str): 日期字符串
            op_type (str): 操作类型 ('follow', 'like', 'reply', 'retweet')
            count (int): 操作数量，默认为1
        """
        if date not in self.dic_date_count:
            self.dic_date_count[date] = {
                'follow': 0,
                'like': 0,
                'reply': 0,
                'retweet': 0
            }

        if op_type in self.dic_date_count[date]:
            self.dic_date_count[date][op_type] += count

    def get_daily_stats(self, date):
        """
        获取指定日期的操作统计

        Args:
            date (str): 日期字符串

        Returns:
            dict: 包含各种操作数量的字典
        """
        return self.dic_date_count.get(date, {
            'follow': 0,
            'like': 0,
            'reply': 0,
            'retweet': 0
        })

    def get_today_stats(self):
        """
        获取今日操作统计

        Returns:
            dict: 包含今日各种操作数量的字典
        """
        today = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)
        return self.get_daily_stats(today)

    def print_daily_stats(self):
        """打印每日操作统计信息"""
        if self.dic_date_count:
            self.logit(None, 'Daily operation counts:')
            for date, counts in sorted(self.dic_date_count.items()):
                total = sum(counts.values())
                self.logit(None,
                           f'{date}: Follow={counts["follow"]}, '
                           f'Like={counts["like"]}, Reply={counts["reply"]}, '
                           f'Retweet={counts["retweet"]}, Total={total}')
        else:
            self.logit(None, 'No daily operation counts found')

    def print_session_stats(self, session_counts):
        """
        打印会话统计信息

        Args:
            session_counts (dict): 当前会话的操作统计
        """
        today_counts = self.get_today_stats()

        # 显示当前会话统计
        self.logit(None,
                   f'This session - Follow: {session_counts["follow"]}, '
                   f'Like: {session_counts["like"]}, '
                   f'Reply: {session_counts["reply"]}, '
                   f'Retweet: {session_counts["retweet"]}')

        # 显示当日总计
        total_today = {
            'follow': today_counts['follow'] + session_counts['follow'],
            'like': today_counts['like'] + session_counts['like'],
            'reply': today_counts['reply'] + session_counts['reply'],
            'retweet': today_counts['retweet'] + session_counts['retweet']
        }
        self.logit(None,
                   f'Today total - Follow: {total_today["follow"]}, '
                   f'Like: {total_today["like"]}, '
                   f'Reply: {total_today["reply"]}, '
                   f'Retweet: {total_today["retweet"]}')

    def check_daily_limits(self, op_type, current_count, max_limit):
        """
        检查是否达到每日操作限制

        Args:
            op_type (str): 操作类型
            current_count (int): 当前会话已执行的操作数量
            max_limit (int): 最大限制

        Returns:
            tuple: (是否达到限制, 当前总数, 限制信息)
        """
        if max_limit == 0:
            return True, 0, "Operation disabled"

        if max_limit == -1:
            return False, 0, "No limit"

        today_counts = self.get_today_stats()
        total_count = today_counts[op_type] + current_count

        if total_count >= max_limit:
            return True, total_count, (f"Daily {op_type} limit reached: "
                                       f"{total_count}/{max_limit}")

        return False, total_count, (f"Current {op_type} count: "
                                    f"{total_count}/{max_limit}")

    def set_args(self, args):
        self.args = args
        self.is_update = False

        # Current X User
        self.i_xuser = None

        self.file_status = (
            f'{DEF_PATH_DATA_STATUS}/xwool/status_{self.args.s_profile}.csv'
        )
        self.file_advertising = (
            f'{DEF_PATH_DATA_STATUS}/xwool/advertising.csv'
        )
        self.file_ad_user = f'{DEF_PATH_DATA_STATUS}/xwool/ad_user.csv'

        self.load_processed_url()

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

                        # 解析日期和操作类型
                        s_datetime = fields[0]  # 完整的时间戳
                        s_date = s_datetime.split('T')[0]  # 提取日期部分
                        s_op_type = fields[1]  # 操作类型
                        s_url = fields[3]

                        if fields[2] == DEF_INTERACTION_IGNORE:
                            self.set_url_ignored.add(s_url)
                            continue

                        # 统计操作数量
                        if 'follow' == s_op_type:
                            name = fields[4]
                            if name in self.set_user_followed:
                                continue
                            self.set_user_followed.add(name)
                            if fields[2] == DEF_INTERACTION_OK:
                                self.update_daily_stats(s_date, 'follow', 1)
                        elif 'like' == s_op_type:
                            if s_url in self.set_url_liked:
                                continue
                            self.set_url_liked.add(s_url)
                            if fields[2] == DEF_INTERACTION_OK:
                                self.update_daily_stats(s_date, 'like', 1)
                        elif 'reply' == s_op_type:
                            if s_url in self.set_url_replied:
                                continue
                            self.set_url_replied.add(s_url)
                            if fields[2] == DEF_INTERACTION_OK:
                                self.update_daily_stats(s_date, 'reply', 1)
                        elif 'retweet' == s_op_type:
                            if s_url in self.set_url_retweeted:
                                continue
                            self.set_url_retweeted.add(s_url)
                            if fields[2] == DEF_INTERACTION_OK:
                                self.update_daily_stats(s_date, 'retweet', 1)

        self.logit(None, f'load_ignored_url: {len(self.set_url_ignored)}')  # noqa
        self.logit(None, f'load_followed_user: {len(self.set_user_followed)}')  # noqa
        self.logit(None, f'load_liked_url: {len(self.set_url_liked)}')  # noqa
        self.logit(None, f'load_replied_url: {len(self.set_url_replied)}')  # noqa
        self.logit(None, f'load_retweeted_url: {len(self.set_url_retweeted)}')  # noqa

        # 显示每日统计信息
        self.print_daily_stats()

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

    def is_task_complete(self, idx_status, s_profile=None):
        if s_profile is None:
            s_profile = self.args.s_profile

        if s_profile not in self.dic_status:
            return False

        claimed_date = self.dic_status[s_profile][idx_status]
        date_now = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)  # noqa
        if date_now != claimed_date:
            return False
        else:
            return True

    def is_liked(self, ele_blk):
        lst_path = [
            '@@tag()=button@@data-testid=like',
            '@@tag()=button@@data-testid=unlike',
        ]
        ele_like = self.inst_dp.get_ele_btn(ele_blk, lst_path)
        if not isinstance(ele_like, NoneElement):
            s_attr = ele_like.attr('data-testid')
            if s_attr == 'unlike':
                return True
            else:
                return False

        return False

    def is_followed(self, name):
        tab = self.browser.latest_tab

        s_lower_name = name.lower()
        lst_path = [
            f'@@tag()=button@@data-testid:follow@@aria-label:{name}',
            f'@@tag()=button@@data-testid:follow@@aria-label:{s_lower_name}',  # noqa
        ]
        ele_btn = self.inst_dp.get_ele_btn(tab, lst_path)
        if ele_btn is not NoneElement:
            # data-testid="1649307142871212032-unfollow"
            s_attr = ele_btn.attr('data-testid').split('-')[-1]
            # Status: following
            if s_attr == 'unfollow':
                return True
        return False

    def is_keyword_follow(self, s_tweet_text):
        """
        互关贴
        """
        # 如果帖子长度超过 120 字，则认为不是互关贴
        if len(s_tweet_text) > 120:
            return False

        lst_keywords = [
            '互关',
            '互粉',
            '有关必回',
        ]
        for s_keyword in lst_keywords:
            # 不区分大小写
            if s_keyword.lower() in s_tweet_text.lower():
                return True
        return False

    def get_analyze_type(self, s_tweet_text):
        """
        分析贴，调用大模型回复
        """
        s_lower_text = s_tweet_text.lower()
        # if 'cookie' not in s_lower_text:
        #     return 'other'

        dic_keywords = {
            'yapper': 'Yapper',
            'Kaito': 'Kaito',
            'shout': 'Shout',
            'espresso': 'Espresso',
        }
        for s_keyword, s_type in dic_keywords.items():
            # 不区分大小写
            if s_keyword.lower() in s_lower_text:
                return s_type
        return 'other'

    def get_tweet_type_by_keyword(self, s_tweet_text):
        """
        根据关键词判断帖子类型
        """
        if self.is_keyword_follow(s_tweet_text):
            return 'follow'
        else:
            s_analyze_type = self.get_analyze_type(s_tweet_text)
            return s_analyze_type

    def follow_user(self, name):
        b_ret = False
        user_url = f'https://x.com/{name}'  # noqa
        tab = self.browser.new_tab(user_url)
        if self.is_followed(name):
            self.logit(None, 'Already followed, skip ...')
        else:
            self.logit(None, f'Try to Follow x: {name}')
            if self.inst_x.x_follow(name):
                tab.wait(1)
                self.status_append(
                    s_op_type='follow',
                    s_url=user_url,
                    s_msg=f'{name}',
                    s_status=DEF_INTERACTION_OK,
                )
                # 更新每日统计
                today = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)
                self.update_daily_stats(today, 'follow', 1)
                b_ret = True
            else:
                self.logit(None, f'Follow x: {name} [Failed]')
        tab.close()

        return b_ret

    def is_reply_ok(self, s_reply, n_max_len=60):
        """
        检查回复内容是否合格

        检查规则：
        1. 如果 @ # $ 出现次数超过 1 次，则认为回复不合格
        2. 如果回复长度超过 n_max_len 字，则认为回复不合格
        3. 如果非中文字符串(英文、数字、符号，符号只考虑 @ # $ 三个)与中文之间没有空格，则认为回复不合格

        Args:
            s_reply: 回复内容
            n_max_len: 最大长度限制，默认60字

        Returns:
            tuple: (bool, str) - (是否合格, 不合格原因)
                   True表示合格，False表示不合格
        """
        errors = []

        # 检查长度
        if len(s_reply) > n_max_len:
            # errors.append(f'长度超限({len(s_reply)}>{n_max_len})')
            errors.append(f'长度超限({len(s_reply)}>{n_max_len}) [回答太长了，字数减少一半]')

        # 检查特殊字符出现次数
        special_chars = ['@', '#', '$']
        for char in special_chars:
            count = s_reply.count(char)
            if count > 1:
                errors.append(f'"{char}"出现{count}次')

        # 是否有换行符号
        if '\n' in s_reply:
            errors.append('出现换行符号')

        # 开头是否有空格
        if s_reply.startswith(' '):
            errors.append('开头有空格')
        # 末尾是否有空格
        if s_reply.endswith(' '):
            errors.append('末尾有空格')

        # 检查是否出现 <|begin_of_box|> 和 <|end_of_box|> 标签
        if '<|begin_of_box|>' in s_reply or '<|end_of_box|>' in s_reply:
            errors.append('出现 <|begin_of_box|> 和 <|end_of_box|> 标签')

        # 检查非中文字符(英文、数字、符号，符号只考虑 @ # $ 三个)与中文之间是否有空格
        # 查找中文字符后紧跟非中文字符的情况(英文、数字、@ # $ 符号)
        pattern1 = r'[\u4e00-\u9fff][a-zA-Z0-9@#$]'
        # 查找非中文字符后紧跟中文字符的情况
        pattern2 = r'[a-zA-Z0-9@#$][\u4e00-\u9fff]'

        match1 = re.search(pattern1, s_reply)
        match2 = re.search(pattern2, s_reply)

        if match1 or match2:
            problem_text = match1.group() if match1 else match2.group()
            errors.append(f'中英文之间缺少空格，问题片段: "... {problem_text} ..."')

        # 如果有错误，返回 False 和拼接的错误信息
        if errors:
            error_msg = '; '.join(errors)
            self.logit(None, f'Reply not qualified: {error_msg}')
            return False, error_msg

        return True, DEF_INTERACTION_OK

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

    def reply_tweet(self, s_tweet_type, s_tweet_text):
        self.logit('reply_tweet', f's_tweet_type: {s_tweet_type}')
        s_reply = ''
        if s_tweet_type == 'follow':
            lst_reply = [
                '来了！',
                '来啦！',
                '安排！',
                '互关！',
                '互粉！',
                '互关互粉，冲！',
                '来啦！互关！'
            ]
            s_reply = random.choice(lst_reply)

            # 生成一个随机字符串，长度为 1 到 5 个字符(0-9,a-z,A-Z)
            chars = (
                '0123456789abcdefghijklmnopqrstuvwxyz'
                'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            )
            s_random = ''.join(
                random.choices(chars, k=random.randint(1, 5))
            )
            s_reply += f' {s_random}'

            # 使用已加载的广告 URL
            if len(self.lst_advertise_url) > 0:
                s_reply += '\n'
                s_reply += random.choice(self.lst_advertise_url)
        else:
            # 调用大模型
            s_cont = s_tweet_text[:300]

            # "回复尽量幽默风趣，使用小红书风格"
            # s_rules = (
            #     "回复内容要符合给定帖子内容\n"
            #     "回复内容要避开敏感信息\n"
            #     "请用中文输出\n"
            #     "输出不要出现换行符\n"
            #     "回复内容 @ 不要超过1个\n"
            #     "避免引用#话题，禁止出现 # \n"
            #     "回复内容积极向上，不要出现负面情绪\n"
            #     "输出不要超过 50 字\n"
            #     "特别注意，中文(汉字)与非中文(英文、数字、符号)之间要加一个空格，不要连在一起，增加可读性\n"
            #     "特别注意，不要出现回复如下之类的字眼，直接输出回复内容\n"
            # )

            # <|begin_of_box|>双方合作助力链上 AI 信任度与数据利用效率提升。<|end_of_box|>

            # "回复尽量简短，一句话回复"
            s_rules = (
                "简短回复，一句话回复\n"
                "回复内容要符合给定帖子内容\n"
                "回复内容要避开敏感信息\n"
                "请用中文输出\n"
                "输出不要出现换行符\n"
                "回复内容禁止出现 @\n"
                "避免引用#话题，禁止出现 # \n"
                "回复不要超过 30 字\n"
                "特别注意，中文(汉字)与非中文(英文、数字、符号)之间要加一个空格，不要连在一起，增加可读性\n"
                "特别注意，不要出现回复如下之类的字眼，直接输出回复内容\n"
                "特别注意，回复不要出现 <|begin_of_box|> 和 <|end_of_box|> 标签\n"
            )

            s_prompt = (
                "# 【功能】\n"
                "阅读给定帖子内容，生成回复\n"
                "# 【要求】\n"
                f"{s_rules}"
                "# 【帖子内容如下】\n"
                f"{s_cont}"
            )
            try:
                s_reply = gene_by_llm(s_prompt)
                if not s_reply:
                    self.logit(None, 's_reply from llm is empty, skip ...')
                    return False
            except Exception as e:
                self.logit(None, f'Error calling gene_by_llm: {e}')
                return False

            # 尝试生成合格的回复，最多尝试次数
            max_attempts = 8
            for attempt in range(1, max_attempts + 1):

                # 如果有多个空格，只保留1个空格
                s_reply = re.sub(r'\s+', ' ', s_reply)
                # 去掉前后的空格
                s_reply = s_reply.strip()
                # 去掉换行符
                s_reply = s_reply.replace('\n', '')
                # 去掉 <|begin_of_box|> 和 <|end_of_box|> 标签
                s_reply = re.sub(r'<\|begin_of_box\|>|<\|end_of_box\|>', '', s_reply)  # noqa

                self.logit(None, f'[To Verify]reply_by_llm: {s_reply}')
                # 验证回复内容是否合格
                is_ok, reason = self.is_reply_ok(s_reply, n_max_len=69)
                if is_ok:
                    self.logit(
                        None,
                        f'Reply qualified on attempt {attempt}/{max_attempts}'
                    )
                    break
                else:
                    self.logit(
                        None,
                        f'Attempt {attempt}/{max_attempts}: '
                        f'Reply not qualified: {reason}'
                    )
                    if attempt < max_attempts:
                        # 修改 prompt，要求大模型根据错误原因进行改进
                        s_prompt = (
                            "# 【要求】\n"
                            f"{s_rules}"
                            f"# 【回复内容有问题，请根据错误原因进行修改】\n"
                            f"{reason}\n"
                            f"# 【回复内容】{s_reply}"
                        )
                        try:
                            s_reply = gene_by_llm(s_prompt)
                            if not s_reply:
                                self.logit(None, 's_reply from llm is empty, skip ...')  # noqa
                                return False
                        except Exception as e:
                            self.logit(None, f'Error calling gene_by_llm: {e}')
                            return False
                    else:
                        self.logit(None, 'All attempts failed, skip ...')
                        return False

            """
            s_reply += '\n'
            s_reply += '@sparkdotfi @cookiedotfun @cookiedotfuncn'

            if s_tweet_type == 'Spark':
                s_reply += '\n'
                s_reply += '#SparkFi #Cookie #SNAPS'
            elif s_tweet_type == 'Sapien':
                s_reply += '\n'
                s_reply += '#SapienFi #Cookie #SNAPS'
            elif s_tweet_type == 'Openledger':
                s_reply += '\n'
                s_reply += '@OpenledgerHQ\n'
                s_reply += '\n'
                s_reply += '#SapienFi #Cookie #SNAPS'
            else:
                s_reply += '\n'
                s_reply += '#Cookie #SNAPS'
            """

        if self.inst_x.x_reply(s_reply):
            s_msg = s_reply.replace('\n', ' ')
            self.logit(None, f'Reply Text: {s_msg}')
            s_error_msg = self.get_error_msg()
            if s_error_msg:
                self.logit(None, f'Error Message: {s_error_msg}')

                s_msg = f'[{self.args.s_profile}]{s_error_msg}'
                ding_msg(s_msg, DEF_DING_TOKEN, msgtype='text')

                return False
            self.status_append(
                s_op_type='reply',
                s_url=self.browser.latest_tab.url,
                s_msg=f'[Reply] {s_msg}',
                s_status=DEF_INTERACTION_OK,
            )
            return True
        return False

    def proc_tw_url(self, tweet_url, is_reply=True, is_all_reply=False,
                    is_like=True, is_retweet=False, is_follow=True):
        """
        is_reply: 是否回复
        is_all_reply: 是否回复所有帖子
        is_like: 是否点赞
        is_retweet: 是否转发
        is_follow: 是否关注
        """
        b_ret = False
        counts = {'follow': 0, 'like': 0, 'reply': 0, 'retweet': 0}
        if not tweet_url:
            return b_ret, counts

        if tweet_url in self.set_url_ignored:
            self.logit(None, 'Already ignored before, skip ...')
            return b_ret, counts

        if tweet_url.startswith('https://x.com/'):
            name = tweet_url.split('com/')[-1].split('/')[0]

            tab = self.browser.new_tab(tweet_url)
            self.logit(None, f'Try to Like x: {tweet_url}')

            if tweet_url in self.set_url_replied:
                self.logit(None, 'Already replied before, skip ...')
            else:
                if self.inst_x.x_is_replied():
                    self.logit(None, 'Already replied, skip ...')
                    self.set_url_replied.add(tweet_url)
                else:
                    # get tweet text
                    ele_tweet_text = tab.ele(
                        '@@tag()=div@@data-testid=tweetText', timeout=3
                    )
                    if not isinstance(ele_tweet_text, NoneElement):
                        s_tweet_text = ele_tweet_text.text.replace('\n', ' ')
                        self.logit(None, f'tweet_text: {s_tweet_text[:50]} ...')  # noqa
                    else:
                        self.logit(None, 'tweet_text is not found')
                        tab.close()
                        return b_ret, counts

                    s_tweet_type = self.get_tweet_type_by_keyword(s_tweet_text)
                    if is_all_reply:
                        self.logit(None, f'is_all_reply: {is_all_reply}')
                        pass
                    else:
                        if s_tweet_type == 'other':
                            self.logit(None, 'other tweet, skip ...')

                            self.status_append(
                                s_op_type='reply',
                                s_url=tweet_url,
                                s_msg='[NotReply] other tweet, ignore',
                                s_status=DEF_INTERACTION_IGNORE,
                            )
                            self.set_url_ignored.add(tweet_url)

                            tab.close()

                            return b_ret, counts
                        self.logit(None, f's_tweet_type: {s_tweet_type}')

                    # reply
                    if is_reply:
                        if self.reply_tweet(s_tweet_type, s_tweet_text):
                            counts['reply'] = 1

            # like
            if is_like:
                if tweet_url in self.set_url_liked:
                    self.logit(None, 'Already liked before, skip ...')
                else:
                    if self.inst_x.x_like():
                        tab.wait(1)
                        self.status_append(
                            s_op_type='like',
                            s_url=tweet_url,
                            s_msg='',
                            s_status=DEF_INTERACTION_OK,
                        )
                        counts['like'] = 1
                        b_ret = True

            # retweet
            if is_retweet:
                if tweet_url in self.set_url_retweeted:
                    self.logit(None, 'Already retweeted before, skip ...')
                else:
                    if self.inst_x.x_retweet():
                        tab.wait(1)
                        self.status_append(
                            s_op_type='retweet',
                            s_url=tweet_url,
                            s_msg='',
                            s_status=DEF_INTERACTION_OK,
                        )
                        counts['retweet'] = 1
                        b_ret = True

            tab.close()

            # follow
            if is_follow:
                if name in self.set_user_followed:
                    self.logit(None, 'Already followed before, skip ...')
                else:
                    is_success = self.follow_user(name)
                    if is_success:
                        counts['follow'] = 1
                        b_ret = True

        return b_ret, counts

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

    def list_tabs(self):
        """
        获取所有标签

        为你推荐
        关注
        X 推特华语区 ｜蓝V互关｜Kaito｜Cookie
        X 推特华语区【蓝V互关】
        互关
        """
        lst_tabs = []
        tab = self.browser.latest_tab
        ele_blk = tab.ele(
            '@@tag()=div@@data-testid=ScrollSnap-List', timeout=3
        )
        if not isinstance(ele_blk, NoneElement):
            ele_btns = ele_blk.eles(
                '@@tag()=div@@role=presentation', timeout=3
            )
            for ele_btn in ele_btns:
                self.logit(None, f'list_tabs: {ele_btn.text}')
                if ele_btn.text in ['关注']:
                    continue
                lst_tabs.append(ele_btn.text)
        return lst_tabs

    def select_tab(self, s_tab_name):
        tab = self.browser.latest_tab
        ele_blk = tab.ele(
            '@@tag()=div@@data-testid=ScrollSnap-List', timeout=3
        )
        if not isinstance(ele_blk, NoneElement):
            ele_btns = ele_blk.eles(
                '@@tag()=div@@role=presentation', timeout=3
            )
            for ele_btn in ele_btns:
                # self.logit(None, f'list_tabs: {ele_btn.text}')
                if ele_btn.text != s_tab_name:
                    continue
                if ele_btn.wait.clickable(timeout=3):
                    ele_btn.click()
                    self.logit(None, f'select_tab[{s_tab_name}] [Success]')
                    tab.wait.doc_loaded()
                    tab.wait(5)
                    return True
        return False

    def interaction(self, is_reply=True, is_all_reply=False,
                    is_like=True, is_retweet=False, is_follow=True,
                    max_num_proc=-1):
        b_ret = False
        self.click_display_post()
        tab = self.browser.latest_tab

        # 初始化计数器
        n_follow_count = 0
        n_like_count = 0
        n_reply_count = 0
        n_retweet_count = 0

        # 获取当日已执行的操作数量（通过统计函数获取）

        for i in range(1, 5):
            ele_blks_top = tab.eles(
                '@@tag()=div@@class=css-175oi2r@@data-testid=cellInnerDiv',
                timeout=3
            )
            if len(ele_blks_top) > 0:
                time.sleep(3)
                break
            self.inst_x.wrong_retry()
            time.sleep(3)

        n_blks_top = len(ele_blks_top)
        self.logit(None, f'len(ele_blks_top)={n_blks_top}')
        if not ele_blks_top:
            self.inst_x.wrong_retry()
            return False

        num_blk = 0
        n_proc_success = 0
        for ele_blk_top in ele_blks_top:
            num_blk += 1
            self.logit(None, f'num_blk={num_blk}/{n_blks_top}')
            try:
                ele_blk = ele_blk_top.ele(
                    '@@tag()=article@@aria-labelledby:id', timeout=3
                )
                if isinstance(ele_blk, NoneElement):
                    continue
            except Exception:
                # self.logit(None, f'An error occurred: {e}')
                self.logit(None, 'An error occurred, continue ...')
                continue

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

                if tweet_url in self.set_url_ignored:
                    self.logit(None, 'Already ignored before, skip ...')
                    continue

                # 检查是否已达到最大限制
                if is_follow:
                    is_limit_reached, _, limit_msg = self.check_daily_limits(
                        'follow', n_follow_count, self.args.max_follow)
                    if is_limit_reached:
                        is_follow = False
                        self.logit(None, limit_msg)

                if is_like:
                    is_limit_reached, _, limit_msg = self.check_daily_limits(
                        'like', n_like_count, self.args.max_like)
                    if is_limit_reached:
                        is_like = False
                        self.logit(None, limit_msg)

                if is_reply:
                    is_limit_reached, _, limit_msg = self.check_daily_limits(
                        'reply', n_reply_count, self.args.max_reply)
                    if is_limit_reached:
                        is_reply = False
                        self.logit(None, limit_msg)

                if is_retweet:
                    is_limit_reached, _, limit_msg = self.check_daily_limits(
                        'retweet', n_retweet_count, self.args.max_retweet)
                    if is_limit_reached:
                        is_retweet = False
                        self.logit(None, limit_msg)

                # 如果所有操作都被限制，则跳过
                if not (is_reply or is_like or is_retweet or is_follow):
                    self.logit(None,
                               'All operations reached max limit, skip ...')
                    break

                is_success, counts = self.proc_tw_url(
                    tweet_url, is_reply=is_reply, is_all_reply=is_all_reply,
                    is_like=is_like, is_retweet=is_retweet, is_follow=is_follow
                )
                if is_success:
                    b_ret = True
                    # 更新计数器
                    n_follow_count += counts.get('follow', 0)
                    n_like_count += counts.get('like', 0)
                    n_reply_count += counts.get('reply', 0)
                    n_retweet_count += counts.get('retweet', 0)

                    # 更新每日统计
                    today = format_ts(time.time(), style=1,
                                      tz_offset=TZ_OFFSET)
                    if counts.get('follow', 0) > 0:
                        self.update_daily_stats(today, 'follow',
                                                counts['follow'])
                    if counts.get('like', 0) > 0:
                        self.update_daily_stats(today, 'like',
                                                counts['like'])
                    if counts.get('reply', 0) > 0:
                        self.update_daily_stats(today, 'reply',
                                                counts['reply'])
                    if counts.get('retweet', 0) > 0:
                        self.update_daily_stats(today, 'retweet',
                                                counts['retweet'])
            else:
                self.logit(None, 'tweet_url is not found')

            tab.wait(10)

            n_proc_success += 1
            if max_num_proc > 0 and n_proc_success >= max_num_proc:
                break

        self.logit(None, f'n_proc_success={n_proc_success}')

        # 显示会话统计信息
        session_counts = {
            'follow': n_follow_count,
            'like': n_like_count,
            'reply': n_reply_count,
            'retweet': n_retweet_count
        }
        self.print_session_stats(session_counts)

        return b_ret

    def proc_ad_user(self, x_user, x_nickname):
        """
        Like, Follow, Retweet, Comment
        """
        self.logit(None, f'proc_ad_user: {x_user} {x_nickname}')
        b_ret = False
        tab = None

        if self.i_xuser == x_user:
            self.logit(None, 'Self user, skip ...')
            return False

        user_url = f'https://x.com/{x_user}'  # noqa
        tab = self.browser.new_tab(user_url)

        if x_user in self.set_user_followed:
            self.logit(None, 'Already followed before, skip ...')
        else:
            # 检查关注限制
            is_follow_limit, follow_count, follow_msg = (
                self.check_daily_limits('follow', 0, self.args.max_follow))
            if is_follow_limit:
                self.logit(None, f'Follow: {follow_msg}')
                self.logit(None, 'Follow limit reached, skip ...')
            else:
                self.logit(None, f'Follow: {follow_msg}')
                # Follow
                # user_url = f'https://x.com/{x_user}' # noqa
                # tab = self.browser.new_tab(user_url)
                if self.is_followed(x_user):
                    self.logit(None, 'Already followed, skip ...')
                else:
                    self.logit(None, f'Try to Follow x: {x_user}')
                    if self.inst_x.x_follow(x_user):
                        tab.wait(1)
                        self.status_append(
                            s_op_type='follow',
                            s_url=user_url,
                            s_msg=f'{x_user}',
                            s_status=DEF_INTERACTION_OK,
                        )
                        # 更新每日统计
                        today = format_ts(time.time(), style=1,
                                          tz_offset=TZ_OFFSET)
                        self.update_daily_stats(today, 'follow', 1)
                        b_ret = True
                        self.set_user_followed.add(x_user)
                    else:
                        self.logit(None, f'Follow x: {x_user} [Failed]')

        # 生成一个 1-2 随机数
        n_max_proc = random.randint(1, 2)
        self.logit('proc_ad_user', f'interaction n_max_proc={n_max_proc}')
        is_success = self.interaction(
            is_reply=True, is_all_reply=True,
            is_like=True, is_retweet=False, is_follow=True,
            max_num_proc=n_max_proc
        )
        if is_success:
            b_ret = True

        if tab:
            tab.close()

        return b_ret

    def water_by_url(self, tweet_url):
        """
        Like, Follow, Retweet, Comment
        """
        if tweet_url in self.set_url_ignored:
            self.logit(None, 'Already ignored before, skip ...')
            return False

        # 检查当日操作限制
        # 检查回复限制
        is_reply_limit, reply_count, reply_msg = self.check_daily_limits(
            'reply', 0, self.args.max_reply)
        if is_reply_limit:
            self.logit(None, f'Reply: {reply_msg}')
        else:
            self.logit(None, f'Reply: {reply_msg}')

        # 检查点赞限制
        is_like_limit, like_count, like_msg = self.check_daily_limits(
            'like', 0, self.args.max_like)
        if is_like_limit:
            self.logit(None, f'Like: {like_msg}')
        else:
            self.logit(None, f'Like: {like_msg}')

        # 检查转帖限制
        is_retweet_limit, retweet_count, retweet_msg = self.check_daily_limits(
            'retweet', 0, self.args.max_retweet)
        if is_retweet_limit:
            self.logit(None, f'Retweet: {retweet_msg}')
        else:
            self.logit(None, f'Retweet: {retweet_msg}')

        # 检查关注限制
        is_follow_limit, follow_count, follow_msg = self.check_daily_limits(
            'follow', 0, self.args.max_follow)
        if is_follow_limit:
            self.logit(None, f'Follow: {follow_msg}')
        else:
            self.logit(None, f'Follow: {follow_msg}')

        # Like
        tab = self.browser.new_tab(tweet_url)

        # Follow
        # Retweet
        # Comment

        self.logit(None, f'Try to Reply x: {tweet_url}')
        if is_reply_limit:
            self.logit(None, 'Reply limit reached, skip ...')
        elif self.inst_x.x_is_replied():
            self.logit(None, 'Already replied, skip ...')
        else:
            # get tweet text
            ele_tweet_text = tab.ele(
                '@@tag()=div@@data-testid=tweetText', timeout=3
            )
            if not isinstance(ele_tweet_text, NoneElement):
                s_tweet_text = ele_tweet_text.text.replace('\n', ' ')
                self.logit(None, f'tweet_text: {s_tweet_text[:50]} ...')
            else:
                self.logit(None, 'tweet_text is not found')
                tab.close()
                return False

            s_tweet_type = self.get_tweet_type_by_keyword(s_tweet_text)
            # if s_tweet_type == 'other':
            #     self.logit(None, 'other tweet, skip ...')
            #     tab.close()
            #     return
            self.logit(None, f's_tweet_type: {s_tweet_type}')

            # reply
            if self.reply_tweet(s_tweet_type, s_tweet_text) is True:
                self.set_url_replied.add(tweet_url)

        # like
        self.logit(None, f'Try to Like x: {tweet_url}')
        if is_like_limit:
            self.logit(None, 'Like limit reached, skip ...')
        elif tweet_url in self.set_url_liked:
            self.logit(None, 'Already liked before, skip ...')
        else:
            if self.inst_x.x_like():
                tab.wait(1)
                self.status_append(
                    s_op_type='like',
                    s_url=tweet_url,
                    s_msg='',
                    s_status=DEF_INTERACTION_OK,
                )
                self.set_url_liked.add(tweet_url)
                # 更新每日统计
                today = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)
                self.update_daily_stats(today, 'like', 1)

        # retweet
        self.logit(None, f'Try to Retweet x: {tweet_url}')
        if is_retweet_limit:
            self.logit(None, 'Retweet limit reached, skip ...')
        elif tweet_url in self.set_url_retweeted:
            self.logit(None, 'Already retweeted before, skip ...')
        else:
            if self.inst_x.x_retweet():
                tab.wait(1)
                self.status_append(
                    s_op_type='retweet',
                    s_url=tweet_url,
                    s_msg='',
                    s_status=DEF_INTERACTION_OK,
                )
                self.set_url_retweeted.add(tweet_url)
                # 更新每日统计
                today = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)
                self.update_daily_stats(today, 'retweet', 1)

        tab.close()

        # follow
        self.logit(None, f'Try to Follow x: {tweet_url}')
        name = tweet_url.split('com/')[-1].split('/')[0]
        if is_follow_limit:
            self.logit(None, 'Follow limit reached, skip ...')
        elif name in self.set_user_followed:
            self.logit(None, 'Already followed before, skip ...')
        else:
            if self.follow_user(name):
                self.set_user_followed.add(name)

        return True

    def load_ad_tw_urls(self):
        self.lst_advertise_url = []
        lst_ad_url = load_advertising_urls(
            self.file_advertising
        )
        # https://x.com/ablenavy/
        for s_url in lst_ad_url:
            x_user = s_url.split('/')[3]
            if self.i_xuser != x_user:
                self.lst_advertise_url.append(s_url)
        if len(self.lst_advertise_url) > 1:
            random.shuffle(self.lst_advertise_url)

    def xwool_run(self):
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
            ding_msg(s_msg, DEF_DING_TOKEN, msgtype='text')
            return True

        # 根据配置决定是否执行扩展检测
        if hasattr(args, 'do_extension_check') and args.do_extension_check:
            # 使用配置的扩展检测参数
            if hasattr(args, 'extension_id') and args.extension_id:
                # 使用自定义扩展ID
                lst_extension_id = [
                    (s_id, 'custom') for s_id in args.extension_id.split(',')
                ]
            else:
                # 使用默认扩展
                lst_extension_id = [
                    (EXTENSION_ID_YESCAPTCHA, 'yescaptcha'),
                    (EXTENSION_ID_CAPMONSTER, 'capmonster'),
                ]

            # 使用配置的重试次数
            max_try = getattr(args, 'extension_check_max_try', 1)
            self.inst_dp.check_extension(
                n_max_try=max_try, lst_extension_id=lst_extension_id
            )
        else:
            logger.info('扩展检测已禁用，跳过扩展检查')

        if self.inst_dp.init_capmonster() is False:
            return False

        if self.inst_dp.init_yescaptcha() is False:
            return False

        self.inst_x.twitter_run()

        s_x_status = self.inst_x.get_x_status()
        if not s_x_status:
            pass
        elif s_x_status != DEF_STATUS_OK:
            self.logit(None, 'X Account is suspended, return ...')
            return True

        if self.args.ad_user:
            self.lst_ad_user = []
            lst_x_user = load_ad_user(self.file_ad_user)
            for x_user in lst_x_user:
                if self.i_xuser != x_user:
                    self.lst_ad_user.append(x_user)

            self.logit(None, f'len(self.lst_ad_user)={len(self.lst_ad_user)}')
            # 打乱顺序，最多取n个
            lst_random = copy.deepcopy(self.lst_ad_user)
            random.shuffle(lst_random)
            n_max_proc = 5
            n_proc_success = 0
            for x_user, x_nickname in lst_random:
                if n_proc_success >= n_max_proc:
                    break

                # 检查是否已达到每日关注限制
                is_follow_limit, _, follow_msg = self.check_daily_limits(
                    'follow', 0, self.args.max_follow)
                if is_follow_limit:
                    self.logit(None, f'Daily follow limit reached: '
                               f'{follow_msg}')
                    self.logit(None, 'Stop processing ad users due to limit')
                    break

                is_success = self.proc_ad_user(x_user, x_nickname)
                if is_success:
                    n_proc_success += 1

        if self.args.water:
            # 加载广告 URL
            self.load_ad_tw_urls()

            # lst_random = copy.deepcopy(self.lst_advertise_url)
            for s_url in self.lst_advertise_url[:5]:
                self.water_by_url(s_url)

        n_max_run = self.args.max_interactions
        for i in range(1, n_max_run+1):
            self.logit(None, f'Run {i}/{n_max_run} times ...')

            lst_tabs = self.list_tabs()
            # lst_tabs = ['X 推特华语区【蓝V互关】']
            # lst_tabs = ['为你推荐']
            for s_tab_name in lst_tabs:
                self.select_tab(s_tab_name)
                self.interaction()
            self.browser.latest_tab.refresh()
            n_sleep = random.randint(60, 120)
            self.logit(None, f'Sleep {n_sleep} seconds ...')
            time.sleep(n_sleep)

        if self.args.manual_exit and self.args.headless is False:
            s_msg = 'Press any key to exit! ⚠️'  # noqa
            input(s_msg)

        self.logit('xwool_run', 'Finished!')
        self.close()

        return True


def send_msg(x_wool, lst_success):
    if len(DEF_DING_TOKEN) > 0 and len(lst_success) > 0:
        s_info = ''
        for s_profile in lst_success:
            lst_status = None
            if s_profile in x_wool.inst_x.dic_status:
                lst_status = x_wool.inst_x.dic_status[s_profile]

            if lst_status is None:
                lst_status = [s_profile, -1]

            s_info += '- {},{}\n'.format(
                s_profile,
                lst_status[IDx_wool_DATE],
            )
        d_cont = {
            'title': 'Daily Check-In Finished! [xwool]',
            'text': (
                'Daily Check-In [xwool]\n'
                '- account,op_date\n'
                '{}\n'
                .format(s_info)
            )
        }
        ding_msg(d_cont, DEF_DING_TOKEN, msgtype="markdown")


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

    x_wool = XWool()

    if len(args.profile) > 0:
        items = args.profile.split(',')
    else:
        # 从配置文件里获取钱包名称列表
        items = list(x_wool.inst_x.dic_account.keys())

    profiles = copy.deepcopy(items)

    # 每次随机取一个出来，并从原列表中删除，直到原列表为空
    total = len(profiles)
    n = 0

    lst_success = []

    def is_complete(lst_status):
        if args.force:
            return False

        b_ret = True
        date_now = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)

        if lst_status:
            for idx_status in [IDx_wool_DATE]:
                s_date = lst_status[idx_status]
                if date_now != s_date:
                    b_ret = b_ret and False
        else:
            b_ret = False

        return b_ret

    def get_sec_wait(lst_status):
        n_sec_wait = 0
        if lst_status:
            avail_time = lst_status[IDX_UPDATE]
            if avail_time:
                n_sec_wait = time_difference(avail_time) + 1

        return n_sec_wait

    # 将已完成的剔除掉
    x_wool.inst_x.status_load()
    # 从后向前遍历列表的索引
    for i in range(len(profiles) - 1, -1, -1):
        s_profile = profiles[i]
        if s_profile in x_wool.inst_x.dic_status:
            lst_status = x_wool.inst_x.dic_status[s_profile]

            if is_complete(lst_status):
                n += 1
                profiles.pop(i)

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

        if args.create is False:
            if s_profile not in x_wool.inst_x.dic_account:
                logger.info(f'{s_profile} is not in account conf [ERROR]')
                sys.exit(0)

        # 如果出现异常(与页面的连接已断开)，增加重试
        max_try_except = 3
        for j in range(1, max_try_except+1):
            try:
                if j > 1:
                    logger.info(f'⚠️ 正在重试，当前是第{j}次执行，最多尝试{max_try_except}次 [{s_profile}]')  # noqa

                x_wool.set_args(args)
                x_wool.inst_dp.set_args(args)
                x_wool.inst_x.set_args(args)

                x_wool.inst_x.set_vpn_manual(s_profile, DEF_DING_TOKEN)

                if s_profile in x_wool.inst_x.dic_status:
                    lst_status = x_wool.inst_x.dic_status[s_profile]
                else:
                    lst_status = None

                if is_complete(lst_status):
                    logger.info(f'[{s_profile}] Last update at {lst_status[IDX_UPDATE]}')  # noqa
                    break
                else:
                    if x_wool.xwool_run():
                        lst_success.append(s_profile)
                        break

            except Exception as e:
                logger.info(f'[{s_profile}] An error occurred: {str(e)}')
                x_wool.close()
                if j < max_try_except:
                    time.sleep(5)

        if x_wool.inst_x.is_update is False:
            continue

        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile} Finish]')

        if len(profiles) > 0:
            sleep_time = random.randint(args.sleep_sec_min, args.sleep_sec_max)
            if sleep_time > 60:
                logger.info('sleep {} minutes ...'.format(int(sleep_time/60)))
            else:
                logger.info('sleep {} seconds ...'.format(int(sleep_time)))
            time.sleep(sleep_time)

    send_msg(x_wool, lst_success)


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
        '--auto_appeal', required=False, action='store_true',
        help='Auto appeal when account is suspended'
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
        '--create', required=False, action='store_true',
        help='Create'
    )
    parser.add_argument(
        '--vpn', required=False, default=None,
        help='Set vpn, default is None'
    )
    parser.add_argument(
        '--no_auto_vpn', required=False, action='store_true',
        help='Ignore Clash Verge API'
    )
    # 手动设置 VPN，默认为 False
    parser.add_argument(
        '--vpn_manual', required=False, action='store_true',
        help='Set vpn manually, default is False'
    )
    parser.add_argument(
        '--name', required=False, default='',
        help='Optional, can be generated by default'
    )
    parser.add_argument(
        '--password', required=False, default='',
        help='Optional, can be generated by default'
    )
    parser.add_argument(
        '--email', required=False, default='',
        help='Required'
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

    # 添加最大数量限制参数
    parser.add_argument(
        '--max_follow', required=False, default=-1, type=int,
        help='[默认为 -1] 当日最大关注数量，-1表示无限制，0表示不关注'
    )
    parser.add_argument(
        '--max_like', required=False, default=-1, type=int,
        help='[默认为 -1] 当日最大点赞数量，-1表示无限制，0表示不点赞'
    )
    parser.add_argument(
        '--max_reply', required=False, default=-1, type=int,
        help='[默认为 -1] 当日最大回复数量，-1表示无限制，0表示不回复'
    )
    parser.add_argument(
        '--max_retweet', required=False, default=-1, type=int,
        help='[默认为 -1] 当日最大转帖数量，-1表示无限制，0表示不转帖'
    )

    args = parser.parse_args()
    show_msg(args)
    if args.loop_interval <= 0:
        main(args)
    else:
        while True:
            main(args)
            logger.info('#####***** Loop sleep {} seconds ...'.format(args.loop_interval))  # noqa
            time.sleep(args.loop_interval)

"""
# noqa
python xwool.py --no_auto_vpn --force --profile=g01
python xwool.py --no_auto_vpn --force --ad_user --profile=g01

python xwool.py --no_auto_vpn --force --manual_exit --profile=g01

python xwool.py --no_auto_vpn --force --manual_exit --water --profile=g02

python xwool.py --manual_exit --water

python xwool.py --auto_like --auto_appeal --manual_exit --profile=g22
python xwool.py --auto_like --auto_appeal --manual_exit --water --profile=g22

python xwool.py --no_auto_vpn --force --manual_exit --water --ad_user --profile=g07

python xwool.py --auto_like --manual_exit --water --ad_user --profile=g07

# 使用新的当日最大数量限制参数
python xwool.py --no_auto_vpn --force --profile=g01 --max_follow=5 --max_like=10 --max_reply=3 --max_retweet=2
python xwool.py --no_auto_vpn --force --ad_user --profile=g01 --max_follow=3 --max_like=8
"""
