import os
import sys
import subprocess
import pyautogui
import keyboard
import shutil
import time as t
import json
from datetime import datetime
from pathlib import Path

global path, iterations, ser

pyautogui.FAILSAFE = False

def get_manual_location_with_prompt(image_name):
    pyautogui.alert(
        text=f"Please move your mouse over the '{os.path.basename(image_name)}' element and press the 'CTRL' key to mark its location.",
        title="Manual Input Required",
        button="OK"
    )
    while keyboard.is_pressed('ctrl'):
        t.sleep(0.1)
    while not keyboard.is_pressed('ctrl'):
        t.sleep(0.1)
    
    return pyautogui.position()

def robust_click_location(image, confidence=0.9, critical=True, clicks=1, double_click=False):
    t.sleep(1)
    locations = list(pyautogui.locateAllOnScreen(str(image), confidence=confidence))

    if locations:
        print(f"Found '{os.path.basename(image)}'. Clicking.")
        center_point = pyautogui.center(locations[0])
        if double_click:
            pyautogui.doubleClick(center_point)
        else:
            pyautogui.click(center_point, clicks=clicks)
        return True
    else:
        print(f"Could not automatically locate '{os.path.basename(image)}'.")
        choice = pyautogui.confirm(
            text=f"Image not found: '{os.path.basename(image)}'\n\nWhat would you like to do?",
            title="Automation Action Needed",
            buttons=['Locate Manually', 'Skip', 'Abort']
        )

        if choice == 'Locate Manually':
            pos = get_manual_location_with_prompt(image)
            print(f"User provided location: {pos}. Clicking.")
            if double_click:
                pyautogui.doubleClick(pos)
            else:
                pyautogui.click(pos, clicks=clicks)
            return True
        elif choice == 'Skip':
            print(f"WARNING: User skipped action on '{os.path.basename(image)}'.")
            if critical:
                pyautogui.alert("This is a critical step and cannot be skipped.", "Aborting Script")
                sys.exit("Aborted due to skipped critical step.")
            return False
        else:
            print("User chose to abort the script.")
            sys.exit("Script aborted by user.")

def improved_flashing_validate_result():
    timeout_seconds = 700
    flash_success_img = './Images/flash_complete.PNG'
    flash_failed_img = './Images/flash_fail.PNG'
    
    print("Waiting for flashing result...")
    end_time = t.time() + timeout_seconds
    
    while t.time() < end_time:
        if pyautogui.locateOnScreen(flash_success_img, confidence=0.8):
            print("Flashing completed successfully.")
            pyautogui.screenshot(f'./Results/FlashLog_Success_{t.time()}.png')
            return "Success"
            
        if pyautogui.locateOnScreen(flash_failed_img, confidence=0.8):
            print("Flashing FAILED.")
            pyautogui.screenshot(f'./Results/FlashLog_Failed_{t.time()}.png')
            return "Failed"
        
        print(f"Flashing in progress... (timeout in {round(end_time - t.time())}s)")
        t.sleep(5)

    print("Timeout reached while waiting for flash result.")
    pyautogui.screenshot(f'./Results/FlashLog_Timeout_{t.time()}.png')
    
    choice = pyautogui.confirm(
        text="Could not determine flash result automatically.\n\nPlease select the outcome:",
        title="Manual Flash Verification",
        buttons=['Flash was Successful', 'Flash Failed', 'Continue (Unknown)']
    )
    return "Success" if choice == 'Flash was Successful' else "Failed" if choice == 'Flash Failed' else "Unknown"

try:
    with open("user_data.json", "r") as file:
        data = json.load(file)
    print("Loaded data:", data)
    username = data["username"]
    password = data["password"]
except FileNotFoundError:
    user_data = {
        "username": input("Enter your cda username: "),
        "password": input("Enter your cda password: ")
    }
    with open("user_data.json", "w") as file:
        json.dump(user_data, file)        
except json.JSONDecodeError:
    print("Error decoding JSON. Please check the file format.")

currentDir = os.getcwd()
EFD_PATH_A = os.path.join(currentDir, 'EFD')
EFD_PATH_B = os.path.join(currentDir, 'EFD')
print(f"\nEFD_PATH_A: {EFD_PATH_A}\nEFD_PATH_B: {EFD_PATH_B}")

