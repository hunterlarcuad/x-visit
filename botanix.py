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
from datetime import timedelta

from DrissionPage import ChromiumOptions
from DrissionPage import Chromium
from DrissionPage._elements.none_element import NoneElement

from fun_utils import ding_msg
from fun_utils import load_file
from fun_utils import save2file
from fun_utils import format_ts
from fun_utils import get_index_from_header

from auto_utils import auto_click

from fun_okx import OkxUtils
from fun_x import XUtils
from fun_dp import DpUtils

from conf import DEF_USE_HEADLESS
from conf import DEF_DEBUG
from conf import DEF_PATH_USER_DATA
from conf import DEF_NUM_TRY
from conf import DEF_DING_TOKEN
from conf import DEF_PATH_DATA_STATUS

from conf import DEF_WINDOW_LOCATION
from conf import DEF_WINDOW_SIZE
from conf import DEF_MINE_SAT_XY

# from conf import TZ_OFFSET
from conf import DEL_PROFILE_DIR

from conf import FILENAME_LOG
from conf import logger

# gm Check-in use UTC Time
TZ_OFFSET = 0

DEF_INSUFFICIENT_ETH = 'Insufficient ETH balance'
DEF_SUCCESS = 'Success'
DEF_FAIL = 'Fail'

"""
2025.05.17
"""


