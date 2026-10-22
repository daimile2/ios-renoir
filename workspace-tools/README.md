# 主机工作区工具

这些脚本保持本机工作区约定：仓库克隆在工作区的src/，工具运行在工作区的tools/。在新的工作区将此目录脚本复制到与src同级的tools/，然后按docs/renoir中的指南准备依赖。不要从workspace-tools目录直接运行。脚本并非全部零风险：启动任何备份、镜像构建、刷写验证前先阅读其参数与指南。QEMU按用户要求默认跳过。

```bash
mkdir -p tools
cp src/workspace-tools/*.py src/workspace-tools/*.sh tools/
```

Apple用户态、校准数据、分区备份、镜像和工具链需在本机单独准备，不在Git仓库内。
