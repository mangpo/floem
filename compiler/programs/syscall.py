from dsl import *
from elements_library import *
from queue import *

@composite_instance("syscall")
def syscall_func(arg_app, ret_kernel, t_app, t_ker):
    app2ker_enq, app2ker_deq = create_circular_queue_instances("app2ker", "int", 8, blocking=True)
    app2ker_enq(arg_app)
    arg_ker = app2ker_deq()

    ker2app_enq, ker2app_deq = create_circular_queue_instances("ker2app", "int", 8, blocking=True)
    ker2app_enq(ret_kernel)
    ret_app = ker2app_deq()

    t_app.run_order(app2ker_enq, ker2app_deq)
    t_ker.run(app2ker_deq, ker2app_enq)

    return arg_ker, ret_app

Forward = create_identity("Forward", "int")
Inc = create_add1("Inc", "int")
Print = create_element("Print", [Port("in", ["int"])], [], r'''printf("%d\n", in());''')

f = Forward("f")
inc = Inc()
p = Print()

# Use before definition. This is quite ugly.
# t_app = API_thread("add_syscall", ["int"], None)
# t_ker = internal_thread("kernel")
# t_app.run(f, p)
# t_ker.run(inc)
#
# arg_app2 = f(None)
# ret_ker2 = inc(None)
# arg_ker2, ret_app2 = syscall_func(arg_app2, ret_ker2, t_app, t_ker)
# inc(arg_ker2)
# p(ret_app2)

def syscall(ker_func, t_app):
    def dummy(arg_app2):
        t_ker = internal_thread("kernel")
        t_ker.run(ker_func)

        ret_ker2 = ker_func()
        arg_ker2, ret_app2 = syscall_func(arg_app2, ret_ker2, t_app, t_ker)
        ker_func(arg_ker2)
        return ret_app2
    return dummy

t_app = API_thread("add_syscall", ["int"], None)
t_app.run(f, p)
kernel_add = syscall(inc, t_app)

p(kernel_add(f(None)))


c = Compiler()
c.testing = "f(0); f(1); f(2);"
c.generate_code_and_run([1,2,3])


