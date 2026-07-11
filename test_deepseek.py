import os
import traceback

import httpx
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.environ.get("DEEPSEEK_API_KEY")
print("API_KEY_LOADED:", bool(api_key))
print("API_KEY_PREFIX:", api_key[:3] if api_key else "")

try:
    http_client = httpx.Client(trust_env=False)
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=30,
        http_client=http_client
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": "只回复你好"}]
    )
    print("SDK_CALL_SUCCESS: True")
    print("RESPONSE_RECEIVED:", bool(response.choices[0].message.content))
except BaseException as exc:
    print("SDK_CALL_SUCCESS: False")
    print("EXCEPTION_TYPE:", type(exc).__module__ + "." + type(exc).__name__)
    print("EXCEPTION_REPR:", repr(exc))
    print("CAUSE:", repr(exc.__cause__))
    print("TRACEBACK:")
    traceback.print_exc()