class ClsBotanix():

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
        self.DEF_HEADER_STATUS = 'account,botanix_btc,botanix_usd,sats_total,sats_today,sats_date,update_time'  # noqa
        self.IDX_BALANCE_BTC = 1
        self.IDX_BALANCE_USD = 2
        self.IDX_SATS_TOTAL = 3
        self.IDX_SATS_TODAY = 4
        self.IDX_SATS_DATE = 5
        self.IDX_UPDATE = 6
        self.FIELD_NUM = self.IDX_UPDATE + 1

    def set_args(self, args):
        self.args = args
        self.is_update = False

    def __del__(self):
        pass
        # self.status_save()

    def get_status_file(self):
        filename = 'botanix'
        self.file_status = f'{DEF_PATH_DATA_STATUS}/botanix/{filename}.csv'

    def status_load(self):
        if self.file_status is None:
            self.get_status_file()

        self.dic_status = load_file(file_in=self.file_status,
                                    idx_key=0,
                                    header=self.DEF_HEADER_STATUS)

    def status_save(self):
        save2file(file_ot=self.file_status,
                  dic_status=self.dic_status,
                  idx_key=0,
                  header=self.DEF_HEADER_STATUS)

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

    def save_screenshot(self, name):
        tab = self.browser.latest_tab
        # 对整页截图并保存
        # tab.set.window.max()
        s_name = f'{self.args.s_profile}_{name}'
        tab.get_screenshot(path='tmp_img', name=s_name, full_page=True)

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

    def update_date(self, idx_status, update_ts=None):
        if not update_ts:
            update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)

        claim_date = update_time[:10]

        self.update_status(idx_status, claim_date)

    def connect_wallet(self):
        n_tab = self.browser.tabs_count

        n_try = 16
        for i in range(1, n_try + 1):
            self.logit('connect_wallet', f'trying ... {i}/{n_try}')

            tab = self.browser.latest_tab
            tab.wait.doc_loaded()
            tab.wait(3)

            self.click_by_text('button', 'Get Started')
            self.click_by_text('button', 'Skip')

            ele_blk = tab.ele('@@tag()=div@@class=relative w-full',
                              timeout=2)  # noqa
            if not isinstance(ele_blk, NoneElement):
                ele_btn = ele_blk.ele('@@tag()=button', timeout=2)
                if not isinstance(ele_btn, NoneElement):
                    s_info = ele_btn.text
                    self.logit(None,
                               f'Connect Wallet Button Text: {s_info}')  # noqa
                    if s_info in ['Connect Wallet', 'Sign In']:
                        try:
                            ele_btn.wait.enabled(timeout=5)
                            if ele_btn.wait.clickable(timeout=5):
                                ele_btn.click(by_js=True)
                                tab.wait(1)
                        except Exception as e:  # noqa
                            # self.logit('connect_wallet', f'Sign in Exception: {e}')
                            continue

                        ele_btn = tab.ele('@@tag()=div@@text()=OKX Wallet',
                                          timeout=2)
                        if not isinstance(ele_btn, NoneElement):
                            if ele_btn.wait.clickable(timeout=5):
                                ele_btn.click()

                        if self.inst_okx.wait_popup(n_tab + 1, 10):
                            tab.wait(2)
                            self.inst_okx.okx_connect()

                        if self.inst_okx.wait_popup(n_tab + 1, 10):
                            tab.wait(2)
                            try:
                                if self.inst_okx.okx_confirm():
                                    self.logit(None,
                                               'Signature request Confirm')
                                    self.inst_okx.wait_popup(n_tab, 15)
                                    tab.wait(3)
                            except Exception as e:  # noqa
                                self.logit('connect_wallet',
                                           f'[okx_confirm] Error: {e}')  # noqa
                                continue

                    else:
                        self.logit(None, 'Log in success')
                        return True

        self.logit(None, 'Failed to Connect Wallet [ERROR]')
        return False

    def wait_button(self, s_text=None, wait_sec=10):
        i = 0
        while i < wait_sec:
            i += 1
            tab = self.browser.latest_tab
            if s_text is None:
                lst_path = [
                    '@@tag()=button@@text()=The Citadel',
                    '@@tag()=button@@text()=Continue',
                    '@@tag()=button@@text()=Mine SATs',
                    '@@tag()=button@@class:flex items-center justify-center@@text():h',
                    '@@tag()=button@@text()=Mint NFT',
                ]
            else:
                lst_path = [
                    f'@@tag()=button@@text()={s_text}',
                ]

            ele_btn = self.inst_dp.get_ele_btn(tab, lst_path)
            if ele_btn is not NoneElement:
                return ele_btn.text
            self.logit(None, f'Wait for continue button ... {i}/{wait_sec}')
            self.browser.wait(1)
        return None

    def click_by_text(self, s_tag, s_text):
        tab = self.browser.latest_tab

        ele_btn = tab.ele(f'@@tag()={s_tag}@@text()={s_text}', timeout=2)
        if not isinstance(ele_btn, NoneElement):
            if ele_btn.wait.clickable(timeout=2):
                ele_btn.click(by_js=True)
                tab.wait(2)
                return True
        return False

    def save_canvas(self, canvas_element):
        if canvas_element:
            # 执行 JavaScript，将 canvas 内容导出为 Data URL
            # canvas.toDataURL() 方法会返回一个 Base64 编码的字符串
            js_code = """
            var canvas = document.querySelector('canvas');
            if (canvas) {
                return canvas.toDataURL('image/png'); // 你也可以指定 'image/jpeg'
            }
            return null;
            """
            data_url = tab.run_js(js_code)

            if data_url:
                print("成功获取 Canvas Data URL。")
                # Data URL 示例: 'data:image/png;base64,iVBORw0KGgoAAA...'
                # 提取 Base64 编码部分并保存为图片文件
                match = re.match(r'data:image/(png|jpeg);base64,(.*)',
                                 data_url)
                if match:
                    base64_data = match.group(2)
                    file_extension = "png" if match.group(
                        1) == "png" else "jpeg"
                    img_data = base64.b64decode(base64_data)
                    with open(f'canvas_content.{file_extension}', 'wb') as f:
                        f.write(img_data)
                    print(f"Canvas 内容已保存为 canvas_content.{file_extension}。")
                else:
                    print("Data URL 格式不正确。")
            else:
                print("未能从 Canvas 获取 Data URL。")
        else:
            print("未找到 Canvas 元素。")

    def update_total_points(self):
        tab = self.browser.latest_tab

        ele_points = tab.ele('@@tag()=p@@class:font-balooPaaji2 text',
                             timeout=2)
        if not isinstance(ele_points, NoneElement):
            s_point = ele_points.text
            self.logit(None, 'Total Points: {}'.format(s_point))
            self.update_status(self.IDX_SATS_TOTAL, s_point)
            return True
        return False

    def botanix_process(self):
        # open botanix url
        # tab = self.browser.latest_tab
        # tab.get(self.args.url)
        self.args.url = 'https://2100abitcoinworld.com/'
        tab = self.browser.new_tab(self.args.url)
        tab.wait.doc_loaded()
        # tab.wait(3)
        # tab.set.window.max()

        # Connect wallet
        if self.connect_wallet() is False:
            self.click_by_text('button', 'Get Started')
            tab.wait(3)
            self.click_by_text('button', 'Skip')
            return False

        b_goto_citadel = True
        n_try = 8
        for i in range(1, n_try + 1):
            self.logit('botanix_process', f'trying ... {i}/{n_try}')

            # canvas_element = tab.ele('.upper-canvas', timeout=2)
            # self.save_canvas(canvas_element)

            # castle_xy_in_canvas = [376, 439]
            # auto_click(castle_xy_in_canvas, n_click=2)

            if b_goto_citadel:
                self.wait_button(wait_sec=10)
                if self.click_by_text('button', 'The Citadel'):
                    self.logit(None, 'Click The Citadel on Bar')
                    tab.wait(2)
                    b_goto_citadel = False

            if self.click_by_text('button', 'Continue'):
                self.logit(None, 'Welcome to Citadel, Click continue button')
                tab.wait(2)

            if self.click_by_text('button', 'Accept and Continue'):
                self.logit(None, 'Accept and Continue, click ...')
                tab.wait(2)

            # Mine SATs
            # checkin_xy_in_canvas = [1015, 260]
            auto_click(DEF_MINE_SAT_XY, n_click=2)

            s_dest_text = 'Mint NFT'
            s_btn_text = self.wait_button(s_dest_text, wait_sec=2)
            if s_btn_text == s_dest_text:

                if self.click_by_text('button', 'Mint NFT'):
                    self.logit(None, 'Click Mint NFT button')
                    tab.wait(2)
                if self.inst_dp.get_tag_info('label', 'Enter Referral Code') is False:
                    continue

                s_msg = 'Input invite code. Press any key to exit! ⚠️' # noqa
                input(s_msg)

                tab.refresh()
                tab.wait.doc_loaded()
                tab.wait(3)
                b_goto_citadel = True
                continue

            if self.click_by_text('button', 'Mine SATs'):
                self.logit(None, 'Click Mine SATs button')
                tab.wait(2)

            ele_info = tab.ele(
                '@@tag()=div@@class=-mt-10 flex flex-col items-center',
                timeout=2)
            if not isinstance(ele_info, NoneElement):
                s_info = ele_info.text.replace('\n', ': ')
                self.logit(None, 'Today\'s points: {}'.format(s_info))
                s_points = s_info.split(': ')[1].split(' ')[0]
                self.update_status(self.IDX_SATS_TODAY, s_points)
                self.update_date(self.IDX_SATS_DATE)
                self.update_total_points()
                tab.wait(3)

                return True

            ele_info = tab.ele('@@tag()=div@@class=mt-4', timeout=2)
            if not isinstance(ele_info, NoneElement):
                s_info = ele_info.text
                self.logit(None, 'Info: {}'.format(s_info))
                if len(s_info.split(':')) == 3:
                    self.update_status(self.IDX_SATS_TODAY, '1')
                    self.update_date(self.IDX_SATS_DATE)
                    self.update_total_points()
                    return True

        return False

    def botanix_run(self):
        self.browser = self.inst_dp.get_browser(self.args.s_profile)

        self.inst_okx.set_browser(self.browser)

        tab = self.browser.latest_tab
        if self.args.set_window_size == 'max':
            # 判断窗口是否是最大化
            if tab.rect.window_state != 'maximized':
                # 设置浏览器窗口最大化
                tab.set.window.max()
                self.logit(None, 'Set browser window to maximize')
        if DEF_WINDOW_LOCATION:
            x, y = DEF_WINDOW_LOCATION
            tab.set.window.location(x, y)
        if DEF_WINDOW_SIZE:
            w, h = DEF_WINDOW_SIZE
            tab.set.window.size(w, h)

        # tab.rect.window_location
        # tab.rect.window_size

        if self.inst_okx.init_okx(is_bulk=True) is False:
            return False

        s_chain = 'Botanix'
        s_coin = 'Botanix_BTC'
        (s_balance_coin,
         s_balance_usd) = self.inst_okx.get_balance_by_chain_coin(
             s_chain, s_coin)
        self.logit(
            None,
            f'Balance: {s_balance_coin} {s_balance_usd} [{s_chain}][{s_coin}]')
        self.update_status(self.IDX_BALANCE_BTC, s_balance_coin)
        self.update_status(self.IDX_BALANCE_USD, s_balance_usd)

        self.botanix_process()

        if self.args.manual_exit:
            s_msg = 'Manual Exit. Press any key to exit! ⚠️'  # noqa
            input(s_msg)

        self.logit('botanix_run', 'Finished!')

        return True


