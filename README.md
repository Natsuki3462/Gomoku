# GomokuFloat

置顶半透明的桌面浮窗，用肉眼复刻真实对局、由本地 Rapfi 实时提示最佳落点。  
支持**连珠（有禁手）**&#x4E0E;**无禁手**两种规则。

纯本地运行：不截图、不识别、不联网、不上传任何东西。

---

## 功能

- **15×15 交叉点棋盘**，自绘：木纹底色、星位、双线外框
- **单点落子**：点空交叉点即落子，无「起点→终点」
- **引擎建议**：绿色圆环标出推荐落点；灰色表示上一轮遗留
- **空格一键落子**在建议位置，或打开 `A` 自动落子
- **禁手提示**：连珠模式下黑棋回合，悬停禁手点显示红叉
- **规则切换**：连珠（有禁手）↔ 无禁手，切换即重置棋局
- **撤销 / 重做 / 回退到第 N 手**，历史条点任意一手跳转
- **四档分析强度**，引擎低优先级不抢 CPU
- 无级透明度、置顶、紧凑模式

## 快捷键

| 键                   | 作用                     |
| ------------------- | ---------------------- |
| `空格`                | 在建议位置落子                |
| `Ctrl+Z` / `Ctrl+Y` | 撤销 / 重做                |
| `F`                 | 翻转视角                   |
| `N`                 | 新开一局                   |
| `↑` / `↓`           | 透明度 ±2%                |
| `Ctrl+滚轮`           | 任意位置调透明度               |
| `Ctrl+1` ~ `Ctrl+4` | 分析强度：轻快 / 均衡 / 深度 / 极限 |
| 双击顶栏                | 紧凑模式                   |

---

## 快速开始

```bash
git clone <本仓库地址>
cd Gomoku
```

**第 1 步：放引擎**

从 <https://github.com/dhbloo/rapfi/releases> 下载 `Rapfi-engine.7z`（约 37MB），  
**整个解压目录的内容**放进 `engine/`。必须保留这几类文件：

| 文件                           | 作用                                                   |
| ---------------------------- | ---------------------------------------------------- |
| `pbrain-rapfi-windows-*.exe` | 引擎本体，按 CPU 指令集选一个                                    |
| `config.toml`                | 规则与权重映射配置，缺了引擎起不来                                    |
| `mix9svq*.bin.lz4`           | 四份 NNUE 权重（freestyle / standard / renju 黑 / renju 白） |
| `model210901.bin`            | 基础模型                                                 |

指令集选择：`avxvnni` > `avx2` > `sse`，从高到低试，能启动就用。  
`avx512` 版本在 12~14 代酷睿上会被系统屏蔽，直接无法启动。

> 国内网络拉 GitHub Release 常卡住，可用镜像前缀：  
> `https://ghfast.top/https://github.com/dhbloo/rapfi/releases/download/250615/Rapfi-engine.7z`

**第 2 步：装依赖**

双击 `install.bat`：建虚拟环境、装 PyQt6 / pygomo-lib、检查引擎、跑 M0 验证。  
所有内容都落在本文件夹内，不污染系统 Python、不写注册表。

**第 3 步：启动**

双击 `run.bat`（或 `run-debug.bat` 带控制台日志）。选择执黑/执白，之后循环：  
看到对手落子 → 在浮窗上复刻 → 等绿环出现 → `空格` 落子。

---

## 规则说明

|         | 连珠（有禁手）   | 无禁手   |
| ------- | --------- | ----- |
| 五连获胜    | ✔         | ✔     |
| 长连（6+）  | 黑棋禁手；白棋获胜 | 双方都算赢 |
| 三三 / 四四 | 黑棋禁手      | 允许    |
| 白棋限制    | 无         | 无     |

**禁手只针对黑棋**。白棋形成长连、双三、双四都合法。

---

## 分析强度

| 档位         | 单步限时   | 线程 | Hash   | 实测深度 |
| ---------- | ------ | -- | ------ | ---- |
| 轻快         | 300ms  | 2  | 128MB  | 20   |
| **均衡（默认）** | 800ms  | 4  | 256MB  | 22   |
| 深度         | 1500ms | 6  | 512MB  | 26   |
| 极限         | 3000ms | 8  | 1024MB | 27   |

