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

from mnemonic import Mnemonic

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

from conf import DEF_USE_HEADLESS
from conf import DEF_DEBUG
from conf import DEF_PATH_USER_DATA
from conf import DEF_NUM_TRY
from conf import DEF_DING_TOKEN
from conf import DEF_PATH_DATA_STATUS

from conf import DEF_PATH_DATA_ACCOUNT
from conf import DEF_HEADER_ACCOUNT

from conf import TZ_OFFSET
from conf import DEL_PROFILE_DIR

from conf import FILENAME_LOG
from conf import logger

"""
2025.04.25
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
IDX_CREATE_DATE = 2
IDX_NUM_VISIT = 3
IDX_UPDATE = 4
FIELD_NUM = IDX_UPDATE + 1

# X STATUS
DEF_STATUS_OK = 'OK'
DEF_STATUS_SUSPEND = 'SUSPEND'
DEF_STATUS_APPEALED = 'APPEALED'

DEF_OKX = False


class XCreate():
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

    def set_args(self, args):
        self.args = args
        self.is_update = False

    def __del__(self):
        pass
        # self.status_save()

    # def account_load(self):
    #     self.file_account = DEF_FILE_X_ENCRIYPT
    #     self.dic_account = load_file(
    #         file_in=self.file_account,
    #         idx_key=0,
    #         header=DEF_HEADER_ACCOUNT
    #     )

    # def status_load(self):
    #     self.file_status = DEF_FILE_X_STATUS
    #     self.dic_status = load_file(
    #         file_in=self.file_status,
    #         idx_key=0,
    #         header=DEF_HEADER_STATUS
    #     )

    # def status_save(self):
    #     self.file_status = DEF_FILE_X_STATUS
    #     save2file(
    #         file_ot=self.file_status,
    #         dic_status=self.dic_status,
    #         idx_key=0,
    #         header=DEF_HEADER_STATUS
    #     )

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

    def update_status(self, idx_status, s_value):
        update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)

        def init_status():
            self.dic_status[self.args.s_profile] = [
                self.args.s_profile,
            ]
            for i in range(1, FIELD_NUM):
                self.dic_status[self.args.s_profile].append('')

        if self.args.s_profile not in self.dic_status:
            init_status()
        if len(self.dic_status[self.args.s_profile]) != FIELD_NUM:
            init_status()
        if self.dic_status[self.args.s_profile][idx_status] == s_value:
            return

        self.dic_status[self.args.s_profile][idx_status] = s_value
        self.dic_status[self.args.s_profile][IDX_UPDATE] = update_time

        self.status_save()
        self.is_update = True

    def get_status_by_idx(self, idx_status, s_profile=None):
        if s_profile is None:
            s_profile = self.args.s_profile

        s_val = ''
        lst_pre = self.dic_status.get(s_profile, [])
        if len(lst_pre) == FIELD_NUM:
            try:
                s_val = int(lst_pre[idx_status])
            except: # noqa
                pass

        return s_val

    def get_pre_num_visit(self, s_profile=None):
        num_visit_pre = 0

        s_val = self.get_status_by_idx(IDX_NUM_VISIT, s_profile)

        try:
            num_visit_pre = int(s_val)
        except: # noqa
            pass

        return num_visit_pre

    def update_num_visit(self, s_profile=None):
        date_now = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)
        s_update = self.get_status_by_idx(-1, s_profile)
        if len(s_update) > 10:
            date_update = s_update[:10]
        else:
            date_update = ''
        if date_now != date_update:
            num_visit = 1
        else:
            num_visit_pre = self.get_pre_num_visit(s_profile)
            num_visit = num_visit_pre + 1

        self.update_status(IDX_NUM_VISIT, str(num_visit))

    def update_date(self, idx_status, update_ts=None):
        if not update_ts:
            update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)

        claim_date = update_time[:10]

        self.update_status(idx_status, claim_date)

    def xcreate_run(self):
        self.browser = self.inst_dp.get_browser(self.args.s_profile)

        self.inst_x.status_load()
        self.inst_x.set_browser(self.browser)

        if self.args.no_auto_vpn:
            logger.info(f'{self.args.s_profile} Use Current VPN') # noqa
        else:
            if self.args.vpn is None:
                idx_vpn = get_index_from_header(DEF_HEADER_ACCOUNT, 'proxy')
                if self.args.s_profile in self.inst_x.dic_account:
                    s_vpn = self.inst_x.dic_account[self.args.s_profile][idx_vpn] # noqa
                else:
                    logger.info(f'{self.args.s_profile} is not in self.inst_x.dic_account [ERROR]') # noqa
                    sys.exit(0)
            else:
                s_vpn = self.args.vpn

            if self.inst_dp.set_vpn(s_vpn) is False:
                return False

        if self.inst_dp.init_capmonster() is False:
            return False

        if self.inst_dp.init_yescaptcha() is False:
            return False

        self.inst_x.update_create(self.inst_x.IDX_C_PROXY, self.args.vpn)
        self.inst_x.twitter_create()

        if self.args.manual_exit:
            s_msg = 'Press any key to exit! ⚠️' # noqa
            input(s_msg)

        self.logit('xcreate_run', 'Finished!')
        self.close()

        return True


def send_msg(x_create, lst_success):
    if len(DEF_DING_TOKEN) > 0 and len(lst_success) > 0:
        s_info = ''
        for s_profile in lst_success:
            lst_status = None
            if s_profile in x_create.inst_x.dic_create:
                lst_status = x_create.inst_x.dic_create[s_profile]

            if lst_status is None:
                lst_status = [s_profile, -1]

            s_info += '- {},{}\n'.format(
                s_profile,
                lst_status[x_create.inst_x.IDX_C_USERNAME],
            )
        d_cont = {
            'title': 'Daily Check-In Finished! [xcreate]',
            'text': (
                'Daily Check-In [xcreate]\n'
                '- account,time_next_claim\n'
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
    if args.create is False:
        logger.info('self.args.create is False. Exit')
        sys.exit(0)
    if args.reset_profile is True:
        s_directory = f'{DEF_PATH_USER_DATA}/{args.profile}'
        if os.path.exists(s_directory) and os.path.isdir(s_directory):
            # 删除目录
            shutil.rmtree(s_directory)
            logger.info(f'Directory {s_directory} is deleted') # noqa

    if args.sleep_sec_at_start > 0:
        logger.info(f'Sleep {args.sleep_sec_at_start} seconds at start !!!') # noqa
        time.sleep(args.sleep_sec_at_start)

    if DEL_PROFILE_DIR and os.path.exists(DEF_PATH_USER_DATA):
        logger.info(f'Delete {DEF_PATH_USER_DATA} ...')
        shutil.rmtree(DEF_PATH_USER_DATA)
        logger.info(f'Directory {DEF_PATH_USER_DATA} is deleted') # noqa

    x_create = XCreate()

    if len(args.profile) > 0:
        items = args.profile.split(',')
    else:
        # 从配置文件里获取钱包名称列表
        items = list(x_create.inst_x.dic_account.keys())

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
            for idx_status in [IDX_CREATE_DATE]:
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
    x_create.inst_x.status_load()
    # 从后向前遍历列表的索引
    for i in range(len(profiles) - 1, -1, -1):
        s_profile = profiles[i]
        if s_profile in x_create.inst_x.dic_status:
            lst_status = x_create.inst_x.dic_status[s_profile]

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
            if s_profile not in x_create.inst_x.dic_account:
                logger.info(f'{s_profile} is not in account conf [ERROR]')
                sys.exit(0)

        # 如果出现异常(与页面的连接已断开)，增加重试
        max_try_except = 3
        for j in range(1, max_try_except+1):
            try:
                if j > 1:
                    logger.info(f'⚠️ 正在重试，当前是第{j}次执行，最多尝试{max_try_except}次 [{s_profile}]') # noqa

                x_create.set_args(args)
                x_create.inst_dp.set_args(args)
                x_create.inst_x.set_args(args)

                if s_profile in x_create.inst_x.dic_status:
                    lst_status = x_create.inst_x.dic_status[s_profile]
                else:
                    lst_status = None

                if is_complete(lst_status):
                    logger.info(f'[{s_profile}] Last update at {lst_status[IDX_UPDATE]}') # noqa
                    break
                else:
                    if x_create.xcreate_run():
                        lst_success.append(s_profile)
                        break

            except Exception as e:
                logger.info(f'[{s_profile}] An error occurred: {str(e)}')
                x_create.close()
                if j < max_try_except:
                    time.sleep(5)

        if x_create.inst_x.is_update is False:
            continue

        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile} Finish]')

        if len(profiles) > 0:
            sleep_time = random.randint(args.sleep_sec_min, args.sleep_sec_max)
            if sleep_time > 60:
                logger.info('sleep {} minutes ...'.format(int(sleep_time/60)))
            else:
                logger.info('sleep {} seconds ...'.format(int(sleep_time)))
            time.sleep(sleep_time)

    send_msg(x_create, lst_success)


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
        '--reset_profile', required=False, action='store_true',
        help='Delete profile'
    )
    parser.add_argument(
        '--vpn', required=False, default=None,
        help='[Optional] Set vpn, default is None'
    )
    parser.add_argument(
        '--no_auto_vpn', required=False, action='store_true',
        help='Ignore Clash Verge API'
    )
    parser.add_argument(
        '--name', required=False, default='',
        help='[Optional] can be generated by default'
    )
    parser.add_argument(
        '--password', required=False, default='',
        help='[Optional] can be generated by default'
    )
    parser.add_argument(
        '--email', required=False, default='',
        help='Required [1. userabc@gmail.com; 2. @gmail.com]'
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

    email_fields = args.email.split('@')
    if not email_fields[0]:
        mnemo = Mnemonic("english")
        words = mnemo.generate(strength=12 * 32 // 3).split()
        # 选择两个最短的单词
        shortest_words = sorted(words, key=len)[:2]
        email_fields[0] = ''.join(shortest_words)
        args.email = '@'.join(email_fields)

    if (args.loop_interval <= 0) or args.create:
        main(args)
    else:
        while True:
            main(args)
            logger.info('#####***** Loop sleep {} seconds ...'.format(args.loop_interval)) # noqa
            time.sleep(args.loop_interval)

"""
# noqa
python xcreate.py --auto_like --auto_appeal --sleep_sec_min=30 --sleep_sec_max=60 --loop_interval=60
python xcreate.py --auto_like --auto_appeal --sleep_sec_min=600 --sleep_sec_max=1800 --loop_interval=180
python xcreate.py --auto_like --auto_appeal --sleep_sec_min=60 --sleep_sec_max=180
python xcreate.py --auto_like --auto_appeal --sleep_sec_min=120 --sleep_sec_max=360
python xcreate.py --auto_like --auto_appeal --sleep_sec_min=180 --sleep_sec_max=360 --headless

python xcreate.py --auto_like --auto_appeal --profile=g05
python xcreate.py --auto_like --auto_appeal --force --profile=g05

python xcreate.py --auto_like --auto_appeal --force --headless --profile=t33

python xcreate.py --auto_like --auto_appeal --force --create --no-headless --profile=g95

python xcreate.py --create --no-headless --force --vpn=gcp-g01-tw --email=gcpsleep@xxone.xyz --profile=b101

python xcreate.py --create --no-headless --reset_profile --vpn=gcp-g03-kr --no_auto_vpn --email=@xxone.xyz --profile=b303
"""
