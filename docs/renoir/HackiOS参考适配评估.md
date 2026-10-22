# HackiOS 参考适配评估

固定参考：[`oosexgang/hackios-xnu-kernel`，8e61187098f2c26c5daee8f9f72b6416aa64b9ab](https://github.com/oosexgang/hackios-xnu-kernel/tree/8e61187098f2c26c5daee8f9f72b6416aa64b9ab)。本地只读参考树：`toolchain/hackios-xnu-kernel-reference`，目前取出docs/xnu/common，未运行其设备脚本、未启动其预编译镜像。以下是源码审阅结果，不能当作renoir已实现的功能。

| 范围 | 参考入口 | 对renoir的用途及边界 |
| --- | --- | --- |
| 触控 | xnu/files/bsd/dev/redwood_goodix.c | 同时含Goodix GT9916、FT3680，GENI FIFO与GPIO模拟SPI。FTS读取0xa0、数据偏移7和CRC8408可交叉核对。renoir为FT3658U、GPIO20–23/reset30/IRQ31；不能复制redwood GPIO52–55或其固件上传。0098仍使用本机已验证GSI映射与LOCK会话。 |
| SMP | xnu/files/osfmk/arm64/psci_smp.c、相关redwood.patch | CPU_ON、缓存可见性、启动阶段、超时与CPU_OFF可参考。须接入本树CPU注册/入口/GICR/MPIDR和定时器，先2核再更多；不能仅把cpus=1改8就认定成功。 |
| CPU频率 | xnu/files/bsd/dev/redwood_cpufreq.c | EPSS调频可参考；地址、频率表及电源限制必须按SM7350 DT验证。与SMP分开开关和验收。 |
| GPU | xnu/files/bsd/dev/redwood_adreno.c、iokit/Kernel/RedwoodGPU.cpp | 有GMU/RPMh/SMMU/固件/命令处理器的分阶段启动，适合按只读探测到首帧推进。redwood Adreno642L与本机GPU的芯片信息、寄存器、固件须重核。还依赖hackios-xnu-userland里的Mesa/CoreAnimation适配；不能只移植内核就获得SpringBoard加速。 |
| 电池 | xnu/files/bsd/dev/redwood_battery.c、iokit/Kernel/RedwoodBattery.cpp | 其使用PMIC GLINK/ADSP及loader共享状态，不是简单SPMI电量寄存器读取。先核对renoir的charger/firmware链路再决定是否移植；本机当前电池图标仍是占位。 |
| Wi-Fi/音频 | redwood_wifi.c、redwood_audio.c及配套模块 | 可参考Qualcomm SMEM/SMP2P/GLINK/QRTR/QMI基础设施，但其固件、内核兼容层及用户态服务依赖多，须分阶段验证。 |
| 构建 | xnu/README.md、xnu-build.sh、xnu-deps | 声称支持Linux构建，值得另建隔离构建环境评估。其XNU8796.121.2与本树8796.141.3及SDK/链接支持不同，当前CI验证链继续保留。不能忽略本项目构建错误来套用其-k策略。 |
| 启动/调试 | docs/PORTING.md、xnuloader、uefi | 原方案依赖UEFI loader和xl日志。本项目现有ABL→shim临时boot及UFS日志已工作，暂不替换，以免同时引入启动链变化。 |

## 调整后的开发先后

1. 触控SPI ID、坐标、HID，逐步实机验收。0097会话锁已通过，0098测试ID。
2. SMP与CPU性能：先安全启用第二核心，再扩展核心数量；独立评估频率，搭配framebuffer拷贝延迟测量。
3. 真实电池遥测及可持续USB诊断链路，先验证各自前置依赖。
4. Wi-Fi、蓝牙、音频、相机依赖链，按实际可复用程度拆分。
5. GPU单独推进只读硬件核对、供电时钟、GMU、SMMU、命令首帧，再接Mesa/系统合成。可与上述工作在不同镜像分支交替，但不承诺单版完成。

锁屏日期由红变白的现象已记录。现有首批swap日志为BGRA，但还没逐像素对照源surface与屏幕，不能据此断言GPU或固定通道顺序是根因。后续用图像与源/目标像素证据判断重绘、合成、缓存或用户态渲染路径。

补充核对：本机保存的`dtb/renoir-live.dts`在GPU节点记录`qcom,chipid=0x06060010`，参考驱动常量为`0x06030500`。设备树可能包含平台默认/覆盖关系，需结合本机实际硬件及固件核对；不得直接照搬GPU常量。
