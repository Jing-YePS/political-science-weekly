# 政治学与社会科学英文期刊周报

这个目录是一个静态周报网站。入口是 `index.html`，每周报告保存在 `reports/YYYY-MM-DD.html`。

GitHub Actions 设定为每周一上午 10:00（中国时间）运行，检索主要英文政治学、国际关系、政策评论期刊，The China Quarterly 和 American Sociological Review 的新近论文，生成中文摘要与研究信息表，并自动发布到 GitHub Pages。

公网地址：https://jing-yeps.github.io/political-science-weekly/

## 自动更新配置

仓库默认使用 DeepSeek API。需要设置 GitHub Secret：

- `DEEPSEEK_API_KEY`：用于把英文摘要翻译成中文，并归纳研究主题、方法、资料和发现。

可选设置 GitHub Actions Variable：

- `DEEPSEEK_MODEL`：默认使用 `deepseek-v4-flash`。
- `LLM_PROVIDER`：默认是 `deepseek`；如果改成 `openai`，则读取 `OPENAI_API_KEY` 和 `OPENAI_MODEL`。

也可以使用其他 OpenAI-compatible 服务：

- Secret `LLM_API_KEY`
- Variable `LLM_BASE_URL`
- Variable `LLM_MODEL`
- Variable `LLM_PROVIDER` 设为任意非 `deepseek` / `openai` 的名称

手动补生成某周报告时，可以在 GitHub 仓库的 Actions 页面运行 `Weekly journal report`，并填写 `report_date`、`from_date`、`to_date`。
