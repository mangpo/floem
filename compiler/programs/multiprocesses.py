from dsl import *

print_hi = create_element_instance("print_hi", [], [], r'''printf("hi\n");''')
print_hello = create_element_instance("print_hello", [], [], r'''printf("hello\n");''')

t1 = internal_thread("t1")
t2 = internal_thread("t2")
t1.run(print_hi)
t2.run(print_hello)

CPU_process("hi", t1)
CPU_process("hello", t2)

master_process("hi")

c = Compiler()
c.generate_code_and_run()