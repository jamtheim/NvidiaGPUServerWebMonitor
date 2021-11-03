# ***************************************************
# Idea and code by Christian Jamtheim Gustafsson, PhD
# Medical Physicist Expert and AI researcher
# Skåne University Hospital
# ***************************************************
# Version: 1.0 | 2021-10-26
# ***************************************************
"""
Description: 
This Python scripts connects to one or several Linux host and pulls the NVIDIA GPU monitoring status by the use of nvidia-smi.
It outputs it to a txt file which is then parsed into html with additional information. The html file is uploaded to a share
which acts as a WWW directory for a website. This makes it easy to montitor the GPU status of several machines without manually
connecting to them. It also adds monitoring for OS and kernel version, CPU, memory and disks.
"""

# Import packages
import os
from smb.SMBConnection import SMBConnection #pip install pysmb
import paramiko #SSH package
import time 

# Configuration
# Get current working directory
currDir = os.getcwd()
# Set update interval to be displayed. Meta data header update section of index.html file should be the same value. 
updateInterval = 30
# Set default authentication configuration for the share on the webserver
# See https://gist.github.com/joselitosn/e74dbc2812c6479d3678
userID = 'smb_username'
password = 'smb_password'
client_machine_name = 'client_machine_name'
server_name = 'dns_server_name'
server_ip = 'ip_server'
domain_name = 'domainname'
# Define remote share folder name 
sharedFolderName = 'remoteFolderName'

# Set up dictionary with servername, ip and authentication information for the desired servers with GPUs
# Use dictonary like this to get ip adress: hostInfoDict[keyname]["ipadress"] 
hostInfoDict = {
  "GPUServer1": {"ipadress":"192.168.0.1", "user":"machineUser1", "pass":"secretPassword1"},
  "GPUServer2": {"ipadress":"192.168.0.2", "user":"machineUser2", "pass":"secretPassword2"},
  "GPUServer3": {"ipadress":"192.168.0.3", "user":"machineUser3", "pass":"secretPassword3"},
}

def findMostCommonUser(stringSet, wordsOfInterest): 
    """
    Find the most frequent word in a string data set
    The word must be contained in the wordsOfInterest
    """
    from collections import Counter
    # Returns list of all the words in the string
    allWords = stringSet.split()
    # Init a variable as empty
    filteredWords =[] 
    # Loop through all words and add all words if they are of interest
    for word in allWords: 
        if word in wordsOfInterest:
            filteredWords.append(word)
    # Pass the filteredWords list to instance of Counter class.
    Counter = Counter(filteredWords)
    # most_common() produces k frequently encountered
    # input values and their respective counts.
    mostOccurWord = Counter.most_common(1)
    # Get only the string, not frequency
    mostOccurWord = mostOccurWord[0][0]
    return(mostOccurWord)

