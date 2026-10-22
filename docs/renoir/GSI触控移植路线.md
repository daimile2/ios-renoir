# renoir GSI 触控传输移植路线

2026-10-22：0096已验证真实NOP DMA完成（100µs、无fault）；0097正在构建LOCK/UNLOCK会话与逐项事件验证。历史版本记录按编号保留，最新接续状态以src/NOTES.md顶部为准。

已确认：SPI固件protocol1，S2时钟分支可开启，FIFO_DISABLE_RO在开启前后均为1；两路触控电源请求完成，GPIO30复位已拉高。尚未发送有效SPI数据，未读取FT3658U芯片ID，未发HID触控事件。

## 硬件与参考源码

- GPI top：0x900000，范围0x60000；动态组mask0x7e，静态组mask1，最大12组。
- `qcom,gpi-ee-offset=0x10000`：小米源码从top指针**减去**该值。实际通道上下文物理地址为 `0x900000 - 0x10000 + 0x20000 + group*0x4000 + channel*0x80`。不能加偏移。
- SPI DT DMA参数：TX `(0,2,1,0x40,2)`，RX `(1,2,1,0x40,2)`；SE ID为2，不等于GPI组号2。原驱动动态选择mask内空闲组，并复用同SE的配对通道。
- DMA stream ID：0x4d6，apps-SMMU：0x15000000。DT有`qcom,skip-init`和GPI `qcom,le-vm`；必须保留共享映射与其他设备通道。
- 官方固定参考：`toolchain/renoir-linux-reference/gpi/` 的 gpi.c、msm_gpi_mmio.h、msm_gpi.h、arm-smmu.h；以及platform目录spi-msm-geni.c。版本、URL和哈希在本地provenance中。

## 实现顺序与验收

1. **0089只读探测**：读取动态组1–6的TX/RX/event配置、状态、scratch、错误状态；读取SMMU ID/CR0及SID0x4d6对应的SMR/S2CR。零状态只代表未分配候选，不能认定有所有权。既不分配/重置通道，也不敲doorbell、不改SMMU。
2. **确认可用DMA地址**：S2CR若是translate，需要核对相应context和有效IOVA，建立仅本stream所需的映射；不能直接把XNU的8GiB以上物理地址当作IOVA。若显示bypass也要核对全局控制、权限及实际事务，不凭单个寄存器认定可DMA。不重置共享SMMU，不改其他stream。
3. **通道与event ring初始化**：只操作有明确归属的组。参照原驱动的channel/event状态机，所有命令有超时；未完成的DMA不能释放或复用内存。需要正确的cache维护、ring对齐、门铃和event消费协议。LE-VM模式的停止/复位行为与普通模式不同，照实际驱动确认。
4. **最小SPI事务**：按下游spi-msm-geni.c配置SPI CONFIG/GO/DMA TRE，先发10字节的FTS寄存器读取请求，验证状态及CRC16，稳定读A3/9F得到5652。先单次、再重复，保留错误事件与SMMU fault日志。不进行固件升级。
5. **坐标读取**：寄存器01开始，按FocalTech官方报文格式处理。原驱动point_buf[0]存命令01，返回数据从buf[1]放起；复用偏移时要补回这个前导字节。坐标含额外3位，不能套普通FTS的12位格式。检查包长、触点数、ID、CRC、抬手和坏包。
6. **HID接入**：调用现有SweetHID的sweet_hid_touch，传面板1080×2400坐标；它内部已处理1125×2436逻辑画布偏移，不要重复缩放。先只读日志、再单指、再上滑和多指。失败/设备掉线必须正确释放已按下触点。

每版两项目标仍分别验收：前置探测不算完整驱动，DMA命令完成不等于芯片响应正确，ID正确也不等于上滑有效。镜像、CI、哈希、启动参数、日志及失败位置写入src/NOTES.md顶部。

当前可靠回退：0088的phone-power-fifo-v1（时间/按键/10Hz及供电请求、复位序列）；0089探测镜像启动结果以其manifest与NOTES为准。日常只fastboot boot，不重刷userdata。

## 0089实测与0090边界

