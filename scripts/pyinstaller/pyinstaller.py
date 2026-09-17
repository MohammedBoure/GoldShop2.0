# build_exe.py
import os
import sys
import subprocess
import shutil
import mysql.connector


def build_production():

    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    main_script = os.path.join(project_dir, "main.py")
    exe_name = "GOLDSHOP"
    dist_root = os.path.join(project_dir, "dist")
    build_root = os.path.join(project_dir, "build")
    output_root = dist_root

    # Detect MySQL connector paths (pure Python)
    mysql_path = os.path.dirname(mysql.connector.__file__)
    plugins_src = os.path.join(mysql_path, "plugins")
    locales_src = os.path.join(mysql_path, "locales")

    # === التحقق الذكي من وجود الملفات والمجلدات الأساسية قبل البناء ===
    required_assets = {
        "ui/logo.png": os.path.join(project_dir, "ui", "logo.png"),
        "ui/styles.qss": os.path.join(project_dir, "ui", "styles.qss"),
        "translations": os.path.join(project_dir, "translations"),
        "web/templates": os.path.join(project_dir, "web", "templates"),
        "web/static": os.path.join(project_dir, "web", "static"),
    }
    
    for name, path in required_assets.items():
        if not os.path.exists(path):
            print(f"\n[FATAL ERROR] Missing required asset: {name}")
            print(f"Expected at: {path}")
            print("Please make sure the file/folder exists and try again.")
            sys.exit(1)
    # ================================================================

    # 1. Clean Workspace
    for folder_path in (dist_root, build_root):
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
            except PermissionError:
                if folder_path == dist_root:
                    output_root = os.path.join(project_dir, "dist_rebuild")
                    if os.path.exists(output_root):
                        shutil.rmtree(output_root)
                    print(f"[WARN] dist is locked; building into {os.path.relpath(output_root, project_dir)} instead.")
                else:
                    raise

    command = [
        sys.executable, "-m", "PyInstaller",

        "--noconsole",
        "--onedir",
        f"--name={exe_name}",
        f"--distpath={output_root}",
        "--clean",
        "--noupx",

        # UI & Web assets
        "--add-data=ui/logo.png;ui",
        "--add-data=ui/styles.qss;ui",
        "--add-data=translations;translations",
        "--add-data=web/templates;web/templates",
        "--add-data=web/static;web/static",

        # MySQL pure-python resources
        f"--add-data={plugins_src};mysql/connector/plugins",
        f"--add-data={locales_src};mysql/connector/locales",

        # Mandatory collections
        "--collect-all=mysql.connector",
        "--collect-all=reportlab",
        "--collect-all=qtawesome",
        "--collect-all=flask",
        "--collect-all=jinja2",
        "--collect-all=werkzeug",
        "--collect-all=web",

        # Hidden imports
        "--hidden-import=app",
        "--hidden-import=web_security",
        "--hidden-import=duckdns_updater",
        "--hidden-import=services.duckdns",
        "--hidden-import=services.runtime_control",
        "--hidden-import=mysql.connector.plugins.mysql_native_password",
        "--hidden-import=sqlalchemy",
        "--hidden-import=pandas",
        "--hidden-import=numpy",
        "--hidden-import=openpyxl",
        
        "--collect-submodules=database",
        "--collect-data=database",
        "--collect-submodules=services",
        "--collect-submodules=web",

        # Optional scientific/image packages
        "--exclude-module=scipy",
        "--exclude-module=numba",
        "--exclude-module=llvmlite",
        "--exclude-module=cv2",
        "--exclude-module=pygame",

        "--icon=ui/logo.png",
        main_script
    ]

    try:
        print(f"Building {exe_name} for production...\n")
        subprocess.check_call(command, cwd=project_dir)

        # 3. Post-build: copy external config files and guarantee web & translation assets
        dist_path = os.path.join(output_root, exe_name)

        for cfg in (".env", "config.json"):
            cfg_path = os.path.join(project_dir, cfg)
            if os.path.exists(cfg_path):
                shutil.copy(cfg_path, dist_path)
                print(f"[OK] Copied external config: {cfg}")

        # Ensure web assets and translations exist directly in output directory
        dist_web = os.path.join(dist_path, "web")
        for subfolder in ("templates", "static"):
            src_sub = os.path.join(project_dir, "web", subfolder)
            dst_sub = os.path.join(dist_web, subfolder)
            if os.path.exists(src_sub) and not os.path.exists(dst_sub):
                shutil.copytree(src_sub, dst_sub)
                print(f"[OK] Copied web/{subfolder} to output directory")

        dist_trans = os.path.join(dist_path, "translations")
        src_trans = os.path.join(project_dir, "translations")
        if os.path.exists(src_trans) and not os.path.exists(dist_trans):
            shutil.copytree(src_trans, dist_trans)
            print(f"[OK] Copied translations to output directory")

        # 4. Create runtime folders
        for folder in ("runtime", "documents", "exports", "factures"):
            os.makedirs(os.path.join(dist_path, folder), exist_ok=True)

        print("\nSUCCESS!")
        print(f"Application generated in: {os.path.relpath(dist_path, project_dir)}")

    except subprocess.CalledProcessError as e:
        print("\n[ERROR] PyInstaller failed.")
        print(e)

    except Exception as e:
        print("\n[ERROR] Unexpected error.")
        print(e)


if __name__ == "__main__":
    build_production()