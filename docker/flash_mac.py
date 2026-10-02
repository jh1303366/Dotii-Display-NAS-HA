"""Update only Dotii's application partition; keep NVS and Wi-Fi settings."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    image=root/'firmware'/'state_display.bin'
    manifest=root/'firmware'/'ha-firmware.json'
    if not image.is_file() or not manifest.is_file():raise SystemExit('缺少 Home Assistant 固件，请重新解压完整固件包。')
    info=json.loads(manifest.read_text(encoding='utf-8'))
    if hashlib.sha256(image.read_bytes()).hexdigest()!=info['sha256']:raise SystemExit('固件校验未通过，请重新下载。')
    print('Dotii Home Assistant 屏幕更新 · '+info['version'])
    print('仅更新应用区，保留现有 Wi-Fi 和 NAS 连接配置。')
    from serial.tools import list_ports
    ports=[p for p in list_ports.comports() if p.vid in {0x303a,0x1a86,0x10c4,0x0403} or 'usb' in p.device.lower()]
    if not ports:raise SystemExit('未发现屏幕。请使用能传数据的 USB 线连接 Dotii，再重新打开此文件。')
    for i,p in enumerate(ports,1):print(f'{i}. {p.description} ({p.device})')
    choice=input('选择 Dotii 的序号（输入 q 退出）：').strip()
    if choice.lower()=='q':return
    try:port=ports[int(choice)-1].device if 1<=int(choice)<=len(ports) else None
    except ValueError:port=None
    if not port:raise SystemExit('序号不正确，请重新运行。')
    if input('回车开始更新，输入 q 退出：').strip().lower()=='q':return
    result=subprocess.run([sys.executable,'-m','esptool','--chip','esp32s3','--port',port,'--baud','460800','--before','default_reset','--after','hard_reset','write_flash','0x10000',str(image)])
    if result.returncode:raise SystemExit('更新未完成。可以断开 USB 后重试；若无法进入下载模式，请按住 BOOT 并按一下 RESET。')
    print('更新完成。屏幕会重启；按侧键切换到 Home Assistant，也可从控制中心进入。')

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\n已取消。')
