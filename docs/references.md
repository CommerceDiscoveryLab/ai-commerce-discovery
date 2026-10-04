# 官方参考与核验记录

核验日期：2026-10-04。这些文档支持字段含义和接入边界，不能证明本项目已获平台认可、已接入任何商家或提升了实际排名。外部规范会更新，升级 adapter 前重新核对。

| 来源 | 用途与范围 |
| --- | --- |
| [Schema.org Product](https://schema.org/Product) / [Offer](https://schema.org/Offer) | 商品、报价、标识与属性的语义映射 |
| [Google Merchant listing structured data](https://developers.google.com/search/docs/appearance/structured-data/merchant-listing) | 商品页与报价基础、与实际页面内容相符的要求；本地审计不是完整官方验证 |
| [Google Merchant product data specification](https://support.google.com/merchants/answer/7052112?hl=en) | RSS 导出的基础商品字段；品类、国家和账户要求另行验证 |
| [Google Identifier exists](https://support.google.com/merchants/answer/6324478?hl=en) | 标识不存在必须来自真实事实，不能自动推断 |
| [OpenAI Stable product file reference](https://developers.openai.com/commerce/specs/file-upload/products?version=currently-stable) | OpenAI 发现 feed 的当前字段、变体与明确的市场范围；不是完整广告或结账实现 |
| [OpenAI Commerce get started](https://developers.openai.com/commerce/guides/get-started) | 接入资格、文件/API路径和官方处理流程 |
| [OpenAI crawler documentation](https://developers.openai.com/api/docs/bots) | 搜索、用户访问与训练抓取的用途区分 |
| [GitHub organization creation](https://docs.github.com/en/organizations/collaborating-with-groups-in-organizations/creating-a-new-organization-from-scratch) | 用组织命名空间建立独立项目地址 |

代码只覆盖文档中的一部分明确字段。目录使用一个商家、一个目标市场，正价零售商品；复杂促销、数字服务、完整 ProductGroup、配送报价、多市场或支付流程不在首版范围内。
