import json

from flask import Flask, request, render_template, redirect, session
from pypdf import PdfReader
from database import (
    init_db,
    save_message,
    clear_messages,
    get_messages,
    get_user_by_username,
    create_user,
    save_history,
    get_history,
    delete_history_record
)
from services.deepseek_service import chat_completion
from services.job_analysis_service import analyze_job_match

app = Flask(__name__)
app.secret_key = "replace-with-a-secret-key"

def summarize_input(text, length=120):
    summary = text.replace("\n", " ").strip()
    return summary[:length] + ("..." if len(summary) > length else "")


@app.route("/", methods=["GET", "POST"])
def home():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        user_input = request.form.get("user_input")

        print("开始请求DeepSeek...")

        chat_history = get_messages(session["user_id"])

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
- 优先给步骤
- 优先给代码示例
"""
            }
        ]

        for msg in chat_history:
            messages.append({
                "role": "user",
                "content": msg["user"]
            })

            messages.append({
                "role": "assistant",
                "content": msg["bot"]
            })

        messages.append({
            "role": "user",
            "content": user_input
        })

        reply = chat_completion(messages)

        print("DeepSeek回复:", reply)

        save_message(user_input, reply, session["user_id"])

    chat_history = get_messages(session["user_id"])

    return render_template(
        "index.html",
        chat_history=chat_history,
        username=session.get("username")
    )


@app.route("/clear", methods=["POST"])
def clear():
    if "user_id" not in session:
        return redirect("/login")
    clear_messages(session["user_id"])
    return redirect("/")


@app.route("/jd", methods=["GET", "POST"])
def jd():
    if "user_id" not in session:
        return redirect("/login")

    analysis = None
    error = None
    if request.method == "POST":
        jd_text = request.form.get("jd_text", "").strip()
        if not jd_text:
            error = "请输入岗位描述后再分析。"
        else:
            prompt = f"请根据以下岗位JD，给出：\n- 岗位核心要求\n- 必备技能\n- 加分技能\n- 我当前项目可以匹配哪些要求\n- 还缺哪些技能\n- 接下来7天学习建议\n\n岗位描述：\n{jd_text}"
            analysis = chat_completion([
                {"role": "system", "content": "你是一个岗位JD分析助手。"},
                {"role": "user", "content": prompt}
            ])
            if analysis:
                save_history(session["user_id"], "JD分析", summarize_input(jd_text), analysis)

    return render_template("jd.html", analysis=analysis, error=error, username=session.get("username"))


@app.route("/resume", methods=["GET", "POST"])
def resume():
    if "user_id" not in session:
        return redirect("/login")

    analysis = None
    error = None
    if request.method == "POST":
        resume_file = request.files.get("resume_file")
        if resume_file is None or resume_file.filename == "":
            error = "请上传 PDF 简历文件。"
        else:
            try:
                reader = PdfReader(resume_file)
                text_parts = []
                for page in reader.pages:
                    text_parts.append(page.extract_text() or "")
                resume_text = "\n".join(text_parts).strip()
                if not resume_text:
                    error = "无法从 PDF 提取文本，请确认文件内容。"
                else:
                    prompt = f"请基于以下简历文本进行分析，返回：\n- 简历整体评价\n- 技术栈分析\n- 项目经历问题\n- 适合投递的岗位\n- 简历修改建议\n- 针对 AI应用开发岗位的优化建议\n\n简历内容：\n{resume_text}"
                    analysis = chat_completion([
                        {"role": "system", "content": "你是一个简历分析专家。"},
                        {"role": "user", "content": prompt}
                    ])
                    if analysis:
                        save_history(session["user_id"], "简历分析", summarize_input(resume_text), analysis)
            except Exception:
                error = "无法读取 PDF 文件，请上传有效的 PDF。"

    return render_template("resume.html", analysis=analysis, error=error, username=session.get("username"))


@app.route("/match", methods=["GET", "POST"])
def match():
    if "user_id" not in session:
        return redirect("/login")

    analysis = None
    error = None
    if request.method == "POST":
        resume_file = request.files.get("resume_file")
        jd_text = request.form.get("jd_text", "").strip()
        
        if resume_file is None or resume_file.filename == "":
            error = "请上传 PDF 简历文件。"
        elif not jd_text:
            error = "请输入岗位 JD 描述。"
        else:
            try:
                reader = PdfReader(resume_file)
                text_parts = []
                for page in reader.pages:
                    text_parts.append(page.extract_text() or "")
                resume_text = "\n".join(text_parts).strip()
                if not resume_text:
                    error = "无法从 PDF 提取文本，请确认文件内容。"
                else:
                    analysis = analyze_job_match(resume_text, jd_text)
                    if analysis:
                        input_summary = summarize_input(jd_text)
                        save_history(
                            session["user_id"],
                            "简历JD匹配",
                            input_summary,
                            json.dumps(analysis, ensure_ascii=False)
                        )
            except Exception:
                error = "无法读取 PDF 文件，请上传有效的 PDF。"

    return render_template("match.html", analysis=analysis, error=error, username=session.get("username"))


@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect("/login")
    records = get_history(session["user_id"])
    return render_template("history.html", records=records, username=session.get("username"))


@app.route("/history/delete", methods=["POST"])
def history_delete():
    if "user_id" not in session:
        return redirect("/login")
    history_id = request.form.get("history_id")
    if history_id:
        try:
            delete_history_record(int(history_id), session["user_id"])
        except ValueError:
            pass
    return redirect("/history")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect("/")

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = get_user_by_username(username)
        if user and user["password"] == password:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/")
        error = "用户名或密码错误"

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect("/")

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            error = "请输入用户名和密码"
        elif get_user_by_username(username) is not None:
            error = "用户名已存在"
        else:
            user_id = create_user(username, password)
            session["user_id"] = user_id
            session["username"] = username
            return redirect("/")

    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
