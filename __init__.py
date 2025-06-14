try:
    import lupa
except:
    from pip模块支持 import entry as pip
    pip.install("lupa")

from tooldelta.constants import SysStatus
from tooldelta.internal.cmd_executor import ConsoleCmdManager
from tooldelta import utils
from tooldelta.utils import fmts
import os
import json
import shutil
import glob
import requests
import importlib
import traceback
from pathlib import Path
from requests.exceptions import RequestException
from tooldelta.utils import fmts
from tooldelta import Plugin, plugin_entry

from . import wrap
importlib.reload(wrap)
from .wrap import Control, LumegaPluginConfig

def sync_folders(src_dir, dst_dir, force_overwrite=None):
    """
    同步源文件夹到目标文件夹，如果目标文件夹缺少文件则复制，可强制覆盖指定文件。

    :param src_dir: 源文件夹路径
    :param dst_dir: 目标文件夹路径
    :param force_overwrite: 需要强制覆盖的文件列表
    """
    if force_overwrite is None:
        force_overwrite = []
    
    for root, dirs, files in os.walk(src_dir):
        # 计算当前目录相对于源目录的相对路径
        rel_path = os.path.relpath(root, src_dir)
        # 构建目标目录路径
        dst_root = os.path.join(dst_dir, rel_path)
        
        # 创建目标目录（如果不存在）
        os.makedirs(dst_root, exist_ok=True)
        
        for file in files:
            src_file = os.path.join(root, file)
            dst_file = os.path.join(dst_root, file)
            
            # 判断是否需要复制或覆盖
            if not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)
            else:
                if src_file in force_overwrite:
                    shutil.copy2(src_file, dst_file)

class LumeltaPlugin(Plugin):
    name = "Lumelta"
    author = "Yeah"
    version = (0, 0, 1)

    def __init__(self, frame):
        super().__init__(frame)
