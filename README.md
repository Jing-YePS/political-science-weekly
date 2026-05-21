# 政治学与社会科学英文期刊周报

这个目录是一个静态周报网站。入口是 `index.html`，每周报告保存在 `reports/YYYY-MM-DD.html`。

GitHub Actions 设定为每周一运行，检索主要英文政治学期刊、The China Quarterly 和 American Sociological Review 的新近论文，生成中文摘要与研究信息表，并自动发布到 GitHub Pages。

公网地址：https://jing-yeps.github.io/political-science-weekly/

## 自动更新配置

仓库需要设置 GitHub Secret：

- `OPENAI_API_KEY`：用于把英文摘要翻译成中文，并归纳研究主题、方法、资料和发现。

可选设置 GitHub Actions Variable：

- `OPENAI_MODEL`：默认使用 `gpt-4.1-mini`。

手动补生成某周报告时，可以在 GitHub 仓库的 Actions 页面运行 `Weekly journal report`，并填写 `report_date`、`from_date`、`to_date`。
