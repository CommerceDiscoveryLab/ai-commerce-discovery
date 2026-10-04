# 电商团队接入流程

## 从商品系统到公开信息

把 PIM/ERP/商城作为事实来源，映射到本项目目录。保持变体、商家、当前价格、币种和库存明确，不将营销文本当规格。对图片、型号、认证及评价单独保留来源记录；本版不包含评价或认证的自动生成。

对已运行商城，优先单独导出 JSON-LD 和 feed，把它们接入已有页面与同步任务。`build` 用来展示可直接读取的静态参考页面，没有购买、登录、订单或支付功能。不要把参考页面当作已具备商家交易能力的网站。

静态目录中的页面路径来自商品 URL，因此要求独立路径，扩展名仅支持 `.html` 或无扩展名。具有查询参数的变体可正常用于导出，但静态构建器会拒绝。现有平台如果已有结构化数据，合并前检查重复 Product、不同价库存与多份 canonical。

## Schema.org 与网页

每个商品生成 Product/Offer，品牌、主图、描述、SKU、价格、币种、库存与商家取自目录。额外规格用 PropertyValue；已知变体属性使用对应字段。输出以 `inProductGroupWithID` 保留分组，不声称实现完整 Google ProductGroup 富结果。

页面可见内容、JSON-LD、feed 与实际结账应来自同一当前快照。使用 [Google Rich Results Test](https://search.google.com/test/rich-results) 与 [Schema.org Validator](https://validator.schema.org/) 复核，再通过商家站点自己的日志与控制台验证抓取。

`audit-page` 只读保存的 HTML。可检测基础元数据、canonical、noindex、JSON-LD 格式，以及 JSON-LD 与所选目录商品的价库存差异。它不会执行前端脚本，也不能证明 HTTP 200、图片质量、可见价格正确、政策有效或真实结账可完成。

## OpenAI 发现 feed

adapter 使用 2026-10-04 核验的 Stable 文件规范的当前字段名，将目录 ID 映射为 item ID，显式禁用广告与结账。仅支持此版本的 US/USD 基线；目录的国家字段不会自动改变 OpenAI 的市场配置。其他市场须先得到平台确认，再修改适配器。

```sh
python3 -m commerce_discovery export your-catalog.json --format openai --out dist/openai.jsonl
```

获得商家接入资格后按 [OpenAI 官方流程](https://developers.openai.com/commerce/guides/get-started)提交，读取处理结果并修复被拒行。输出文件是准备材料，不是提交回执或上架证明。本版不调用任何商家 API、不申请资质、不上传数据、不做 ACP 结账接入。

变体按独立行、共享分组和所选选项导出。未知库存原样保留；不会默认声称有货。通用目录的 `availability_date` 不转成未核对的 OpenAI 发现字段；预计日期保留在页面和 Google feed。商品状态变化时重新提交真实当前值，不能依赖日期自动切换。

## Google 与其他 agent

Google exporter 生成 RSS XML 基础字段；预订映射到 Google 的 `preorder`。未知库存会使导出失败。商家仍须核对品类标识、图片、配送、税务、国家以及账户与政策资格；这些不是本地校验器的全部覆盖范围。

```sh
python3 -m commerce_discovery export your-catalog.json --format google --out dist/google.xml
```

自建 agent 或可使用网络/工具的 GPT、Claude 可以读取公开商品页、`catalog.json` 或逐商品 JSON-LD。开发者需显式接入检索或产品查询工具。给 GitHub 仓库加文件不会自动改变第三方的训练、搜索或推荐系统。

## 爬虫与部署

生产 robots 模板保持公共商品页可抓取，对账户、后台、购物车、结账和私有路径限制抓取；每个特定 agent 组重复这些限制，避免特定组覆盖通用组。默认限制 GPTBot；`--allow-training` 是显式选择，仅改变生成的模板。搜索与训练是不同用途。robots 不是认证控制，私有资源必须由真实鉴权保护。

把模板合并进现有站点，不覆盖商家已有的安全与抓取策略。检查 WAF、CDN、HTTP 头、重定向和实际爬虫访问。demo 模式的 robots 与 noindex 应只用于测试；使用真实目录生产构建后，检查最终输出状态。

每次生成新的快照目录，再由商家正常部署流程切换。不要把删除商品的旧文件留在服务目录中。同步价库存、保留构建版本与平台回执，发生不一致时暂停推广并修正信息。
