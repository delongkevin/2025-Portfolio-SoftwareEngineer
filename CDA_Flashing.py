import os
import sys
import subprocess
import pyautogui #pip install pyautogui
import keyboard #pip install keyboard
import shutil
import time as t
import json
from datetime import datetime
from pathlib import Path

global path, iterations, ser

pyautogui.FAILSAFE = False
###DO NOT MODIFY ANY CODE BELOW THIS POINT###################################
try:
    with open("user_data.json", "r") as file:
        data = json.load(file)
    print("Loaded data:", data)
    
    # Access specific values
    username = data["username"]
    password = data["password"]
    
except FileNotFoundError:
    # Get input from the user
    user_data = {
        "username": input("Enter your cda username: "),
        "password": input("Enter your cda password: ")
    }

    # Save data to a JSON file
    with open("user_data.json", "w") as file:
        json.dump(user_data, file)        
except json.JSONDecodeError:
    print("Error decoding JSON. Please check the file format.")

#username = "T9232KD"
#password = "Kevman#19901446"
#Update the two EFD paths to use to update from and to.
####EFD PATH A is flashed first then EFD PATH B is Flashed and then it repeats A-B-A-B.
currentDir = os.getcwd()
EFD_PATH_A = os.path.join(currentDir, 'EFD')
EFD_PATH_B = os.path.join(currentDir, 'EFD')
print("\nEFD_PATH_A: "+EFD_PATH_A+"\nEFD_PATH_B: "+EFD_PATH_B)


def CheckPartNumbers():
    openCDA()
    loginCDA()
    t.sleep(10)
    pyautogui.click(1378,538) #Benchtop mode
    t.sleep(10)
    pyautogui.click(1411,871) #continue
    t.sleep(5)
    pyautogui.click(532,366) # enter cvadas
    t.sleep(5)
    pyautogui.write("cvadas")
    t.sleep(5)
    pyautogui.press("enter")
    t.sleep(5)
    pyautogui.click(957,638,2) #OK button for diag notice
    t.sleep(5)
    pyautogui.click(1283,353) #close flash pop up
    t.sleep(5)
    pyautogui.click(661,366) #read/write data soft key press
    t.sleep(5)
    pyautogui.click(823,546) #FD-CAN2 TX signals
    t.sleep(5)
    for i in range (0,89):
        pyautogui.click(1489,564) #right box page slider
        t.sleep(2)
        for j in range (0,7):
            pyautogui.press("pagedown")
            t.sleep(1)   
            Evidence = pyautogui.screenshot("./Results/"+str(t.time())+".png")
        t.sleep(1)
        pyautogui.click(991,509) #left box page slider 
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
    pyautogui.moveTo(1059,368) #PID Editor button
    pyautogui.click(1059,368)
    t.sleep(2)
    pyautogui.click(706, 489) #Request space
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
    t.sleep(10) #open CDA tool
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

def click_location(image):
    # Give a brief pause to set up the screen
    t.sleep(2)

    # Locate all instances of the object on the screen
    locations = list(pyautogui.locateAllOnScreen(str(image), confidence=0.9))

    # Check if any instances were found
    if locations:
        print(f"Found {len(locations)} instances of the object.")
    
        # Iterate over each location and click on it
        for location in locations:
            center_x, center_y = pyautogui.center(location)  # Get the center of each located area
            print("Clicking at:", (center_x, center_y))
            pyautogui.click(center_x, center_y)  # Click at the center of each instance
            t.sleep(0.5)  # Optional: pause between clicks
    else:
        print("No instances of the object found on the screen.")

def deviceConnection():
    t.sleep(10)
    #pyautogui.click(1378,538) #Benchtop mode
    click_location('./Images/benchtop_mode.png')
    t.sleep(5)
    #pyautogui.click(1411,871) #continue
    click_location('./Images/continue.png')
    t.sleep(5)
    pyautogui.click(532,366) # enter cvadas
    t.sleep(5)
    pyautogui.write("cvadas")
    t.sleep(5)
    pyautogui.press("enter")
    t.sleep(5)
    pyautogui.click(957,638,2) #OK button for diag notice
    t.sleep(5)
    checkPreconditions()
    t.sleep(5)
    unlockECU()
    pyautogui.click(407,394) #Flash Button Left
    t.sleep(5)
    print("CVADAS is connected to CDA Tool!\n")
    Evidence = pyautogui.screenshot('./Results/Device_Connection_'+str(t.time())+'.png')

def unlockECU():
    print("Unlocking ECU..Please wait...")
    #pyautogui.click(298,773) #close pop up
    #t.sleep(5)
    #pyautogui.click(1192,375) #ecu unlock
    click_location('./Images/ecu_unlock.png')
    t.sleep(5)
    #pyautogui.click(660,635) #unlock button
    click_location('./Images/unlock_button.png')
    t.sleep(15)
    print("Unlock complete..")
    Evidence = pyautogui.screenshot('./Results/CDA_Unlock_'+str(t.time())+'.png')
    send_DID("2F 50 01 03 01") #set gear to park

