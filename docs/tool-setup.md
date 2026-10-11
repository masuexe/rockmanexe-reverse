# 本机工具配置

Ghidra：/home/harp/tools/ghidra_12.1.4_PUBLIC。
完整 JDK：/usr/lib/jvm/java-21-openjdk-amd64。
mGBA：/usr/games/mgba，版本 0.10.2。
初始 REA 版本固定为 5.0.0，后续升级需重新核实 provider 支持。

## 执行配置

在普通 WSL 终端执行：

```bash
cd /home/harp/projects/rockmanexe-reverse
bash scripts/setup-tools.sh
```

脚本恢复指定 Ghidra 启动器及反编译器的用户执行权限，检查工具，
预览并应用 REA 的 Codex 配置，最后检查注册。
REA setup 可能安装其配套技能并修改用户 Codex 配置；由 setup 备份已有配置。
它不会安装 Hopper，未选择其他 Agent。
完成后重启 Codex，检查 REA 工具是否真正出现在新会话中。

环境变量无需全局写入 shell 配置。普通终端可执行
`source scripts/tool-env.sh`；REA setup 应将验证过的 Ghidra/JDK 路径写入 MCP 配置。

## 启动工具

```bash
bash scripts/start-ghidra.sh
bash scripts/start-mgba-debug.sh
```

mGBA 调试器中使用 `break/t 0x080003E4`，然后 `continue`。
第一个候选为按键更新函数。Ghidra 导入日版 Falzar 时采用 Raw Binary，
小端 ARM v4T，基址 0x08000000，候选入口使用 Thumb 状态。
REA 的临时自动导入不能替代此 GBA 映射验证。

## 验证状态

配置脚本已通过 Bash 语法检查。Ghidra/REA 全局接入是否成功仍需运行 setup-tools.sh 核验。
本地 ROM 与参考仓库已迁移到旧目录，由 EXE_REVERSE_LOCAL_DIR 定位。
2026-10-10 已通过普通 Ghidra headless 与 mGBA 验证按键更新函数；
Ghidra 使用临时副本修复执行权限，未修改全局安装。
本机全局 headless 启动器、launch.sh 及原生反编译器的执行权限仍需由配置脚本恢复。
本会话未暴露 REA 工具，未验证其 GBA 自动导入。
结果与复现步骤见 `research/exe6f-input-update.md`。
