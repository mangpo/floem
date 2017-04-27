from dsl import *

create_memory_region("region", 10)

CPU_process("master")

c = Compiler()
c.generate_code()
