# AI Commerce Discovery

**让电商商品信息更容易被 AI 搜索、购物助手和检索系统读取、核对与引用。** 从一份真实商品目录生成结构化数据和商品 feed，并检查价格、库存、标识与网页数据的一致性。

[English](README.en.md) · [商品格式](docs/catalog-contract.md) · [接入指南](docs/integration.md) · [发现检查表](docs/discovery-checklist.md) · [品牌与组织](docs/branding.md)

**联系：** [petterzhang0514@gmail.com](mailto:petterzhang0514@gmail.com)

## 能做什么

| 电商团队的问题 | 首版实现 |
| --- | --- |
| 商品名称、规格、品牌、价格散落在不同系统 | 一个有版本的商品目录格式，校验必填字段、GTIN 校验位、变体分组、价格精度和更新时间 |
| 页面仅靠前端 JavaScript 展示，机器难以直接读取 | 生成静态商品页与 Schema.org `Product` / `Offer` JSON-LD，也可单独导出嵌入现有商城 |
| 多个平台需要不同商品数据格式 | 导出 OpenAI 发现用途 JSONL（US/USD 基线）与 Google Merchant RSS XML 基线 |
| 商品页面和 feed 的价格、库存不一致 | 对保存的 HTML 做基础检查，并与指定目录商品的 JSON-LD 价格、币种、库存做比对 |
| 页面缺少清晰的抓取入口和来源 | 生成 sitemap、robots 模板、`catalog.json` 和逐商品 JSON-LD 文件，提供政策与商家上下文链接 |
| 修改后不知道是否改善了发现效果 | 提供基线查询、抓取日志、引用和引流结果的记录方法，分开评估可抓取、收录、推荐和成交 |

**版本 0.1.0。** CLI 离线运行，不需要模型 API 密钥；生成文件后由商家部署到自己的商城并按各平台流程接入。结构化数据和 feed 可以改善信息可读取性，但不保证 AI 收录、推荐位置、流量或销量。公开 GitHub 仓库本身不会把商品自动提交给任何平台。

## 五分钟试用

Python 3.9+，运行时只依赖标准库；在克隆后的仓库目录执行：

```sh
git clone https://github.com/CommerceDiscoveryLab/ai-commerce-discovery.git
cd ai-commerce-discovery

# 检查三件虚构商品；演示地址会产生预期的警告
python3 -m commerce_discovery validate examples/catalog.demo.json

# 一次构建商品页、feed、JSON-LD、sitemap 和 robots 模板
python3 -m commerce_discovery build examples/catalog.demo.json --demo --out dist/demo

# 分别导出到你的商城或数据处理流程
python3 -m commerce_discovery export examples/catalog.demo.json --format jsonld --demo --out dist/jsonld.json
python3 -m commerce_discovery export examples/catalog.demo.json --format openai --demo --out dist/openai.jsonl
python3 -m commerce_discovery export examples/catalog.demo.json --format google --demo --out dist/google.xml

python3 -m unittest discover -s tests -v
```

构建目录必须不存在或为空；再次运行时请使用新目录，如 `dist/demo-2`。示例使用虚构商品和保留域名，HTML 标记 `noindex`，robots 禁止抓取。不得把演示 feed 当真实商品提交。

本地查看演示：

```sh
python3 -m http.server 8080 --bind 127.0.0.1 --directory dist/demo
```

在浏览器打开 `http://127.0.0.1:8080/`。演示图片展示占位地址，不包含真实商品图片，也不是可购买商城。

## 用于真实商家

1. 将 PIM、ERP、商城或 CSV 的真实字段映射到[目录格式](docs/catalog-contract.md)；示例只是起点，本版不含 Shopify、WooCommerce 或 ERP 连接器。
2. 使用商家自己的 HTTPS 商品地址和真实图片，填写已分配的标识、当前可支付价格、库存、品牌与政策链接，将 `demo` 设为 `false`。
3. 运行 `validate --strict`。缺失或过期信息要追查来源，不通过编造品牌、GTIN、评价或认证消除警告。
4. 为既有商城导出 JSON-LD / feed；静态 `build` 是参考发布方式，其页面没有购物车或支付功能。构建器要求独立 URL 路径；使用查询参数选择变体的商城应采用单独导出。
5. 由开发者把结构化数据嵌入真实可购买页面，合并 sitemap / robots，验证 HTTP 状态、图片、公开抓取、可见价格与结账价格。
6. 依各平台的资质与市场支持提交 feed，查看实际处理回执；价格或库存变化后重新同步。[完整指南](docs/integration.md)。

本地网页检查示例：先把**你有权访问的商品页 HTML**保存到文件，再执行：

```sh
python3 -m commerce_discovery audit-page saved-product.html --catalog your-catalog.json --id YOUR-ITEM-ID
```

审计器检查保存的 HTML，不请求网络，也不执行 JavaScript。它比较 JSON-LD 与目录，不能替代可见页面、HTTP 响应、WAF、图片或真实结账的验证。演示页的 `noindex` 会被审计器正确报告为阻断项。

退出码：`0` 无阻断错误，`1` 发现阻断错误（或 `--strict` 下存在警告），`2` 无效输入、I/O 或不支持的导出操作。非严格验证的 `0` 可能仍有警告；读取完整 JSON 报告。`0` 不表示已被平台收录。

## 平台与标准边界

- Schema.org 描述商品与报价的可读结构；本版输出单个 `Product`，用分组 ID 标识变体，不生成完整 Google `ProductGroup` 丰富结果实现。
- Google RSS 导出是基础字段映射，品类、国家、配送、税务及 Merchant Center 账户要求仍由商家验证。
- OpenAI adapter 依据 2026-10-04 核对的 Stable 文件规范，采用当前字段名，限定发现用途与 US/USD 基线，不启用广告或结账。其他市场需要先确认平台支持并扩展适配器。
- OpenAI 官方接入仍需获批；让爬虫访问网页与接入官方商品 feed 是不同路径。搜索抓取设置和模型训练抓取设置也不同。
- Claude、其他 GPT 和自建 agent 可通过其可用工具读取公开页面或目录，但没有“所有 AI 通用自动推荐接口”。

来源与核验日期见[官方参考](docs/references.md)。本版没有实测排名提升结论，不采用隐藏提示词、伪造评价、站群、关键词刷屏或对 AI 施加推荐指令。

## 文件与贡献

`commerce_discovery/` 是工具；`schemas/catalog.schema.json` 是输入结构；`examples/` 是虚构样本；`docs/` 是商家工作流；`tests/` 检查语义、格式与安全输出。下一步可以扩展商品系统连接器、完整变体标记、市场适配和效果监测，以真实数据与平台回执验证结果。

项目采用 MIT，欢迎按 [CONTRIBUTING.md](CONTRIBUTING.md) 提交改进。敏感问题见 [SECURITY.md](SECURITY.md)。项目名称独立于维护者账号；GitHub 地址必须包含账号或组织命名空间，组织迁移方式见[品牌说明](docs/branding.md)。