# Main magic function comes here
def getAndStoreData(serverName, hostInfoDict):
    """
    This functions collects the data from SSH connection and parses it to a txt file.
    It then creates html tags and other information and sends it to a remote SMB share which is 
    www root. Very important that the SSH session is closed in the end. 
    """
    # Inputs: Servername and whole host info dictioary
    # Outputs: One html file for each GPU server stored on the remote SMB share 

    # Define server dictionary as a subpart of original dictionary
    serverDict = hostInfoDict[serverName] 
    # Setup the SSH connection to the server 
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 
    # Connect to SSH using the dictionary values 
    ssh.connect(hostname=serverDict["ipadress"], username=serverDict["user"], password=serverDict["pass"])
    # Get nvidia-smi status and store it 
    ssh_stdin, ssh_nvidia_smi, ssh_stderr=ssh.exec_command("nvidia-smi")
    # Get CPU utilization
    #ssh_stdin, ssh_cpu, ssh_stderr=ssh.exec_command(" top -b -n 1 | grep \"Cpu(s)\" ") 
    # Get memory utilization
    #ssh_stdin, ssh_mem, ssh_stderr=ssh.exec_command(" top -b -n 1 | grep \"Mem\" ") 
    # Get dstat information (ths information is really nice and covers everything needed) 
    sh_stdin, ssh_dstat, ssh_stderr=ssh.exec_command(" dstat -c -d -m -l -n --nocolor 1 2 | awk \"NR==1 || NR==2 || NR==4\" ") 
    # Headers and information after 1 second (second update). 
    # Usage dstat [-afv] [options..] [delay [count]]
    # Get Ubuntu OS and kernel version
    sh_stdin, ssh_ver, ssh_stderr=ssh.exec_command(" hostnamectl | awk \"NR==6 || NR==7\" | sed -e \" s/^[[:space:]]*//\" ") 
    # Extracts line 6 and 7 and eliminate leading spaces. 
    # Get uptime in pretty format
    sh_stdin, ssh_uptime, ssh_stderr=ssh.exec_command(" uptime -p ") 
    # Get the most common username of the top process regarding CPU usage. Top is by default sorted on CPU usage.
    # This way we get the user who has the most number of active threads. Extract the n first rows
    sh_stdin, ssh_topUser, ssh_stderr=ssh.exec_command(" top -b -n 1 | head -n 38 ") # 8 rows header, and 30 rows of activety. 
    # Get CPU hardware information 
    sh_stdin, ssh_CPUhw, ssh_stderr=ssh.exec_command(" grep 'model name' /proc/cpuinfo | uniq | cut -d':' -f2- | xargs ") 
    
    # Read lines and collect them in a topStringLong
    topStringLong = '' 
    for line in ssh_topUser.readlines():
        topStringLong = topStringLong + line
    # Find most common user
    wordsOfInterest = ['machineUser1', 'machineUser2', 'machineUser3', 'otherUser'] 
    topUser = findMostCommonUser(topStringLong, wordsOfInterest)
    # Convert to real names for display
    if topUser == 'machineUser1': topUser='RealNameUser1'
    if topUser == 'machineUser2': topUser='RealNameUser2'

    # Set name and path for output html files 
    htmlFileName = serverName + "-nvidia-smi.html"
    htmlFilePath = os.path.join(currDir, htmlFileName)
    # Open the html file for writing and populate it with html tags and the information
    with open(htmlFilePath, "w") as e:
        # Server name
        e.write("<pre><strong><big>" + serverName + "</pre></strong></big>\n")
        # OS version and kernel version
        for line in ssh_ver.readlines():
            e.write("<pre>" + line + "</pre>\n")
        # CPU hardware
        for line in ssh_CPUhw.readlines():
            e.write("<pre>" + line + "</pre>\n")
        # Heaviest user
        e.write("<pre>" + 'Current heaviest user: ' + topUser + "</pre>\n")
        # Uptime
        for line in ssh_uptime.readlines():
            e.write("<pre>" + line + "</pre>\n")
        # CPU, memory and so on
        for line in ssh_dstat.readlines():
            e.write("<pre>" + line + "</pre>\n")
        # nvidia-smi
        for line in ssh_nvidia_smi.readlines():
            e.write("<pre>" + line + "</pre>\n")
        # Update interval
        e.write("<pre><strong>" "---" + str(updateInterval) + ' seconds update interval' + "---" "</pre></strong>\n")         

    # Store the html file on SMB share
    with open(htmlFilePath, 'rb') as file:
        conn.storeFile(sharedFolderName, htmlFileName, file)
    # Close SSH connection to the server. 
    # This is important or else memory leak will occur and 
    # hundreds of threads will be created as they are not closed. 
    # In the end this program will crash if ssh session is not closed. 
    ssh.close() 


# Init counter 
counter = 0 
# Start infinite loop to continously pull and store information to the WWW server
while 1 == 1: #Forever
    counter+=1
    print('Update #' + str(counter))
    # Start SMB connetion to remote SMB share
    try:
        conn = SMBConnection(userID, password, client_machine_name, server_name, domain=domain_name, use_ntlm_v2=True, is_direct_tcp=True)
        conn.connect(server_ip, 445)
        print('Connected to SMB share')
    except: 
        print('Something went wrong with the SMB connection')
    # Loop through all servers defined in the dictionary
    for serverName in hostInfoDict: 
        try:    
            getAndStoreData(serverName, hostInfoDict)
            print('Updating data for ' + serverName)
        except:
            print("Something went wrong, however it was caughth in an exception")
    
    try: 
        # Close SMB connection to share 
        print('Disconnected from SMB share')
        conn.close()
    except: 
        print('Could not close the SMB connection')
    # Sleep the interval
    print('Sleeping ' + str(updateInterval) + ' seconds...')
    time.sleep(updateInterval)
    print(' ')

# END OF FILE
