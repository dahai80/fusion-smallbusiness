# 架构合规整改计划

> 审计日期: 2026-08-02
> 关联 Issue: #10
> 违规等级: P1（职责边界违规，需近期整改）
> 合规评级: C

## 层级定位

**五、垂直行业产品** — 中小企业

核心职责：中小企业特有的业务逻辑和场景。

## 违规项与整改

| # | 违规项 | 整改方案 | 截止 |
|---|--------|----------|------|
| 1 | src/fsb/engine/llm_client.py 绕过 fusion-core | 改为使用 fusion_core.mlx_client.FusionMLXClient | P1-S1 |
| 2 | EventBus/Connector/Skill/Workflow Registry 自建通用中间件 | 抽取至 fusion-plugins-ecosystem 或独立 L4 模块 | P1-S2 |

## 对标合规项目

fusion-finance、fusion-k12-teacher 正确使用 fusion_core.mlx_client.FusionMLXClient，应以他们为标杆。

## 合规标准

整改完成后：
- 使用 fusion_core.mlx_client.FusionMLXClient 调用 LLM
- 不自建通用中间件
- 只包含中小企业特有业务逻辑