#        self.inject_system_menu()
#        self.ListenFrameExit(self.on_exit)
        self.datas_remote_url = "https://raw.githubusercontent.com/Yeah114/Lumelta/main/datas.json"
        self.ListenActive(self.active)
        self.ListenFrameExit(self.uninstallation_lumega)
        #self.ListenPreload(self.setup_lumega)
        self.python_dir_path = Path(__file__).parent
        self.datas_file_path = self.python_dir_path / 'datas.json'
        self.neomega_storage_dir_path = Path("./neomega_storage")
        self.default_neomega_storage_dir_path = self.python_dir_path / "neomega_storage"
        os.makedirs(self.neomega_storage_dir_path, exist_ok=True)
        self.lumega_plugin_configs_dir_path = self.neomega_storage_dir_path / "config"
        self.lumega_plugins_dir_path = self.neomega_storage_dir_path / "lang" / "LuaLoader"
        sync_folders(self.default_neomega_storage_dir_path, self.neomega_storage_dir_path,  [str(self.lumega_plugins_dir_path / "coromega.lua")])
        self.lumega_plugins = []
        self.fmts_header = fmts.colormode_replace("§f Lumelta ", 7) + " "

    def active(self):
        self.check_update()
        self.setup_lumega()

    @utils.thread_func("lumelta.check_update")
    def check_update(self):
        """
        检查本地datas.json与远程GitHub仓库中的datas.json版本差异
        """
        try:
            # 读取本地JSON文件
            with open(self.datas_file_path, 'r', encoding='utf-8') as f:
                local_datas = json.load(f)
                local_version = local_datas.get('version', 'UNKNOWN')
                self.print(f"当前版本: v{local_version}")
                
            # 获取远程JSON文件
            self.print("正在检查更新...")
            response = requests.get(self.datas_remote_url, timeout=5)
            response.raise_for_status()  # 检查HTTP错误
            
            remote_data = response.json()
            remote_version = remote_data.get('version', '未知版本')
            
            # 比较版本
            if remote_version != local_version:
                self.print("发现新版本可用！")
                self.print(f"当前版本: v{local_version} → 最新版本: v{remote_version}")
                self.print("请访问项目仓库获取更新: https://github.com/Yeah114/Lumelta")
            else:
                self.print("当前已是最新版本")
                
        except FileNotFoundError:
            self.print(f"错误：本地文件 {local_file} 不存在")
        except json.JSONDecodeError:
            self.print("错误：JSON解析失败，请检查文件格式")
        except RequestException as e:
            self.print(f"网络请求失败: {str(e)}")
        except Exception as e:
            self.print(f"发生未知错误: {str(e)}")

    def setup_lumega(self):
        self.control = Control(self.frame, self.neomega_storage_dir_path)
        plugin_config_file_paths = glob.glob(str(self.lumega_plugin_configs_dir_path / '**' / '*.json'), recursive=True)
        total = len(plugin_config_file_paths)
        i = 0
        for plugin_config_file_path in plugin_config_file_paths:
            i += 1
            load_header = f"[{i}/{total}] "
            with open(plugin_config_file_path, "r", encoding="utf-8") as plugin_config_file:
                plugin_config = LumegaPluginConfig(plugin_config_file.read(), plugin_config_file_path)
                if plugin_config.source == "LuaLoader":
                    lua_plugin_file_path = self.lumega_plugins_dir_path / plugin_config.name
                    fmts.print(load_header + f"正在加载 Lua 插件：{plugin_config.name}")
                    if plugin_config.disable:
                        fmts.print_war(load_header + f"跳过加载 Lua 插件：{plugin_config.name}")
                        continue
                    if not lua_plugin_file_path.exists():
                        fmts.print_war(load_header + f"无法找到 Lua 插件：{plugin_config.name}")
                        continue
                    self.control.load_lua_plugin_file(lua_plugin_file_path, plugin_config, load_header)
                elif plugin_config.source == "Built-In":
                    fmts.print(load_header + f"正在加载 Built-In 插件：{plugin_config.name}")
                    if plugin_config.disable:
                        fmts.print_war(load_header + f"跳过加载 Built-In 插件：{plugin_config.name}")
                        continue
                    builtin_plugin_dir_path = Path(__file__).parent / "wrap" / "builtin_plugins" / plugin_config.name
                    if not builtin_plugin_dir_path.exists():
                        fmts.print_war(load_header + f"无法找到 Built-In 插件：{plugin_config.name}")
                        continue
                    self.control.load_builtin_plugin(plugin_config, load_header)

    def uninstallation_lumega(self, _):
        #self.control.stop_all_lua_plugin(True)
        self.control.stop()

    """
    def inject_system_menu(self):
        self.cmd_manager = self.frame.cmd_manager
        self._original_system_readline = self.cmd_manager.command_readline_proc

        @utils.thread_func("控制台执行命令-兼容模式")
        def command_readline_proc():
            fmts.print_suc("ToolHack Terminal [兼容模式] 进程已注入, 允许开启标准输入")
            while 1:
                try:
                    try:
                        rsp = input()
                        if rsp in ("^C", "^D"):
                            raise KeyboardInterrupt
                    except (KeyboardInterrupt, EOFError):
                        fmts.print_inf("按退出键退出中...")
                        self.frame.launcher.update_status(SysStatus.NORMAL_EXIT)
                        return
                    self.cmd_manager.execute_cmd(rsp)
                except (EOFError, KeyboardInterrupt):
                    fmts.print_war("命令执行被中止")
                except Exception:
                    fmts.print_err(f"控制台指令执行出现问题: {traceback.format_exc()}")
                    fmts.print_err("§6虽然出现了问题, 但是您仍然可以继续使用控制台菜单")
                    
        self.frame.cmd_manager.command_readline_proc = command_readline_proc

    def uninject_system_menu(self):
        self.frame.cmd_manager.command_readline_proc = self._original_system_readline

    def on_exit(self, _):
        self.uninject_system_menu()
    """

entry = plugin_entry(LumeltaPlugin)