import os
import logging

import httpx
import openai
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

logger = logging.getLogger(__name__)

http_client = httpx.Client(trust_env=False)

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    http_client=http_client
)


def chat_completion(messages, model="deepseek-chat"):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages
        )
        return response.choices[0].message.content
    except openai.APIConnectionError:
        logger.exception("DeepSeek API connection failed")
        return "无法连接 DeepSeek API，请检查网络、VPN、代理或 API 地址。"
