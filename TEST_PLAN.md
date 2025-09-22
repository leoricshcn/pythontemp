# 测试计划

本测试计划用于支撑季度再融资数据采集脚本的验证工作。每次测试执行后，请在“实际结果/结论”列中记录执行情况，并同步更新 `DEVELOPMENT_PLAN.md` 中的进度。

## 测试范围
- 单元测试：覆盖解析函数与辅助函数。
- 集成测试：模拟多季度抓取流程与 CSV 输出。
- 回归测试：关键用户路径与命令行入口。

## 测试环境
- Python 3.9 及以上版本。
- 依赖安装：`pip install -r requirements.txt`。
- 离线夹具位于 `tests/fixtures/`（计划步骤完成后加入）。

## 测试用例
| 编号 | 类型 | 前置条件 | 测试步骤 | 预期结果 | 实际结果/结论 |
| --- | --- | --- | --- | --- | --- |
| TC-UNIT-001 | 单元 | 无 | 调用 `parse_maturity`，输入包含“2-Year”、“13 Week”、“30 day”等样例。 | 返回正确的期限数值与单位（YEARS/MONTHS/WEEKS/DAYS）。 | 未执行 |
| TC-UNIT-002 | 单元 | 无 | 调用 `categorize_security`，输入覆盖 Bill、Note、Bond、FRN、TIPS、未知证券。 | 正确识别证券类型，对未知输入返回 `OTHER`。 | 未执行 |
| TC-UNIT-003 | 单元 | 提供矩阵格式推荐表格 PDF 夹具。 | 调用 `_parse_matrix_recommended_pages`，验证输出条目数量与字段。 | 返回每个证券对应的推荐金额，字段完整无缺失。 | 未执行 |
| TC-UNIT-004 | 单元 | 提供文本表格格式推荐 PDF 夹具。 | 调用 `parse_recommended_pdf`，验证推荐数据与净短期国库券记录。 | 提取出的金额与日期匹配夹具内容。 | 未执行 |
| TC-UNIT-005 | 单元 | 提供官方讲话 HTML 夹具。 | 调用 `parse_official_article`，验证公告日期、历史数据与预测数据分类。 | 公告日期解析正确，历史数据标记为 `HISTORICAL_REFERENCE`，预测标记为 `INDICATIONS_FOR_NEXT_REFUNDING`。 | 未执行 |
| TC-INT-001 | 集成 | 模拟一个季度的官方讲话 HTML 与推荐 PDF 响应。 | 调用 `collect_data(max_quarters=1)`，使用 mock 会话返回夹具内容。 | 返回的条目列表包含 HTML 与 PDF 数据，数量符合预期。 | 未执行 |
| TC-INT-002 | 集成 | 准备两个季度的响应夹具。 | 调用 `collect_data(max_quarters=2)` 并验证写入 CSV。 | 输出 CSV 含有所有字段标题，行数等于所有条目之和。 | 未执行 |
| TC-CLI-001 | 回归 | 提供模拟响应夹具。 | 运行 `python collect_refunding_data.py --max-quarters 1 --output temp.csv`（功能实现后）。 | 程序正常退出，打印写入行数，生成的 CSV 可被 Pandas 读取。 | 未执行 |
| TC-CLI-002 | 回归 | 断网或模拟请求超时。 | 运行脚本，观察异常处理与日志输出。 | 程序捕获异常并输出可诊断信息，不产生部分写入的 CSV。 | 未执行 |

## 测试记录模板
执行测试时，请追加如下记录：

```
### 2024-04-05 回归测试记录
- 涉及用例：TC-INT-001, TC-UNIT-001
- 结果：全部通过
- 备注：……
```

## 风险与注意事项
- 真正的财政部网站结构可能变化，需定期更新夹具。
- PDF 解析可能受库版本影响，升级依赖后需重新运行全部回归测试。
- 若新增功能（例如 CLI 参数），请同步补充新的测试用例条目。
