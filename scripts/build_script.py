import os
import sys
import subprocess
import shutil
import time
from pathlib import Path

class Colors:
    """控制台颜色输出类"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_colored(text, color=Colors.WHITE):
    """打印彩色文本"""
    print(f"{color}{text}{Colors.END}")

def print_header(title):
    """打印标题"""
    print("\n" + "="*60)
    print_colored(f"🚀 {title}", Colors.BOLD + Colors.CYAN)
    print("="*60)

def print_step(step, description):
    """打印步骤"""
    print_colored(f"\n📋 步骤 {step}: {description}", Colors.BOLD + Colors.BLUE)

def print_success(message):
    """打印成功信息"""
    print_colored(f"✅ {message}", Colors.GREEN)

def print_warning(message):
    """打印警告信息"""
    print_colored(f"⚠️  {message}", Colors.YELLOW)

def print_error(message):
    """打印错误信息"""
    print_colored(f"❌ {message}", Colors.RED)

def print_info(message):
    """打印信息"""
    print_colored(f"💡 {message}", Colors.CYAN)

def check_python_environment():
    """检查Python版本和PyInstaller安装"""
    print_step(1, "检查Python环境和PyInstaller")
    
    # 检查Python版本
    version = sys.version_info
    print_info(f"当前Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major != 3 or version.minor < 7:
        print_error("需要Python 3.7或更高版本")
        return False
    
    if version.minor >= 12:
        print_warning("Python 3.12+可能存在兼容性问题，建议使用Python 3.8-3.11")
    
    # 检查PyInstaller
    try:
        result = subprocess.run([sys.executable, '-m', 'PyInstaller', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            pyinstaller_version = result.stdout.strip()
            print_success(f"PyInstaller已安装: {pyinstaller_version}")
        else:
            print_error("PyInstaller未正确安装或不可用")
            print_info("尝试安装PyInstaller...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller>=5.0,<7.0'])
            print_success("PyInstaller安装成功")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print_error("PyInstaller未安装，正在尝试安装...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller>=5.0,<7.0'])
            print_success("PyInstaller安装成功")
        except Exception as e:
            print_error(f"PyInstaller安装失败: {e}")
            print_info("请手动运行 'pip install pyinstaller>=5.0,<7.0' 进行安装。")
            return False
    except Exception as e:
        print_error(f"检查PyInstaller时出错: {e}")
        return False
    
    print_success("Python环境和PyInstaller检查通过")
    return True

def ensure_dependencies_installed():
    """确保依赖已安装。优先读取 pyproject.toml 的 [project.dependencies]，
    若不可解析，则尝试安装 requirements.txt。
    """
    print_step(1.5, "安装项目依赖")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pyproject_path = os.path.join(project_root, 'pyproject.toml')
    requirements_path = os.path.join(project_root, 'requirements.txt')

    tried = False

    # 优先使用 pip 根据当前项目安装（PEP 517）
    try:
        print_info("尝试使用 pip 根据 pyproject.toml 安装项目依赖（可编辑模式）...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-e', project_root])
        print_success("项目依赖安装完成（可编辑模式）")
        tried = True
    except Exception as e:
        print_warning(f"使用 -e 安装失败: {e}")

    if not tried and os.path.exists(pyproject_path):
        try:
            print_info("尝试使用 pip 根据 pyproject.toml 构建并安装...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', project_root])
            print_success("项目依赖安装完成（构建安装）")
            tried = True
        except Exception as e:
            print_warning(f"直接安装项目失败: {e}")

    # 兜底：requirements.txt
    if not tried and os.path.exists(requirements_path):
        try:
            print_info("尝试根据 requirements.txt 安装依赖...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', requirements_path])
            print_success("requirements.txt 依赖安装完成")
            tried = True
        except Exception as e:
            print_warning(f"requirements 安装失败: {e}")

    if not tried:
        print_warning("未能自动安装依赖。请手动安装依赖后重试。")
    return tried

def check_required_files():
    """检查必需文件，并更新路径"""
    print_step(2, "检查必需文件")
    
    # 获取项目根目录 (假设 build_script.py 在 scripts 目录下，项目根目录是 scripts 的上一级)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 主程序文件路径
    main_script_path = os.path.join(project_root, 'src', 'main.py')
    
    # 图标文件路径
    icon_candidates = [
        os.path.join(project_root, 'src', 'app_icon.ico'),
        os.path.join(project_root, 'src', 'assets', 'icons', 'app_icon.ico'),
    ]
    icon_path = next((p for p in icon_candidates if os.path.exists(p)), None)

    if not os.path.exists(main_script_path):
        print_error(f"主程序文件未找到: {main_script_path}")
        return False, None, None, None
    print_success(f"主程序文件找到: {main_script_path}")

    if not icon_path:
        print_warning("图标文件未找到，将使用默认图标。")
    else:
        print_success(f"图标文件找到: {icon_path}")

    params_path = None

    return True, main_script_path, icon_path, params_path

def clean_build_directories():
    """清理构建目录"""
    print_step(3, "清理旧的构建文件")
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    directories_to_clean = [
        os.path.join(project_root, 'build'),
        os.path.join(project_root, 'dist'),
    ]
    
    cleaned_items = []
    
    for dir_path in directories_to_clean:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                cleaned_items.append(f"目录: {os.path.basename(dir_path)}")
                print_info(f"已删除目录: {dir_path}")
            except Exception as e:
                print_warning(f"无法删除目录 {dir_path}: {e}")
    
    # 清理项目根目录下的 __pycache__ 文件夹
    pycache_path = os.path.join(project_root, '__pycache__')
    if os.path.exists(pycache_path):
        try:
            shutil.rmtree(pycache_path)
            cleaned_items.append(f"目录: {os.path.basename(pycache_path)}")
            print_info(f"已删除目录: {pycache_path}")
        except Exception as e:
            print_warning(f"无法删除目录 {pycache_path}: {e}")

    # 清理项目根目录下的 .pyc 和 .pyo 文件
    for root, dirs, files in os.walk(project_root):
        for file in files:
            if file.endswith(('.pyc', '.pyo')):
                try:
                    file_path = os.path.join(root, file)
                    os.remove(file_path)
                    cleaned_items.append(f"文件: {os.path.relpath(file_path, project_root)}")
                except Exception as e:
                    print_warning(f"无法删除文件 {file_path}: {e}")
    
    if cleaned_items:
        print_success(f"已清理 {len(cleaned_items)} 个项目")
    else:
        print_info("没有需要清理的文件")
    
    return True

def run_pyinstaller(main_script, icon_path, params_path):
    """运行PyInstaller打包"""
    print_step(4, "执行PyInstaller打包")
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec_file = os.path.join(project_root, 'scripts', 'app.spec') # 修改这里，指向 scripts 目录
    
    if not os.path.exists(spec_file):
        print_error(f"Spec文件未找到: {spec_file}。请确保 'scripts/app.spec' 文件存在。") # 更新提示
        return False

    print_info(f"使用配置文件: {spec_file}")
    print_info("开始打包，这可能需要几分钟时间...")
    
    try:
        # 使用--clean参数确保完全重新构建
        cmd = [sys.executable, '-m', 'PyInstaller', '--clean', spec_file]
        
        # 添加图标和数据文件（如果存在）
        # 注意：这里不再需要手动添加 --icon 和 --add-data，因为它们已经在 .spec 文件中处理了
        # PyInstaller 在处理 .spec 文件时会读取这些信息
        
        print_colored(f"执行命令: {' '.join(cmd)}", Colors.YELLOW)
        
        # 执行打包命令
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'  # 忽略编码错误
        )
        
        if process.returncode == 0:
            print_success("PyInstaller执行成功")
            return True
        else:
            print_error("PyInstaller执行失败")
            print_colored("错误输出:", Colors.RED)
            print(process.stderr)
            if process.stdout:
                print_colored("标准输出:", Colors.YELLOW)
                print(process.stdout)
            return False
            
    except FileNotFoundError:
        print_error("找不到pyinstaller命令，请确保已安装PyInstaller")
        print_info("安装命令: pip install pyinstaller")
        return False
    except Exception as e:
        print_error(f"执行PyInstaller时出错: {e}")
        return False

def verify_build_result():
    """验证构建结果"""
    print_step(5, "验证打包结果")
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe_name = "比对程序.exe" # 统一exe名称
    exe_path = os.path.join(project_root, 'dist', exe_name)
    
    if not os.path.exists(exe_path):
        print_error(f"未找到生成的exe文件: {exe_path}")
        return False
    
    # 检查文件大小
    file_size = os.path.getsize(exe_path)
    file_size_mb = file_size / (1024 * 1024)
    
    print_success(f"exe文件已生成: {exe_path}")
    print_info(f"文件大小: {file_size_mb:.2f} MB")
    
    # 文件大小合理性检查
    if file_size_mb < 10:
        print_warning("文件大小偏小，可能缺少依赖")
    elif file_size_mb > 100:
        print_warning("文件大小偏大，考虑优化依赖")
    else:
        print_success("文件大小正常")
    
    return True

def print_final_summary():
    """打印最终总结"""
    print_header("打包完成")
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe_name = "比对程序.exe"
    exe_path = os.path.join(project_root, 'dist', exe_name)
    
    if os.path.exists(exe_path):
        print_success("🎉 打包成功完成！")
        print_info(f"📂 可执行文件位置: {os.path.abspath(exe_path)}")
        
        print_colored("\n📋 使用说明:", Colors.BOLD + Colors.CYAN)
        print_info("• 可以将exe文件复制到任意位置运行")
        print_info("• 首次运行可能较慢（10-30秒），这是正常现象")
        print_info("• 支持Windows 7及以上系统")
        print_info("• 无需安装Python环境")
        
        print_colored("\n🚀 分发建议:", Colors.BOLD + Colors.CYAN)
        print_info("• 可以直接分发exe文件")
        print_info("• 建议压缩后分发以减小传输大小")
        print_info("• 如需要，可以创建安装程序")
        
    else:
        print_error("❌ 打包失败！")
        print_info("请检查上方的错误信息并重试")

def main():
    """主函数"""
    print_header("数据集比对程序 自动打包程序")
    
    start_time = time.time()
    
    # 步骤1：检查Python环境和PyInstaller
    if not check_python_environment():
        return False

    # 新增：安装依赖
    ensure_dependencies_installed()
    
    # 步骤2：检查必需文件，并获取更新后的路径
    success_check_files, main_script, icon_path, params_path = check_required_files()
    if not success_check_files:
        return False
    
    # 步骤3：清理构建目录
    clean_build_directories()
    
    # 步骤4：运行PyInstaller
    # 不再传递 icon_path 和 params_path，因为它们在 .spec 文件中处理
    if not run_pyinstaller(main_script, None, None):
        return False
    
    # 步骤5：验证构建结果
    if not verify_build_result():
        return False
    
    # 计算总耗时
    end_time = time.time()
    total_time = end_time - start_time
    
    print_colored(f"\n⏱️  总耗时: {total_time:.2f} 秒", Colors.MAGENTA)
    
    # 打印最终总结
    print_final_summary()
    
    return True

if __name__ == '__main__':
    try:
        success = main()
        if success:
            print_colored("\n🎊 打包流程全部完成！", Colors.BOLD + Colors.GREEN)
            sys.exit(0)
        else:
            print_colored("\n💥 打包流程失败！", Colors.BOLD + Colors.RED)
            sys.exit(1)
    except KeyboardInterrupt:
        print_colored("\n\n⚠️  用户中断了打包过程", Colors.YELLOW)
        sys.exit(1)
    except Exception as e:
        print_error(f"打包过程中出现未预期的错误: {e}")
        sys.exit(1) 