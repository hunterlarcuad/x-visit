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

from DrissionPage import ChromiumOptions
from DrissionPage import Chromium
from DrissionPage._elements.none_element import NoneElement

from fun_utils import ding_msg
from fun_utils import load_file
from fun_utils import save2file
from fun_utils import format_ts
from fun_utils import get_index_from_header

from fun_okx import OkxUtils
from fun_x import XUtils
from fun_dp import DpUtils

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
2025.04.23
"""


class ClsActivity():
    def __init__(self) -> None:
        self.args = None

        self.file_status = None

        # 是否有更新
        self.is_update = False

        # 账号执行情况
        self.dic_status = {}
        self.dic_account = {}

        self.inst_okx = OkxUtils()
        self.inst_dp = DpUtils()
        self.inst_x = XUtils()

        self.inst_dp.plugin_yescapcha = True
        self.inst_dp.plugin_capmonster = True
        self.inst_dp.plugin_okx = True

        # output
        self.DEF_HEADER_STATUS = 'account,status,update_time' # noqa
        self.IDX_STATUS = 1
        self.IDX_UPDATE = 2
        self.FIELD_NUM = self.IDX_UPDATE + 1

        self.STATUS_SUCCESS = 'SUCCESS'
        self.STATUS_FAIL = 'FAIL'

    def set_args(self, args):
        self.args = args
        self.is_update = False

    def __del__(self):
        pass
        # self.status_save()

    def get_status_file(self):
        if not self.args.url:
            logger.info('Invalid self.args.url')
            sys.exit(-1)
        filename = self.args.url.split('/')[-1]
        self.file_status = f'{DEF_PATH_DATA_STATUS}/xactivity/{filename}.csv'

    def status_load(self):
        if self.file_status is None:
            self.get_status_file()

        self.dic_status = load_file(
            file_in=self.file_status,
            idx_key=0,
            header=self.DEF_HEADER_STATUS
        )

    def status_save(self):
        save2file(
            file_ot=self.file_status,
            dic_status=self.dic_status,
            idx_key=0,
            header=self.DEF_HEADER_STATUS
        )

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
            for i in range(1, self.FIELD_NUM):
                self.dic_status[self.args.s_profile].append('')

        if self.args.s_profile not in self.dic_status:
            init_status()
        if len(self.dic_status[self.args.s_profile]) != self.FIELD_NUM:
            init_status()
        if self.dic_status[self.args.s_profile][idx_status] == s_value:
            return

        self.dic_status[self.args.s_profile][idx_status] = s_value
        self.dic_status[self.args.s_profile][self.IDX_UPDATE] = update_time

        self.status_save()
        self.is_update = True

    def get_status_by_idx(self, idx_status, s_profile=None):
        if s_profile is None:
            s_profile = self.args.s_profile

        s_val = ''
        lst_pre = self.dic_status.get(s_profile, [])
        if len(lst_pre) == self.FIELD_NUM:
            try:
                s_val = int(lst_pre[idx_status])
            except: # noqa
                pass

        return s_val

    def update_date(self, idx_status, update_ts=None):
        if not update_ts:
            update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)

        claim_date = update_time[:10]

        self.update_status(idx_status, claim_date)

    def xactivity_process(self):
        # idx_addr = get_index_from_header(DEF_HEADER_ACCOUNT, 'evm_address')
        # s_reply = self.inst_okx.dic_purse[self.args.s_profile][idx_addr]

        s_reply = self.addr

        # s_reply = f'''invoke://OG/
        # {self.addr}
        # /sig-38b7xt9mJp
        # Verifying code integrity
        # Direct access granted: Phase-X
        # Connection secure, awaiting input'''

        for i in range(1, DEF_NUM_TRY+1):
            self.logit('xactivity_process', f'trying ... {i}/{DEF_NUM_TRY}')

            tab = self.browser.latest_tab
            tab.get(self.args.url)
            tab.wait.doc_loaded()

            ele_btn = tab.ele('@@tag()=a@@data-testid=login', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit(None, f'Click Log in Button: [{s_info}]') # noqa
                ele_btn.click(by_js=True)
                tab.wait(5)
                self.inst_x.twitter_run()
                continue

            if self.inst_x.x_reply(s_reply) is True:
                self.update_status(self.IDX_STATUS, self.STATUS_SUCCESS)
            else:
                self.update_status(self.IDX_STATUS, self.STATUS_FAIL)
                continue

            self.inst_x.x_like()
            self.inst_x.x_retweet()

            s_name = self.args.url.split('/')[3]

            self.inst_x.x_follow(s_name)

            return True

        return False

    def xactivity_run(self):
        self.browser = self.inst_dp.get_browser(self.args.s_profile)

        self.inst_okx.set_browser(self.browser)

        if self.inst_okx.init_okx(is_bulk=True) is False:
            return False

        self.addr = self.inst_okx.get_addr_by_chain('Solana', 'SOL')
        # self.addr = self.inst_okx.get_addr_by_chain('Bitcoin', 'BTC')

        self.inst_x.status_load()
        self.inst_x.set_browser(self.browser)

        idx_vpn = get_index_from_header(DEF_HEADER_ACCOUNT, 'proxy')
        s_vpn = self.inst_x.dic_account[self.args.s_profile][idx_vpn]
        if self.inst_dp.set_vpn(s_vpn) is False:
            return False

        if self.inst_dp.init_capmonster() is False:
            return False

        if self.inst_dp.init_yescaptcha() is False:
            return False

        if self.args.force is False:
            if self.args.s_profile in self.inst_x.dic_status:
                x_status = self.inst_x.dic_status[self.args.s_profile][self.inst_x.IDX_STATUS] # noqa
                if not x_status:
                    pass
                elif x_status != self.inst_x.DEF_STATUS_OK:
                    self.logit('xactivity_run', f'x_status is {x_status}')
                    self.update_status(self.IDX_STATUS, x_status)
                    return True
        self.inst_x.twitter_run()

        self.xactivity_process()

        self.logit('xactivity_run', 'Finished!')

        return True


def send_msg(inst_xactivity, lst_success):
    if len(DEF_DING_TOKEN) > 0 and len(lst_success) > 0:
        s_info = ''
        for s_profile in lst_success:
            lst_status = None
            if s_profile in inst_xactivity.dic_status:
                lst_status = inst_xactivity.dic_status[s_profile]

            if lst_status is None:
                lst_status = [s_profile, -1]

            s_info += '- {},{}\n'.format(
                s_profile,
                lst_status[inst_xactivity.IDX_STATUS],
            )
        d_cont = {
            'title': 'Daily Check-In Finished! [xactivity]',
            'text': (
                'Daily Check-In [xactivity]\n'
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
    if args.sleep_sec_at_start > 0:
        logger.info(f'Sleep {args.sleep_sec_at_start} seconds at start !!!') # noqa
        time.sleep(args.sleep_sec_at_start)

    if DEL_PROFILE_DIR and os.path.exists(DEF_PATH_USER_DATA):
        logger.info(f'Delete {DEF_PATH_USER_DATA} ...')
        shutil.rmtree(DEF_PATH_USER_DATA)
        logger.info(f'Directory {DEF_PATH_USER_DATA} is deleted') # noqa

    inst_xactivity = ClsActivity()
    inst_xactivity.set_args(args)

    if len(args.profile) > 0:
        items = args.profile.split(',')
    else:
        # 从配置文件里获取钱包名称列表
        items = list(inst_xactivity.inst_okx.dic_purse.keys())

    profiles = copy.deepcopy(items)

    # 每次随机取一个出来，并从原列表中删除，直到原列表为空
    total = len(profiles)
    n = 0

    lst_success = []

    def is_complete(lst_status):
        if args.force:
            return False

        b_ret = True
        # date_now = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)

        if lst_status:
            # if date_now != lst_status[inst_xactivity.IDX_UPDATE][:10]:
            #     b_ret = b_ret and False

            for idx_status in [inst_xactivity.IDX_STATUS]:
                if lst_status[idx_status] in [inst_xactivity.STATUS_SUCCESS]:
                    b_complete = True
                else:
                    b_complete = False

                b_ret = b_ret and b_complete
        else:
            b_ret = False

        return b_ret

    # 将已完成的剔除掉
    inst_xactivity.status_load()
    # 从后向前遍历列表的索引
    for i in range(len(profiles) - 1, -1, -1):
        s_profile = profiles[i]
        if s_profile in inst_xactivity.dic_status:
            lst_status = inst_xactivity.dic_status[s_profile]

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

        if s_profile not in inst_xactivity.inst_okx.dic_purse:
            logger.info(f'{s_profile} is not in okx account conf [ERROR]')
            sys.exit(0)

        # 如果出现异常(与页面的连接已断开)，增加重试
        max_try_except = 3
        for j in range(1, max_try_except+1):
            try:
                if j > 1:
                    logger.info(f'⚠️ 正在重试，当前是第{j}次执行，最多尝试{max_try_except}次 [{s_profile}]') # noqa

                inst_xactivity.set_args(args)
                inst_xactivity.inst_dp.set_args(args)
                inst_xactivity.inst_x.set_args(args)
                inst_xactivity.inst_okx.set_args(args)

                if s_profile in inst_xactivity.dic_status:
                    lst_status = inst_xactivity.dic_status[s_profile]
                else:
                    lst_status = None

                if is_complete(lst_status):
                    logger.info(f'[{s_profile}] Last update at {lst_status[inst_xactivity.IDX_UPDATE]}') # noqa
                    break
                else:
                    b_ret = inst_xactivity.xactivity_run()
                    inst_xactivity.close()
                    if b_ret:
                        lst_success.append(s_profile)
                        break

            except Exception as e:
                logger.info(f'[{s_profile}] An error occurred: {str(e)}')
                inst_xactivity.close()
                if j < max_try_except:
                    time.sleep(5)

        if inst_xactivity.is_update is False:
            continue

        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile} Finish]')

        if len(profiles) > 0:
            sleep_time = random.randint(args.sleep_sec_min, args.sleep_sec_max)
            if sleep_time > 60:
                logger.info('sleep {} minutes ...'.format(int(sleep_time/60)))
            else:
                logger.info('sleep {} seconds ...'.format(int(sleep_time)))
            time.sleep(sleep_time)

    send_msg(inst_xactivity, lst_success)


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
        '--url', required=False, default='',
        help='okx xactivity url'
    )
    parser.add_argument(
        '--get_task_status', required=False, action='store_true',
        help='Check task result'
    )

    args = parser.parse_args()
    show_msg(args)
    if args.loop_interval <= 0:
        main(args)
    else:
        while True:
            main(args)

            if args.get_task_status:
                break

            logger.info('#####***** Loop sleep {} seconds ...'.format(args.loop_interval)) # noqa
            time.sleep(args.loop_interval)

"""
# noqa
python xactivity.py --auto_like --auto_appeal --sleep_sec_min=30 --sleep_sec_max=60 --loop_interval=60
python xactivity.py --auto_like --auto_appeal --sleep_sec_min=600 --sleep_sec_max=1800 --loop_interval=180
python xactivity.py --auto_like --auto_appeal --sleep_sec_min=60 --sleep_sec_max=180
python xactivity.py --auto_like --auto_appeal --sleep_sec_min=120 --sleep_sec_max=360

python xactivity.py --auto_like --auto_appeal --profile=g05
python xactivity.py --auto_like --auto_appeal --force --profile=g05

python xactivity.py --auto_like --auto_appeal --force --profile=t33

python xactivity.py --auto_like --auto_appeal --force --url=https://x.com/mooarofficial/status/1914707322145824819 --profile=g03
python xactivity.py --auto_like --auto_appeal --url=https://x.com/mooarofficial/status/1914707322145824819 --profile=g28

python xactivity.py --auto_like --headless --url=https://x.com/mooarofficial/status/1914707322145824819

python xactivity.py --auto_like --url=https://x.com/BRCRWA/status/1915224423659114709 --profile=g05
python xactivity.py --auto_like --headless --url=https://x.com/BRCRWA/status/1915224423659114709 --profile=g05

python xactivity.py --auto_like --url=https://x.com/MagicEden/status/1915751335858733209 --profile=g05

python xactivity.py --auto_like --url=https://x.com/miossol/status/1916418607698805031 --profile=g05

# 2025.05.14
python xactivity.py --auto_like --url=https://x.com/pigmo_co/status/1922557162217148477 --sleep_sec_min=60 --sleep_sec_max=360 --headless
"""
