from dsl import *
from elements_library import *

@composite_instance("syscall")
def syscall(arg_app):
    app2ker_enq, app2ker_deq = create_circular_queue_instances("app2ker", "int", 8, blocking=True)
    app2ker_enq(arg_app)
    return app2ker_deq()

@composite_instance("sysreturn")
def sysreturn(ret_kernel):
    ker2app_enq, ker2app_deq = create_circular_queue_instances("ker2app", "int", 8, blocking=True)
    ker2app_enq(ret_kernel)
    return ker2app_deq()

Forward = create_identity("Forward", "int")
Inc = create_add1("Inc", "int")
Print = create_element("Print", [Port("in", ["int"])], [], r'''printf("%d\n", in());''')

f = Forward()
inc = Inc()
p = Print()

# TODO: how to order app2ker_enq -> ker2app_deq
arg_ker = syscall(f(None))
ret_ker = inc(arg_ker)
ret_app = sysreturn(ret_ker)
p(ret_app)


# TODO: use before definition
arg_app2 = f(None)
ret_ker2 = inc(None)
arg_ker2, ret_app2 = syscall(arg_app2, ret_ker2)
inc(arg_ker2)  # very ugly