def CheckPartNumbers():
    openCDA()
    loginCDA()
    t.sleep(10)
    pyautogui.click(1378,538)
    t.sleep(10)
    pyautogui.click(1411,871)
    t.sleep(5)
    pyautogui.click(532,366)
    t.sleep(5)
    pyautogui.write("cvadas")
    t.sleep(5)
    pyautogui.press("enter")
    t.sleep(5)
    pyautogui.click(957,638,2)
    t.sleep(5)
    pyautogui.click(1283,353)
    t.sleep(5)
    pyautogui.click(661,366)
    t.sleep(5)
    pyautogui.click(823,546)
    t.sleep(5)
    for i in range (0,89):
        pyautogui.click(1489,564)
        t.sleep(2)
        for j in range (0,7):
            pyautogui.press("pagedown")
            t.sleep(1)   
            Evidence = pyautogui.screenshot("./Results/"+str(t.time())+".png")
        t.sleep(1)
        pyautogui.click(991,509)
        t.sleep(0.2)
        pyautogui.press("down")
        t.sleep(0.2)
        pyautogui.press("enter")
        t.sleep(2)
        Evidence = pyautogui.screenshot("./Results/"+str(t.time())+".png")
        t.sleep(0.2)
    Postcondition()

def saveLog():
    os.getcwd();

def getScreenSize():
    print(pyautogui.size())

def getPosition():
    print(pyautogui.position())

def moveTo(x,y,duration=1):
    pyautogui.moveTo(int(x), int(y), int(duration))

def checkPreconditions():
    pyautogui.moveTo(1059,368)
    pyautogui.click(1059,368)
    t.sleep(2)
    pyautogui.click(706, 489)
    t.sleep(2)
    pyautogui.click(662,478,2)
    for i in range(0,20):
        pyautogui.press("delete")
    pyautogui.write("31 01 D0 02")
    t.sleep(2)
    pyautogui.click(668,854)
    t.sleep(2)

def interruptCDA():
    os.system("taskkill /IM CDA.exe")
    t.sleep(10)

def openCDA():
    os.popen("C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\CDA 6\\CDA 6.lnk")
    t.sleep(10)
    print("CDA is launched!\n")
    Evidence = pyautogui.screenshot("./Results/CDA_Launch_Attempt_"+str(t.time())+".png")

def getCredentials():
    global username, password
    if username or password in globals():
        return username, password
    else: 
        username = pyautogui.prompt("Enter your CDA user name credentials: ")
        password = pyautogui.prompt("Enter your CDA password: ")
    return username, password

def loginCDA():
    getCredentials()    
    pyautogui.click(848,512,2)
    for i in range (0,10):
        pyautogui.press('backspace');
    pyautogui.write(str(username))
    t.sleep(5)
    pyautogui.press("tab")
    t.sleep(2)
    pyautogui.write(str(password))
    t.sleep(5)
    pyautogui.press("enter")
    print("Attempted to Login to CDA!\n")
    Evidence = pyautogui.screenshot('./Results/Login_To_CDA_Attempt_'+str(t.time())+'.png')

def deviceConnection():
    t.sleep(10)
    robust_click_location('./Images/benchtop_mode.png')
    t.sleep(5)
    robust_click_location('./Images/continue.png')
    t.sleep(5)
    pyautogui.click(532,366)
    t.sleep(5)
    pyautogui.write("cvadas")
    t.sleep(5)
    pyautogui.press("enter")
    t.sleep(5)
    pyautogui.click(957,638,2)
    t.sleep(5)
    checkPreconditions()
    t.sleep(5)
    unlockECU()
    pyautogui.click(407,394)
    t.sleep(5)
    print("CVADAS is connected to CDA Tool!\n")
    Evidence = pyautogui.screenshot('./Results/Device_Connection_'+str(t.time())+'.png')

def unlockECU():
    print("Unlocking ECU..Please wait...")
    robust_click_location('./Images/ecu_unlock.png')
    t.sleep(5)
    robust_click_location('./Images/unlock_button.png')
    t.sleep(15)
    print("Unlock complete..")
    Evidence = pyautogui.screenshot('./Results/CDA_Unlock_'+str(t.time())+'.png')
    send_DID("2F 50 01 03 01")

