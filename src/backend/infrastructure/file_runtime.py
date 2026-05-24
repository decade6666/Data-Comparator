import datetime
import os
import shutil
import xml.etree.ElementTree as ET
import zipfile
from typing import List, Optional, Tuple

import appdirs
import pandas as pd
from openpyxl import load_workbook

from ...shared.log_utils import log
from ..domain.processing_control import check_stop_frequently

try:
    import pythoncom
    import win32com.client as win32
except Exception:
    win32 = None
    pythoncom = None


def check_and_remove_file_protection(
    file_path: str, exclude_sheets: List[str], log_func
) -> Tuple[bool, bool, str, List[str]]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    base, ext = os.path.splitext(file_path)
    temp_app_dir = get_app_temp_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    original_filename = os.path.basename(base)
    new_file_name = f"{original_filename}_nofilter_{timestamp}{ext}"
    new_file_path = os.path.join(temp_app_dir, new_file_name)

    try:
        shutil.copy2(file_path, new_file_path)
        check_stop_frequently(log_func)
    except InterruptedError:
        raise
    except Exception as e:
        log_func(f"❌ 创建副本失败: {str(e)}")
        raise

    zone_id_stream = f"{file_path}:Zone.Identifier"
    is_protected = False
    protection_removed = False

    try:
        if os.path.exists(zone_id_stream):
            with open(zone_id_stream, "r") as f:
                content = f.read()
            is_protected = "[ZoneTransfer]" in content and "ZoneId=3" in content
        else:
            is_protected = False
    except Exception:
        is_protected = True

    if is_protected:
        try:
            os.remove(zone_id_stream)
            protection_removed = True
        except Exception as e:
            protection_removed = False
            log_func(f"⚠️ 解除文件保护失败: {str(e)}")
    else:
        log_func("ℹ️ 文件未受保护，继续处理...")

    actually_removed: List[str] = []

    try:
        if win32 is None:
            raise ImportError("pywin32 未安装或不可用")

        try:
            pythoncom.CoInitialize()
        except Exception:
            pass

        excel_app = None
        wb_com = None
        filters_cleared_by_pywin32 = False
        created_standalone_app = False
        try:
            dispatch_method = getattr(win32, "DispatchEx", None)
            if dispatch_method is not None:
                excel_app = dispatch_method("Excel.Application")
                created_standalone_app = True
            else:
                excel_app = win32.Dispatch("Excel.Application")
            excel_app.Visible = False
            excel_app.DisplayAlerts = False

            check_stop_frequently(log_func)

            wb_com = excel_app.Workbooks.Open(
                new_file_path, UpdateLinks=0, ReadOnly=False
            )
            for ws_com in wb_com.Worksheets:
                try:
                    check_stop_frequently(log_func)
                except Exception:
                    if wb_com is not None:
                        wb_com.Close(SaveChanges=False)
                    if excel_app is not None and created_standalone_app:
                        excel_app.Quit()
                    raise

                try:
                    if getattr(ws_com, "FilterMode", False):
                        try:
                            ws_com.ShowAllData()
                        except Exception:
                            try:
                                ws_com.AutoFilter.ShowAllData()
                            except Exception:
                                pass
                        filters_cleared_by_pywin32 = True
                except Exception:
                    pass

                try:
                    if getattr(ws_com, "AutoFilterMode", False):
                        ws_com.AutoFilterMode = False
                        filters_cleared_by_pywin32 = True
                except Exception:
                    pass

                try:
                    list_objects = getattr(ws_com, "ListObjects", None)
                    if list_objects is not None:
                        for lo in list_objects:
                            try:
                                if (
                                    getattr(lo, "ShowAutoFilter", None) is not None
                                    and lo.ShowAutoFilter
                                ):
                                    lo.ShowAutoFilter = False
                                    filters_cleared_by_pywin32 = True
                                try:
                                    lo.AutoFilter.ShowAllData()
                                except Exception:
                                    pass
                            except Exception:
                                pass
                except Exception:
                    pass

            wb_com.Save()
        finally:
            try:
                if wb_com is not None:
                    wb_com.Close(SaveChanges=False)
            except Exception:
                pass
            try:
                if excel_app is not None and created_standalone_app:
                    excel_app.Quit()
            except Exception:
                pass
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

        if filters_cleared_by_pywin32:
            log_func("✅ 成功通过pywin32清除自动筛选器。")
        else:
            log_func("ℹ️ 文件中未发现自动筛选器，跳过清除。")
    except InterruptedError:
        raise
    except Exception as e:
        log_func(
            f"⚠️ 主要预处理（pywin32清除筛选器或删除Sheet）失败: {str(e)}，尝试回退方法..."
        )
        try:
            remove_auto_filters_from_xlsx(new_file_path, new_file_path, log_func)
            log_func("✅ 成功通过备用方法清除自动筛选器。")
        except InterruptedError:
            raise
        except Exception as fallback_e:
            log_func(f"❌ 备用筛选器清除失败，跳过继续处理: {str(fallback_e)}")

    return is_protected, protection_removed, new_file_path, actually_removed


