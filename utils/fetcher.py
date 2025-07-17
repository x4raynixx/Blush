command_list = [
    "mkdir",
    "clear",
    "cls"
]

def ifexists(input):
    if input.lower() in command_list:
        return True
    else:
        return False
    
def execute(cmd):
    if ifexists(cmd) == False:
        return "NOT_EXIST"
    if cmd.lower() == "mkdir":
        return "Created"
    elif cmd.lower() == "clear":
        return "$C_CLEAR"
    elif cmd.lower() == "cls":
        return "$C_CLEAR"