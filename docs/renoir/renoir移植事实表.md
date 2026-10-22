# renoir 移植事实表（2026-10-20 实机采集）

原始证据仅保存在本机 `dtb/`、`backup/device/`，不提交设备序列号和校准数据。
用户提供的配套事实表未附文件，本文依据本机重新建立，不能将参考值当实测。

| 项目 | 实测 | 证据 / 状态 |
| --- | --- | --- |
| 机型 | M2101K9C / renoir / SM7350 | adb、live FDT model |
| CPU | CPU0–3 Cortex-A55 (0xd05)，CPU4–7 Cortex-A78 (0xd41) | /proc/cpuinfo；不是 sweet 的 6+2 |
| root | uid=0 | su -c id |
| BL | Android 属性被 Play Integrity Fix 伪装锁定；启动参数 orange | 用户说明；fastboot boot 已成功，且用户确认红底文字 |
| 当前槽 | _a | /proc/cmdline |
| 启动镜像 | boot v3，DTB 在 vendor_boot v3 | 备份解包头 |
| splash | 0xe1000000 + 0x02300000 | /reserved-memory/splash_region |
| 面板 | mdss_dsi_k9_42_02_0b_mp_dsc_cmd | 实际 bootargs；命令模式可能需要 DSI kick |
| 画幅 | 1080 × 2400 | touch 坐标与面板配置；shim 以 32bpp/stride 4320 真机出字通过 |
| UFS | 0x01d84000 + 0x3000 | live FDT 与 iomem；真机 UFS READ rc=0、GPT EFI PART 通过 |
| GICD | 0x17a00000 + 0x10000 | live FDT |
| GICR | 0x17a60000 + 0x100000；stride 0x20000 | live FDT |
| 定时器 | 19.2 MHz；虚拟 PPI 11 → INTID 27，物理 PPI 14 → INTID 30 | live FDT /soc/timer；与 sweet 的 19/18 不同 |
| UART alias | /soc/qcom,qup_uart@994000 | live FDT；不代表可物理访问 |
| RAM | 0x80000000+0x39700000；0x180000000+0x100000000；0xc0000000+0xc0000000 | live FDT /memory，三段不能直接合并 |
| 内存候选 | 0x200000000+0x80000000 | iomem 显示该段为 RAM 无子 carveout；仅候选，未验证 XPU |
| 触控 | FocalTech，ID 0x5652，SPI 0x988000，DTB 6 MHz；运行时驱动 12 MHz / mode 0 | dmesg fts_get_ic_information 与 input 设备路径；不是 GT9897T；官方 FT3658U 配置映射吻合 |
| 触控电源 | avdd → PM8350C L7；iovdd → PM8350C L2 | live FDT phandle 0x2f9 / 0x2f4；驱动 supplier 一致 |
| 触控 GPIO | reset 30，IRQ 31 | live FDT xiaomi_k9_touch@0 |
| 校准/启动备份 | 17 分区逐一验证大小与手机 SHA-256 | backup/partitions/manifest.json |

## 必须修正的假设

- FB_BASE 与 FB_PHYS 必须统一修改；只改 mmu.h 不足。
- 0xe1000000 在 32 MiB 块 0xe0000000 内偏移 0x01000000；XNU 早期页表必须映射对齐物理块并补 VA 偏移。
- 不能照抄 sweet 的 RAM 基址、大小、timer INTID、触控或 PMIC 驱动。
- boot_a 是当前 root 环境的启动镜像，不能称为未经修改的原厂镜像；原厂救砖包和 EDL 授权路径尚未核实。
- 上游基线固定为 11da58bd050672960c0a83b5bef2176047eea479，共 81 补丁。

## 已获取的用户态输入（2026-10-20）

