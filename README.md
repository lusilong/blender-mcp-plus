# Blender MCP Plus

**一个 MCP 服务器，同时拥有官方 Blender Lab 的工具集和 Poly Haven 资产库。**

无需在多个 MCP 之间来回切换，也不会出现两个服务抢 `localhost:9876` 端口的问题。
基于官方 [blender_mcp](https://projects.blender.org/lab/blender_mcp)（GPL-3.0-or-later）扩展，
Blender 侧使用**官方插件**，本仓库只增强 MCP 服务器。

> One MCP server for Blender: the official Blender Lab tool set **plus** a Poly Haven
> asset library. It talks to Blender's official `MCP` add-on, so you only need one
> add-on and one MCP client entry. Tested with Blender 5.2.2 LTS.

## 特性

- **28 个工具**：任意 `bpy` 代码执行、后台 Blender 执行、场景/工程体检、Blender Python API
  与用户手册全文检索、截图/渲染、视口跳转。
- **Poly Haven 资产库**（新增，免费 CC0，无需 API key）：
  - `search_assets`：搜索 500+ 模型、HDRI、贴图
  - `import_asset`：模型按真实尺寸缩放导入；HDRI 设为世界环境光；贴图建材质赋给对象
- **一个插件、一个 MCP**：Blender 里只需启用官方 `MCP` 插件，客户端只配一条服务器。
- **可选的 `.mcpb` 一键安装包**：支持 MCP Bundle 的客户端可直接导入。
- **可发布**：自带 PyPI / GitHub Release 一键发布脚本和 GitHub Actions 工作流。

## 架构

```
MCP 客户端 (Claude Desktop / Cursor / DSH / ...)
        │  stdio
        ▼
blender-mcp-plus  （本仓库，Python MCP 服务器）
        │  TCP localhost:9876
        ▼
官方 Blender 插件 "MCP"（Blender 5.1+）
        │
        ▼
Blender 5.x / bpy
```

## 前置条件

| 依赖 | 要求 |
|---|---|
| Blender | **5.1 或更新**（官方插件要求；已在 5.2.2 LTS 实测） |
| 官方 MCP 插件 | `mcp-1.0.3.zip`（下方脚本会下载并安装） |
| Python | 3.10+（用 `uvx` 时自动管理，无需手动安装） |
| [uv](https://docs.astral.sh/uv/) | Windows: `winget install --id=astral-sh.uv -e` |
| MCP 客户端 | Claude Desktop / Cursor / DSH / 任意支持 stdio MCP 的客户端 |

## 安装

### 1. 安装 Blender 官方插件

**方式 A：脚本一键安装（推荐）**

```powershell
# 自动查找 Blender；也可以显式指定路径
powershell -ExecutionPolicy Bypass -File scripts\install_blender_addon.ps1 `
  -BlenderExe "E:\Blender 5.2\blender.exe"
```

脚本会从 Blender Lab 官方 release 下载 `mcp-1.0.3.zip` 并用 Blender CLI 安装、启用。

**方式 B：手动安装**

1. 下载 <https://projects.blender.org/lab/blender_mcp/releases/download/v1.0.3/mcp-1.0.3.zip>
2. 打开 Blender → 编辑 → 偏好设置 → 插件 → 右上角下拉 → **从磁盘安装**
3. 搜索 `MCP`，勾选启用
4. 确认偏好设置 → 系统 → **允许在线访问**（插件需要）
5. 3D 视图按 `N` 可看到 `MCP` 面板；插件默认在 Blender 启动后自动监听 `localhost:9876`

### 2. 安装并运行 MCP 服务器

**发布到 PyPI 后（最简单）：**

```powershell
uvx blender-mcp-plus
```

**从 GitHub 直接运行（无需发布）：**

```powershell
uvx --from git+https://github.com/lusilong/blender-mcp-plus blender-mcp-plus
```

**本地 wheel：**

```powershell
uv pip install dist\blender_mcp_plus-1.0.3-py3-none-any.whl
```

**MCP Bundle（`.mcpb`）：** 在 `dist\` 里找到 `blender-mcp-plus-1.0.3.mcpb`，
在支持 MCP Bundle 的客户端里双击/导入即可。

### 3. 配置 MCP 客户端

Claude Desktop（`claude_desktop_config.json`）或 Cursor：

```json
{
  "mcpServers": {
    "blender": {
      "command": "uvx",
      "args": ["blender-mcp-plus"]
    }
  }
}
```

Windows 上若客户端找不到 `uvx`（GUI 启动不继承 PATH），使用：

```json
{
  "mcpServers": {
    "blender": {
      "command": "cmd",
      "args": ["/c", "uvx", "blender-mcp-plus"]
    }
  }
}
```

DeepSeek Harness（`~/.dsh/profiles/desktop/cordis.patch.yml`）追加：

```yaml
- id: mcp-blender
  name: "@deepseek-ai/dsh-mcp-client"
  config:
    serverName: blender
    transport: stdio
    command: "uvx"
    args: ["blender-mcp-plus"]
    env:
      BLENDER_PATH: "E:\\Blender 5.2\\blender.exe"
```

> `BLENDER_PATH` 只用于 `*_for_cli` 系列（后台 Blender）。不配置也能用其余工具。

### 4. 开始使用

保持 Blender 打开，对 AI 说：

- 「在 Blender 里建一个低多边形咖啡杯加托盘，青绿陶瓷材质，三点布光，渲染预览。」
- 「搜索 Poly Haven 的椅子，把 ArmChair_01 导入并缩放到 1.2 米。」
- 「用 HDRI studio_small_03 做环境光，强度 1.2。」
- 「给选中的椅子贴上 Poly Haven 的木纹贴图，渲染 1200x900 的 EEVEE 预览。」
- 「把刚才的杯子改成磨砂金属赤陶色，杯身拉高 18%，再渲染对比。」

## 工具清单（28）

### 官方 Blender Lab 工具（26）

| 类别 | 工具 |
|---|---|
| 代码执行 | `execute_blender_code`、`execute_blender_code_for_cli` |
| 工程体检 | `get_blendfile_summary_datablocks`、`..._missing_files`、`..._of_linked_libraries`、`..._path_info`、`..._usage_guess`（各含 `_for_cli` 版本） |
| 场景读取 | `get_objects_summary`、`get_object_detail_summary` |
| 文档检索 | `get_python_api_docs`、`search_api_docs`、`search_manual_docs` |
| 观察 | `get_screenshot_of_window_as_image`、`get_screenshot_of_area_as_image`、`get_screenshot_of_window_as_json`、`render_viewport_to_path`、`render_thumbnail_to_path` |
| 视图 | `jump_to_view3d_object_by_name`、`jump_to_view3d_object_data_by_name`、`jump_to_tab_by_name`、`jump_to_tab_by_space_type` |

### 本仓库新增（2）

| 工具 | 参数 | 说明 |
|---|---|---|
| `search_assets` | `query`, `asset_type`(models/hdris/textures/all), `category`, `limit`, `min_size_m` | 搜索 Poly Haven 资产，按下载量排序 |
| `import_asset` | `id`, `asset_type`, `resolution`(1k/2k/4k/8k), `target_size`, `apply_to`, `strength` | 下载并导入模型 / HDRI / 贴图 |

## 与官方版的关系

本仓库是官方 [blender_mcp](https://projects.blender.org/lab/blender_mcp) 的衍生版本，
保留其全部工具，新增 Poly Haven 资产工具，并修复了官方 `*_for_cli` 工具在
“MCP 服务器本身使用管道 stdio”时可能卡满 120 秒超时的问题（改为临时文件承接子进程输出）。
Blender 插件**没有修改**，仍是官方版本。

## 安全

- `execute_blender_code` 及其 CLI 版本会以你的用户权限执行**任意 Python**。执行前保存工程；
  不要对不可信的 `.blend` 运行。
- 官方插件 socket 只监听 localhost，无鉴权、无加密，禁止端口转发。
- 第三方资产/场景的元数据可能包含提示注入内容，处理不可信文件时使用副本。
- 官方文档也明确建议在虚拟机或无敏感数据的机器上使用此类 MCP。

## 开发与发布

```powershell
# 安装开发依赖
uv sync --extra dev

# 构建 wheel / sdist
uv build

# 构建 .mcpb
python scripts/build_mcpb.py

# 一键发布（创建 GitHub 仓库 + push + tag + Release + 可选 PyPI）
$env:UV_PUBLISH_TOKEN = "pypi-..."   # 需要发布 PyPI 时
powershell -ExecutionPolicy Bypass -File scripts\publish.ps1 -CreateRepo -PyPI
```

`scripts\publish.ps1` 会：

1. 从 `pyproject.toml` 读取版本号，清理并重新构建 `dist/`
2. 构建 `.mcpb`
3. `git init`（如需要）、提交、打 tag `v<version>`
4. 用 `gh` 创建/推送仓库（`-CreateRepo`）并创建 GitHub Release，上传 wheel/sdist/.mcpb
5. 若设置了 `UV_PUBLISH_TOKEN` 且带 `-PyPI`，执行 `uv publish`

GitHub Actions 也提供了 `ci.yml` 和 `publish.yml`（打 tag 自动发布，支持 PyPI Trusted Publishing）。

## 目录结构

```
blender-mcp-plus/
├── blender_mcp_plus/          # Python 包（MCP 服务器）
│   ├── tools/                 # 自动发现的工具模块
│   ├── tools_helpers/         # socket 桥、CLI、文档检索
│   └── data/                  # 内置 API 参考 + 用户手册（RST）
├── scripts/
│   ├── install_blender_addon.ps1
│   ├── build_mcpb.py
│   └── publish.ps1
├── tests/
├── manifest.json              # MCPB manifest
├── pyproject.toml
├── LICENSE                    # GPL-3.0
└── NOTICE
```

## 致谢与许可

- 上游：[Blender Lab / blender_mcp](https://projects.blender.org/lab/blender_mcp)，GPL-3.0-or-later
- 资产：[Poly Haven](https://polyhaven.com)，CC0
- 本仓库的修改同样以 **GPL-3.0-or-later** 发布，详见 `LICENSE` 与 `NOTICE`。
