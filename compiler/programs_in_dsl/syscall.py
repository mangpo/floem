from dsl import *
from elements_library import *


def syscall(arg_app, ret_kernel, t_app, t_kernel):
    app2ker_enq, app2ker_deq = create_circular_queue_instances("app2ker", "int", 8, blocking=True)
    app2ker_enq(arg_app)
    arg_kernel = app2ker_deq()

    ker2app_enq, ker2app_deq = create_circular_queue_instances("ker2app", "int", 8, blocking=True)
    ker2app_enq(ret_kernel)
    ret_app = ker2app_deq()

    t_app.run(app2ker_enq, ker2app_deq)  # connect them
    t_kernel.run(app2ker_deq, ker2app_enq)
    return arg_kernel, ret_app