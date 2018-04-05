from floem import *

class param_message(State):
    group_id = Field(Int)
    member_id = Field(Int)  # worker
    start_id = Field(Uint(64))
    n = Field(Int)
    parameters = Field(Array(Int))
    layout = [group_id, member_id, start_id, n, parameters]

n_params = 5000
n_groups = 32
n_workers = 2
buffer_size = 128

define = r'''
#define N_PARAMS %d
#define N_GROUPS %d
#define BUFFER_SIZE %d
#define BITMAP_FULL 0x3
''' % (n_params, n_groups, buffer_size)