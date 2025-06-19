import os # noqa
import sys # noqa
import argparse
import random
import time
import copy
import pdb # noqa
import shutil
import math
import re # noqa
from datetime import datetime # noqa
import pyotp

from DrissionPage import ChromiumOptions
from DrissionPage import Chromium
from DrissionPage._elements.none_element import NoneElement

from fun_utils import ding_msg
from fun_utils import load_file
from fun_utils import save2file
from fun_utils import format_ts
from fun_utils import time_difference
from fun_utils import get_index_from_header

from fun_encode import decrypt
from fun_gmail import get_verify_code_from_gmail

from proxy_api import set_proxy

from fun_okx import OkxUtils
from fun_x import XUtils
from fun_dp import DpUtils

from fun_glm import gene_by_llm

from conf import DEF_USE_HEADLESS
from conf import DEF_DEBUG
from conf import DEF_PATH_USER_DATA
from conf import DEF_NUM_TRY
from conf import DEF_DING_TOKEN
from conf import DEF_PATH_DATA_STATUS

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

        self.set_url_processed = set([])

    def set_args(self, args):
        self.args = args
        self.is_update = False

        self.file_status = f'{DEF_PATH_DATA_STATUS}/xwool/status_{self.args.s_profile}.csv'

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
        s_content = f'{update_time},{s_op_type},{s_status},{s_url},{s_msg}'
        self.append2file(
            file_ot=self.file_status,
            s_content=s_content,
            header=self.DEF_HEADER_STATUS
        )
        self.is_update = True

    def close(self):
        # 在有头浏览器模式 Debug 时，不退出浏览器，用于调试
        if DEF_USE_HEADLESS is False and DEF_DEBUG:
            pass
        else:
            if self.browser:
                try:
                    self.browser.quit()
                except Exception as e: # noqa
                    # logger.info(f'[Close] Error: {e}')
                    pass

    def logit(self, func_name=None, s_info=None):
        s_text = f'{self.args.s_profile}'
        if func_name:
            s_text += f' [{func_name}]'
        if s_info:
            s_text += f' {s_info}'
        logger.info(s_text)

    def save_screenshot(self, name):
        tab = self.browser.latest_tab
        # 对整页截图并保存
        # tab.set.window.max()
        s_name = f'{self.args.s_profile}_{name}'
        tab.get_screenshot(path='tmp_img', name=s_name, full_page=True)

    def is_task_complete(self, idx_status, s_profile=None):
        if s_profile is None:
            s_profile = self.args.s_profile

        if s_profile not in self.dic_status:
            return False

        claimed_date = self.dic_status[s_profile][idx_status]
        date_now = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET) # noqa
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
        if 'cookie' not in s_lower_text:
            return 'other'

        dic_keywords = {
            'Spark': 'Spark',
            'Sapien': 'Sapien',
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
        user_url = f'https://x.com/{name}'
        tab = self.browser.new_tab(user_url)
        if self.is_followed(name):
            self.logit(None, f'Already followed, skip ...')
        else:
            self.logit(None, f'Try to Follow x: {name}')
            if self.inst_x.x_follow(name):
                tab.wait(1)
                self.status_append(
                    s_op_type='follow',
                    s_url=user_url,
                    s_msg=f'{name}',
                    s_status='OK',
                )
            else:
                self.logit(None, f'Follow x: {name} [Failed]')
        tab.close()

    def reply_tweet(self, s_tweet_type, s_tweet_text):
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
            lst_tw = [
                'https://x.com/ablenavy/status/1935701819508113805',
                'https://x.com/ablenavy/status/1935695847389594050',
            ]
            s_reply = random.choice(lst_reply)
            s_reply += '\n'
            s_reply += random.choice(lst_tw)
        else:
            # 调用大模型
            s_cont = s_tweet_text[:300]

            # "回复尽量幽默风趣，使用小红书风格"

            s_prompt = (
                "【功能】"
                "根据给定帖子内容，生成回复"
                "【要求】"
                "回复内容要符合给定帖子内容"
                "回复内容要避开敏感信息"
                "请用中文输出"
                "输出不要出现换行符"
                "中文与非中文之间要加空格"
                "输出不要超过60字"
                "【帖子内容如下】"
                f"{s_cont}"
            )
            s_reply = gene_by_llm(s_prompt)
            if not s_reply:
                self.logit(None, 's_reply from llm is empty, skip ...')
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
            else:
                s_reply += '\n'
                s_reply += '#Cookie #SNAPS'
            """

        if self.inst_x.x_reply(s_reply):
            s_msg = s_reply.replace('\n', ' ')
            self.logit(None, f'Reply Text: {s_msg}')
            self.status_append(
                s_op_type='reply',
                s_url=self.browser.latest_tab.url,
                s_msg=f'[Reply] {s_msg}',
                s_status='OK',
            )
            return True
        return False

    def proc_tw_url(self, tweet_url):
        if not tweet_url:
            return

        if tweet_url.startswith('https://x.com/'):
            name = tweet_url.split('com/')[-1].split('/')[0]

            tab = self.browser.new_tab(tweet_url)
            self.logit(None, f'Try to Like x: {tweet_url}')

            # get tweet text
            ele_tweet_text = tab.ele('@@tag()=div@@data-testid=tweetText', timeout=3)
            if not isinstance(ele_tweet_text, NoneElement):
                s_tweet_text = ele_tweet_text.text.replace('\n', ' ')
                self.logit(None, f'tweet_text: {s_tweet_text[:50]} ...')
            else:
                self.logit(None, 'tweet_text is not found')
                tab.close()
                return

            s_tweet_type = self.get_tweet_type_by_keyword(s_tweet_text)
            if s_tweet_type == 'other':
                self.logit(None, 'other tweet, skip ...')
                tab.close()
                return
            self.logit(None, f's_tweet_type: {s_tweet_type}')

            # reply
            self.reply_tweet(s_tweet_type, s_tweet_text)

            # like
            if self.inst_x.x_like():
                tab.wait(1)
                self.status_append(
                    s_op_type='like',
                    s_url=tweet_url,
                    s_msg='',
                    s_status='OK',
                )
            tab.close()

            # follow
            self.follow_user(name)

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
        ele_blk = tab.ele('@@tag()=div@@data-testid=ScrollSnap-List', timeout=3)
        if not isinstance(ele_blk, NoneElement):
            ele_btns = ele_blk.eles('@@tag()=div@@role=presentation', timeout=3)
            for ele_btn in ele_btns:
                self.logit(None, f'list_tabs: {ele_btn.text}')
                if ele_btn.text in ['关注']:
                    continue
                lst_tabs.append(ele_btn.text)
        return lst_tabs

    def select_tab(self, s_tab_name):
        tab = self.browser.latest_tab
        ele_blk = tab.ele('@@tag()=div@@data-testid=ScrollSnap-List', timeout=3)
        if not isinstance(ele_blk, NoneElement):
            ele_btns = ele_blk.eles('@@tag()=div@@role=presentation', timeout=3)
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

    def interaction(self):
        self.click_display_post()
        tab = self.browser.latest_tab

        for i in range(1, 5):
            ele_blks_top = tab.eles('@@tag()=div@@class=css-175oi2r@@data-testid=cellInnerDiv', timeout=3)
            if len(ele_blks_top) > 0:
                time.sleep(3)
                break
            self.inst_x.wrong_retry()
            time.sleep(3)

        n_blks_top = len(ele_blks_top)
        self.logit(None, f'len(ele_blks_top)={n_blks_top}')
        if not ele_blks_top:
            self.inst_x.wrong_retry()
            return

        num_blk = 0
        for ele_blk_top in ele_blks_top:
            num_blk += 1
            self.logit(None, f'num_blk={num_blk}/{n_blks_top}')
            try:
                ele_blk = ele_blk_top.ele('@@tag()=article@@aria-labelledby:id', timeout=3)
                if isinstance(ele_blk, NoneElement):
                    continue
            except Exception as e:
                #self.logit(None, f'An error occurred: {e}')
                self.logit(None, f'An error occurred, continue ...')
                continue

            # xuser_name
            ele_tweet_url = ele_blk.ele('@@tag()=a@@href:status@@dir=ltr', timeout=3)
            if not isinstance(ele_tweet_url, NoneElement):
                tweet_url = ele_tweet_url.attr('href')
                self.logit(None, f'tweet_url: {tweet_url}')
                if tweet_url in self.set_url_processed:
                    self.logit(None, 'tweet_url is already processed, continue ...')
                    continue

                if '/ablenavy/' in tweet_url:
                    continue

                if self.is_liked(ele_blk):
                    self.logit(None, 'Already liked, continue ...')
                    continue

                self.set_url_processed.add(tweet_url)
                self.proc_tw_url(tweet_url)
            else:
                self.logit(None, 'tweet_url is not found')

            tab.wait(10)

    def xwool_run(self):
        self.browser = self.inst_dp.get_browser(self.args.s_profile)

        self.inst_x.status_load()
        self.inst_x.set_browser(self.browser)

        if self.args.no_auto_vpn:
            logger.info(f'{self.args.s_profile} Use Current VPN') # noqa
        else:
            if self.args.vpn is None:
                idx_vpn = get_index_from_header(DEF_HEADER_ACCOUNT, 'proxy')
                if self.args.s_profile in self.inst_x.dic_account:
                    s_vpn = self.inst_x.dic_account[self.args.s_profile][idx_vpn]
                else:
                    logger.info(f'{self.args.s_profile} is not in self.inst_x.dic_account [ERROR]') # noqa
                    sys.exit(0)
            else:
                s_vpn = self.args.vpn

            if self.inst_dp.set_vpn(s_vpn) is False:
                return False

        self.inst_dp.check_extension(n_max_try=1)

        if self.inst_dp.init_capmonster() is False:
            return False

        if self.inst_dp.init_yescaptcha() is False:
            return False

        self.inst_x.twitter_run()
        n_max_run = 10
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
            s_msg = 'Press any key to exit! ⚠️' # noqa
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
        logger.info(f'Sleep {args.sleep_sec_at_start} seconds at start !!!') # noqa
        time.sleep(args.sleep_sec_at_start)

    if DEL_PROFILE_DIR and os.path.exists(DEF_PATH_USER_DATA):
        logger.info(f'Delete {DEF_PATH_USER_DATA} ...')
        shutil.rmtree(DEF_PATH_USER_DATA)
        logger.info(f'Directory {DEF_PATH_USER_DATA} is deleted') # noqa

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
    logger.info(f'Progress: {percent}% [{n}/{total}]') # noqa

    while profiles:
        n += 1
        logger.info('#'*40)
        s_profile = random.choice(profiles)
        percent = math.floor((n / total) * 100)
        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile}]') # noqa
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
                    logger.info(f'⚠️ 正在重试，当前是第{j}次执行，最多尝试{max_try_except}次 [{s_profile}]') # noqa

                x_wool.set_args(args)
                x_wool.inst_dp.set_args(args)
                x_wool.inst_x.set_args(args)

                if s_profile in x_wool.inst_x.dic_status:
                    lst_status = x_wool.inst_x.dic_status[s_profile]
                else:
                    lst_status = None

                if is_complete(lst_status):
                    logger.info(f'[{s_profile}] Last update at {lst_status[IDX_UPDATE]}') # noqa
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

    args = parser.parse_args()
    show_msg(args)
    if args.loop_interval <= 0:
        main(args)
    else:
        while True:
            main(args)
            logger.info('#####***** Loop sleep {} seconds ...'.format(args.loop_interval)) # noqa
            time.sleep(args.loop_interval)

"""
# noqa
python xwool.py --no_auto_vpn --force --profile=g01
python xwool.py --no_auto_vpn --force --manual_exit --profile=g01
"""