def Precondition():
    openCDA()
    loginCDA()
    deviceConnection()

def Flash_Build_A(build_a=EFD_PATH_A):
    robust_click_location('./Images/select_flash_file.png')
    t.sleep(5)
    pyautogui.click(1017,264)
    t.sleep(2)
    pyautogui.write(EFD_PATH_A)
    t.sleep(3)
    pyautogui.press("enter")
    t.sleep(3)
    pyautogui.click(707,601,2)
    t.sleep(3)
    pyautogui.press("down")
    t.sleep(5)
    pyautogui.press("enter")
    t.sleep(5)
    robust_click_location('./Images/start_flash.png')
    t.sleep(2)
    improved_flashing_validate_result()
    robust_click_location('./Images/select_flash_file.png')
    t.sleep(5)
    pyautogui.click(707,601,2)
    t.sleep(3)
    pyautogui.press("down")
    pyautogui.press("up")
    t.sleep(3)
    pyautogui.press("enter")
    robust_click_location('./Images/start_flash.png')
    t.sleep(5)
    improved_flashing_validate_result()
    print("Build: "+str(build_a)+"\n")

def Flash_Build_B(build_b=EFD_PATH_B):
    robust_click_location('./Images/select_flash_file.png')
    t.sleep(5)
    pyautogui.click(1017,264)
    t.sleep(2)
    pyautogui.write(EFD_PATH_A)
    t.sleep(3)
    pyautogui.press("enter")
    t.sleep(3)
    pyautogui.click(707,601,2)
    t.sleep(3)
    pyautogui.press("down")
    t.sleep(5)
    pyautogui.press("enter")
    t.sleep(5)
    robust_click_location('./Images/start_flash.png')
    t.sleep(2)
    improved_flashing_validate_result()
    robust_click_location('./Images/select_flash_file.png')
    t.sleep(5)
    pyautogui.click(707,601,2)
    t.sleep(3)
    pyautogui.press("down")
    pyautogui.press("up")
    t.sleep(3)
    pyautogui.press("enter")
    robust_click_location('./Images/start_flash.png')
    t.sleep(5)
    improved_flashing_validate_result()
    print("Build: "+str(build_b)+"\n")

def postcondition():
    os.system("taskkill /IM CDA.exe")
    print("Testing Completed!\nClosing CDA Tool!\n")
    t.sleep(5)
    Evidence = pyautogui.screenshot('./Results/CDA_Closed_Attempt_'+str(t.time())+'.png')

def closeFlashScreenPopUp():
    pyautogui.click(1280,355,2)
    t.sleep(2)

def openFlashScreenPopUp():
    pyautogui.click(407,394)
    t.sleep(5)

def CDA_Flash_Sequence():
    Precondition()
    Flash_Build_A(EFD_PATH_A)
    Flash_Build_B(EFD_PATH_B)
    Evidence = pyautogui.screenshot('./Results/Testing_Iterations_Completed_'+str(t.time())+'.png')    

def clear_PID_Editor():
    pyautogui.click(1054,375, 2)
    t.sleep(1)
    pyautogui.click(664,479)
    pyautogui.click(button='right')
    t.sleep(1)
    pyautogui.click(736,573)
    t.sleep(1)
    pyautogui.press("delete")
    t.sleep(1)

def hard_reset():
    pyautogui.click(989,361,2)
    t.sleep(1)
    pyautogui.click(878,487,2)
    t.sleep(15)
    p.readCurrent(ser)
    p.readVoltage(ser)

def send_proxy(proxy):
    clear_PID_Editor()
    pyautogui.write(str(proxy))
    t.sleep(1)
    pyautogui.press("enter")
    t.sleep(1)
    hard_reset()
    Evidence = pyautogui.screenshot('./Results/Proxy_'+str(t.time())+'.png')  

def send_DID(DID):
    clear_PID_Editor()
    pyautogui.write(str(DID))
    t.sleep(1)
    pyautogui.press("enter")
    t.sleep(1)
    Evidence = pyautogui.screenshot('./Results/DID_'+str(DID)+'_'+str(t.time())+'.png') 

def CDA_Flash(iterations=1):
    for i in range(0,int(iterations)):
        CDA_Flash_Sequence()
        
