# ios-renoir

小米11 Lite 5G（renoir / SM7350）的XNU与iOS 16实验移植。本仓库独立维护，保留源代码历史和上游贡献。

本项目基于[dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet)的shim、XNU补丁和用户态适配发展而来；原说明保存在[上游README](docs/upstream-ios-sweet-README.md)。独立建仓不改变已有代码的来源或许可，现有文件中的版权声明与许可证继续适用。Apple用户态与厂商固件不在本仓库分发。

## 已经验证

- 真机XNU、UFS、可写HFS+根文件系统、launchd、SpringBoard和锁屏。
- 电源键及两个音量键、校准RTC与上海时区；10Hz屏幕拷贝比30Hz响应改善。
- 触控电源请求、复位、GPI/SMMU专用DMA及NOP/LOCK/UNLOCK完成事件（0097）通过。
- 0098新增FT3658U GSI SPI芯片ID与CRC读取测试，完整CI通过但真机重启，已回退0097；0099正在加入持久日志检查点定位，尚无有效芯片ID。

触控坐标/HID尚未完成，未实现GPU加速、真实电池遥测、Wi-Fi/蓝牙/音频。当前只启用一个CPU核心，仍有明显卡顿。红色字体随时间变白的现象已记录，原因未确认。原sweet设备的触控和SMP结果不能视为renoir已实现。

## 启动与继续开发

先阅读[当前接续状态](NOTES.md)、[启动和日志指南](docs/renoir/启动与驱动移植交接指南.md)、[驱动顺序](docs/renoir/驱动开发顺序.md)、[硬件事实表](docs/renoir/renoir移植事实表.md)。[GSI触控路线](docs/renoir/GSI触控移植路线.md)记录实际事件验证，[HackiOS参考评估](docs/renoir/HackiOS参考适配评估.md)说明可复用部分及差异。

本机工作区为`/home/daimile/桌面/ios-renoir`，仓库在`src/`。在新电脑可创建工作区后克隆到其src子目录；[workspace-tools](workspace-tools/README.md)提供与src同级的主机脚本。文档中的本机artifacts/logs/备份不会随clone下载。

真机只用临时`fastboot boot`；不要直接启动redwood/sweet预编译镜像。userdata已改为iOS，本机原有boot保留，普通重启不等于回到可用Android。后续破坏性写入需要单独确认。

用户要求后续跳过QEMU；本地编译、严格补丁检查、完整CI和真机日志仍需分别验收。

## 来源与致谢

Apple开源XNU、IOHIDFamily、libpthread、HFS；dipa-studio/ios-sweet及其贡献者；blacktop/darwin-xnu-build；BearSSL；Qualcomm/Xiaomi开源内核；OrangeFox/TWRP相关项目。另参考[oosexgang/hackios-xnu-kernel](https://github.com/oosexgang/hackios-xnu-kernel)的公开驱动实现；当前未把其redwood整套驱动移植到本机。详细版本与观察记录见NOTES。
