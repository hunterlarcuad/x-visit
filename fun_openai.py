"""
OpenAI 协议 LLM 接口（官方 OpenAI 或兼容网关均可）。

Chat Completions:
https://platform.openai.com/docs/api-reference/chat
"""
import sys

from openai import OpenAI

from conf import DEF_LLM_OPENAI
from conf import DEF_MODEL_OPENAI
from conf import DEF_BASE_URL_OPENAI
from conf import DEF_MAX_TOKENS_OPENAI


def get_openai_client():
    kwargs = {"api_key": DEF_LLM_OPENAI}
    if DEF_BASE_URL_OPENAI:
        kwargs["base_url"] = DEF_BASE_URL_OPENAI
    return OpenAI(**kwargs)


def gene_repeal_msg(s_in):
    """
    Return:
        None: Fail to generate msg by llm
        string: generated content by llm
    """
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
    return gene_by_llm(s_prompt)


def gene_by_llm_once(s_prompt):
    """
    Return:
        None: Fail to generate msg by llm
        string: generated content by llm
    """
    client = get_openai_client()
    try:
        response = client.chat.completions.create(
            model=DEF_MODEL_OPENAI,
            messages=[
                {
                    "role": "user",
                    "content": s_prompt,
                }
            ],
            max_tokens=DEF_MAX_TOKENS_OPENAI,
            timeout=180,
        )
    except Exception:
        return None

    try:
        s_cont = response.choices[0].message.content
    except (IndexError, AttributeError):
        return None

    if not s_cont:
        return None
    return s_cont


def gene_by_llm(s_prompt, max_retry=3):
    """
    Return:
        None: Fail to generate msg by llm
        string: generated content by llm
    """
    n_try = 0
    while n_try < max_retry:
        n_try += 1
        s_cont = gene_by_llm_once(s_prompt)
        if not s_cont:
            continue
        return s_cont
    return None


if __name__ == "__main__":
    s_in = "I don't know why my account can't like or post, and I haven't logged in for a while. Can you help lift the ban?"
    s_out = gene_repeal_msg(s_in)
    print(s_out)

    sys.exit(0)