def CDA_Flash_from_Flashing_Screen(iterations):
    for i in range (0,int(iterations)):
        closeFlashScreenPopUp()
        checkPreconditions()
        unlockECU()
        openFlashScreenPopUp()
        Flash_Build_A(EFD_PATH_A)
        Flash_Build_B(EFD_PATH_B)

def Proxy_Test_with_NVM_Erase():
    data = []
    i = 1
    closeFlashScreenPopUp()
    clear_PID_Editor()
    with open('./proxy_list.txt', 'r') as f:
        for line in f.readlines():
            data = i
            print("Proxy "+ str(i) + ": "+line)
            i+=1
            send_DID("2E FD 4E 00")
            print("Please wait for NVM to clear")
            t.sleep(10)
            hard_reset()
            send_proxy(line)
            send_DID("22 29 2E")
            send_DID("22 FD F3")
            send_DID("22 FD F2")
            send_DID("22 FD 13")
            send_DID("22 FD 61")
    f.close()

def Proxy_Test():
    data = []
    i = 1
    closeFlashScreenPopUp()
    clear_PID_Editor()
    with open('./proxy_list.txt', 'r') as f:
        for line in f.readlines():
            data = i
            print("Proxy "+ str(i) + ": "+line)
            i+=1
            send_proxy(line)
            send_DID("22 29 2E")
            send_DID("22 FD F3")
            send_DID("22 FD F2")
            send_DID("22 FD 13")
            send_DID("22 FD 61")
    f.close()
     
def Intro_Msg():
     print("Press a key to select a menu:\n\
           L - Launch CDA tool and Login\n\
           p - Get X-Y mouse coordinates\n\
           e - EFD Flash (User is already at Flash Screen) \n\
           f - EFD Flash (Launches CDA tool and Flashes) \n\
           2 - Read Part Number Test\n\
           x - To quit and Create Report\n\
           ")

datetime.now()        
try:
    Intro_Msg()
    while True:
        if keyboard.is_pressed("p"):
            getPosition()
        elif keyboard.is_pressed("L") or keyboard.is_pressed("l"):
            Precondition()
        elif keyboard.is_pressed("f"):
            iterations = pyautogui.prompt("How many iterations do you wish to run test for Flashing loop? ","EFD Automated Flashing")
            CDA_Flash(iterations)
            send_DID("22 FD 13")
            send_DID("22 F1 80")
            send_DID("22 F1 81")
            send_DID("22 F1 82")
            send_DID("11 01")
            postcondition()
            break
        elif keyboard.is_pressed("e"):
            iterations = pyautogui.prompt("How many iterations do you wish to run test for Flashing loop? ","EFD Automated Flashing")
            CDA_Flash_from_Flashing_Screen(iterations)
            send_DID("22 FD 13")
            send_DID("22 F1 80")
            send_DID("22 F1 81")
            send_DID("22 F1 82")
            send_DID("11 01")
            postcondition()
            break
        elif keyboard.is_pressed("1"):
            Proxy_Test()
            break
        elif keyboard.is_pressed("2"):
            iterations = pyautogui.prompt("How many iterations do you wish to run Power Cycle Test? ","Power Cycle Test-EFD-Flashing")
            Power_Cycle_Test(iterations)
            break
        elif keyboard.is_pressed("3"):
            EFD_Flash_Interruption_Test()
            break
        elif keyboard.is_pressed("4"):
            CheckPartNumbers()
            break
        elif keyboard.is_pressed("i"):
            print("installing dependencies, please wait...")
            os.system("install_dependencies.bat")
            os.system("cls")
            Intro_Msg()
        elif keyboard.is_pressed("x"):
            break
        t.sleep(0.1)

    newReportDir = 'Report_'+str(round(t.time()))
    sys.stdout = open("./Software_Test_Report.csv",'a')
    os.mkdir(newReportDir)
    source = './Results/'
    allfiles = os.listdir(source)
    for f in allfiles:
        src_path = os.path.join(source, f)
        dst_path = os.path.join(newReportDir, f)
        os.rename(src_path, dst_path)
        print("Files Copied to Report: " + str(f) + "\n")
    sys.stdout.close()
        
except Exception as e:
    print(e)