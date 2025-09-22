# 退款数据采集脚本软件设计文档

## 1. 文档概述
- **项目名称**：季度再融资公开信息采集脚本
- **版本**：v1.0（初稿）
- **作者**：自动生成
- **最后更新时间**：2025-09-21
- **适用范围**：本设计文档适用于 `collect_refunding_data.py` 脚本及其相关资源。

## 2. 背景与目标
美国财政部在季度再融资公告中发布推荐融资表格（PDF）与官方讲话（HTML）。本脚本自动化抓取最新若干个季度的公开数据，解析结构化信息，并生成统一的 CSV 输出文件，便于后续的数据分析与可视化。

## 3. 系统范围
- **包含内容**：
  - 从财政部官网抓取推荐融资表格与官方讲话页面。
  - 解析 HTML 表格与 PDF 文件中的拍卖规模数据。
  - 统一整理字段并输出 `refunding_data.csv`。
- **不包含内容**：
  - 历史文件的本地缓存与增量更新。
  - 数据可视化、数据库入库或 API 服务。
  - 抓取失败的自动重试与报警机制。

## 4. 关键需求
### 4.1 功能性需求
1. 默认抓取最近四个季度的数据，支持通过 `max_quarters` 参数调整。
2. 解析官方讲话 HTML 表格，输出历史实际拍卖与下一季度预测数据。
3. 解析推荐融资 PDF 中的表格信息，兼容常规文本表格与矩阵格式。
4. 生成包含固定字段集的 CSV 文件，字段顺序保持稳定。
5. 在控制台输出写入记录数。

### 4.2 非功能性需求
- **可靠性**：在网络正常的情况下，应尽量捕获解析异常并给出可诊断的信息。
- **可维护性**：代码应模块化，函数职责单一，易于扩展新的解析逻辑。
- **可移植性**：依赖的第三方库应在常见的 Python 环境中可用。
- **性能**：一次运行的网络请求量为选定季度数的两倍（HTML+PDF），可接受。

## 5. 系统上下文
```
财政部官网 (HTML, PDF)
        │
        ▼
collect_refunding_data.py
        │
        ▼
  refunding_data.csv
```
- 外部依赖：`https://home.treasury.gov` 网站。
- 输出结果：本地 CSV 文件，供分析工具（如 Pandas、Excel）使用。

## 6. 架构与组件设计
脚本为单文件结构，通过若干函数协作完成数据收集，主要组件如下：

### 6.1 链接收集层
- `extract_quarter_links(page_url)`：解析季度索引页面的 HTML 表格，抽取季度对应的详情页链接。利用 BeautifulSoup 和正则处理年份、季度信息。
- `extract_official_links()` / `extract_recommended_links()`：分别针对官方讲话和推荐表格两个页面调用通用函数。
- `quarter_key(year, quarter)`、`format_quarter(year, quarter)`：封装季度键与显示文本。
- `absolute_url(href)`：确保相对链接转换为绝对 URL。

### 6.2 解析层
- **官方讲话解析** `parse_official_article`：
  - 使用 BeautifulSoup 提取公告日期（ISO 时间）。
  - 在正文表格中识别月份行，解析各证券列的数值。
  - 根据是否包含 `<strong>` 或表头加粗判断预测值与历史值，设置 `Data_type` 字段。
  - 将证券名称映射至类别（`categorize_security`）、期限（`parse_maturity`）。

- **推荐表格解析** `parse_recommended_pdf`：
  - 通过 pdfplumber 提取 PDF 文本。
  - 判断是否为矩阵布局，若是则交由 `_parse_matrix_recommended_pages`。
  - 对文本型表格使用正则提取证券、日期、金额等字段。
  - 处理“净短期国库券发行量”等特殊行。
  - 记录推荐类型、拍卖月份、备注信息。

- **辅助函数**：
  - `parse_maturity`：从证券文本提取期限数值及单位。
  - `categorize_security`：基于关键词分类证券类型。
  - `_parse_matrix_recommended_pages`：对矩阵格式的 PDF 表格按固定列索引提取数值。

### 6.3 业务流程控制层
- `collect_data(max_quarters)`：
  - 构建官方讲话与推荐表格的季度链接字典。
  - 求交集并按时间倒序选择最近若干季度。
  - 循环下载 HTML/PDF，调用解析函数并汇总结果。
  - 使用 `requests.Session` 复用连接，提高性能。

- `write_csv(entries, path)`：
  - 以固定字段顺序写入 CSV。
  - 确保 UTF-8 编码及换行兼容。