- iPhone10,3 / D22AP iOS 16.7.16 (20H392)，Apple CDN 的 OS、SystemOS、AppOS 和 DeviceTree 均通过 ZIP CRC 与 BuildManifest SHA-384。
- D22AP ADT 解码为 186084 字节，完整解析 186084 字节；/product 68 个原始属性；生成器会排除 iBoot 占位属性与 bookkeeping。
- 本机 QEMU 已启动上游 0081 内核至测试 PID 1，存在 5 次心跳。此结果不是 renoir 真机 XNU 启动证据。
- 小米官方 Mi 11 Lite 5G 内核参考位于 [star-r-oss](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/a9244def8a5178edee9ed4a30d60034de8286cbb/drivers/input/touchscreen/focaltech_spi)，不是不存在的 renoir-r-oss。下载到 toolchain/renoir-linux-reference，已对比 Git blob 哈希。

## 恢复环境与分区表

- 官方 renoir TWRP 3.7.0_11-0 已临时启动，ADB uid=0，设备 renoir，/dev/block/by-name/userdata 可访问。首个 ADB 等待窗口超时，随后设备正常上线，不能把等待超时当启动失败。
- 镜像 SHA-256：f5bb1e1bc42930e57fbafb8b32f93e7036ba43c1e7d786fa22428d9b46c06871，与 [TeamWin 官方校验文件页面](https://dl.twrp.me/renoir/twrp-3.7.0_11-0-renoir.img.html) 一致。未安装 recovery。
- sda/sdb/sdc/sdd/sde/sdf 共六 LUN 的主、备 GPT 已读取到 backup/gpt；两份头 CRC 与两份分区数组 CRC 均通过，并比对所有分区范围一致。
- GPT 不是 Android 个人数据备份，也不代表已验证 EDL Firehose 权限。

## GUI 与输入阶段核对（2026-10-21）

- 真机 identity v3 已显示锁屏；随后 0084 验证电源与两个音量键全部有效。触控仍未实现，红色字体原因未确认。10Hz 屏幕拷贝版用户确认按键反馈明显改善。
- 原先卡 Logo：lsd 的应用登记在 MobileGestalt `UniqueDeviceID` 查询中等待网络信息。补齐 `/chosen/mac-address-wifi0`、`mac-address-bluetooth0` 的固定测试值后，用户确认进入锁屏。这不表示真实 Wi-Fi/蓝牙已驱动。
- 电池图标目前来自静态服务：`sweetbattery=0` 发布 100%、4200mV、外接电源 true；不能作为充电/电量驱动验收。
- 原 Android 日志确认 SPMI v5（0x50020000）。PON 为 SID0 的 Gen3 HLOS，基址 0x1300、RT_STS 0x1310，电源 bit7、音量下 bit6，子类型需验证 0x09。
- 音量上为 PM8350 SID1 GPIO6，DT GPIO 编号从 1 开始，基址 0x8800+(6−1)×0x100=0x8d00，RT_STS 0x8d10，低有效。
- SPI 基址 0x988000，DT pinctrl 组名 qupv3_se10，GPIO20–23 为 qup10 复用；时钟枚举名却为 GCC_QUPV3_WRAP0_S2_CLK（72），不能按组名猜 GCC wrapper 编号。
- GCC 基址 0x100000：S2 RCG 0x17270、分支 0x1726c、投票寄存器 0x52008 bit12；wrapper0 M/S AHB 投票同寄存器 bit6/bit7。
- Shima TLMM 基址 0x0f000000，寄存器偏移为 0x100000+GPIO×0x1000。GPIO20–23、30、31 均按同一公式；这些值已核对官方 pinctrl-shima.c，尚未做裸机 SPI 验证。
- FT3658U 参考驱动请求 AVDD 3.3V、IOVDD 1.8V；L7C 的 DT 范围 3.0–3.544V，L2C 为 1.62–1.98V。没有执行供电改写。
- cmd-db 保留区 0x80860000+0x20000；apps RPMh DRV2 为 0x18220000，TCS 偏移 0xd00。renoir DT TCS 配置按顺序为 WAKE2、ACTIVE3、SLEEP3；不能复用 sweet 的 ACTIVE2/起始槽假设。
- RTC 为 PMK8350 SID0：控制 0x6146，四字节计数 0x6148–0x614b。原 Android 也先读到 1970 年，再加校时偏移；备份 persist 的 `/time/ats_2` 是 8 字节小端毫秒偏移，已只读提取到本地 artifacts/time-reference，数值不提交。

以上输入与时钟寄存器来自实际 live DT、备份日志及小米官方固定提交 `a9244def8a5178edee9ed4a30d60034de8286cbb` 的驱动；源码和哈希清单位于 `toolchain/renoir-linux-reference/platform/`。0084 按键补丁已通过本地编译、84 补丁检查、CI 39458056923、受限定时器 QEMU 和真机按键验收。0085 正在加入校准 RTC 和只读 GENI SPI 状态探测，尚待新内核真机验证。

- 2026-10-21 recovery 只读 RTC 加备份 persist 校准，与主机 UTC 约差 1 秒；校准输入已验证。原始数值及比对 JSON 仅存本地 artifacts/time-reference，不提交。

- 0085 真机日志确认：GENI SPI FW=0x102、protocol=1，status=0，TX/RX FIFO 空；RTC APID=65，校准采样成功。尚未确认 FTS SPI 数据传输/芯片 ID。

- 0086 真机：时区链接替换返回 error=0，但界面仍为 UTC−7；SPI 复位 GPIO30=0、IRQ31=0，引脚20–23配置均0x1。门控0x083c8000，S2 branch0x80004220，RCG0x80000000/0x00100000，SE clkcfg0x11。ID请求因此未执行，不能声称 SPI 读写已通。
- 时区候选原因：上一链接目标 zoneinfo.default 未使用 ICU 识别 Olson 名称的 `/zoneinfo/` 路径；0087 改为规范路径，尚待验收。

- 0087 用户确认北京时间正常。日志确认 RTC 校准和时区设置；触控仍未进入 RPMh 初始化，也未读取 ID，不能将电源初始化实现写成真机验收通过。0088 正在解耦供电与 FIFO 检查并补充门控/模式诊断。

- 0088：SPI分支开启后0x4220、等待1次，FIFO禁用仍1。RSC id0x20300、config0x800c8104、8TCS/16命令；cmd-db有效，ldoc2=0x42800、ldoc7=0x41400。两路请求完成，GPIO30 cfg0x200/IO0x3。未测模拟电压；未读芯片ID。
- GPI top0x900000，EE offset0x10000在小米驱动中从地址减去。动态组mask0x7e，不应将SE2硬编码等同于GPII2；GPI DMA SID0x4d6，apps-SMMU0x15000000，DT带skip-init和LE-VM。

- 0089/0090真机：SID4d6无匹配SMR，USFCFG=1；ID0=4c017e59、ID1=6000003c、ID2=5111。89个SMR（0090有82个无效）、60个CB、寄存器页4KiB、CB偏移80000；ID0_ATOSNS=1，不支持ATS1PR测试。
- 0090未引用CB7/8/9的SCTLR.M=0，但TTBR等有残留值。GPI动态组状态0；全零筛选导致未发ALLOCATE，0091修正该条件。残留值不能当作有效页表，也不能要求未分配ring全零。尚无DMA、芯片ID或HID触控实测。

- 0092真机GPI组1 EV/TX/RX分配和释放均新completion、约10微秒。0093对GPI组7 context（物理0x92c000）的CPU读取触发同步外部abort，PC反汇编和FAR吻合。DTmax12不是MMIO访问授权；当前仅0..6读取已验证，动态只分配1..6。0093未到SMMU配置或DMA；旧持久环不能当新启动结果。

- 0094 VA64 context实测SCTLR=c00027（bit12写1读0）、TCR=802020、TCR2=38071；0095调整hint读回判定后发布SID4d6 slot7/CB7/ASID255，IOVA100000+10000专用pool，配置读回通过。尚无DMA完成事件。
- FSR400是Format[10:9]=2/AArch64，不是fault；固定Linux的fault mask=c00001fe。0095因任意非零谓词错误提前退出，FAR在faultmask0时无故障含义；0096修复，待真机事件验收。
