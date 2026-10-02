# Home Assistant 接入与触摸操作

本扩展连接现有 Home Assistant，NAS 负责获取状态和调用服务，Dotii 使用 1.3.0-ha 固件显示与交互。HA 令牌仅保存在 NAS `/data/ha.json`，权限 600，不进入屏幕快照。

## 接入自己的家庭

1. 按 [NAS 部署教程](部署说明-极空间Z4.md) 启动后台，在浏览器登录管理页并进入 **Home Assistant**。
2. 在 HA 个人资料中创建专用长期访问令牌；复制到管理页的令牌输入框。不要将令牌发到 Issues 或放进仓库。
3. 填写 HA 基础地址，例如 `http://192.168.1.101:8123`，保存后发现实体。
4. 选择要显示或控制的实体，设置短名称并排序，最多 32 个。无需选择所有设备；传感器、专用页面辅助实体也计入限额。
5. 启用 HA 模块，将屏幕更新为 HA 固件并配网。令牌撤销或失效时在管理页重新填写。

支持实体域：`sensor`、`binary_sensor`、`light`、`switch`、`fan`、`climate`、`weather`、`vacuum`。温湿度与 PM2.5 按 HA `device_class` 识别；实体没有相应属性时，需先在 HA 配置属性或修改适配逻辑。

## 页面与操作

| 页面 | 操作 |
| --- | --- |
| 首页 | 时间、温湿度、天气、在线比例、已开启灯数、PM2.5 |
| 灯光 | 左右箭头选择灯，电源按钮开关；支持亮度时开放调光 |
| 空调 | 点击顶部名称切换空调，加减调温，底部选择模式；模式弹层取消不发送指令 |
| 环境 | 温度、湿度与空气传感器数据 |
| 扫地机 | 状态、电量；根据 `supported_features` 开放启动、暂停、停止、回充 |
| 车辆 | 电量、续航、锁车、充电、车温与状态；只读，不唤醒或解锁车辆 |
| NAS | CPU、内存与温度，只读 |
| 其他设备 | 开关、风扇；支持百分比调速时显示调速控件 |

屏幕顶部下拉打开控制中心，通过房屋图标进入 HA；侧键按模块顺序切换。HA 内左右滑动翻页或返回，底部圆点提示当前位置。温度范围、步进、空调模式及其他操作由实体能力决定。断线、数据过期和实体不可用时禁止控制；操作后的显示以 HA 返回状态为准。

首页在线率是所选实体可用比例，灯光计数只统计所选灯。PM2.5 的“优/良/偏高”是界面阈值，不是完整空气质量指数。天气图形是装饰素材，天气文字来自真实 HA 状态。

## 车辆、NAS 和辅助电量映射

本版专用角色仍使用 `bridge/ha_client.py` 中 `entity_role()` 的示例 ID 表。其他家庭的实体 ID 不一定一致。部署前将表中键替换成自己的实体 ID，保留右侧角色名，重新构建后台镜像；屏幕固件无需因此重编译。修改名称不能替代修改实体 ID。

| 示例实体 ID | 角色 |
| --- | --- |
| `sensor.tesla_battery_level` | `vehicle_battery` |
| `sensor.tesla_rated_battery_range` | `vehicle_range` |
| `sensor.tesla_inside_temp` | `vehicle_temperature` |
| `binary_sensor.tesla_locked` | `vehicle_lock` |
| `sensor.tesla_charging_state` | `vehicle_charging` |
| `sensor.tesla_state` | `vehicle_status` |
| `sensor.p20_pro_battery` | `vacuum_battery` |
| `sensor.nas_cpufu_zai` | `nas_cpu` |
| `sensor.nasnei_cun_shi_yong_lu` | `nas_memory` |
| `sensor.naswen_du` | `nas_temperature` |

修改后也需在管理页选中这些实体。车辆/NAS 的属性值与单位需符合页面预期，其他品牌尚未逐一适配。没有对应设备时不必配置。窗帘、场景、通知、GPS 与任意 HA 服务调用尚未实现，参考效果图中的所有设备类型不代表本版已经支持。

## 更新与预览

已有 Dotii 基础固件的设备可使用 [Release 固件包](https://github.com/jh1303366/Dotii-Display-NAS-HA/releases) 中的 Mac 更新助手。它先校验固件，仅写 `0x10000` 应用分区，保留 NVS 中的 Wi-Fi 和 NAS 绑定。全新开发板先安装完整基础固件，见部署教程。

[界面图片](docs/previews) 来自实际 LVGL 代码在电脑上的渲染，示例数值不是实时设备数据。外壳、玻璃反光与摄影背景属于参考产品图。尚未完成实机刷入、触摸与恢复测试，本版仍为预发布。
