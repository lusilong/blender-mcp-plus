# blender-mcp-plus（官方 Blender MCP 的本地增强分支）

## 来源

- 上游：<https://projects.blender.org/lab/blender_mcp>
- 基线提交：`dbbf836ad4b1025f14a2b3b504c43903f39e0b04`（2026-09-29）
- 版本：`1.0.3`（上游 1.0.2 + 本地改动；只用于本机，不改包名，MCP 工具名不变）
- 许可证：GPL-3.0-or-later（与上游一致）

## 改动

| 文件 | 内容 |
|---|---|
| `blmcp/tools/polyhaven_assets.py` | **新增**：`search_assets`、`import_asset` 两个 MCP 工具，接入 Poly Haven 免费 CC0 资产库 |
| `blmcp/tools_helpers/blender_cli.py` | **修复**：`run_blender_cli` 改用临时文件承接 stdout/stderr，替代 `subprocess.run(capture_output=True)`。当 MCP 服务器本身以管道 stdio 运行时，Blender 子进程继承的 stdout 管道会让 `communicate()` 一直等不到 EOF，导致 `execute_blender_code_for_cli` / `*_for_cli` 每次卡满 120s 超时；临时文件版本实测 0.6s 返回 |
| `pyproject.toml` | 版本号 1.0.2 → 1.0.3，便于 `uv tool install` 重新构建（本地目录的 wheel 有缓存，不改版本可能装到旧代码） |

其余文件与上游一致，**Blender 插件保持官方原版**，没有改插件。

### 资产工具实现方式

HTTP（搜索 / 下载 / 依赖文件准备）在 MCP 服务器进程里用标准库完成，
只把「导入这个本地文件」的小段 `bpy` 代码通过现有的 `send_code` 桥发给 Blender：

- `search_assets(query, asset_type=models|hdris|textures|all, category, limit, min_size_m)`
- `import_asset(id, asset_type=models|hdris|textures, resolution=1k|2k|4k|8k, target_size, apply_to, strength)`
  - models → 下载 glTF（含 .bin/贴图）后 `bpy.ops.import_scene.gltf`，可按 `target_size`（米）等比缩放
  - hdris → 下载 EXR/HDR 并接到 World 环境贴图
  - textures → 取 Diffuse 贴图建材质，赋给 `apply_to` 或当前激活的网格对象

### 未移植

`generate_3d`（Tripo / Meshy / Hunyuan3D / Hyper3D）没有移植：
Hyper3D 免费试用 key（`vibecoding`）已返回 `API_INSUFFICIENT_FUNDS`，
Meshy/Tripo 的 API 域名在本机网络不可达，其余 provider 需要用户自己的付费 key，移植后无法实测。
需要时按同样的「server 侧 HTTP + `send_code` 导入」模式补一个工具模块即可。

## 安装 / 更新

```powershell
# 安装（覆盖旧版本；注意本地目录 wheel 有缓存，必须带 --force 且版本号不同才会重建）
uv tool install --force --python 3.12 "D:\Reasonix_BOX\dsh\vendor\blender-mcp-plus"

# 验证
& "$env:APPDATA\uv\tools\blender-mcp\Scripts\blender-mcp.exe" --help
```

安装后 DSH 的 MCP 配置指向：

```
C:\Users\user\AppData\Roaming\uv\tools\blender-mcp\Scripts\blender-mcp.exe
```

这是**非 editable** 安装（uv tool 复制一份）。改完本目录源码后必须重新执行上面的安装命令；
如果频繁调试，可临时用 `uv tool install --force --editable --python 3.12 <path>`，
但最终交付建议保持非 editable，避免依赖工作区路径。

## 跟上游同步

```powershell
git -C <upstream-clone> pull
# 用新版 blmcp/ 覆盖本目录，再把 polyhaven_assets.py 放回 blmcp/tools/，
# 重新施加 blender_cli.py 的临时文件修改，递增版本号，重新安装
```

当前上游无 `stdin=DEVNULL` / 临时文件修复，升级后要重新检查
`tools_helpers/blender_cli.py` 和 `tools_helpers/connection.py` 的接口是否变化。
