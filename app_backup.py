from flask import Flask, request, render_template
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(
    api_key="sk-8daa0f05d667416d8a13ea29b3919e7c",
    base_url="https://api.deepseek.com"
)

chat_history = []

@app.route("/", methods=["GET", "POST"])
def home():

    if request.method == "POST":

        user_input = request.form.get("user_input")

        print("开始请求DeepSeek...")

        # 系统提示词
        messages = [
            {
                "role": "system",
                "content": """
你叫MJ AI助手。
你的开发者是明杰。
MJ代表明杰。

回答要求：
- 中文
- 简洁
- 可执行
"""
            }
        ]

        # 历史记忆
        for msg in chat_history:
            messages.append({
                "role": "user",
                "content": msg["user"]
            })

            messages.append({
                "role": "assistant",
                "content": msg["bot"]
            })

        # 当前问题
        messages.append({
            "role": "user",
            "content": user_input
        })

        # 调用 DeepSeek
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=True
        )

        reply = ""

        for chunk in response:

            content = chunk.choices[0].delta.content

            if content:

                reply += content

                print(content, end="", flush=True)

        print()

        chat_history.append({
            "user": user_input,
            "bot": reply
        })

    return render_template(
        "index.html",
        chat_history=chat_history
    )

if __name__ == "__main__":
    app.run(debug=True)