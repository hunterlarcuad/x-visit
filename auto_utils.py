import sys
import time
import pyautogui as pg
import screeninfo
import argparse

"""
pip install pyautogui
pip install screeninfo
"""

DEF_SCREEN_WIDTH = 1512
DEF_SCREEN_HEIGHT = 982
DEF_ICON_XY = [823, 754]


def get_position():
    # 获取所有屏幕的尺寸和位置
    screens = screeninfo.get_monitors()

    # 打印屏幕数量
    print(f'当前连接的显示器数量为：{len(screens)}')

    for i in range(len(screens)):
        print(screens[i])

    try:
        while True:
            # 获取当前鼠标的位置
            x, y = pg.position()
            # 打印鼠标的X和Y坐标
            print(f'鼠标位置: ({x}, {y})', end='\r') # noqa
            # 稍微等待一下，避免输出太快
            time.sleep(0.1)
    except KeyboardInterrupt:
        print('\n程序已终止。')


def get_window_size():
    screen_width, screen_height = pg.size()
    return (screen_width, screen_height)


def auto_click(xy=None, n_click=1):
    """
    black_list: proxy_name black list
    """
    if xy is None:
        xy = DEF_ICON_XY

    # 获取屏幕尺寸
    # 元组类型的返回值
    screen_width, screen_height = pg.size()
    # 获取屏幕宽高
    # print("屏幕宽度:", screen_width)
    # print("屏幕高度:", screen_height)

    # if screen_width != DEF_SCREEN_WIDTH or screen_height != DEF_SCREEN_HEIGHT:
    #     return False

    # 鼠标移动速度
    move_speed_sec = 1

    for i in range(n_click):
        pg.moveTo(xy[0], xy[1], duration=move_speed_sec)
        time.sleep(1)
        pg.click()

    return True


def main(args):
    """
    time.sleep(5)
    # pic = pg.screenshot(region=[695, 430, 385, 20])
    pic = pg.screenshot()
    pic.save('proxy_using.png')
    sys.exit(-1)
    """

    if args.show_position:
        get_position()
    elif args.auto_click:
        auto_click()
    else:
        print('Usage: python {} -h'.format(sys.argv[0]))


if __name__ == '__main__':
    """
    生成 p001 到 p020 的列表
    每次随机取一个出来，并从原列表中删除，直到原列表为空
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--show_position', required=False, action='store_true',
        help='显示鼠标在屏幕上的坐标'
    )
    parser.add_argument(
        '--auto_click', required=False, action='store_true',
        help='click'
    )
    args = parser.parse_args()
    main(args)

"""
python auto_utils.py --show_position
"""
