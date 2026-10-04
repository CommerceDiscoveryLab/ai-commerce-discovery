# 商品目录契约 v1.0

目录是一个 UTF-8 JSON 对象。它来自商家的真实商品系统，不从自然语言推测事实。[JSON Schema](../schemas/catalog.schema.json) 校验结构；CLI 还检查字段之间的关系、日期、GTIN 校验位、重复项与币种精度。二者都不验证实际真实性或公网可达性。

顶层只能包含 `schema_version: "1.0"`、`demo`（布尔值）、`merchant`、`products`。`demo=true` 需要显式 `--demo` 才能导出；任何保留域名在生产导出中均被拒绝。

## 商家

| 字段 | 要求 |
| --- | --- |
| `name` | 商家公开展示名称，最多 200 字符 |
| `url` | 商家 HTTPS 站点根地址，不含路径、查询参数或凭据 |
| `country` | 此目录面向的市场，二位大写国家代码；本地只检查代码形状，不自动配置平台市场 |
| `language` | 语言标签，例如 `en-US`、`zh-CN` |
| `support_url`、`shipping_policy_url`、`return_policy_url` | 可选的公开联系、配送、退换货政策地址；缺失产生警告 |
| `privacy_policy_url`、`terms_url` | 可选的公开政策地址；不会据此宣称具备支付/结账接入能力 |

配送和退货链接用于核对上下文；本版不把 URL 推断为免费配送、可退货或具体退货天数。

## 每件可购买商品或变体

| 字段 | 必填/规则 |
| --- | --- |
| `id` | 必填，1–50 个 ASCII 字母、数字、下划线或短横线，以字母或数字开头；目录中唯一且长期稳定 |
| `title` | 必填，最多 150 字符，真实名称及所选变体 |
| `description` | 必填，最多 5000 字符，真实纯文本描述，不含 HTML |
| `url` | 必填，商家同源的 HTTPS 详情页；每个商品/所选变体具有不同 URL |
| `image_url` | 必填，该变体真实主图的公开 HTTPS 地址 |
| `brand` | 必填，页面上实际品牌，最多 100 字符 |
| `price`、`currency` | 必填，正数十进制字符串与支持的三字母币种；不接受指数、分隔符、货币符号或自动四舍五入 |
| `availability` | 必填，`in_stock`、`out_of_stock`、`pre_order`、`backorder`、`unknown` |
| `condition` | 必填，`new`、`used`、`refurbished` |
| `updated_at` | 必填，商家实际观察价库存的 ISO 8601 时间戳，必须有时区 |
| `sku`、`mpn`、`gtin` | 可选，商家 SKU、厂家型号、已分配的 GTIN。GTIN 保留前导零，只接收 8/12/13/14 位且校验位正确；校验位正确不证明它真的被分配 |
| `identifier_exists` | 可选布尔值。仅在已确认商品不存在相应标识时填 `false`；不能仅为去掉警告填写 |
| `additional_images` | 可选，最多十张其他真实视角图的 HTTPS 地址 |
| `category` | 可选，商家真实品类路径；不自动当作 Google 官方分类 ID |
| `attributes` | 可选，1–20 个真实属性文本对，键最多 100 字符、值最多 500 字符，单位应明确 |
| `group_id`、`variant` | 一起填写。稳定的分组 ID 与所选变体属性；支持 `color`、`size`、`material`、`pattern` |
| `availability_date` | 预订/延期交货时必填，有时区的预计可用日期时间；不自动切换库存状态 |

同组商品必须使用相同变体属性名、不同属性组合、同一品牌。分组 ID 不得等于目录中任何商品 ID。属性与变体若使用同一键，则值必须相同。不要把价格、库存或营销措辞放进稳定 ID。

支持币种与最大小数位：USD/CNY/EUR/GBP/AUD/CAD/HKD/SGD 为 2，JPY/KRW 为 0，KWD/BHD 为 3。这是首版范围，不代表这些市场都可接入任意平台。其他货币、零价订阅产品或复杂促销需要扩展并核对规则。

`unknown` 库存可用于 OpenAI 发现 feed；Schema.org 输出不声称它有库存，Google RSS 导出直接拒绝未知库存。跨平台输出失败时先恢复事实，不能默认当作 `in_stock`。

## 时效与导出

默认超过 48 小时的价库存快照产生警告，可用 `validate --max-age-hours` 调整。这是项目的可配置运营阈值，不是平台规则；高频变化的商品应更频繁更新。未来超过 5 分钟的更新时间产生错误。

未知字段、重复 JSON 键、非有限数值均拒绝。未提供的可选字段保持缺失，工具不凭空补值。完整示例见[演示目录](../examples/catalog.demo.json)，其中的品牌、型号、商品及域名全部虚构。
