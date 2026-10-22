# renoir XNU / iOS 移植工程

2026-10-22：真机已运行 XNU、UFS/HFS+ root、launchd、SpringBoard 与锁屏。电源及两个音量键有效，校准后的上海时间正常。用户确认将屏幕拷贝从30Hz降至10Hz后响应改善。**触控、GPU加速、真实电池遥测尚未实现，当前仅启用一个CPU核心。**

代码仓库为独立的 [daimile2/ios-renoir](https://github.com/daimile2/ios-renoir)，保留上游贡献历史及署名。工作目录为 `/home/daimile/桌面/ios-renoir`，所有工具、源码和产物都在本目录。操作见[启动与驱动移植交接指南](启动与驱动移植交接指南.md)，开发计划见[驱动开发顺序](驱动开发顺序.md)，触控细节见[GSI触控移植路线](GSI触控移植路线.md)。接续开发先读[src/NOTES.md](src/NOTES.md)顶部和[事实表](renoir移植事实表.md)。

## 启动已验证镜像

手机手动进入FASTBOOT，USB连接电脑，在Ubuntu执行：

```bash
cd /home/daimile/桌面/ios-renoir
fastboot devices
fastboot boot artifacts/xnu-renoir-0088/phone-power-fifo-v1/shim-boot.img
```

0088镜像SHA-256：`a194831438ff3a769291d33cf71719a2d13867fc0107470fdadab3e95f5a0cc8`。

这是临时启动，每次重启需要再执行。userdata已是iOS，无需重刷；boot仍为原有SukiSU镜像。普通重启不能保证回到Android。`payload.bin`、ADT和裸kernel不能直接交给fastboot。

## 读取日志

iOS目前没有USB ADB。手动进入FASTBOOT后临时启动TWRP，等正常root ADB上线：

```bash
fastboot boot downloads/recovery/twrp-3.7.0_11-0-renoir.img
adb devices
adb shell id
sh src/tools/sweet-log-pull.sh logs/ios-latest.txt
```

TWRP的ADB可能需要30–100秒；不要格式化Data或刷入recovery。脚本只读userdata末尾持久日志环，同时保存原始`.txt.bin`与解码`.txt`。完整步骤与示例见交接指南。

## 当前开发结果

| 版本 | 已验证结果 |
| --- | --- |
| 0083 | 修正CNTP访问异常，真实锁屏运行 |
| 0084 | 电源/音量键有效；10Hz版响应改善 |
| 0087 | RTC校准与上海时区正确，用户验收通过 |
| 0088 | 触控两路供电请求完成、复位拉高；开启时钟后FIFO仍禁用，必须适配GSI/DMA |
| 0089 | GPI动态组1–6报告未分配；SID0x4d6无SMMU匹配，默认未匹配stream会fault |
| 0090 | CI/QEMU及真实锁屏/时间/按键通过；分配被过严的全零条件挡住，没有发出命令 |
| 0091 | CI/QEMU及真实锁屏正常；确认实际筛选阻断为各组output mask0x7f，未发送命令 |
| 0092 | EV/TX/RX分配与逆序释放全部出现新的完成标志，约10微秒/条；真实锁屏/时间/按键正常 |
| 0093 | CI/QEMU通过；真机读取未授权GPI第7组时外部访问异常，未到SMMU写入或DMA提交；勿作日常启动 |
| 0094 | 锁屏正常、越界崩溃已修复；context校验因SCTLR bit12读0被挡住，SID未发布、无DMA |
| 0095 | context/SID配置读回及TX/RX启动通过；把FSR格式位误当fault，NOP轮询立即退出，尚无有效完成事件 |
| 0096 | NOP真实DMA完成：100µs，有效event、guard1、faults0，复位与释放通过 |
| 0097 | NOP/LOCK/UNLOCK均100µs，有效事件、guard1/faults0及复位释放通过 |
| 0098 | CI成功但真机反复重启；日志未落盘，已回退0097，勿继续启动主测试镜像 |
| 0099 | 同步日志33次落盘，所有SE初始化通过，重启发生在首次SPI事务附近 |
| 0100开发中 | 按DT静态标志纠正SPI至GPI0，真机待验证 |

最新已读日志：`logs/ios-gpi-lock-0097-v1.txt`。SMMU有82个空闲SMR，未引用context的寄存器有残留值；不能以全零认定归属。ID0_ATOSNS=1表示不支持ATS翻译测试，不能使用ATS1PR/PAR。0092未提交DMA；0093新增独立开关测试专用映射与NOP，成功与否仍须真机日志。芯片ID、坐标与HID触控尚未打通。

红色字体原因尚未确定；无GPU加速是候选解释。充电图标来自静态占位服务，不代表已经实现充电检测。

## 目录与接续约定

- `src/`是独立源码Git仓库，工作分支`renoir/input`；GUI历史基线`renoir/bringup`。
- `tools/`为主机脚本；`toolchain/`为工具、XNU工作树和固定版本的小米参考源码。
- `artifacts/`保存版本化内核、镜像、manifest和QEMU证据；`logs/`保存构建和真机日志。
- `backup/`、`dtb/`、`downloads/`与Apple用户态均保留本地、不提交。

已验证17个备份分区共832045056字节；六LUN的GPT未修改。仅userdata曾经授权刷入iOS，后续只临时启动。EDL尚未实测；新破坏性刷写需单独确认。用户要求手机反馈使用数字选项，询问后30秒无回应即暂停并保存现场。

模板为[dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet)，固定基线`11da58bd050672960c0a83b5bef2176047eea479`，原始81补丁保留，renoir修改从0082递增。源码：[daimile2/ios-renoir](https://github.com/daimile2/ios-renoir)。每版精确提交、CI、SHA及未完成事项以`src/NOTES.md`顶部为准。

**后续按用户要求跳过QEMU**（2026-10-22）；仍执行本地编译、补丁/仓库检查、完整CI及真机日志验收。

## 2026-10-22：0096 DMA 真机通过

日志 `logs/ios-gpi-dma-0096-v1.txt`（flush11）确认 NOP success=1，100µs，有效event及保护区检查通过，SMMU faults=0/GFSR=0；RESET和释放均完成。不是SPI芯片ID或触控成功。0097开发目标：独立NOP→LOCK→UNLOCK与多事件验证，暂不发SPI数据。QEMU按用户要求跳过。

## 0097已验收／0098目标（2026-10-22）

0097真机NOP、LOCK、UNLOCK均100µs完成，事件指针/类型/代码正确，guard1、faults0，复位释放成功；日志`logs/ios-gpi-lock-0097-v1.txt`。0098将以`gpilock=2`进行两次10字节SPI读取，仅A3/9F ID与CRC验证，尚未上机。用户新观察：锁屏日期红字随时间变白，需排查合成/重绘/缓存，尚不能认定GPU是根因。
