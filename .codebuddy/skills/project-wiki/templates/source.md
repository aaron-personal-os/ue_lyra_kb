---
id: _raw/{{SUBTYPE}}/{{DATE}}-{{SLUG}}
type: source
status: current
language: zh
owner: human  # raw 是用户给的，AI 不改
source_type: spec  # spec | meeting | chat | pr | commit | external
source_origin: {{URL_OR_PATH}}
captured_at: {{DATE}}
anchors: []
related: []
tags: [raw]
---

# {{TITLE}}

> 原始素材，AI 不会修改本文件。摘要与提炼见 ingest 后产出的 wiki 页。

## 来源

- 类型：{{SOURCE_TYPE}}（spec / 会议 / PR / commit / 外部文章）
- 出处：{{URL_OR_PATH}}
- 采集时间：{{DATE}}
- 采集方式：（手动粘贴 / 网页抓取 / 文件拷贝）

## 原文

（原文内容粘贴/拷贝到这里。如果是大文件，可以只放摘要，原文放同级 `.attachment.<ext>`。）

## 已产出的 wiki 页

ingest 后，列出本素材对应/影响的 wiki 页：

- [[20-modules/.../X]]
- [[60-decisions/NNNN-...]]
- [[70-topics/...]]