0089日志：`logs/ios-gpi-smmu-0089-v1.txt`。动态组1–6三路state均0、scratch0；SID0x4d6无匹配SMR。CR0=0x280406，未匹配stream会fault，不能直接使用PA。ID0=0x4c017e59、ID1=0x6000003c、ID2=0x5111。寄存器页4KiB、CB偏移0x80000、60个bank、89个SMR。

特别注意：SMMUv2的ID0_ATOSNS为1表示**不支持**ATS地址翻译操作（固定小米arm-smmu.c中FEAT_TRANS_OPS判断）。不要用ATS1PR/PAR做自检；不能把该位误读为支持。软件页表检查也不能证明实际DMA成功。

0090分为GPI命令分配/释放验证与SMMU可用资源只读核对。新增`renoirgpialloc=1`，只选DT动态mask内上下文/ring/scratch/IRQ状态与mask均空的组，type输出IRQ保持屏蔽，轮询新产生的source completion。先EV、再TX/RX分配，逆序释放；未START、无ring地址/doorbell、无DMA、不写SMMU。下游DEALLOC不改变硬件state，必须按新completion判断，不能盲等state回零。超时不切换其他组、不全局reset，需重启。

构建开关：`RENOIR_GPI_ALLOC=1`需同时`RENOIR_GPI_PROBE=1`，其余沿用`tools/build-rtc-spi.sh`。SMMU inventory只记录候选bank，不代表已取得所有权。下一步仍是仅映射专用DMA内存的SID0x4d6上下文，再验证真实GPI event和FTS ID。

## 0090结果与0091修正

0090正常进入锁屏，用户确认时间和按键正常；日志`logs/ios-gpi-alloc-0090-v1.txt`显示分配被筛选条件挡住，没有发送命令。SMMU有82个无效SMR、首个index7；CB7/8/9未被有效SMR引用且SCTLR.M=0，但TTBR等有残留值。这不证明可直接用，更不能把随机值当有效页表。

上面0090的“ring全部为零”规则过严：未分配的ring/部分scratch值未定义，不应以全零判断资源归属。0091只考虑DT授权动态组1–6，要求三路state0、无协议关联、两路scratch0=0、output mask0；记录筛选值后发送ALLOCATE，以新completion确认授权。保留并恢复原source masks，不假设其初值为零。其他限制不变。0091仍需CI/QEMU/真机验收，不能提前宣称分配成功。

## 下一步SMMU实现所需约束（尚未实现）

参考源码追加固定版本`gpi/arm-smmu.c`与`gpi/io-pgtable-arm.c`，各自有source.json记录URL和SHA。CB基址按ID1计算：`(1 << (NUMPAGENDXB + 1)) << pgshift`，本机为0x80000；bank步长0x1000。GR1为base+0x1000，CBAR位于GR1+4*n，CBA2R位于GR1+0x800+4*n。不能用CPU的16KiB页大小替代SMMU寄存器页或4KiB页表粒度。

建立映射前扫描全部有效SMR，确认目标SID没有匹配、bank未被任何translate条目引用、SCTLR.M=0；未引用/disabled不单独证明所有权，还要核对启动环境与并发使用。只建立SID0x4d6精确匹配，保持其他SMR、全局CR0和已有domain不变。不使用全局bypass。不以TTBR残留为有效配置，也不以全零作为分配前提。

页表和ring使用专用连续分配，4KiB对齐、物理地址范围符合36位OAS；只把专用缓冲区映射到DT的IOVA pool内。可参考UFS的kmem_alloc_contig/pmap_find_phys及clean_dcache64/flush_dcache64，但它的静态函数不能跨文件直接调用。软件walk、越界guard、寄存器readback只能验证软件配置；真正翻译成功仍要靠有界DMA事件及SMMU fault检查。ATS不可用。

固定arm-smmu.c的初始化顺序为CBA2R/CBAR、TCR2、TCR、TTBR、MAIR、SCTLR；TCR2还有SEP_UPSTREAM及AArch64 AS位，不能只写IPS。页表flags、cacheability和TCR来源为io-pgtable-arm.c，不应套XNU CPU页表常量。处理TLB invalidation/sync、cache维护和失败清理后，才允许START/doorbell。DMA超时的内存必须隔离到重启，不能释放复用；LE-VM终止分支与普通STOP不同，参照下游gpi_terminate_all。

