import os
import sys
import argparse
import logging
from logging.handlers import RotatingFileHandler

# 1. 导入你原本的业务核心
try:
    from backend.api_service import ApiService
except ImportError:
    print("错误: 找不到 backend.api_service 模块，请确保在正确的目录下运行此脚本。")
    sys.exit(1)

# 2. 复用你的日志配置逻辑
def get_log_xdg_base_path():
    data_home = os.environ.get('XDG_DATA_HOME')
    if not data_home or data_home == '':
        data_home = os.path.expanduser('~/.local/share')
    return os.path.join(data_home, "BiliLiveTool")

def get_log_path():
    if sys.platform.startswith('linux'):
        base_path = get_log_xdg_base_path()
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    log_dir = os.path.join(base_path, 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    return os.path.join(log_dir, 'app_cli.log')

# 配置日志（同时输出到终端和文件）
log_file = get_log_path()
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
stream_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    level=logging.INFO, # 命令行模式默认 INFO 即可，需要排查改为 DEBUG
    format='%(asctime)s - %(name)-15s - %(levelname)-8s - %(message)s',
    handlers=[file_handler, stream_handler]
)
logging.getLogger("urllib3").setLevel(logging.INFO)
logger = logging.getLogger("CLI_Main")

# 3. 命令行参数解析
def parse_args():
    parser = argparse.ArgumentParser(description="Bilibili 直播工具命令行版")
    parser.add_argument('action', choices=['start', 'stop'], help="执行的动作: start(开播) 或 stop(断播)")
    parser.add_argument('--area1', type=str, help="大分区名称 (可选，若不填则使用上次保存的配置)")
    parser.add_argument('--area2', type=str, help="子分区名称 (可选，若不填则使用上次保存的配置)")
    return parser.parse_args()

# 4. 执行主逻辑
def main():
    args = parse_args()
    
    logger.info("正在初始化 BiliLive API 服务...")
    api = ApiService()
    
    if args.action == 'start':
        logger.info("正在请求开播...")
        
        # 参照你源码中 tray_start_live() 的逻辑
        if args.area1 and args.area2:
            res = api.start_live(args.area1, args.area2)
        else:
            user_config = api.user_service.load_saved_config()
            if user_config and 'last_area_name' in user_config:
                area = user_config['last_area_name']
                if isinstance(area, list) and len(area) >= 2:
                    res = api.start_live(area[0], area[1])
                else:
                    res = api.start_live()
            else:
                res = api.start_live()
        
        # 处理开播结果
        if res and res.get('code') == 0:
            stream_data = res.get('data', {})
            rtmp_info = stream_data.get('rtmp1', {})
            
            print("\n" + "="*50)
            print("🎉 开播成功！")
            print(f"📡 RTMP 🚀地址: {rtmp_info.get('addr')}")
            print(f"🔑 🔑  推流码: {rtmp_info.get('code')}")
            print("="*50 + "\n")
            
            # 命令行直接打印完整的推流 URL 方便 OBS 直接复制
            full_url = f"{rtmp_info.get('addr')}{rtmp_info.get('code')}"
            print(f"🔗 完整推流链接:\n{full_url}\n")
            
        elif res and res.get('code') == 60024:
            logger.error("❌ 开播失败：需要人脸识别验证！")
            print(f"请使用图形界面或前往提示的 URL 扫码验证: {res.get('qr', '')}")
        else:
            msg = res.get('msg', '未知错误') if res else '请求未响应'
            logger.error(f"❌ 开播失败: {msg}")

    elif args.action == 'stop':
        logger.info("正在请求下播...")
        res = api.stop_live()
        if res and res.get('code') == 0:
            logger.info("🛑 已成功关闭直播间。")
            # 执行下播清理
            try:
                api.config_manager.save()
            except Exception:
                pass
        else:
            msg = res.get('msg', '未知错误') if res else '请求未响应'
            logger.error(f"❌ 下播失败: {msg}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被用户终止。")
        sys.exit(0)
