import commands

# Create path.rtk
status, abs_path = commands.getstatusoutput("pwd")
f = open("floem/path.py", "w")
f.write("srcpath = \"" + abs_path + "/floem\"\n")
print "path.py is created."