## 0091实测纠正与0092

0091进入锁屏，用户确认时间/按键正常；日志`logs/ios-gpi-alloc-0091-v1.txt`显示每组output mask均0x7f，导致筛选拒绝，仍未发送命令。此前把0090拒绝归因于ring残留值过早，**已确认的原因是mask条件**；非零mask不能证明通道归属。

0092要求动态组state0、无协议/scratch0关联、无pending type IRQ；选中后保存output mask、写0屏蔽并readback，轮询source完成后恢复原source/output masks。没有GIC处理器时不能直接打开输出。0092完整构建和真机结果尚待验证；仍无START/doorbell、SMMU写入、DMA、芯片ID或触控事件。

## 0092通过与0093目标（2026-10-22）

0092日志`logs/ios-gpi-alloc-0092-v1.txt`确认：组1的EV、TX、RX分配均fresh1/state1，逆序释放均fresh1/state0，每条约10微秒；没有DMA。用户确认锁屏/时间/按键正常。

0093增加独立`renoirgpidma=1`，需allocator/probe同时启用；主机构建变量`RENOIR_GPI_DMA=1`。先确认其他GPI组未运行、SID无匹配，再选空SMR和未引用disabled CB、未使用ASID。连续80KiB内存包含3张4KiB页表和64KiB专用pool，IOVA100000..10ffff，前后guard invalid，所有内存保留到重启。只配置本SID和本CB，不改全局CR0/旁路、不用ATS。实际ring/页表字段读回通过后才提交NOP。

NOP验证EV/TX/RX ring、cache维护及事件DMA，不访问触控芯片。验收需正确的事件pointer/type/code/status、padding guard与无CB fault；另记录全局fault但不清除共享错误。LE-VM按固定源码RESET双通道后释放；reset不确定则保持输出屏蔽、隔离内存和映射直到重启。0093目前尚未真机验证，不提前宣称DMA或触控成功。

## 0093真机panic与0094修复

照片`IMG_2726.jpeg`：PC fffffe00074ee268，ESR96000010，FARfffffe79cb9e0000。对应0093内核反汇编`ldr w12,[x10,x11]`；x8=7，GPI寄存器VA为fffffe79cb9b4000，偏移2c000，物理92c000，正是第7组context。G0..6读取通过；max-num-gpii=12只表示硬件容量，不能跨过当前MMIO访问授权。0094将检查限制在可读组0..6，仍只分配动态1..6，不操作静态0，不访问7..11。

panic在SMMU写入/连续内存分配/doorbell之前，没有提交DMA。`handshake structure not initialized`不能当根因。`logs/ios-gpi-dma-0093-v1.txt`仍是0092旧环（flush8），新启动早于落盘就panic，必须以照片和精确内核分析；分析文件在`artifacts/xnu-renoir-0093/panic-analysis.json`和`panic-disasm.txt`。0093 DMA镜像标记失败；0094尚待完整构建、QEMU与真机。

## 0094结果与0095（以后跳过QEMU）

0094恢复正常锁屏，用户确认时间/按键正常。`logs/ios-gpi-dma-0094-v1.txt`记录组0..6检查完成；context读回SCTLR=c00027、TCR=802020、TCR2=38071、TTBR=ff0002:03904000、CBAR=1f300。写SCTLR bit12后读0，严格校验因此拒绝，CB已关闭、SID未发布，没有DMA。0095只从必需位比较中排除bit12；固定Linux同样写ASIDPNE但不要求读回为1，地址、fault/endian/cache控制和guard不变。

用户2026-10-22明确要求后续跳过QEMU；执行本地对象编译、完整补丁/仓库检查与CI，然后真机日志。旧的QEMU优先流程已被此要求替代，不能把跳过写成通过。

