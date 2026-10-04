# 贡献方式

欢迎改进商品系统连接器、目录数据质量、变体与市场适配、输出一致性和观察方法。提交改动时说明具体问题、改后的行为、验证方式与平台规范链接及日期。

所有公开示例必须虚构并标记 demo；不要提交真实客户目录、后台截图、订单、凭据或私有日志。真实商家的效果主张须有授权、测量方法、适用范围和可复核数据，不能根据一个模型回答宣传普遍排名提升。

开发检查：

```sh
python3 -m unittest discover -s tests -v
python3 -m commerce_discovery validate examples/catalog.demo.json
git diff --check
```

以小而明确的改动为主。涉及平台字段或逻辑时更新映射说明和有意义的测试；不要为真实商家编造标识、评价、价格、库存、配送或认证。报告工具漏洞见 [SECURITY.md](SECURITY.md)。
