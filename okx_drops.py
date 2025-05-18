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
2025.04.18
"""


class ClsDrops():
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
        self.file_status = f'{DEF_PATH_DATA_STATUS}/drops/{filename}.csv'

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

    def set_lang(self):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('set_lang', f'trying ... {i}/{DEF_NUM_TRY}')
            tab = self.browser.latest_tab
            ele_btn = tab.ele('.nav-item nav-language other-wrap', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                self.logit(None, 'Click language setting button ...') # noqa
                if ele_btn.states.is_clickable:
                    ele_btn.click()
                    tab.wait(2)
                else:
                    self.logit(None, 'language setting button is not clickable ...') # noqa

            ele_blk = tab.ele('.oxnv-dialog-container', timeout=2)
            if not isinstance(ele_blk, NoneElement):
                ele_btn = ele_blk.ele('@@tag()=a@@id=language_zh_CN', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    if 'item selected' == ele_btn.attr('class'):
                        ele_close = tab.ele('#okdDialogCloseBtn', timeout=1)
                        if not isinstance(ele_close, NoneElement):
                            ele_close.click(by_js=True)
                    else:
                        self.logit(None, 'Click language setting button ...') # noqa
                        ele_btn.click(by_js=True)
                        tab.wait(1)
                    return True
            self.logit(None, 'Language elements not found [ERROR]') # noqa
            tab.wait(1)

            if i > DEF_NUM_TRY/2:
                tab.set.window.max()
                self.logit(None, 'set.window.max') # noqa

        self.logit(None, 'Fail to set language [ERROR]') # noqa
        return False

    def connect_wallet(self):
        for i in range(1, DEF_NUM_TRY+1):
            tab = self.browser.latest_tab
            ele_btn = tab.ele('.nav-item nav-address', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit(None, f'Connect Wallet Button Text: {s_info}') # noqa
                if s_info == '连接钱包':
                    ele_btn = tab.ele('@@tag()=div@@class:connect-wallet-button', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        ele_btn.wait.enabled(timeout=5)
                        ele_btn.wait.clickable(timeout=5)
                        ele_btn.click(by_js=True)
                        tab.wait(5)
                else:
                    return True

                # Connect Wallet Button
                lst_path = [
                    '@@tag()=div@@class:Connect_title',  # pc
                    '@@tag()=div@@class:wallet-dialog-title-block'  # mobile
                ]
                ele_btn = self.inst_dp.get_ele_btn(self.browser.latest_tab, lst_path) # noqa
                if ele_btn is not NoneElement:
                    ele_btn.wait.clickable(timeout=5).click(by_js=True)
                    tab.wait(2)

                # wallet list
                lst_path = [
                    '@@tag()=button@@class:wallet-btn',  # pc
                    '@@tag()=button@@class:wallet-plain-button'  # mobile
                ]
                ele_btn = self.inst_dp.get_ele_btn(self.browser.latest_tab, lst_path) # noqa
                if ele_btn is not NoneElement:
                    n_tab = self.browser.tabs_count
                    ele_btn.wait.clickable(timeout=5).click(by_js=True)
                    self.inst_okx.wait_popup(n_tab+1, 10)
                    tab.wait(2)
                    self.inst_okx.okx_connect()
                    self.inst_okx.wait_popup(n_tab, 10)

            self.logit('connect_wallet', f'trying ... {i}/{DEF_NUM_TRY}')
            tab.wait(2)

        return False

    def okx_verify_click(self):
        # geetest_text_tips
        tab = self.browser.latest_tab
        ele_btn = tab.ele('@@tag()=div@@class:geetest_text_tips', timeout=1) # noqa
        if not isinstance(ele_btn, NoneElement):
            s_text = ele_btn.text
            self.logit(None, f'Verify Manual: {s_text}')
            return True
        return False

    def connect_x(self):
        n_tab = self.browser.tabs_count
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('connect_x', f'trying ... {i}/{DEF_NUM_TRY}')
            if self.okx_verify_click():

                s_msg = f'[{self.args.s_profile}] OKX Graphic captcha challenge [TODO]' # noqa
                ding_msg(s_msg, DEF_DING_TOKEN, msgtype='text')

                b_manual = True
                max_wait_sec = 300
                i = 0
                while i < max_wait_sec:
                    i += 1
                    if self.okx_verify_click() is False:
                        self.logit(None, 'OKX Graphic captcha challenge is success') # noqa
                        b_manual = False
                        s_msg = f'[{self.args.s_profile}] OKX Graphic captcha challenge [Success]' # noqa
                        ding_msg(s_msg, DEF_DING_TOKEN, msgtype='text')
                        break
                    self.browser.wait(1)

                if b_manual:
                    s_msg = 'Manual captcha challenge. Press any key to continue! ⚠️' # noqa
                    input(s_msg)

            tab = self.browser.latest_tab
            ele_btn = tab.ele('@@tag()=button@@class:btn-outline-primary', timeout=1) # noqa
            if not isinstance(ele_btn, NoneElement):
                s_text = ele_btn.text.replace('\n', ' ')
                self.logit(None, f'connect_x Button Status: {s_text}')
                if s_text in ['连接中 加载中']:
                    # 连接账号
                    # 请注意钱包地址限定绑定一个 X 账号，完成任务后不可解除绑定
                    ele_btn = tab.ele('@@tag()=button@@data-testid=okd-dialog-confirm-btn', timeout=1) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        s_text = ele_btn.text
                        self.logit(None, f'connect_x Button Status: {s_text}')
                        ele_btn.wait.clickable(timeout=5).click(by_js=True)
                        # Popup X window
                        self.inst_okx.wait_popup(n_tab+1, 30)
                    else:
                        tab.wait(10)
                elif s_text in ['连接', 'Cancel']:
                    tab.actions.move_to(ele_btn)
                    try:
                        ele_btn.wait.clickable(timeout=5).click(by_js=True)
                        self.logit(None, 'connect_x Button Clicked ...')
                        self.inst_okx.wait_popup(n_tab+1, 20)

                        tab.wait(2)
                        if self.inst_okx.okx_confirm():
                            self.logit(None, 'Signature request Confirm')
                            self.inst_okx.wait_popup(n_tab, 15)
                            tab.wait(3)
                            continue
                    except: # noqa
                        continue
                elif s_text in ['断开连接', '已连接']:
                    self.logit(None, 'connect_x success')
                    return True
            if self.browser.tabs_count == (n_tab + 1):
                self.inst_x.confirm_error()
                if self.inst_x.should_sign_in():
                    # 关闭登录弹窗
                    self.browser.latest_tab.close()
                    # 新打开一个标签页
                    self.browser.new_tab()
                    self.inst_x.xutils_login()
                    # 登录后再关闭 X 页面
                    self.browser.latest_tab.close()
                    continue

                self.inst_x.x_authorize_app()
                self.inst_okx.wait_popup(n_tab, 10)
                tab.wait(3)
        return False

    def get_task_result(self):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('get_task_result', f'trying ... {i}/{DEF_NUM_TRY}')
            ele_btn = self.get_verify_btn()
            if ele_btn is not NoneElement:
                s_text = ele_btn.text.replace('\n', ' ')
                self.logit(None, f'Button text: {s_text}')
                self.update_status(self.IDX_STATUS, s_text)

                return s_text
            self.browser.wait(2)
        return None

    def process_btn(self, ele_btn):
        s_text = ele_btn.text
        self.logit(None, f'Button text: {s_text}')
        tab = self.browser.latest_tab
        n_tab = self.browser.tabs_count
        ele_btn.wait.clickable(timeout=5).click(by_js=True)
        if self.inst_okx.wait_popup(n_tab+1, 10) is False:
            return False

        # Change to popup window
        tab = self.browser.latest_tab
        if tab.url.find('x.com/intent/follow') >= 0:
            name = tab.url.split('=')[-1]
            self.logit(None, f'Try to Follow x: {name}')
            if self.inst_x.x_follow(name):
                tab.wait(1)
        elif tab.url.find('x.com/intent/retweet') >= 0:
            # https://x.com/intent/retweet?tweet_id=1912443347928773118
            # tweet_id = tab.url.split('=')[-1]
            self.logit(None, f'Try to retweet x: {tab.url}')
            if self.inst_x.x_retweet():
                tab.wait(1)
        elif tab.url.find('x.com/intent/like') >= 0:
            # https://x.com/intent/like?tweet_id=1912443347928773118
            self.logit(None, f'Try to retweet x: {tab.url}')
            if self.inst_x.x_like():
                tab.wait(1)
        else:
            self.logit(None, 'Manual task.')
            s_msg = 'Manual task, Press any key to exit! ⚠️' # noqa
            input(s_msg)
        tab.close()

    def complete_tasks(self):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('complete_tasks', f'trying ... {i}/{DEF_NUM_TRY}')

            tab = self.browser.latest_tab

            # 2025.04.20 该任务被移除
            # 完成欧易 Web3 任务
            # ele_blks = tab.eles('@@tag()=div@@class:index_item__5J7ea', timeout=2) # noqa
            # if not ele_blks:
            #     tab.wait(1)
            #     continue
            # for ele_blk in ele_blks:
            #     # process each task
            #     # Task title
            #     # 活动期间持有 ≥ 0.05 BNB
            #     ele_btn = ele_blk.ele('@@tag()=div@@class:index_item', timeout=2) # noqa
            #     if not isinstance(ele_btn, NoneElement):
            #         s_text = ele_btn.text
            #         self.logit(None, f'Task title: {s_text}')
            #     # BNB 余额：0.0165 BNB
            #     ele_btn = ele_blk.ele('@@tag()=div@@class:index_desc', timeout=2) # noqa
            #     if not isinstance(ele_btn, NoneElement):
            #         s_text = ele_btn.text
            #         self.logit(None, f'Task desc: {s_text}')

            # Connect X
            if self.connect_x() is False:
                self.logit(None, 'Fail to connect X')
                continue

            tab = self.browser.latest_tab
            # 完成 X 社媒任务
            ele_blks = tab.eles('@@tag()=div@@class:index_wrap__OR3MB', timeout=2) # noqa
            if not ele_blks:
                tab.wait(1)
                continue
            for ele_blk in ele_blks:
                # process each task
                # Task title
                ele_btn = ele_blk.ele('@@tag()=div@@class:index_title', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    s_text = ele_btn.text
                    self.logit(None, f'Task title: {s_text}')

                # Task status
                ele_btn = ele_blk.ele('@@tag()=i@@class:icon iconfont okx-defi-nft-selected', timeout=1) # noqa
                if not isinstance(ele_btn, NoneElement):
                    self.logit(None, 'Task status: sucess')
                    continue

                # Task action & verify
                ele_btns = ele_blk.eles('@@tag()=button@@class:nft-btn', timeout=1) # noqa
                if len(ele_btns) == 2:
                    # Task action
                    if self.process_btn(ele_btns[0]) is False:
                        continue

                    # Task verify
                    ele_btn_2 = ele_btns[1]
                    ele_btn_2.wait.clickable(timeout=5).click(by_js=True)
                    tab.wait(2)
                if not isinstance(ele_btn, NoneElement):
                    self.logit(None, 'Task status: sucess')
                    continue

            return True

        self.logit(None, 'Task elements not found [ERROR]')
        return False

    def get_verify_btn(self):
        tab = self.browser.latest_tab
        ele_blk = tab.ele('@@tag()=div@@class:index_inner-right', timeout=1) # noqa
        if not isinstance(ele_blk, NoneElement):
            lst_path = [
                '@@tag()=button@@class:nft nft-btn btn-md btn-fill-highlight index_button',  # pc # noqa
                '@@tag()=button@@class:nft nft-btn btn-md btn-fill-highlight mobile index_button-sub__X3Dbw',  # mobile # noqa
                '@@tag()=button@@class:nft nft-btn btn-md btn-outline-primary btn-disabled', # task completed # noqa
                '@@tag()=div@@class=index_wrap__NS7Tv', # task completed # noqa
                '@@tag()=div@@class:index_text__', # 恭喜中签！ # noqa
            ]
            ele_btn = self.inst_dp.get_ele_btn(ele_blk, lst_path)
        else:
            ele_btn = NoneElement
        return ele_btn

    def task_verify(self):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('task_verify', f'trying ... {i}/{DEF_NUM_TRY}')
            ele_btn = self.get_verify_btn()
            if ele_btn is not NoneElement:
                s_text = ele_btn.text
                self.logit(None, f'Click Verify Button [{s_text}]')
                ele_btn.wait.clickable(timeout=5).click(by_js=True)
                self.browser.wait(3)
                return True
            self.browser.wait(2)
        return False

    def drops_process(self):
        # open drops url
        # tab = self.browser.latest_tab
        # tab.get(self.args.url)
        tab = self.browser.new_tab(self.args.url)
        tab.wait.doc_loaded()
        # tab.wait(3)
        # tab.set.window.max()

        # set language
        if self.set_lang() is False:
            return False

        # Connect wallet
        if self.connect_wallet() is False:
            return False

        for i in range(1, DEF_NUM_TRY+1):
            self.logit('drops_process', f'trying ... {i}/{DEF_NUM_TRY}')

            # Query Task Result
            if self.get_task_result() in ['等待中签结果', '活动已结束']:
                return True

            self.complete_tasks()

            if self.get_task_result() == '申购':
                self.task_verify()
                self.browser.wait(1)

        return False

    def drops_run(self):
        self.browser = self.inst_dp.get_browser(self.args.s_profile)

        self.inst_okx.set_browser(self.browser)

        if self.inst_okx.init_okx(is_bulk=True) is False:
            return False

        if self.args.get_task_status:

            tab = self.browser.latest_tab
            tab.get(self.args.url)
            tab.wait.doc_loaded()
            tab.wait(3)

            # Connect wallet
            if self.connect_wallet() is False:
                return False

            # Wait to update button status
            tab.wait.doc_loaded()

            max_wait_sec = 30
            i = 0
            while i < max_wait_sec:
                i += 1
                s_text = self.get_task_result()

                lst_result = [
                    '等待中签结果',
                    '未中签，请关注后续活动',
                    '本次活动已结束申购。很遗憾你未能参与，欢迎参与其他活动！',
                    '恭喜中签！'
                ]
                for s_rst in lst_result:
                    if s_text.find(s_rst) >= 0:
                        return True
                tab.wait(1)

            return True

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

        self.inst_x.twitter_run()
        x_status = self.inst_x.dic_status[self.args.s_profile][self.inst_x.IDX_STATUS] # noqa
        if x_status != self.inst_x.DEF_STATUS_OK:
            self.logit('drops_run', f'x_status is {x_status}')
            return False

        self.drops_process()

        if self.args.manual_exit:
            s_msg = 'Manual Exit. Press any key to exit! ⚠️' # noqa
            input(s_msg)

        self.logit('drops_run', 'Finished!')

        return True


def send_msg(inst_drops, lst_success):
    if len(DEF_DING_TOKEN) > 0 and len(lst_success) > 0:
        s_info = ''
        for s_profile in lst_success:
            lst_status = None
            if s_profile in inst_drops.dic_status:
                lst_status = inst_drops.dic_status[s_profile]

            if lst_status is None:
                lst_status = [s_profile, -1]

            s_info += '- {},{}\n'.format(
                s_profile,
                lst_status[inst_drops.IDX_STATUS],
            )
        d_cont = {
            'title': 'Daily Check-In Finished! [okx_drops]',
            'text': (
                'Daily Check-In [okx_drops]\n'
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

    inst_drops = ClsDrops()
    inst_drops.set_args(args)

    args.s_profile = 'ALL'
    inst_drops.inst_okx.set_args(args)
    inst_drops.inst_okx.purse_load(args.decrypt_pwd)

    if len(args.profile) > 0:
        items = args.profile.split(',')
    else:
        # 从配置文件里获取钱包名称列表
        items = list(inst_drops.inst_okx.dic_purse.keys())

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
            if date_now != lst_status[inst_drops.IDX_UPDATE][:10]:
                b_ret = b_ret and False

            for idx_status in [inst_drops.IDX_STATUS]:
                if lst_status[idx_status] in ['等待中签结果']:
                    b_complete = True
                else:
                    b_complete = False

                b_ret = b_ret and b_complete
        else:
            b_ret = False

        return b_ret

    # 将已完成的剔除掉
    inst_drops.status_load()
    # 从后向前遍历列表的索引
    for i in range(len(profiles) - 1, -1, -1):
        s_profile = profiles[i]
        if s_profile in inst_drops.dic_status:
            lst_status = inst_drops.dic_status[s_profile]

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

        if s_profile not in inst_drops.inst_okx.dic_purse:
            logger.info(f'{s_profile} is not in okx account conf [ERROR]')
            sys.exit(0)

        # 如果出现异常(与页面的连接已断开)，增加重试
        max_try_except = 3
        for j in range(1, max_try_except+1):
            try:
                if j > 1:
                    logger.info(f'⚠️ 正在重试，当前是第{j}次执行，最多尝试{max_try_except}次 [{s_profile}]') # noqa

                inst_drops.set_args(args)
                inst_drops.inst_dp.set_args(args)
                inst_drops.inst_x.set_args(args)
                inst_drops.inst_okx.set_args(args)

                if s_profile in inst_drops.dic_status:
                    lst_status = inst_drops.dic_status[s_profile]
                else:
                    lst_status = None

                if is_complete(lst_status):
                    logger.info(f'[{s_profile}] Last update at {lst_status[inst_drops.IDX_UPDATE]}') # noqa
                    break
                else:
                    b_ret = inst_drops.drops_run()
                    inst_drops.close()
                    if b_ret:
                        lst_success.append(s_profile)
                        break

            except Exception as e:
                logger.info(f'[{s_profile}] An error occurred: {str(e)}')
                inst_drops.close()
                if j < max_try_except:
                    time.sleep(5)

        if inst_drops.is_update is False:
            continue

        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile} Finish]')

        if len(profiles) > 0:
            sleep_time = random.randint(args.sleep_sec_min, args.sleep_sec_max)
            if sleep_time > 60:
                logger.info('sleep {} minutes ...'.format(int(sleep_time/60)))
            else:
                logger.info('sleep {} seconds ...'.format(int(sleep_time)))
            time.sleep(sleep_time)

    send_msg(inst_drops, lst_success)


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
        '--decrypt_pwd', required=False, default='',
        help='decrypt password'
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
        help='okx drops url'
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
python okx_drops.py --auto_like --auto_appeal --sleep_sec_min=30 --sleep_sec_max=60 --loop_interval=60
python okx_drops.py --auto_like --auto_appeal --sleep_sec_min=600 --sleep_sec_max=1800 --loop_interval=180
python okx_drops.py --auto_like --auto_appeal --sleep_sec_min=60 --sleep_sec_max=180
python okx_drops.py --auto_like --auto_appeal --sleep_sec_min=120 --sleep_sec_max=360

python okx_drops.py --auto_like --auto_appeal --profile=g05
python okx_drops.py --auto_like --auto_appeal --force --profile=g05

python okx_drops.py --auto_like --auto_appeal --force --profile=t33

python okx_drops.py --auto_like --auto_appeal --force --url=https://web3.okx.com/zh-hans/drops/event/otherworlds --profile=g03
python okx_drops.py --auto_like --auto_appeal --url=https://web3.okx.com/zh-hans/drops/event/otherworlds --profile=g28

python okx_drops.py --get_task_status --headless --url=https://web3.okx.com/zh-hans/drops/event/otherworlds
python okx_drops.py --get_task_status --url=https://web3.okx.com/zh-hans/drops/event/otherworlds
python okx_drops.py --get_task_status --url=https://web3.okx.com/zh-hans/drops/event/otherworlds --profile=g03
python okx_drops.py --get_task_status --force --url=https://web3.okx.com/zh-hans/drops/event/otherworlds --profile=g03

python okx_drops.py --auto_like --url=https://web3.okx.com/drops/event/pixelmoo --profile=g03
python okx_drops.py --auto_like --url=https://web3.okx.com/drops/event/pixelmoo --profile=g06 --manual_exit
python okx_drops.py --get_task_status --url=https://web3.okx.com/drops/event/pixelmoo

python okx_drops.py --auto_like --url=https://web3.okx.com/zh-hans/drops/event/dood --profile=g01
python okx_drops.py --get_task_status --url=https://web3.okx.com/zh-hans/drops/event/dood

python okx_drops.py --auto_like --url=https://web3.okx.com/zh-hans/drops/event/chillonic
python okx_drops.py --get_task_status --url=https://web3.okx.com/zh-hans/drops/event/chillonic
"""