Rapfi 每层比 Pikafish 更贵，深度涨得慢，所以档位整体比象棋版高一档。

---

## 实现要点

- **引擎用 `send_raw` 而不是 `set_rule`**  
  pygomo-lib 0.1.1 的 `set_rule()` 是坏的（命令路由没注册 handler，静默失败）。  
  实测 `execute("INFO RULE 4")` 返回 `No handler registered`，  
  必须改用 `engine.send_raw("INFO RULE N")`（0=freestyle，4=renju）。
- **禁手由本地守门**  
  Gomocup 的 `TURN` 是「对手落子」语义，引擎只校验占用、**不校验禁手**。  
  实测在连珠模式下把双三禁手点发给引擎，它照样接受并继续应对。  
  所以本地 `RenjuBitBoard.is_forbidden()` 是唯一守门人，引擎建议作为旁证  
  （renju 模式下引擎不会建议禁手点）。  
  设置里可关闭「禁手拦截」，降级为仅提示。
- **撤销用整盘重灌**  
  `engine.board(BoardPosition(moves))` 一次性同步，不必 restart + 逐手重放。  
  `board()` 会自动思考并返回 `PlayResult`，省掉一次 `turn()` 往返。
- **`place()` 静默失败**  
  pygomo 的 `place()` 对占用点、禁手着法都是返回 `False` 不抛异常。  
  重放历史时必须检查返回值，否则棋盘会静默偏离历史。
- **`is_forbidden()` 依赖轮次**  
  它只在 `current_player == BLACK` 时判定，白棋回合恒返回 `False`。  
  判定前必须保证棋盘轮次正确，否则永远判不出禁手。

## 目录结构

```
Gomoku/
├─ run.bat / run-debug.bat    启动
├─ install.bat                一次性安装
├─ requirements.txt
├─ config.json                窗口与引擎参数（首次运行生成，不入库）
├─ app/
│  ├─ main.py                 入口
│  ├─ config.py               预设与配置持久化
│  ├─ session.py              BitBoard / RenjuBitBoard 封装 + 历史栈
│  ├─ engine_worker.py        Rapfi 子线程
│  ├─ board_view.py           15×15 交叉点棋盘
│  ├─ pieces.py               棋子绘制
│  ├─ float_window.py         浮窗 / 工具条 / 历史 / 设置
│  └─ theme.py                配色与样式
├─ engine/                    放入 Rapfi 全套文件
└─ tools/                     验证脚本
```

## 自检脚本

```bash
.venv\Scripts\python.exe tools\validate_m0.py    # 引擎与禁手一致性
.venv\Scripts\python.exe tools\check_rules.py    # 规则层（禁手/胜负/切换/撤销）
.venv\Scripts\python.exe tools\check_pixels.py   # 棋盘像素级
.venv\Scripts\python.exe tools\shot.py           # 界面交互回归 + 截图
```

---

## 合规边界（重要）

本软件**仅用于个人复盘、离线对局分析、自建环境练习**。

在在线对战平台使用引擎辅助属于违规行为，会破坏对局公平。本软件不面向、也不适配该场景，  
并且刻意不包含任何图像识别、屏幕读取、自动输入/注入能力 —— 局面完全由用户自己输入。

Rapfi 的权重许可同样声明：仅限合法用途，用于在线作弊等超范围使用由使用者自行承担后果。

---

## 第三方组件与许可

| 组件                                                        | 版本     | 许可            |
| --------------------------------------------------------- | ------ | ------------- |
| [Rapfi](https://github.com/dhbloo/rapfi)                  | 250615 | GPLv3         |
| [pygomo-lib](https://github.com/nguyencongminh090/pygomo) | ≥0.1.1 | MIT           |
| [PyQt6](https://riverbankcomputing.com/software/pyqt/)    | ≥6.6   | GPLv3 / 商业双许可 |

本项目整体以 **GPLv3** 发布，完整文本见 [LICENSE](LICENSE)。

> 引擎与权重不随仓库分发，请按上方「第 1 步」自行下载。
