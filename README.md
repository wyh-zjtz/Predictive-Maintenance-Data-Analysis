基于 Python 的工业设备传感器数据异常筛查与维护建议分析项目。项目使用公开预测性维护模拟数据，对设备运行记录进行数据质量检查、统计异常识别、故障关联分析、风险复核排序和结果可视化。

> 说明：本项目中的“统计异常”用于风险初筛，不等同于已确认的机器故障、故障诊断或故障根因。

---

## 项目背景

在工业设备维护中，设备运行参数如温度、转速、扭矩和刀具磨损可用于发现偏离常态的工况。对于维护团队而言，分析目标并不只是识别极端读数，更重要的是将有限的巡检资源优先分配给故障风险相对集中的记录。

本项目构建了一套可解释的统计筛查流程：

- 对设备传感器记录进行质量检查和描述统计；
- 使用统计阈值识别偏离总体分布的运行记录；
- 将异常筛查结果与真实机器故障标签进行交叉验证；
- 比较正常样本与故障样本的关键特征差异；
- 生成异常复核池和多指标异常优先复核清单；
- 输出面向维护场景的初步建议。

---

## 数据来源

- 数据集：UCI AI4I 2020 Predictive Maintenance Dataset
- 数据性质：公开的预测性维护模拟数据
- 原始数据规模：**10,000 条记录、14 个源字段**
- 数据文件：`ai4i2020.csv`

数据集包含以下主要字段：

| 字段 | 含义 |
|---|---|
| `UDI` | 样本记录编号 |
| `Product ID` | 产品编号 |
| `Type` | 产品质量变体，分为 L、M、H |
| `Air temperature [K]` | 空气温度 |
| `Process temperature [K]` | 过程温度 |
| `Rotational speed [rpm]` | 转速 |
| `Torque [Nm]` | 扭矩 |
| `Tool wear [min]` | 刀具磨损时间 |
| `Machine failure` | 是否发生机器故障 |
| `TWF` / `HDF` / `PWF` / `OSF` / `RNF` | 细分故障标签 |

### 数据使用边界

- `UDI` 是记录编号，**不是时间戳**，不能用于真实时序趋势或设备退化过程分析。
- `Product ID` 在该数据集中每条记录唯一，不能用于跟踪同一台物理设备的长期状态。
- `Type` 表示模拟数据中的产品质量变体，不应解释为设备型号或设备类型。
- 该数据为模拟数据，结果需要经过真实现场数据验证后才能用于生产环境。

---

## 分析方法

### 1. 数据质量检查

对数据完成以下检查：

- 数据维度与字段类型检查；
- 缺失值检查；
- 重复记录检查；
- 描述统计量计算与导出。

### 2. 单变量统计异常筛查

针对以下传感器指标进行异常筛查：

- 空气温度；
- 过程温度；
- 转速；
- 扭矩；
- 刀具磨损。

对于每个指标，满足以下任一条件即标记为统计异常：

1. 数值位于均值 ± 3 倍标准差之外；
2. 数值低于 1% 分位数或高于 99% 分位数。

当一条记录至少有一个指标被标记为异常时，将其纳入异常初筛复核池。

### 3. 风险分组

根据一条记录触发的异常指标数量进行统计风险分组：

| 分组 | 异常指标数量 | 定位 |
|---|---:|---|
| Normal | 0 | 未触发统计异常 |
| Low | 1 | 单指标统计异常 |
| Medium | 2 | 双指标统计异常 |
| High | 3 项及以上 | 多指标统计异常 |

该分组用于复核排序，不是官方故障等级，也不代表故障率必然随风险等级严格递增。

### 4. 故障标签验证

将统计异常标记与 `Machine failure` 真实故障标签进行交叉验证，并计算：

- Precision：异常记录中真实故障的比例；
- Recall：真实故障中被异常规则筛查出的比例；
- Specificity：未故障记录未被规则误判为异常的比例。

---

## 关键结果

### 1. 数据质量可用

- 原始数据集包含 **10,000 条记录、14 个源字段**；
- 缺失值数量为 **0**；
- 重复记录数量为 **0**；
- 数据完整，可用于后续统计分析与异常筛查。

