"""
2025.03.31
https://www.bigmodel.cn/dev/api/normal-model/glm-4

https://open.bigmodel.cn/pricing

200万通用模型资源包
200万GLM-4-Plus推理资源包
1600万GLM-4-Air 推理资源包
"""
import sys
import csv
import argparse
import time
import pdb

from conf import DEF_LLM_ZHIPUAI

from zhipuai import ZhipuAI


def get_glm_client():
    client = ZhipuAI(api_key=DEF_LLM_ZHIPUAI) # 请填写您自己的APIKey
    return client


def test():
    client = get_glm_client()
    response = client.chat.asyncCompletions.create(
        model="glm-4-plus",  # 请填写您要调用的模型名称
        messages=[
            {
                "role": "user",
                "content": "作为童话之王，请以始终保持一颗善良的心为主题，写一篇简短的童话故事。故事应能激发孩子们的学习兴趣和想象力，同时帮助他们更好地理解和接受故事中蕴含的道德和价值观。"
            }
        ],
    )
    print(response)


def get_rsp_by_id(task_id):
    client = get_glm_client()
    # task_id = response.id
    task_status = ''
    get_cnt = 0

    while task_status != 'SUCCESS' and task_status != 'FAILED' and get_cnt <= 40:
        result_response = client.chat.asyncCompletions.retrieve_completion_result(id=task_id)
        print(result_response)
        task_status = result_response.task_status

        time.sleep(2)
        get_cnt += 1


def gene_repeal_msg(s_in):
    """
    Return:
        None: Fail to generate msg by llm
        string: generated content by llm
    """
    client = get_glm_client()
    s_prompt = (
        "【功能】"
        "对申诉内容进行改写"
        "【要求】"
        "改写后的申诉与原申诉内容的相似度不超过70%"
        "要有礼貌，在最后对审核人员表示感谢"
        "请用英语输出"
        "输出不要出现换行符"
        "【参考申诉内容如下】"
        f"{s_in}"
    )
    response = client.chat.asyncCompletions.create(
        model="GLM-4-Air",  # 请填写您要调用的模型名称
        messages=[
            {
                "role": "user",
                "content": s_prompt
            }
        ],
    )
    task_id = response.id
    task_status = ''
    get_cnt = 0

    while task_status != 'SUCCESS' and task_status != 'FAILED' and get_cnt <= 40:
        result_response = client.chat.asyncCompletions.retrieve_completion_result(id=task_id)
        # print(result_response)
        task_status = result_response.task_status

        if task_status == 'SUCCESS':
            s_cont = result_response.choices[0].message.content
            return s_cont

        time.sleep(2)
        get_cnt += 1

    return None


def gene_by_llm(s_prompt):
    """
    Return:
        None: Fail to generate msg by llm
        string: generated content by llm
    """
    # s_model = "glm-4-air"
    s_model = "glm-4-plus"
    client = get_glm_client()
    response = client.chat.asyncCompletions.create(
        model=s_model,  # 请填写您要调用的模型名称
        messages=[
            {
                "role": "user",
                "content": s_prompt
            }
        ],
    )
    task_id = response.id
    task_status = ''
    get_cnt = 0

    while task_status != 'SUCCESS' and task_status != 'FAILED' and get_cnt <= 40:
        result_response = client.chat.asyncCompletions.retrieve_completion_result(id=task_id)
        # print(result_response)
        task_status = result_response.task_status

        if task_status == 'SUCCESS':
            s_cont = result_response.choices[0].message.content
            return s_cont

        time.sleep(2)
        get_cnt += 1

    return None


# def main():
#     parser = argparse.ArgumentParser(description="CSV 文件加密工具")
#     parser.add_argument("--file_in", help="输入的 CSV 文件路径")
#     parser.add_argument("--file_ot", default="output.csv", help="输出的 CSV 文件路径，默认为 output.csv") # noqa
#     parser.add_argument("--idx", type=int, default=0, help="要加密的列索引，默认为第 1 列（从 0 开始）") # noqa
#     parser.add_argument("--s_in", help="单个字符串输入，用于加密或解密")
#     parser.add_argument("--key", help="Secret Key")
#     parser.add_argument("--encode_type", choices=["encrypt", "decrypt"], help="加密或解密操作类型") # noqa

#     args = parser.parse_args()

#     if args.file_in:
#         # 如果传入了 --file_in 参数，则对 CSV 文件进行加密
#         encrypt_csv_column(args.file_in, args.file_ot, args.idx, args.key)
#     elif args.s_in and args.encode_type:
#         # 如果传入了 --s_in 和 --encode_type 参数，则对单个字符串进行加密或解密
#         if args.encode_type == "encrypt":
#             result = encrypt(args.key, args.s_in)
#             print(f"加密结果：{result}")
#         elif args.encode_type == "decrypt":
#             result = decrypt(args.key, args.s_in)
#             print(f"解密结果：{result}")
#     else:
#         print("请传入有效的参数。")


if __name__ == "__main__":
    """
    """
    s_in = "I don't know why my account can't like or post, and I haven't logged in for a while. Can you help lift the ban?"
    gene_repeal_msg(s_in)
    # test()
    # get_rsp_by_id('73461743384968928-8844185384718838052')

    # main()

    sys.exit(0)

    # 测试代码
    s_key = "mysecretkey"
    s_in = "Hello, this is a test message!"

    encrypted = encrypt(s_key, s_in)
    print(f"加密后的字符串: {encrypted}")

    decrypted = decrypt(s_key, encrypted)
    print(f"解密后的字符串: {decrypted}")


"""
# noqa
"""
