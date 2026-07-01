---
name: criminal-dossier-review-cn
description: 中国大陆刑事案件卷宗阅卷 skill。用于多卷、大体积 PDF 刑事卷宗的本地预处理、Umi-OCR 页级识别、卷宗索引、阅卷报告、精读分析、全案证据框架和带卷名页码定位的质证意见。触发场景包括刑事阅卷、审查起诉阅卷、庭审质证准备、刑事证据审查、卷宗 OCR、讯问笔录比对、电子数据/鉴定意见/扣押清单审查、证据缺口和辩护意见准备。
---

# 刑事案件阅卷

## 核心原则

- 用中文输出，先给结论再说明依据；区分卷宗记载、OCR 识别、原件核验、法律依据和分析判断。
- 原始卷宗只读处理：用户提供原始 PDF 文件夹路径，不复制原始 PDF 到工作区。
- 工作区只保存派生文件：OCR JSON、OCR 文本、索引、缓存、分析笔记、输出成果。解密/去水印副本仅在必要时生成，并标注“仅供 OCR/检索，不作为原件”。
- 不模拟人类三遍阅卷；采用一次流水线处理，同步分层产出索引、报告、分析、证据框架和质证意见。
- OCR 只用于检索和初筛。签名、捺印、印章、页码、讯问起止时间、讯问人/记录人、认罪认罚具结书、扣押清单、鉴定意见等关键事实必须回看原始页图或原 PDF。
- 引用法条、司法解释、量刑规则、类案时必须核验现行有效来源；未核验写“引用待核实”。参考资料是学习材料，不替代现行法律依据。

## 工作流

1. **案件入口核验**
   - 确认案件阶段、涉嫌罪名、我方身份、是否审查起诉阶段、是否兼顾庭审质证。
   - 确认材料使用限于本案程序范围内。未确认保密和使用边界时，只能做流程建议，不进入实质阅卷。

2. **预处理与索引**
   - 读取 `references/preprocessing.md`。
   - 对原始路径运行 `scripts/scan_dossier.py`，生成文件清单、页数、加密状态、可读状态和文本层状态。
   - 如需 OCR，优先调用本机 Umi-OCR API；禁止默认调用云端 OCR 或在线 AI 服务。
   - 运行 `scripts/build_index.py` 生成页级索引、材料目录草表和 SQLite 检索库。

3. **证据分类与审查框架**
   - 读取 `references/evidence-categories-cn-criminal.md` 和 `references/criminal-evidence-review-primer.md`。
   - 以《刑事诉讼法》第五十条八类证据为主轴分类：物证、书证、证人证言、被害人陈述、犯罪嫌疑人/被告人供述和辩解、鉴定意见、勘验检查辨认侦查实验等笔录、视听资料/电子数据。
   - 技术侦查/调查证据、行政执法证据转化、监察证据转化作为扩展问题单独标注。

4. **一次流水线分层产出**
   - 先输出 `卷宗索引.md`，让律师快速知道卷宗结构、缺页、重复、模糊和 OCR 风险。
   - 同步输出 `阅卷报告.md`，形成全案初步认识：案件概况、指控事实、证据结构、关键人物、关键时间线、初步争点和明显缺口。
   - 输出 `精读分析笔记.md`，按法定证据类别记录摘录、定位、证明目的、三性问题、矛盾点和待核实事项。
   - 输出 `全案证据框架.md`，以待证事实、构成要件、量刑情节为主线，整理已有证据、缺失证据、有利证据、不利证据和证据链断点。
   - 输出 `质证意见.md`，每项证据必须附卷名、原始 PDF 文件名或路径、PDF 页序号、卷宗页码和庭审快速定位提示。

## 参考文件导航

- `references/preprocessing.md`：处理大体积 PDF、密码、水印、Umi-OCR、缓存和断点续跑。
- `references/criminal-evidence-review-primer.md`：默认审查总纲，来自本地“刑事证据审查书籍精华提炼”。
- `references/criminal-evidence-review-knowledge.md`：四份学习材料的“标准-方法-清单-问题”规则库。
- `references/evidence-categories-cn-criminal.md`：刑事诉讼法证据类别和各类质证重点。
- `references/dossier-index-template.md`：卷宗索引和页级索引模板。
- `references/reading-report-template.md`：阅卷报告模板。
- `references/deep-review-template.md`：精读分析笔记模板。
- `references/evidence-framework-template.md`：全案证据框架模板。
- `references/cross-examination-template.md`：质证意见模板。
- `references/quality-gates.md`：交付前必须执行的质量闸门。

## 脚本使用

脚本均以 UTF-8 文本输出，默认不修改原始 PDF。

```powershell
python scripts/scan_dossier.py "D:\案件卷宗原始路径" --case-dir "cases\案件名"
python scripts/ocr_with_umi.py --case-dir "cases\案件名" --umi-url "http://127.0.0.1:1224/api/ocr"
python scripts/build_index.py --case-dir "cases\案件名"
python scripts/search_evidence.py --case-dir "cases\案件名" --query "讯问笔录"
```

运行大型卷宗时，先做清点模式，再决定 OCR 范围。不要一次性把全卷 OCR 文本读入上下文；用索引、关键词、证据类别和页码范围分批读取。

## 质证意见硬要求

每条质证意见至少包含：证据名称、法定证据类别、卷名、原始文件名或路径、PDF 页序号、卷宗页码、控方证明目的、对我方影响、真实性意见、合法性意见、关联性意见、证明力意见、质证结论、庭审快速定位提示、辩护意见引用提示。

对不利证据不得机械否定；区分排除证据、削弱证明力、限制证明目的、要求补强、保留异议。对有利证据写明采信方向和证明价值。
