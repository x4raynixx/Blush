from .commands import cls, clear, mkdir, rmdir

command_list = [
    "mkdir",
    "clear",
    "cls",
    "rmdir"
]

def ifexists(input):
    if input.lower() in command_list:
        return True
    else:
        return False
    
def execute(cmd):
    if ifexists(cmd[0]) == False:
        return "NOT_EXIST"
    if cmd[0].lower() == "mkdir":
        return mkdir.run(cmd)
    elif cmd[0].lower() == "clear":
        return clear.run(cmd)
    elif cmd[0].lower() == "cls":
        return cls.run(cmd)
    elif cmd[0].lower() == "rmdir":
        return rmdir.run(cmd)