### 2. 共筛查出 616 条统计异常记录

使用“均值 ± 3σ”与“1%/99% 分位数”联合规则后：

- 共识别 **616 条统计异常记录**；
- 占全体记录的 **6.16%**；
- 转速异常比例最高，为 **2.62%**；
- 扭矩异常比例为 **1.98%**；
- 过程温度异常比例为 **1.95%**。

这些记录应作为初步复核对象，而不是直接被定义为故障。

### 3. 异常规则能够集中故障风险，但不能替代故障诊断

统计异常与真实故障标签的交叉验证结果：

| 统计异常状态 | 未发生机器故障 | 发生机器故障 |
|---|---:|---:|
| 否 | 9,171 | 213 |
| 是 | 490 | 126 |

| 指标 | 结果 |
|---|---:|
| 异常记录数 | 616 |
| 实际机器故障数 | 339 |
| Precision | **20.45%** |
| Recall | **37.17%** |
| Specificity | **94.93%** |
| 正常组观察故障率 | **2.27%** |
| 异常组观察故障率 | **20.45%** |

异常组的观察故障率显著高于正常组，说明规则可用于低成本、可解释的风险初筛。但规则存在误报和漏报，不能作为独立的故障预测或根因诊断工具。

### 4. 故障样本具有更高扭矩与更高刀具磨损

故障样本与正常样本的均值对比：

| 指标 | 正常样本均值 | 故障样本均值 | 变化 |
|---|---:|---:|---:|
| 转速 | 1540.26 rpm | 1496.49 rpm | -2.84% |
| 扭矩 | 39.63 Nm | 50.17 Nm | **+26.59%** |
| 刀具磨损 | 106.69 min | 143.78 min | **+34.76%** |

此外，故障类型中：

- 散热故障（HDF）出现 **115 次**，为最高频故障标签；
- 过载故障（OSF）出现 **98 次**；
- 功率故障（PWF）出现 **95 次**。

高扭矩和高刀具磨损与故障记录存在明显关联，适合作为重点风险筛查信号；但正常与故障样本仍有分布重叠，因此不能单独作为故障判据。

---

## 图表

### 扭矩与刀具磨损：正常和故障记录对比

该图展示了故障记录在高扭矩、高刀具磨损区域出现得更频繁，但两类样本仍有重叠。

![Torque vs Tool Wear](analysis_output/torque_vs_tool_wear_by_failure.png)

### 不同统计风险分组的观察故障率

该图用于展示统计异常规则是否能将故障风险集中到非正常组。

> 图中的数值为观察故障率，不是模型预测概率或模型准确率。

![image](https://github.com/wyh-zjtz/Predictive-Maintenance-Data-Analysis/blob/main/img/observed_failure_rate_by_risk_level.png)

### 转速与扭矩分布

![Rotational Speed and Torque Distribution](analysis_output/rotational_speed_and_torque_distribution.png)

### 过程温度与记录编号

![image](https://github.com/wyh-zjtz/Predictive-Maintenance-Data-Analysis/blob/main/img/process_temperature_by_record_index.png)

> `UDI` 为记录编号而非时间戳，因此该图仅展示样本顺序下的分布位置，不代表真实设备时间趋势。

---

## 输出文件

脚本运行后将在 `analysis_output/` 目录生成分析结果：

```text
analysis_output/
├── data_quality_summary.csv
├── descriptive_statistics.csv
├── anomaly_metric_summary.csv
├── statistical_anomaly_records.csv
├── priority_inspection_records.csv
├── risk_level_summary.csv
├── product_type_summary.csv
├── failure_type_summary.csv
├── normal_vs_failure_metric_comparison.csv
├── anomaly_failure_crosstab.csv
├── anomaly_rule_validation_summary.csv
├── process_temperature_by_record_index.png
├── rotational_speed_and_torque_distribution.png
├── torque_vs_tool_wear_by_failure.png
├── observed_failure_rate_by_risk_level.png
└── executive_summary.txt