def send_msg(inst_botanix, lst_success):
    if len(DEF_DING_TOKEN) > 0 and len(lst_success) > 0:
        s_info = ''
        for s_profile in lst_success:
            lst_status = None
            if s_profile in inst_botanix.dic_status:
                lst_status = inst_botanix.dic_status[s_profile]

            if lst_status is None:
                lst_status = [s_profile, -1]

            s_info += '- {},{}\n'.format(
                s_profile,
                lst_status[inst_botanix.IDX_SATS_TODAY],
            )
        d_cont = {
            'title': 'botanix Task Finished! [botanix]',
            'text': (
                'botanix Task\n'
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
        logger.info(f'Sleep {args.sleep_sec_at_start} seconds at start !!!')  # noqa
        time.sleep(args.sleep_sec_at_start)

    if DEL_PROFILE_DIR and os.path.exists(DEF_PATH_USER_DATA):
        logger.info(f'Delete {DEF_PATH_USER_DATA} ...')
        shutil.rmtree(DEF_PATH_USER_DATA)
        logger.info(f'Directory {DEF_PATH_USER_DATA} is deleted')  # noqa

    inst_botanix = ClsBotanix()
    inst_botanix.set_args(args)

    args.s_profile = 'ALL'
    inst_botanix.inst_okx.set_args(args)
    inst_botanix.inst_okx.purse_load(args.decrypt_pwd)

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
        items = [f"{prefix}{str(i).zfill(num_width)}" for i in range(
            start_num, end_num + 1)]
        logger.info(f'Profile list: {items}')
    else:
        # 从配置文件里获取钱包名称列表
        items = list(inst_botanix.inst_okx.dic_purse.keys())

    profiles = copy.deepcopy(items)

    # 每次随机取一个出来，并从原列表中删除，直到原列表为空
    total = len(profiles)
    n = 0

    lst_success = []

    def is_complete(lst_status):
        if args.force:
            return False

        b_ret = False
        date_now = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)

        if lst_status:
            if len(lst_status) < inst_botanix.FIELD_NUM:
                return False

            if date_now == lst_status[inst_botanix.IDX_SATS_DATE]:
                b_ret = True

        else:
            b_ret = False

        return b_ret

    # 将已完成的剔除掉
    inst_botanix.status_load()
    # 从后向前遍历列表的索引
    for i in range(len(profiles) - 1, -1, -1):
        s_profile = profiles[i]
        if s_profile in inst_botanix.dic_status:
            lst_status = inst_botanix.dic_status[s_profile]

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

        if percent > args.max_percent:
            logger.info(
                f'Progress is more than threshold {percent}% > {args.max_percent}% [{n}/{total}] [{s_profile}]')
            break

        profiles.remove(s_profile)

        args.s_profile = s_profile

        if s_profile not in inst_botanix.inst_okx.dic_purse:
            logger.info(f'{s_profile} is not in okx account conf [ERROR]')
            sys.exit(0)

        # 如果出现异常(与页面的连接已断开)，增加重试
        max_try_except = 3
        for j in range(1, max_try_except+1):
            try:
                if j > 1:
                    logger.info(f'⚠️ 正在重试，当前是第{j}次执行，最多尝试{max_try_except}次 [{s_profile}]')  # noqa

                inst_botanix.set_args(args)
                inst_botanix.inst_dp.set_args(args)
                inst_botanix.inst_okx.set_args(args)

                if not args.no_x:
                    inst_botanix.inst_x.set_args(args)

                if s_profile in inst_botanix.dic_status:
                    lst_status = inst_botanix.dic_status[s_profile]
                else:
                    lst_status = None

                if is_complete(lst_status):
                    logger.info(f'[{s_profile}] Last update at {lst_status[inst_botanix.IDX_UPDATE]}')  # noqa
                    break
                else:
                    b_ret = inst_botanix.botanix_run()
                    inst_botanix.close()
                    if b_ret:
                        lst_success.append(s_profile)
                        break

            except Exception as e:
                logger.info(f'[{s_profile}] An error occurred: {str(e)}')
                inst_botanix.close()
                if j < max_try_except:
                    time.sleep(5)

        if inst_botanix.is_update is False:
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
            logger.info(
                f'next_exec_time: {next_exec_time.strftime("%Y-%m-%d %H:%M:%S")}')
            time.sleep(sleep_time)

    send_msg(inst_botanix, lst_success)


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
        help='botanix url'
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

            logger.info('#####***** Loop sleep {} seconds ...'.format(args.loop_interval))  # noqa
            time.sleep(args.loop_interval)

"""
# noqa

2025.07.03
https://2100abitcoinworld.com/

python botanix.py --sleep_sec_min=600 --sleep_sec_max=1800 --loop_interval=180 --profile=g01

python botanix.py --profile=g01
"""