def validate_excel_file(file_path: str, log_func) -> Tuple[bool, Optional[str]]:
    try:
        if not os.path.exists(file_path):
            error = f"文件不存在: {file_path}"
            log(error, log_func)
            return False, error

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            error = f"文件为空: {file_path}"
            log(error, log_func)
            return False, error

        engines = ["openpyxl", "xlrd"]
        validation_errors: List[str] = []

        for engine in engines:
            try:
                if engine == "xlrd" and file_path.endswith(".xlsx"):
                    continue
                pd.read_excel(file_path, sheet_name=0, nrows=1, engine=engine)
                return True, None
            except Exception as engine_error:
                error_msg = str(engine_error)
                validation_errors.append(f"{engine}: {error_msg}")

                if (
                    "invalid XML" in error_msg
                    or "could not read worksheets" in error_msg
                ):
                    log("⚠️ 检测到XML格式错误，建议修复文件后重试", log_func)
                continue

        combined_error = "; ".join(validation_errors)
        log("⚠️ 所有验证引擎都失败，但文件可能仍可修复", log_func)
        return False, combined_error
    except Exception as e:
        error = f"文件验证过程出错: {str(e)}"
        log(error, log_func)
        return False, error


def get_sheet_names(file_path: str, log_func) -> List[str]:
    try:
        wb = load_workbook(file_path, read_only=True)
        sheet_names = wb.sheetnames
        wb.close()
        return sheet_names
    except Exception as e:
        log_func(f"⚠️ 无法获取文件 {os.path.basename(file_path)} 的Sheet名称: {str(e)}")
        try:
            excel_file = pd.ExcelFile(file_path, engine="openpyxl")
            sheet_names = excel_file.sheetnames
            excel_file.close()
            return sheet_names
        except Exception as e_pd:
            log_func(
                f"❌ 无法获取文件 {os.path.basename(file_path)} 的Sheet名称"
                f"（pandas回退也失败）: {str(e_pd)}"
            )
            return []


def get_app_temp_dir() -> str:
    appname = "PyDataCompare"
    appauthor = "YourCompanyOrAuthor"
    temp_dir = appdirs.user_data_dir(appname, appauthor)
    temp_sub_dir = os.path.join(temp_dir, "temp")
    os.makedirs(temp_sub_dir, exist_ok=True)
    return temp_sub_dir


def cleanup_nofilter_files(log_func=None) -> int:
    removed_count = 0
    try:
        temp_dir = get_app_temp_dir()
        if not os.path.isdir(temp_dir):
            return 0
        for name in os.listdir(temp_dir):
            if "_nofilter_" in name and name.lower().endswith((".xlsx", ".xlsm")):
                fpath = os.path.join(temp_dir, name)
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                        removed_count += 1
                except Exception as e:
                    if log_func:
                        log_func(f"⚠️ 删除临时缓存文件失败: {fpath}，原因: {e}")
        if log_func:
            log_func(f"🧹 已清理 nofilter 缓存文件 {removed_count} 个")
    except Exception as e:
        if log_func:
            log_func(f"⚠️ 清理临时缓存文件时出错: {e}")
    return removed_count


def remove_auto_filters_from_xlsx(
    file_path: str, output_path: Optional[str] = None, log_message=None
) -> None:
    output_path = output_path or file_path.replace(".xlsx", ".xlsx")

    temp_app_dir = get_app_temp_dir()
    unique_temp_id = os.urandom(8).hex()
    tmpdirname = os.path.join(temp_app_dir, f"excel_extract_{unique_temp_id}")
    os.makedirs(tmpdirname, exist_ok=True)

    try:
        with zipfile.ZipFile(file_path, "r") as zip_ref:
            zip_ref.extractall(tmpdirname)
        check_stop_frequently(log_message)

        sheet_dir = os.path.join(tmpdirname, "xl", "worksheets")
        for filename in os.listdir(sheet_dir):
            check_stop_frequently(log_message)
            if filename.startswith("sheet") and filename.endswith(".xml"):
                sheet_path = os.path.join(sheet_dir, filename)
                tree = ET.parse(sheet_path)
                root = tree.getroot()
                ns = {
                    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                }
                auto_filter = root.find("main:autoFilter", ns)
                if auto_filter is not None:
                    root.remove(auto_filter)
                    tree.write(sheet_path, encoding="utf-8", xml_declaration=True)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as new_zip:
            for foldername, subfolders, filenames in os.walk(tmpdirname):
                check_stop_frequently(log_message)
                for filename in filenames:
                    check_stop_frequently(log_message)
                    file_path_inner = os.path.join(foldername, filename)
                    arcname = os.path.relpath(file_path_inner, tmpdirname)
                    new_zip.write(file_path_inner, arcname)
    finally:
        if os.path.exists(tmpdirname):
            shutil.rmtree(tmpdirname)