- `main()`：
  - 执行数据收集与写入。
  - 输出写入记录数量。

## 7. 数据模型
输出 CSV 字段定义如下：

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| `Quarter_year` | `str` | 季度标签，例如 `Q1 2024`。|
| `Date` | `str` | 公告日期（官方讲话）或继承自公告日期。|
| `Security_type` | `str` | 证券分类：`BILL`、`NOTE`、`BOND`、`TIPS`、`FRN` 等。|
| `Maturity` | `float/str` | 期限数值（年为主），若无法解析则为空字符串。|
| `Units` | `str` | 期限单位，常见为 `YEARS`。|
| `Auction_month` | `str` | 拍卖月份（`YYYY-MM`），若无则为空。|
| `Auction_date` | `str` | 拍卖具体日期（`YYYY-MM-DD`），仅对推荐表格中含日信息的证券有效。|
| `Offered_amount` | `float` | 拍卖规模或净发行量，单位与源文档一致（通常为十亿美元）。|
| `Data_type` | `str` | 数据来源类型：`RECOMMENDATION_FOR_THIS_REFUNDING`、`INDICATIONS_FOR_NEXT_REFUNDING`、`HISTORICAL_REFERENCE`。|
| `Notes` | `str` | 备注信息，指出数据背景或特殊说明。|

## 8. 运行流程
1. `main()` 调用 `collect_data()`。
2. `collect_data()` 获取官方讲话与推荐表格的季度链接，并选取最近 N 个季度。
3. 对每个季度：
   1. 下载官方讲话 HTML，解析得到公告日期与表格条目。
   2. 下载推荐 PDF，解析生成条目。
4. 汇总所有条目后通过 `write_csv()` 写出 CSV。
5. 控制台打印写入行数。

## 9. 配置与参数
- `DEFAULT_MAX_QUARTERS`：默认抓取季度数（4）。
- 命令行当前未暴露参数，可通过修改 `main()` 或在外部调用 `collect_data(max_quarters=...)` 覆盖。
- 所有 URL 常量位于模块顶部，若财政部网站路径调整需同步更新。

## 10. 错误处理与日志
- 使用 `response.raise_for_status()` 捕获 HTTP 错误。
- 若无法在页面找到季度表格或公告日期，会抛出 `RuntimeError`。
- 对解析失败的行采用忽略策略，保证整体流程继续执行。
- 建议在未来加入结构化日志与异常分类，以便排查。

## 11. 外部依赖
- Python 3.9+
- 第三方库：
  - `requests`：HTTP 请求。
  - `beautifulsoup4` 与 `lxml`：HTML 解析。
  - `pdfplumber`：PDF 内容提取。
- 操作系统：任意支持上述依赖的环境（Linux/macOS/Windows）。

## 12. 安全与隐私
- 数据来源为公开信息，无敏感数据存储。
- 网络访问仅限财政部官网，需遵守对方的访问政策与速率限制。
- 建议通过 HTTPS（默认）访问，避免中间人攻击。

## 13. 性能与扩展性
- 目前按季度顺序串行抓取，网络延迟占主导。
- `requests.Session` 已减少连接开销。
- 若未来需要抓取大量历史数据，可考虑：
  - 引入并发下载（注意速率限制）。
  - 缓存已下载的 PDF/HTML。
  - 将解析结果持久化到数据库。

## 14. 测试策略
- **单元测试建议**：
  - 为 `parse_maturity`、`categorize_security` 等纯函数编写测试用例。
  - 利用离线 HTML/PDF 样本测试解析函数。
- **集成测试建议**：
  - 通过模拟 HTTP 响应验证 `collect_data()` 的整体行为。
  - 针对实际网站执行端到端测试（需控制频率，避免影响官网）。

## 15. 部署与运行
- 脚本以命令行工具形式运行：`python collect_refunding_data.py`。
- 推荐在虚拟环境中安装依赖并定期运行（如使用 cron）。
- 运行后生成 `refunding_data.csv` 文件于当前目录。

## 16. 已知风险与改进方向
- 网站结构变动可能导致解析失败，需定期验证。
- PDF 表格格式较多样，解析规则需持续迭代维护。
- 缺乏重试和错误告警机制，建议结合监控工具使用。
- CSV 输出缺少单位元数据，后续可补充列或配套文档说明。

## 17. 附录
- 主要源文件：`collect_refunding_data.py`
- 输出数据样例：运行脚本后生成的 `refunding_data.csv`
- 依赖安装示例：
  ```bash
  pip install -r requirements.txt  # 若未来添加
  ```