def Precondition():
    openCDA()
    loginCDA()
    deviceConnection()

def Flashing_Validate_Result():
    f = 700 #fail safe time out while loop
    FlashSuccess = './Images/flash_complete.PNG'
    FlashFailed = './Images/flash_fail.PNG'
    while f > 0:
        try:
            f -= 1
            FlashSuccessList = list(pyautogui.locateAllOnScreen(str(FlashSuccess), confidence=0.7))
            FlashFailedList = list(pyautogui.locateAllOnScreen(str(FlashFailed), confidence=0.7))
            if FlashSuccessList or FlashFailedList:
                print("Flashing Completed, exiting...")
                evidence = pyautogui.screenshot('./Results/FlashLog_'+str(t.time())+'.png')
                break
            else:
                print("Flashing not complete. Waiting for Flash Log to complete...")
                t.sleep(5)

        except Exception as e:
            print(e)
            t.sleep(15)

def Flash_Build_A(build_a=EFD_PATH_A):
    #pyautogui.click(1247,469) #Select Flash File
    click_location('./Images/select_flash_file.png')
    t.sleep(5)
    pyautogui.click(1017,264) #Search bar of EFD file dialog
    t.sleep(2)
    pyautogui.write(EFD_PATH_A)
    t.sleep(3)
    pyautogui.press("enter")
    t.sleep(3)
    pyautogui.click(707,601,2) #select window
    t.sleep(3)
    pyautogui.press("down") #second option (boot)
    t.sleep(5)
    pyautogui.press("enter")
    t.sleep(5)
    click_location('./Images/start_flash.png')
    t.sleep(2)
    Flashing_Validate_Result()
    click_location('./Images/select_flash_file.png')
    t.sleep(5)
    pyautogui.click(707,601,2) #select window
    t.sleep(3)
    pyautogui.press("down")
    pyautogui.press("up") #second option (app)
    t.sleep(3)
    pyautogui.press("enter")
    click_location('./Images/start_flash.png')
    t.sleep(5)
    Flashing_Validate_Result()
    print("Build: "+str(build_a)+"\n")

def Flash_Build_B(build_b=EFD_PATH_B):
    #pyautogui.click(1247,469) #Select Flash File
    click_location('./Images/select_flash_file.png')
    t.sleep(5)
    pyautogui.click(1017,264) #Search bar of EFD file dialog
    t.sleep(2)
    pyautogui.write(EFD_PATH_A)
    t.sleep(3)
    pyautogui.press("enter")
    t.sleep(3)
    pyautogui.click(707,601,2) #select window
    t.sleep(3)
    pyautogui.press("down") #second option (boot)
    t.sleep(5)
    pyautogui.press("enter")
    t.sleep(5)
    click_location('./Images/start_flash.png')
    t.sleep(2)
    Flashing_Validate_Result()
    click_location('./Images/select_flash_file.png')
    t.sleep(5)
    pyautogui.click(707,601,2) #select window
    t.sleep(3)
    pyautogui.press("down")
    pyautogui.press("up") #second option (app)
    t.sleep(3)
    pyautogui.press("enter")
    click_location('./Images/start_flash.png')
    t.sleep(5)
    Flashing_Validate_Result()
    print("Build: "+str(build_b)+"\n")

def postcondition():
    #clean up and close CDA to restart again for next iteration
    os.system("taskkill /IM CDA.exe")
    print("Testing Completed!\nClosing CDA Tool!\n")
    t.sleep(5)
    Evidence = pyautogui.screenshot('./Results/CDA_Closed_Attempt_'+str(t.time())+'.png')

def closeFlashScreenPopUp():
    pyautogui.click(1280,355,2)
    t.sleep(2)

def openFlashScreenPopUp():
    pyautogui.click(407,394) #Flash Button Left
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
    t.sleep(15) #wait for ECU to start up
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
            send_DID("2E FD 4E 00") #erase NVM
            print("Please wait for NVM to clear")
            t.sleep(10) #takes time to clear NVM to reset.
            hard_reset() #start test for proxy test here
            send_proxy(line)
            send_DID("22 29 2E") #proxy write counter - should be 0
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
            send_DID("22 29 2E") #proxy write counter - should be 0
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
            send_DID("11 01") #hard reset
            postcondition()
            break
        elif keyboard.is_pressed("e"):
            iterations = pyautogui.prompt("How many iterations do you wish to run test for Flashing loop? ","EFD Automated Flashing")
            CDA_Flash_from_Flashing_Screen(iterations)
            send_DID("22 FD 13")
            send_DID("22 F1 80")
            send_DID("22 F1 81")
            send_DID("22 F1 82")
            send_DID("11 01") #hard reset
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
    #clean up results
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
