import os
import subprocess
import sys

# Function to check and install missing dependencies
def install_missing_packages():
    required_packages = {
        "win32com.client": "pywin32",
        "openpyxl": "openpyxl",
        "pandas": "pandas"
    }

    for package, pip_name in required_packages.items():
        try:
            if package == "win32com.client":
                import win32com.client
            elif package == "openpyxl":
                import openpyxl
            elif package == "pandas":
                import pandas
        except ImportError:
            print(f"Missing {package}, attempting to install it...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            print(f"{pip_name} installed successfully.")

            # Special case for pywin32: run the post-install script if needed
            if pip_name == "pywin32":
                print("Running pywin32 post-install script...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pywin32_postinstall", "-install"])
                    print("pywin32 post-install script completed successfully.")
                except subprocess.CalledProcessError as e:
                    print(f"Error running pywin32 post-install script: {e}")

# Function to load the last used CANoe configuration or prompt for it
def get_canoe_config():
    default_config_path = r"C:\path\to\default\canoe_config.cfg"
    
    if os.path.exists(default_config_path):
        use_default = input(f"Found default CANoe configuration at {default_config_path}. Do you want to use it? (y/n): ").lower()
        if use_default == 'y':
            return default_config_path
    
    canoe_config_path = input("Please enter the full path to the CANoe configuration (.cfg): ")
    while not os.path.exists(canoe_config_path):
        print("Invalid path, please try again.")
        canoe_config_path = input("Please enter the full path to the CANoe configuration (.cfg): ")
    
    return canoe_config_path

# Function to load the last used VT System executable or prompt for it
def get_vtuexe_path():
    default_vtuexe_path = r"C:\path\to\default\test.vtuexe"
    
    if os.path.exists(default_vtuexe_path):
        use_default = input(f"Found default VT executable at {default_vtuexe_path}. Do you want to use it? (y/n): ").lower()
        if use_default == 'y':
            return default_vtuexe_path
    
    vtuexe_path = input("Please enter the full path to the VT executable (.vtuexe): ")
    while not os.path.exists(vtuexe_path):
        print("Invalid path, please try again.")
        vtuexe_path = input("Please enter the full path to the VT executable (.vtuexe): ")
    
    return vtuexe_path

# Function to get the report output path
def get_report_path():
    default_report_path = r"C:\path\to\default\generated_report.csv"
    
    use_default = input(f"Do you want to save the report at the default location {default_report_path}? (y/n): ").lower()
    if use_default == 'y':
        return default_report_path
    
    report_path = input("Please enter the full path to save the report (e.g., C:\\path\\to\\report.csv): ")
    return report_path

# Function to get the Excel output path
def get_excel_path():
    default_excel_output_path = r"C:\path\to\default\output_report.xlsx"
    
    use_default = input(f"Do you want to save the Excel report at the default location {default_excel_output_path}? (y/n): ").lower()
    if use_default == 'y':
        return default_excel_output_path
    
    excel_output_path = input("Please enter the full path to save the Excel file (e.g., C:\\path\\to\\output.xlsx): ")
    return excel_output_path

# Function to start CANoe and load configuration
def load_canoe_config(canoe_config_path):
    print("Loading CANoe configuration...")
    # Initialize CANoe COM interface
    canoe = win32com.client.Dispatch("CANoe.Application")
    canoe.Open(canoe_config_path)
    print(f"CANoe Configuration {canoe_config_path} loaded successfully.")
    return canoe

# Function to execute the .vtuexe file for VT System tests
def execute_vtuexe(vtuexe_path, report_path):
    print("Executing VT System test...")
    # Execute the .vtuexe file using subprocess
    process = subprocess.run([vtuexe_path], check=True)
    if process.returncode == 0:
        print("VT System test executed successfully.")
        print(f"Report saved at: {report_path}")
    else:
        print("Error executing VT System test.")
    return report_path

# Function to embed report into an Excel file
def embed_report_into_excel(report_path, excel_path):
    print("Embedding report into Excel...")
    # Assuming the report is in CSV format for easy handling with pandas
    report_df = pd.read_csv(report_path)

    # Create a new Excel file
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Test Report"

    # Write DataFrame to Excel worksheet
    for r in openpyxl.utils.dataframe_to_rows(report_df, index=False, header=True):
        ws.append(r)

    # Save the Excel file
    wb.save(excel_path)
    print(f"Report embedded into Excel file: {excel_path}")

# Main function to run the test and generate the report
def main():
    # Step 1: Check and install missing packages
    install_missing_packages()

    # Import necessary modules after ensuring dependencies are installed
    import win32com.client
    import pandas as pd
    import openpyxl

    # Step 2: Get CANoe Configuration path (either default or prompt)
    canoe_config_path = get_canoe_config()
    
    # Step 3: Load CANoe Configuration
    canoe = load_canoe_config(canoe_config_path)

    # Step 4: Get VT System executable path (either default or prompt)
    vtuexe_path = get_vtuexe_path()

    # Step 5: Get report output path
    report_path = get_report_path()

    # Step 6: Start CANoe measurement
    canoe.Measurement.Start()
    print("CANoe measurement started...")

    # Step 7: Execute the .vtuexe file and generate report
    report_path = execute_vtuexe(vtuexe_path, report_path)

    # Step 8: Stop CANoe measurement
    canoe.Measurement.Stop()
    print("CANoe measurement stopped.")

    # Step 9: Get Excel output path
    excel_output_path = get_excel_path()

    # Step 10: Embed the report into an Excel file
    embed_report_into_excel(report_path, excel_output_path)

if __name__ == "__main__":
    main()
