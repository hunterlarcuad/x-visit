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
from datetime import timedelta

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

# from conf import TZ_OFFSET
from conf import DEL_PROFILE_DIR

from conf import FILENAME_LOG
from conf import logger

# gm Check-in use UTC Time
# TZ_OFFSET = 0
TZ_OFFSET = 8

DEF_INSUFFICIENT_ETH = 'Insufficient ETH balance'
DEF_SUCCESS = 'Success'
DEF_FAIL = 'Fail'

"""
2025.05.17
"""


class ClsArbUtil():
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
        self.DEF_HEADER_STATUS = 'account,arb_eth,arb_usd,task_status,complete_date,update_time' # noqa
        self.IDX_BALANCE_ETH = 1
        self.IDX_BALANCE_USD = 2
        self.IDX_TASK_STATUS = 3
        self.IDX_TASK_DATE = 4
        self.IDX_UPDATE = 5
        self.FIELD_NUM = self.IDX_UPDATE + 1

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
        # filename = self.args.url.split('/')[-1]
        filename = 'arb-rari'
        self.file_status = f'{DEF_PATH_DATA_STATUS}/layer3/{filename}.csv'

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
        # self.is_update = True

    def get_status_by_idx(self, idx_status, s_profile=None):
        if s_profile is None:
            s_profile = self.args.s_profile

        s_val = ''
        lst_pre = self.dic_status.get(s_profile, [])
        if len(lst_pre) == self.FIELD_NUM:
            try:
                # s_val = int(lst_pre[idx_status])
                s_val = lst_pre[idx_status]
            except: # noqa
                pass

        return s_val

    def update_date(self, idx_status, update_ts=None):
        if not update_ts:
            update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)

        claim_date = update_time[:10]

        self.update_status(idx_status, claim_date)

    def get_eth_amount(self, s_path):
        tab = self.browser.latest_tab
        tab.wait(10)
        # s_path = 'x://*[@id="root"]/div/div[1]/div/div/div[2]/div[1]/div[2]/form/div[2]/div[1]/div/div[3]/div[2]/span[2]'
        ele_info = tab.ele(s_path, timeout=2)
        if not isinstance(ele_info, NoneElement):
            s_text = ele_info.text
            self.logit('get_eth_amount', f'ETH amount: {s_text}')
            try:
                f_amount = float(s_text)
                return f_amount
            except Exception as e: # noqa
                self.logit('get_eth_amount', f'Exception: {e}')
                return 0
        return 0

    def check_understand(self, tab):
        ele_blk = tab.ele('@@tag()=div@@data-headlessui-state=open@@aria-modal=true', timeout=2) # noqa
        if not isinstance(ele_blk, NoneElement):
            ele_btns = ele_blk.eles('@@tag()=button@@aria-checked=false', timeout=2) # noqa
            if len(ele_btns) > 0:
                for ele_btn in ele_btns:
                    if ele_btn.wait.clickable(timeout=3):
                        ele_btn.click(by_js=True)
                        tab.wait(1)
            ele_btn = ele_blk.ele('@@tag()=button@@aria-label=Dialog Continue', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                if ele_btn.wait.clickable(timeout=3):
                    ele_btn.click(by_js=True)
                    tab.wait(1)

    def switch_tab(self, tab, s_tab_name):
        ele_btn = tab.ele(f'@@tag()=button@@aria-label={s_tab_name}', timeout=2) # noqa
        if not isinstance(ele_btn, NoneElement):
            ele_btn.wait.clickable(timeout=3)
            ele_btn.click(by_js=True)
            self.logit(None, f'Switch to tab: {s_tab_name}')
            tab.wait(1)

    def exist_pending_tx(self):
        tab = self.browser.latest_tab
        # 是否出现 You have 1 pending transaction
        ele_info = tab.ele('@@tag()=span@@text():You have', timeout=2)
        if not isinstance(ele_info, NoneElement):
            s_text = ele_info.text
            self.logit(None, f'Transaction result: {s_text}')
            return s_text
        return None

    def bridge_from_rari_mainnet_to_arb(self):
        n_tab = self.browser.tabs_count
        tab = self.browser.latest_tab
        f_fee_keep = 0

        for i in range(1, DEF_NUM_TRY+1):
            self.logit('bridge_from_rari_mainnet_to_arb', f'trying ... {i}/{DEF_NUM_TRY}')

            if self.browser.tabs_count > n_tab:
                self.inst_okx.okx_cancel()

            # Agree to Terms and Continue
            ele_btn = tab.ele('@@tag()=span@@class=truncate', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                s_text = ele_btn.text
                self.logit(None, f'Agree button: {s_text}')
                if s_text == 'Agree to Terms and Continue':
                    ele_btn.wait.clickable(timeout=3)
                    ele_btn.click(by_js=True)
                    tab.wait(1)

            # Connect Wallet
            ele_btn = tab.ele('@@tag()=button@@text()=Connect Wallet', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.clickable(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait(1)

                ele_btn = tab.ele('@@tag()=div@@text()=OKX Wallet', timeout=2)
                if not isinstance(ele_btn, NoneElement):
                    if ele_btn.wait.clickable(timeout=5):
                        ele_btn.click()

                if self.inst_okx.wait_popup(n_tab+1, 10):
                    tab.wait(2)
                    self.inst_okx.okx_connect()
                    self.inst_okx.wait_popup(n_tab, 5)

            # Switch to Transaction History Tab
            self.switch_tab(tab, 'Switch to Transaction History Tab')

            # 是否出现 You have 1 pending transaction
            s_text = self.exist_pending_tx()
            if s_text is not None:
                ele_info = tab.ele('.flex justify-center px-3 align-middle', timeout=2)
                if not isinstance(ele_info, NoneElement):
                    s_text = ele_info.text.replace('\n', ' ')
                    self.logit(None, f'Transaction result: {s_text}')
                    self.update_status(self.IDX_TASK_STATUS, s_text)
                    self.update_status(self.IDX_TASK_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                    return DEF_SUCCESS

            # Switch to Bridge Tab
            self.switch_tab(tab, 'Switch to Bridge Tab')

            # Click MAX Button
            ele_btn = tab.ele('@@tag()=button@@text()=MAX', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                if ele_btn.wait.clickable(timeout=3):
                    ele_btn.click(by_js=True)
                    tab.wait(3)

            # s_path = 'x://*[@id="headlessui-tabs-panel-:r4:"]/div/div[1]/div[1]/div/div[2]/div[2]/div/div/div/div/span[2]'
            s_path = '.whitespace-nowrap text-sm text-white'
            f_eth_amount = self.get_eth_amount(s_path)
            # Max Ammount
            # s_path = 'x://*[@id="headlessui-tabs-panel-:r4:"]/div/div[1]/div[1]/div/div[2]/div[2]/div/div/input'
            s_path = '.h-full w-full bg-transparent px-3 text-xl font-light text-white placeholder:text-gray-300 sm:text-3xl'
            ele_input = tab.ele(s_path, timeout=2)
            if not isinstance(ele_input, NoneElement):
                max_amount = ele_input.value
                try:
                    f_max_amount = float(max_amount)
                except Exception as e: # noqa
                    self.logit(None, f'Exception: {e}')
                    continue
                if f_max_amount <= 0.0002:
                    self.logit(None, 'Insufficient ETH balance')
                    self.update_status(self.IDX_TASK_STATUS, 'Insufficient ETH balance')
                    self.update_status(self.IDX_TASK_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                    return DEF_INSUFFICIENT_ETH

                # Keep 0.00002 ETH ($0.05) For Gas
                f_amount = f_max_amount - 0.00002 - f_fee_keep
                f_amount = round(f_amount, 5)
                s_fee_keep = f"{f_fee_keep:.8f}"
                self.logit(None, f'Bridge amount: {f_amount} [f_fee_keep={s_fee_keep}]')

                if f_amount >= f_eth_amount:
                    self.logit(None, f'Insufficient ETH balance: {f_eth_amount}')
                    self.update_status(self.IDX_TASK_STATUS, 'Insufficient ETH balance')
                    self.update_status(self.IDX_TASK_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                    return DEF_INSUFFICIENT_ETH

                ele_input.click.multi(times=2)
                tab.wait(1)
                ele_input.clear(by_js=True)
                tab.wait(1)
                tab.actions.move_to(ele_input).click().type(f_amount) # noqa
                tab.wait(1)
                if ele_input.value != str(f_amount):
                    continue
            else:
                self.logit(None, f'Input element is not found')
                continue

            # Move funds to Arbitrum One
            ele_btn = tab.ele('@@tag()=button@@text()=Move funds to Arbitrum One', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.clickable(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait(1)
                self.check_understand(tab)

                if self.inst_okx.wait_popup(n_tab+1, 10):
                    tab.wait(2)
                    try:
                        # Approve
                        if self.inst_okx.okx_approve():
                            self.logit(None, 'Approve Confirm')
                            self.inst_okx.wait_popup(n_tab, 15)
                            tab.wait(3)

                        self.check_understand(tab)

                        # Confirm
                        (is_success, f_fee, s_info) = self.inst_okx.okx_confirm_by_fee(max_fee=self.args.max_fee)
                        self.inst_okx.wait_popup(n_tab, 15)
                        tab.wait(2)
                        if is_success:
                            self.logit(None, 'Bridge Confirm Success')
                            self.is_update = True
                        else:
                            self.logit(None, f'Fail info: {s_info}')
                            self.update_status(self.IDX_TASK_STATUS, s_info)
                            self.update_status(self.IDX_TASK_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                            if s_info == self.inst_okx.INFO_NOT_ENOUGH_TO_COVER_FEE:
                                f_fee_keep = f_fee

                    except Exception as e: # noqa
                        self.logit('bridge_from_rari_mainnet_to_arb', f'okx_confirm Exception: {e}') # noqa
                        continue

            # 如果出现 Internal Server Error ，则刷新页面
            ele_info = tab.ele('@@tag()=h2@@text():Internal Server Error', timeout=2)
            if not isinstance(ele_info, NoneElement):
                s_text = ele_info.text
                self.logit(None, f'Error: {s_text}')
                tab.refresh()
                tab.wait.doc_loaded()
                tab.wait(2)
                continue

        return False

    def exist_claim_info(self):
        tab = self.browser.latest_tab
        # 是否出现 You must claim 1 transaction
        ele_info = tab.ele('@@tag()=span@@text():You must claim', timeout=2)
        if not isinstance(ele_info, NoneElement):
            s_text = ele_info.text
            self.logit(None, f'Pending transactions: {s_text}')
            return s_text
        return None

    def claim_from_rari_mainnet_to_arb(self):
        n_tab = self.browser.tabs_count
        tab = self.browser.latest_tab
        f_fee_keep = 0

        for i in range(1, DEF_NUM_TRY+1):
            self.logit('bridge_from_rari_mainnet_to_arb', f'trying ... {i}/{DEF_NUM_TRY}')

            if self.browser.tabs_count > n_tab:
                self.inst_okx.okx_cancel()

            # Agree to Terms and Continue
            ele_btn = tab.ele('@@tag()=span@@class=truncate', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                s_text = ele_btn.text
                self.logit(None, f'Agree button: {s_text}')
                if s_text == 'Agree to Terms and Continue':
                    ele_btn.wait.clickable(timeout=3)
                    ele_btn.click(by_js=True)
                    tab.wait(1)

            # Connect Wallet
            ele_btn = tab.ele('@@tag()=button@@text()=Connect Wallet', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.clickable(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait(1)

                ele_btn = tab.ele('@@tag()=div@@text()=OKX Wallet', timeout=2)
                if not isinstance(ele_btn, NoneElement):
                    if ele_btn.wait.clickable(timeout=5):
                        ele_btn.click()

                if self.inst_okx.wait_popup(n_tab+1, 10):
                    tab.wait(2)
                    self.inst_okx.okx_connect()
                    self.inst_okx.wait_popup(n_tab, 5)

            # Switch to Transaction History Tab
            self.switch_tab(tab, 'Switch to Transaction History Tab')
            tab.wait.doc_loaded()
            tab.wait(10)

            # 是否出现 You must claim 1 transaction
            s_text = self.exist_claim_info()
            if s_text is not None:
                ele_btn = tab.ele('.flex justify-center px-3 align-middle', timeout=2)
                if not isinstance(ele_btn, NoneElement):
                    s_text = ele_btn.text.replace('\n', ' ')
                    self.logit(None, f'Transaction result: {s_text}')

                    if ele_btn.wait.clickable(timeout=3):
                        ele_btn.click()
                        tab.wait(3)

                        if self.inst_okx.wait_popup(n_tab+1, 10):
                            tab.wait(2)
                            try:
                                # Confirm
                                (is_success, f_fee, s_info) = self.inst_okx.okx_confirm_by_fee(max_fee=self.args.max_fee)
                                self.inst_okx.wait_popup(n_tab, 15)
                                tab.wait(2)
                                if is_success:
                                    self.logit(None, 'Claim Confirm Success')
                                    self.is_update = True
                                    self.update_status(self.IDX_TASK_STATUS, DEF_SUCCESS)
                                    self.update_status(self.IDX_TASK_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                                    return DEF_SUCCESS
                                else:
                                    self.logit(None, f'Fail info: {s_info}')

                            except Exception as e: # noqa
                                self.logit('bridge_from_rari_mainnet_to_arb', f'okx_confirm Exception: {e}') # noqa
                                continue

        return False

    def arbutil_process(self):
        # open layer3 url
        # tab = self.browser.latest_tab
        # tab.get(self.args.url)
        tab = self.browser.new_tab(self.args.url)
        tab.wait.doc_loaded()
        # tab.wait(3)
        # tab.set.window.max()

        if self.args.set_window_size == 'max':
            # 判断窗口是否是最大化
            if tab.rect.window_state != 'maximized':
                # 设置浏览器窗口最大化
                tab.set.window.max()
                self.logit(None, 'Set browser window to maximize')

        # n_try = 8
        n_try = 3
        for i in range(1, n_try+1):
            self.logit('arbutil_process', f'trying ... {i}/{n_try}')

            # s_status = self.bridge_from_rari_mainnet_to_arb()
            s_status = self.claim_from_rari_mainnet_to_arb()
            if s_status == DEF_SUCCESS:
                return True

        return False

    def arbutil_run(self):
        self.browser = self.inst_dp.get_browser(self.args.s_profile)

        self.inst_okx.set_browser(self.browser)

        if self.inst_okx.init_okx(is_bulk=True) is False:
            return False

        self.arbutil_process()

        s_chain = 'Arbitrum One'
        s_coin = 'ARB_ETH'
        (s_balance_coin, s_balance_usd) = self.inst_okx.get_balance_by_chain_coin(s_chain, s_coin)
        self.logit(None, f'Balance: {s_balance_coin} {s_balance_usd} [{s_chain}][{s_coin}]')
        self.update_status(self.IDX_BALANCE_ETH, s_balance_coin)
        self.update_status(self.IDX_BALANCE_USD, s_balance_usd)

        if self.args.manual_exit:
            s_msg = 'Manual Exit. Press any key to exit! ⚠️' # noqa
            input(s_msg)

        self.logit('arbutil_run', 'Finished!')

        return True


def send_msg(inst_arbutil, lst_success):
    if len(DEF_DING_TOKEN) > 0 and len(lst_success) > 0:
        s_info = ''
        for s_profile in lst_success:
            lst_status = None
            if s_profile in inst_arbutil.dic_status:
                lst_status = inst_arbutil.dic_status[s_profile]

            if lst_status is None:
                lst_status = [s_profile, -1]

            s_info += '- {},{}\n'.format(
                s_profile,
                lst_status[inst_arbutil.IDX_TASK_STATUS],
            )
        d_cont = {
            'title': 'Layer3 Task Finished! [layer3]',
            'text': (
                'Layer3 Task\n'
                '- account,task_status\n'
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

    inst_arbutil = ClsArbUtil()
    inst_arbutil.set_args(args)

    args.s_profile = 'ALL'
    inst_arbutil.inst_okx.set_args(args)
    inst_arbutil.inst_okx.purse_load(args.decrypt_pwd)

    # 检查 profile 参数冲突
    if args.profile and (args.profile_begin is not None or args.profile_end is not None):
        logger.info('参数 --profile 与 --profile_begin/--profile_end 不能同时使用！')
        sys.exit(1)

    if len(args.profile) > 0:
        items = args.profile.split(',')
    elif args.profile_begin is not None and args.profile_end is not None:
        # 生成 profile_begin 到 profile_end 的 profile 列表
        prefix = re.match(r'^[a-zA-Z]+', args.profile_begin).group()
        start_num = int(re.search(r'\d+', args.profile_begin).group())
        end_num = int(re.search(r'\d+', args.profile_end).group())
        num_width = len(re.search(r'\d+', args.profile_begin).group())
        items = [f"{prefix}{str(i).zfill(num_width)}" for i in range(start_num, end_num + 1)]
        logger.info(f'Profile list: {items}')
    else:
        # 从配置文件里获取钱包名称列表
        items = list(inst_arbutil.inst_okx.dic_purse.keys())

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
            if len(lst_status) < inst_arbutil.FIELD_NUM:
                return False

            if args.only_gm:
                if date_now != lst_status[inst_arbutil.IDX_GM_DATE]:
                    b_ret = b_ret and False
            else:
                idx_status = inst_arbutil.IDX_TASK_STATUS
                lst_status_ok = ['Activation Completed', 'Not enough ETH', 'Success']
                if lst_status[idx_status] in lst_status_ok:
                    b_complete = True
                else:
                    b_complete = False
                b_ret = b_ret and b_complete

        else:
            b_ret = False

        return b_ret

    # 将已完成的剔除掉
    inst_arbutil.status_load()
    # 从后向前遍历列表的索引
    for i in range(len(profiles) - 1, -1, -1):
        s_profile = profiles[i]
        if s_profile in inst_arbutil.dic_status:
            lst_status = inst_arbutil.dic_status[s_profile]

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

        if percent > args.max_percent:
            logger.info(f'Progress is more than threshold {percent}% > {args.max_percent}% [{n}/{total}] [{s_profile}]')
            break

        profiles.remove(s_profile)

        args.s_profile = s_profile

        if s_profile not in inst_arbutil.inst_okx.dic_purse:
            logger.info(f'{s_profile} is not in okx account conf [ERROR]')
            sys.exit(0)

        # 如果出现异常(与页面的连接已断开)，增加重试
        max_try_except = 3
        for j in range(1, max_try_except+1):
            try:
                if j > 1:
                    logger.info(f'⚠️ 正在重试，当前是第{j}次执行，最多尝试{max_try_except}次 [{s_profile}]') # noqa

                inst_arbutil.set_args(args)
                inst_arbutil.inst_dp.set_args(args)
                inst_arbutil.inst_okx.set_args(args)

                if not args.no_x:
                    inst_arbutil.inst_x.set_args(args)

                if s_profile in inst_arbutil.dic_status:
                    lst_status = inst_arbutil.dic_status[s_profile]
                else:
                    lst_status = None

                if is_complete(lst_status):
                    logger.info(f'[{s_profile}] Last update at {lst_status[inst_arbutil.IDX_UPDATE]}') # noqa
                    break
                else:
                    b_ret = inst_arbutil.arbutil_run()
                    inst_arbutil.close()
                    if b_ret:
                        lst_success.append(s_profile)
                        break

            except Exception as e:
                logger.info(f'[{s_profile}] An error occurred: {str(e)}')
                inst_arbutil.close()
                if j < max_try_except:
                    time.sleep(5)

        if inst_arbutil.is_update is False:
            continue

        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile} Finish]')
        if percent > args.max_percent:
            continue

        if len(profiles) > 0:
            sleep_time = random.randint(args.sleep_sec_min, args.sleep_sec_max)
            if sleep_time > 60:
                logger.info('sleep {} minutes ...'.format(int(sleep_time/60)))
            else:
                logger.info('sleep {} seconds ...'.format(int(sleep_time)))

            # 输出下次执行时间，格式为 YYYY-MM-DD HH:MM:SS
            next_exec_time = datetime.now() + timedelta(seconds=sleep_time)
            logger.info(f'next_exec_time: {next_exec_time.strftime("%Y-%m-%d %H:%M:%S")}')
            time.sleep(sleep_time)

    send_msg(inst_arbutil, lst_success)


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
        '--profile_begin', required=False, default=None,
        help='按指定的 profile 开始后缀(包含) eg: g01'
    )
    parser.add_argument(
        '--profile_end', required=False, default=None,
        help='按指定的 profile 结束后缀(包含) eg: g05'
    )

    parser.add_argument(
        '--decrypt_pwd', required=False, default='',
        help='decrypt password'
    )
    # 不使用 X
    parser.add_argument(
        '--no_x', required=False, action='store_true',
        help='Not use X account'
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
        help='okx layer3 url'
    )
    parser.add_argument(
        '--get_task_status', required=False, action='store_true',
        help='Check task result'
    )
    # 添加 --max_percent 参数
    parser.add_argument(
        '--max_percent', required=False, default=100, type=int,
        help='[默认为 100] 执行的百分比'
    )
    parser.add_argument(
        '--only_gm', required=False, action='store_true',
        help='Only do gm checkin'
    )
    parser.add_argument(
        '--set_window_size', required=False, default='normal',
        help='[默认为 normal] 窗口大小，normal 为正常，max 为最大化'
    )
    # add --task_type
    parser.add_argument(
        '--task_type', required=False, default='bridge',
        help='[默认为 bridge] 任务类型，bridge 为桥接'
    )
    # add --max_fee
    parser.add_argument(
        '--max_fee', required=False, default=0.00003, type=float,
        help='[默认为 0.00003] Max network fee'
    )

    args = parser.parse_args()
    show_msg(args)

    if args.only_gm:
        args.no_x = True
        logger.info('-'*40)
        logger.info('Only do gm checkin, set no_x=True')

    if args.loop_interval <= 0:
        main(args)
    elif len(args.profile) > 0:
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
2025.06.02
Bridge from rari to arbitrum
https://bridge.arbitrum.io/?destinationChain=arbitrum-one&sourceChain=rari-mainnet
https://bridge.arbitrum.io/?destinationChain=arbitrum-one&sourceChain=rari-mainnet&tab=tx_history

python arbitrum.py --url='https://bridge.arbitrum.io/?destinationChain=arbitrum-one&sourceChain=rari-mainnet' --task_type=bridge  --max_fee=0.00017 --profile=g01
"""
