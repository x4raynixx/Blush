import os

def run(args):
    args_count = len(args)

    if args_count == 1:
        return "Minimum two arguments required to use this command"

    if args_count > 1 and args[1]:
        try:
            os.makedirs(args[1])
            recode = ["SUCCESS"]
            return recode
        except Exception as e:
            recode = ["ERROR", e]
            return recode