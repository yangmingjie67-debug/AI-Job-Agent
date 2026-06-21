# AI求职助手平台

AI求职助手平台是一款基于大模型的求职分析与职业辅助平台，提供智能聊天、岗位JD分析、简历上传分析、简历JD匹配和分析历史记录功能，帮助用户提升求职效率与简历质量。

## 核心功能

- AI智能对话：实时回答求职问题、职业规划和面试准备。
- 岗位JD分析：解析招聘岗位描述，提取核心要求、必备技能和学习建议。
- 简历上传分析：上传PDF简历后，生成整体评价、技术栈分析和优化建议。
- 简历JD匹配：将简历与岗位JD匹配打分，给出匹配技能、缺失技能和投递建议。
- 分析历史记录：保存个人分析历史，支持查看和删除。

## 技术栈

- Python
- Flask
- SQLite
- DeepSeek API
- HTML/CSS
- pypdf

## 项目目录结构

```
ai-chat-app/
├── app.py
├── README.md
├── mj_ai.db
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── jd.html
│   ├── resume.html
│   ├── match.html
│   ├── history.html
│   └── ...
└── nenv/
```

## 本地运行步骤

1. 进入项目根目录：
   ```bash
   cd ai-chat-app
   ```
2. 激活 Python 虚拟环境：
   ```bash
   .\nenv\Scripts\Activate.ps1
   ```
3. 运行 Flask 应用：
   ```bash
   python app.py
   ```
4. 在浏览器中访问：
   ```
   http://localhost:5000
   ```

## 依赖安装命令

如果没有安装依赖，可使用以下命令安装：

```bash
pip install flask openai pypdf
```

## 配置 DeepSeek API Key

在 `app.py` 中找到 `OpenAI(...)` 初始化部分，替换 `api_key` 为你的 DeepSeek API Key：

```python
client = OpenAI(
    api_key="<你的 DeepSeek API Key>",
    base_url="https://api.deepseek.com"
)
```

## 项目截图

（此处放置项目页面截图，例如首页、JD分析页、简历分析页、历史记录页）

## 后续规划

- 增加用户头像与个人信息管理
- 支持更多简历文件格式（如 DOCX）
- 增加分析结果导出功能
- 优化页面交互与移动端适配
- 添加更多 AI 求职助手场景，如面试题目生成、简历自动生成