ASIDPNE依据补充：Arm IHI0062D.c §1.6.5、§16.5（16-317/318）说明bit12是私有ASID空间与广播TLB维护的hint，不是SCTLR.M翻译使能。本机写1读0是实测现象，不能仅据此认定页表/翻译不可用；0095不再要求该hint读1，其他有效控制位照常验证。规范：[Arm官方PDF](https://documentation-service.arm.com/static/5f900d34f86e16515cdc08fb)，本地固定PDF/哈希在`toolchain/renoir-linux-reference/gpi/arm-smmuv2-spec.*`。这不是DMA成功证据，仍需事件与fault日志。

## 0095结果与0096：FSR格式位不是fault

0095日志`logs/ios-gpi-dma-0095-v1.txt`：slot7/CB7/ASID255、IOVA100000+10000、PA203908000、table203904000读回通过，TX/RX均START fresh1/state2。但NOP poll在0微秒即因FSR400退出，EV RP仍100000、事件全零，不能认定DMA已通；reset和释放均通过。

Arm IHI0062D.c §16.5.9（16-299/300）明确FSR[10:9]为只读Format：值2表示AArch64，所以0x400本身不是错误。固定小米arm-smmu.h/c的FSR_FAULT掩码为c00001fe；旧代码用任意非零判断是bug。0096仅按此掩码判断/清除fault，分开记录raw FSR/faults/format。faultmask为0时FAR未定义旧值不能当故障地址。规范截图在artifacts/arm-smmu-fsr-299.png、300.png。未有实际完成事件前，仍不宣称IOMMU/DMA链路成功；芯片ID与HID未实现。

## 2026-10-22：0096 DMA 真机通过

日志 `logs/ios-gpi-dma-0096-v1.txt`（flush11）确认 NOP success=1，100µs，有效event及保护区检查通过，SMMU faults=0/GFSR=0；RESET和释放均完成。不是SPI芯片ID或触控成功。0097开发目标：独立NOP→LOCK→UNLOCK与多事件验证，暂不发SPI数据。QEMU按用户要求跳过。

0097描述符严格使用固定小米源码 `msm_gpi.h` 的LOCK(type0x30)/UNLOCK(type0x31)且IEOB=1、CHAIN=0；与 `spi_geni_lock_bus` / `spi_geni_unlock_bus` 一样分别提交。每步等待新event，最多250ms。预先只授予15个event slot，本次最多3条，不环绕、不回收；这还不是持续传输的event消费实现。失败不提交后续事务，必须重启再试。

## 后续SPI引脚核对（尚未实施）

`dtb/renoir-live.dts` 的 `qupv3_se10_spi_active`（phandle e5）要求GPIO20–23 qup10、drive-strength6mA、bias-disable。固定小米 `platform/pinctrl-shima.c` 将qup10列为这四个pin的第一alternate；mux_bit2、pull_bit0、drv_bit6、oe_bit9。因此目标低10位为0x84（FUNC1、6mA编码2、pull0、OE0），应保留其余位并读回，不能把当前cfg1理解为FUNC1。真正传输前需结合GENI GSI mode与SE时钟设置检查。0097并不做此修改。

## 新参考：HackiOS（2026-10-22，仅检查，尚未合入）

来源：https://github.com/oosexgang/hackios-xnu-kernel ，固定提交 `8e61187098f2c26c5daee8f9f72b6416aa64b9ab`，本地 `toolchain/hackios-xnu-kernel-reference`。`xnu/files/bsd/dev/redwood_goodix.c` 实际同时支持Goodix和FocalTech FT3680，具有GPIO模拟SPI与FTS 0xa0/CRC读取，可作为renoir FT3658U备用传输设计参考；引脚、电源、芯片ID、坐标格式仍须本机核对。其PRAM固件上传不能直接用于本机。GPU驱动、PSCI SMP、电池实现可进一步对照；GPU还依赖另一个userland仓库的Mesa/CoreAnimation适配，不能只替换内核就宣称加速可用。0097目前仅临时启动成功，用户选择仍在启动、暂停等待，尚未读取LOCK事件。

## 0097已验收／0098目标（2026-10-22）

0097真机NOP、LOCK、UNLOCK均100µs完成，事件指针/类型/代码正确，guard1、faults0，复位释放成功；日志`logs/ios-gpi-lock-0097-v1.txt`。0098将以`gpilock=2`进行两次10字节SPI读取，仅A3/9F ID与CRC验证，尚未上机。用户新观察：锁屏日期红字随时间变白，需排查合成/重绘/缓存，尚不能认定GPU是根因。
